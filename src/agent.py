"""LangGraph-based Data Copilot agent.

Orchestrates the conversation loop:
    User -> Chatbot node -> (optional) Tool node -> Chatbot node -> ... -> END

Optimized for free-tier Gemini API (5 RPM limit):
- Ultra-compact system prompt (~10K chars vs 45K)
- Safe sliding-window rate limiter (default: 4 RPM max)
- Multi-turn Gemini turn compliance: collapses past turns into clean text pairs
  (prevents 'Please ensure that function call turn comes immediately after a user turn' 400 error)
- Dynamic tool pacing: stops immediately after SQL query executes (max 2 LLM calls per turn)
- Real-time usage visibility metrics
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.config import settings
from src.knowledge_loader import KnowledgeBase
from src.prompts import SYSTEM_PROMPT
from src.tools import (
    execute_sql_query,
    get_metric_definition,
    get_table_info,
    list_available_tables,
    search_glossary,
    validate_sql,
)

logger = logging.getLogger(__name__)


# ── Rate Limiter ─────────────────────────────────────────────────────────

class RateLimiter:
    """Sliding-window rate limiter for Gemini free tier.

    Tracks timestamps of recent calls and sleeps if the limit would be
    exceeded.  Default: 4 calls per 60 seconds (leaving 1 RPM headroom
    from the 5 RPM free-tier cap).
    """

    def __init__(self, max_calls: int = 4, window_seconds: int = 60) -> None:
        self.max_calls = max_calls
        self.window = window_seconds
        self._timestamps: deque[float] = deque()
        self.total_calls: int = 0

    def wait_if_needed(self) -> float:
        """Block until a call can be made within the rate limit. Returns seconds slept."""
        now = time.time()

        # Purge old timestamps outside the window
        while self._timestamps and self._timestamps[0] < now - self.window:
            self._timestamps.popleft()

        slept = 0.0
        if len(self._timestamps) >= self.max_calls:
            sleep_for = self._timestamps[0] + self.window - now + 1.0
            if sleep_for > 0:
                logger.warning(
                    "Rate limit pacing: sleeping %.1fs (used %d/%d calls in last %ds)",
                    sleep_for,
                    len(self._timestamps),
                    self.max_calls,
                    self.window,
                )
                time.sleep(sleep_for)
                slept = sleep_for

        self._timestamps.append(time.time())
        self.total_calls += 1
        return slept

    @property
    def calls_remaining(self) -> int:
        now = time.time()
        while self._timestamps and self._timestamps[0] < now - self.window:
            self._timestamps.popleft()
        return max(0, self.max_calls - len(self._timestamps))

    def get_stats(self) -> dict:
        """Return usage stats for visibility."""
        now = time.time()
        while self._timestamps and self._timestamps[0] < now - self.window:
            self._timestamps.popleft()
        recent = len(self._timestamps)
        return {
            "recent_calls_1m": recent,
            "max_calls_1m": self.max_calls,
            "calls_remaining": max(0, self.max_calls - recent),
            "total_calls": self.total_calls,
            "window_seconds": self.window,
        }


# Module-level rate limiter shared across the agent
_rate_limiter = RateLimiter(max_calls=4, window_seconds=60)


# ── Response & Context Helpers ───────────────────────────────────────────

def _extract_text(content) -> str:
    """Extract plain text from LLM response content.

    Newer Gemini models return content as a list of dicts
    [{'type': 'text', 'text': '...', ...}] instead of a plain string.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(content)


def _clean_messages_for_gemini(messages: list, max_past_turns: int = 3) -> list:
    """Format multi-turn conversation history for strict Gemini API compliance.

    Gemini requires function call turns to immediately follow a user turn
    or another function response turn. In multi-turn chat, we collapse completed
    past turns into clean HumanMessage -> text AIMessage pairs (stripping raw
    function calls/results). This prevents 400 errors and saves thousands of tokens.
    """
    last_human_idx = 0
    for i, m in enumerate(messages):
        if isinstance(m, HumanMessage):
            last_human_idx = i

    past = messages[:last_human_idx]
    current = messages[last_human_idx:]

    cleaned_past = []
    for m in past:
        if isinstance(m, HumanMessage):
            cleaned_past.append(m)
        elif isinstance(m, AIMessage):
            # Only keep final text answer, stripping tool_calls
            text = _extract_text(m.content)
            if text.strip():
                cleaned_past.append(AIMessage(content=text))

    # Keep at most `max_past_turns` (each turn = 1 human + 1 ai)
    if len(cleaned_past) > max_past_turns * 2:
        cleaned_past = cleaned_past[-(max_past_turns * 2):]

    return cleaned_past + current


def _should_synthesize(current_turn_messages: list) -> bool:
    """Check if the current turn has completed query execution."""
    tool_messages = [
        m for m in current_turn_messages
        if getattr(m, "type", "") == "tool" or hasattr(m, "tool_call_id")
    ]
    # If 2 or more tools executed in this turn, force synthesis
    if len(tool_messages) >= 2:
        return True

    # If execute_sql_query has completed, force synthesis
    for m in current_turn_messages:
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            for tc in m.tool_calls:
                if tc.get("name") == "execute_sql_query" and len(tool_messages) > 0:
                    return True

    return False


# ── Agent State ──────────────────────────────────────────────────────────

