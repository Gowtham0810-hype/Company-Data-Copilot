"""Multi-Provider LLM Pool (Groq & Google Gemini) with Automatic Failover.

Provides:
- Multi-provider support: Groq (ultra-fast, high free-tier RPM) and Google Gemini
- Tiered failover: Primary provider with instant fallback on 429 (rate limit) or 503 (server error)
- Circuit-breaking and per-provider cooldown tracking
- Tool-binding management across both providers
- Usage and quota visibility metrics
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ProviderEndpoint:
    """Represents an active LLM provider endpoint with health and rate tracking."""

    provider: str  # "groq" or "gemini"
    model: str
    masked_key: str
    api_key: str
    llm: Any
    llm_with_tools: Any
    max_rpm: int = 15
    window_seconds: int = 60
    timestamps: deque[float] = field(default_factory=deque)
    cooldown_until: float = 0.0
    total_calls: int = 0
    total_errors: int = 0
    last_error: str = ""

    def is_available(self) -> bool:
        """Check if this endpoint is not in cooldown and within safe rate limits."""
        now = time.time()
        if now < self.cooldown_until:
            return False

        # Purge timestamps outside window
        while self.timestamps and self.timestamps[0] < now - self.window_seconds:
            self.timestamps.popleft()

        return len(self.timestamps) < self.max_rpm

    def record_call(self) -> None:
        """Record an API call timestamp."""
        self.timestamps.append(time.time())
        self.total_calls += 1

    def mark_cooldown(self, seconds: float, reason: str) -> None:
        """Set a cooldown period after a rate limit or server error."""
        self.cooldown_until = time.time() + seconds
        self.total_errors += 1
        self.last_error = reason
        logger.warning(
            "[%s - %s] Cooling down for %.0fs: %s",
            self.provider.upper(),
            self.model,
            seconds,
            reason,
        )

    def recent_calls(self) -> int:
        now = time.time()
        while self.timestamps and self.timestamps[0] < now - self.window_seconds:
            self.timestamps.popleft()
        return len(self.timestamps)


class MultiProviderLLMPool:
    """Manages multi-provider failover between Groq and Google Gemini."""

    def __init__(self, tools: list | None = None) -> None:
        self.tools = tools or []
        self.endpoints: list[ProviderEndpoint] = []
        self._init_endpoints()

    def _init_endpoints(self) -> None:
        """Initialize provider endpoints based on configured API keys."""
        # 1. Initialize Groq (if key present)
        if settings.groq_api_key and settings.groq_api_key.strip():
            key = settings.groq_api_key.strip()
            masked = key[:6] + "..." + key[-4:] if len(key) > 10 else "***"

            # Register primary Groq model and fallback models
            groq_models_to_register = [settings.groq_model]
            if getattr(settings, "groq_fallback_models", None):
                for fb in settings.groq_fallback_models.split(","):
                    fb = fb.strip()
                    if fb and fb not in groq_models_to_register:
                        groq_models_to_register.append(fb)

            for gr_model in groq_models_to_register:
                try:
                    llm = ChatGroq(
                        model=gr_model,
                        api_key=key,
                        temperature=0,
                        max_retries=0,
                        timeout=30,
                    )
                    llm_with_tools = llm.bind_tools(self.tools) if self.tools else llm
                    self.endpoints.append(
                        ProviderEndpoint(
                            provider="groq",
                            model=gr_model,
                            masked_key=masked,
                            api_key=key,
                            llm=llm,
                            llm_with_tools=llm_with_tools,
                            max_rpm=25,  # Groq free tier allows up to 30 RPM
                        )
                    )
                    logger.info("Groq endpoint registered: %s (%s)", gr_model, masked)
                except Exception as e:
                    logger.error("Failed to initialize Groq endpoint (%s): %s", gr_model, e)

        # 2. Initialize Google Gemini (if key present)
        if settings.google_api_key and settings.google_api_key.strip():
            key = settings.google_api_key.strip()
            masked = key[:6] + "..." + key[-4:] if len(key) > 10 else "***"
            # Register primary Gemini model and fallback models
            models_to_register = [settings.gemini_model]
            if settings.gemini_fallback_models:
                for fb in settings.gemini_fallback_models.split(","):
                    fb = fb.strip()
                    if fb and fb not in models_to_register:
                        models_to_register.append(fb)

            for g_model in models_to_register:
                try:
                    llm = ChatGoogleGenerativeAI(
                        model=g_model,
                        google_api_key=key,
                        temperature=0,
                        max_retries=0,
                        timeout=45,
                    )
                    llm_with_tools = llm.bind_tools(self.tools) if self.tools else llm
                    self.endpoints.append(
                        ProviderEndpoint(
                            provider="gemini",
                            model=g_model,
                            masked_key=masked,
                            api_key=key,
                            llm=llm,
                            llm_with_tools=llm_with_tools,
                            max_rpm=4,  # Gemini free tier safe cap
                        )
                    )
                    logger.info("Gemini endpoint registered: %s (%s)", g_model, masked)
                except Exception as e:
                    logger.error("Failed to initialize Gemini endpoint (%s): %s", g_model, e)

        if not self.endpoints:
            logger.warning("No LLM endpoints registered! Please set GROQ_API_KEY or GOOGLE_API_KEY in .env.")

    def _select_endpoint(self) -> ProviderEndpoint:
        """Select the preferred available endpoint, respecting primary provider preference."""
        if not self.endpoints:
            raise RuntimeError("No LLM providers configured. Set GROQ_API_KEY or GOOGLE_API_KEY in .env.")

        pref = (settings.primary_provider or "groq").lower()

        # 1. Try available endpoints matching primary provider preference
        primary_candidates = [e for e in self.endpoints if e.provider == pref and e.is_available()]
        if primary_candidates:
            return min(primary_candidates, key=lambda e: e.recent_calls())

        # 2. Try any other available endpoint (failover provider)
        failover_candidates = [e for e in self.endpoints if e.is_available()]
        if failover_candidates:
            chosen = min(failover_candidates, key=lambda e: e.recent_calls())
            if any(e.provider == pref for e in self.endpoints):
                logger.info("Primary provider (%s) cooling down. Failing over to %s (%s)...", pref.upper(), chosen.provider.upper(), chosen.model)
            return chosen

        # 3. All endpoints currently busy or in cooldown: wait for the earliest one to recover
        now = time.time()
        earliest = min(
            self.endpoints,
            key=lambda e: max(e.cooldown_until, (e.timestamps[0] + e.window_seconds) if e.timestamps else 0),
        )
        wake_time = max(earliest.cooldown_until, (earliest.timestamps[0] + earliest.window_seconds) if earliest.timestamps else 0)
        sleep_dur = max(0.5, wake_time - now)
        logger.warning(
            "All LLM endpoints cooling down. Pacing for %.1fs until %s (%s) recovers...",
            sleep_dur,
            earliest.provider.upper(),
            earliest.model,
        )
        time.sleep(sleep_dur)
        return earliest

    def invoke(self, messages: list, with_tools: bool = True) -> BaseMessage:
        """Invoke the LLM with automatic multi-provider failover."""
        max_attempts = max(3, len(self.endpoints) * 2)
        last_exception: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            endpoint = self._select_endpoint()
            active_runner = endpoint.llm_with_tools if with_tools else endpoint.llm

            logger.info(
                "[Attempt %d/%d] Invoking %s (%s, tools=%s)...",
                attempt,
                max_attempts,
                endpoint.provider.upper(),
                endpoint.model,
                with_tools,
            )

            endpoint.record_call()
            try:
                response = active_runner.invoke(messages)
                return response
            except Exception as e:
                err_str = str(e)
                last_exception = e

                # Detect quota (429), transient errors (500, 503, 504), or model errors (404)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "rate limit" in err_str.lower():
                    cooldown = 90.0 if "per day" in err_str.lower() else 35.0
                    endpoint.mark_cooldown(cooldown, "Rate limit reached (429)")
                elif "503" in err_str or "UNAVAILABLE" in err_str or "high demand" in err_str.lower():
                    endpoint.mark_cooldown(25.0, "Service unavailable (503)")
                elif "504" in err_str or "DEADLINE" in err_str:
                    endpoint.mark_cooldown(20.0, "Gateway timeout (504)")
                elif "500" in err_str or "INTERNAL" in err_str:
                    endpoint.mark_cooldown(15.0, "Internal error (500)")
                elif "404" in err_str or "not found" in err_str.lower() or "does not exist" in err_str.lower() or "decommissioned" in err_str.lower():
                    endpoint.mark_cooldown(300.0, f"Model unavailable (404): {endpoint.model}")
                else:
                    logger.error("Non-transient error from %s (%s): %s", endpoint.provider, endpoint.model, e)
                    endpoint.mark_cooldown(60.0, f"Error: {err_str[:40]}")
                    if len(self.endpoints) <= 1:
                        raise

                logger.warning(
                    "Failover triggered from %s to alternative endpoint (error: %s)",
                    endpoint.provider.upper(),
                    err_str[:90],
                )

        raise RuntimeError(
            f"All {len(self.endpoints)} LLM provider endpoints failed after {max_attempts} attempts: {last_exception}"
        ) from last_exception

    def get_stats(self) -> dict:
        """Return usage, capacity, and active status for each provider endpoint."""
        now = time.time()
        providers = list({e.provider for e in self.endpoints})
        endpoints_data = []
        for e in self.endpoints:
            endpoints_data.append(
                {
                    "provider": e.provider,
                    "model": e.model,
                    "masked_key": e.masked_key,
                    "recent_calls": e.recent_calls(),
                    "max_rpm": e.max_rpm,
                    "total_calls": e.total_calls,
                    "cooling_down": now < e.cooldown_until,
                    "cooldown_remaining": max(0.0, e.cooldown_until - now),
                    "last_error": e.last_error,
                }
            )

        active_count = sum(1 for e in self.endpoints if e.is_available())
        total_recent = sum(e.recent_calls() for e in self.endpoints)
        total_capacity = sum(e.max_rpm for e in self.endpoints)
        total_calls = sum(e.total_calls for e in self.endpoints)

        providers_str = ", ".join(p.capitalize() for p in providers) if providers else "None"

        return {
            "providers": providers,
            "providers_str": providers_str,
            "num_keys": len(self.endpoints),
            "total_endpoints": len(self.endpoints),
            "active_endpoints": active_count,
            "available_endpoints": active_count,
            "total_recent_1m": total_recent,
            "total_capacity_1m": total_capacity,
            "total_calls": total_calls,
            "endpoints": endpoints_data,
        }