class AgentState(TypedDict):
    """Typed state that flows through the LangGraph nodes."""

    messages: Annotated[list, add_messages]


# ── Agent ────────────────────────────────────────────────────────────────

class DataCopilotAgent:
    """High-level wrapper around the compiled LangGraph.

    Usage::

        agent = DataCopilotAgent()
        answer = agent.chat_sync("Show me the top 10 trades by volume.")
    """

    MAX_TOOL_ROUNDS = 2

    def __init__(self) -> None:
        logger.info("Initializing DataCopilotAgent...")

        logger.info("Loading knowledge base...")
        self.knowledge_base = KnowledgeBase()
        logger.info("Knowledge base loaded")

        self.tools = [
            execute_sql_query,
            get_table_info,
            get_metric_definition,
            validate_sql,
            list_available_tables,
            search_glossary,
        ]

        logger.info("Initializing LLM: model=%s", settings.gemini_model)
        self.llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.google_api_key,
            temperature=0,
            max_retries=3,
            timeout=60,
        )
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        logger.info("LLM initialized and tools bound")

        # Build compact system prompt ONCE
        self._system_prompt = self._build_system_prompt()
        logger.info(
            "System prompt: %d chars (compact)",
            len(self._system_prompt),
        )

        self.graph = self._build_graph()
        logger.info("LangGraph compiled successfully")

    # ── Prompt ───────────────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        """Render a compact system prompt using schema outlines only."""
        return SYSTEM_PROMPT.format(
            schema_context=self.knowledge_base.get_compact_schema(),
            joins_context=self.knowledge_base.get_compact_joins(),
            metrics_list=self.knowledge_base.get_compact_metrics_list(),
        )

    # ── Graph Nodes ──────────────────────────────────────────────────────

    def _chatbot(self, state: AgentState) -> dict:
        """Main chatbot node — rate-limited LLM invocation with clean Gemini history."""
        msg_count = len(state["messages"])
        logger.info(
            "Chatbot node: %d total messages, %d RPM remaining",
            msg_count,
            _rate_limiter.calls_remaining,
        )

        # Rate limit before calling the API
        _rate_limiter.wait_if_needed()

        system_message = SystemMessage(content=self._system_prompt)
        # Clean history ensuring strict turn alternation
        clean_history = _clean_messages_for_gemini(state["messages"], max_past_turns=3)
        messages = [system_message] + clean_history

        # Identify current turn messages
        last_human_idx = 0
        for i, m in enumerate(clean_history):
            if isinstance(m, HumanMessage):
                last_human_idx = i
        current_turn = clean_history[last_human_idx:]

        if _should_synthesize(current_turn):
            logger.info("Query completed. Calling plain LLM to synthesize final answer...")
            active_llm = self.llm
        else:
            logger.info("Active turn. Calling LLM with tools bound (%s)...", settings.gemini_model)
            active_llm = self.llm_with_tools

        try:
            response = active_llm.invoke(messages)
            tc = len(response.tool_calls) if getattr(response, "tool_calls", None) else 0
            cl = len(_extract_text(response.content))
            logger.info("LLM response: %d chars, %d tool_calls", cl, tc)
        except Exception as e:
            logger.error("LLM call failed: %s", e, exc_info=True)
            raise

        return {"messages": [response]}

    @staticmethod
    def _route(state: AgentState) -> str:
        """Route: tools if tool_calls present, else END."""
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            logger.info("-> routing to tools")
            return "tools"
        logger.info("-> routing to END")
        return END

    def _build_graph(self):
        """Construct and compile the LangGraph state machine."""
        tool_node = ToolNode(self.tools)

        builder = StateGraph(AgentState)
        builder.add_node("chatbot", self._chatbot)
        builder.add_node("tools", tool_node)

        builder.add_edge(START, "chatbot")
        builder.add_conditional_edges(
            "chatbot", self._route, {"tools": "tools", END: END}
        )
        builder.add_edge("tools", "chatbot")

        memory = MemorySaver()
        return builder.compile(checkpointer=memory)

    # ── Visibility & Diagnostics ─────────────────────────────────────────

    def get_usage_stats(self) -> dict:
        """Return real-time API call metrics and quota status."""
        return _rate_limiter.get_stats()

    # ── Public API ───────────────────────────────────────────────────────

    async def chat(self, message: str, thread_id: str = "default") -> str:
        """Process a user message asynchronously."""
        logger.info("chat(): thread=%s, msg='%s'", thread_id, message[:80])
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 10,
        }
        try:
            result = await self.graph.ainvoke(
                {"messages": [HumanMessage(content=message)]},
                config=config,
            )
            reply = _extract_text(result["messages"][-1].content)
            logger.info("chat(): reply %d chars", len(reply))
            return reply
        except Exception as e:
            logger.error("chat() failed: %s", e, exc_info=True)
            raise

    def chat_sync(self, message: str, thread_id: str = "default") -> str:
        """Synchronous version of :meth:`chat`."""
        logger.info("chat_sync(): thread=%s, msg='%s'", thread_id, message[:80])
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 10,
        }
        try:
            result = self.graph.invoke(
                {"messages": [HumanMessage(content=message)]},
                config=config,
            )
            reply = _extract_text(result["messages"][-1].content)
            logger.info("chat_sync(): reply %d chars", len(reply))
            return reply
        except Exception as e:
            logger.error("chat_sync() failed: %s", e, exc_info=True)
            raise
