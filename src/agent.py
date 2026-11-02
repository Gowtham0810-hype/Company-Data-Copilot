"""LangGraph-based Data Copilot agent with Multi-Provider Support and PostgreSQL Checkpointer.

Features:
- Multi-Provider Failover: Groq (ultra-fast) + Google Gemini via MultiProviderLLMPool
- Priority 1: Multi-SQL Query Execution (up to 3 queries per question for multi-step analysis and self-correction)
- Priority 2: Persistent Conversation Memory via PostgreSQL Checkpointer (PostgresSaver)
- Priority 3: Structured Context Digest (preserves previous SQL queries and data summaries across turns)
- Strict compliance with turn-alternation requirements for both Groq and Gemini APIs
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from psycopg_pool import ConnectionPool

from src.config import settings
from src.knowledge_loader import KnowledgeBase
from src.llm_pool import MultiProviderLLMPool
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


# ── Response & Context Helpers ───────────────────────────────────────────

def _extract_text(content) -> str:
    """Extract plain text from LLM response content across Gemini and Groq formats."""
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


def _extract_sql_from_text(text: str) -> list[str]:
    """Extract SQL query blocks from markdown text."""
    return re.findall(r"```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)


def _build_context_digest(past_messages: list, max_past_turns: int = 4) -> str:
    """Extract structured summaries (SQL queries, entities, and answers) from previous turns.

    Injects this into the prompt so the LLM retains full context of previous data
    without needing raw, token-heavy ToolMessages from past turns.
    """
    turns: list[dict] = []
    current_human: str = ""

    for m in past_messages:
        if isinstance(m, HumanMessage):
            current_human = _extract_text(m.content).strip()
        elif isinstance(m, AIMessage) and current_human:
            text = _extract_text(m.content).strip()
            if text:
                sql_blocks = _extract_sql_from_text(text)
                turns.append(
                    {
                        "question": current_human,
                        "sql": sql_blocks[-1] if sql_blocks else None,
                        "summary": text[:400].replace("\n", " "),
                    }
                )
                current_human = ""

    if not turns:
        return ""

    recent_turns = turns[-max_past_turns:]
    lines = ["\n## Structured History & Queries from Previous Turns:"]
    for i, t in enumerate(recent_turns, 1):
        lines.append(f"- Turn #{i} Question: \"{t['question']}\"")
        if t["sql"]:
            lines.append(f"  SQL Used: {t['sql'].strip()}")
        lines.append(f"  Key Result Summary: {t['summary']}...")
    lines.append("\nYou can directly reference the entities, IDs, and metrics from previous queries above.\n")
    return "\n".join(lines)


def _format_clean_history(messages: list, max_past_turns: int = 4) -> list:
    """Prepare conversation history for Groq and Gemini.

    Ensures strict Human -> AI turn alternation for all completed past turns,
    while leaving the current active turn's tool-call chain intact.
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
            text = _extract_text(m.content)
            if text.strip():
                # Strip raw tool_calls from past completed turns
                cleaned_past.append(AIMessage(content=text))

    if len(cleaned_past) > max_past_turns * 2:
        cleaned_past = cleaned_past[-(max_past_turns * 2):]

    return cleaned_past + current


def _count_current_turn_tools(messages: list) -> int:
    """Count how many tool results have been executed in the active turn."""
    last_human_idx = 0
    for i, m in enumerate(messages):
        if isinstance(m, HumanMessage):
            last_human_idx = i

    current_turn = messages[last_human_idx:]
    count = 0
    for m in current_turn:
        if getattr(m, "type", "") == "tool" or hasattr(m, "tool_call_id"):
            count += 1
    return count


# ── Agent State ──────────────────────────────────────────────────────────

class AgentState(TypedDict):
    """Typed state that flows through the LangGraph nodes."""

    messages: Annotated[list, add_messages]


# ── Agent ────────────────────────────────────────────────────────────────

class DataCopilotAgent:
    """High-level Data Copilot Agent with PostgreSQL Checkpointing and Multi-Provider Pool.

    Usage::

        agent = DataCopilotAgent()
        answer = await agent.chat("Compare trading volumes between AAPL and MSFT this month.")
    """

    def __init__(self) -> None:
        logger.info("Initializing DataCopilotAgent...")

        # 1. Knowledge Base
        logger.info("Loading knowledge base...")
        self.knowledge_base = KnowledgeBase()
        logger.info("Knowledge base loaded")

        # 2. Tools
        self.tools = [
            execute_sql_query,
            get_table_info,
            get_metric_definition,
            validate_sql,
            list_available_tables,
            search_glossary,
        ]

        # 3. Multi-Provider LLM Pool (Groq + Gemini)
        logger.info("Initializing MultiProviderLLMPool...")
        self.llm_pool = MultiProviderLLMPool(tools=self.tools)

        # 4. PostgreSQL Checkpointer (Persistent Memory)
        logger.info("Initializing PostgreSQL checkpointer on %s...", settings.postgres_db)
        self.pool = ConnectionPool(
            conninfo=settings.postgres_conn_string,
            max_size=10,
            kwargs={"autocommit": True},
        )
        self.checkpointer = PostgresSaver(self.pool)
        self.checkpointer.setup()
        logger.info("PostgreSQL checkpointer tables verified")

        # 5. Compile StateGraph with Checkpointer
        self.graph = self._build_graph()
        logger.info("LangGraph compiled successfully with PostgresSaver")

    def _build_system_prompt(self, past_messages: list) -> str:
        """Render a compact system prompt enriched with structured past query context."""
        context_digest = _build_context_digest(past_messages, max_past_turns=4)
        base_prompt = SYSTEM_PROMPT.format(
            schema_context=self.knowledge_base.get_compact_schema(),
            joins_context=self.knowledge_base.get_compact_joins(),
            metrics_list=self.knowledge_base.get_compact_metrics_list(),
        )
        return base_prompt + "\n" + context_digest

    # ── Graph Nodes ──────────────────────────────────────────────────────

    def _chatbot(self, state: AgentState) -> dict:
        """Main chatbot node supporting multi-step SQL queries and self-correction."""
        all_messages = state["messages"]
        clean_history = _format_clean_history(all_messages)
        tools_executed = _count_current_turn_tools(clean_history)

        max_allowed_rounds = settings.max_sql_rounds_per_question

        # Identify if we should allow another tool call or force final synthesis
        can_use_tools = tools_executed < max_allowed_rounds

        logger.info(
            "Chatbot node: tools_executed_in_turn=%d, can_use_tools=%s (max=%d)",
            tools_executed,
            can_use_tools,
            max_allowed_rounds,
        )

        system_prompt = self._build_system_prompt(all_messages)
        system_message = SystemMessage(content=system_prompt)
        messages_to_send = [system_message] + clean_history

        try:
            response = self.llm_pool.invoke(messages_to_send, with_tools=can_use_tools)
            tc = len(response.tool_calls) if getattr(response, "tool_calls", None) else 0
            cl = len(_extract_text(response.content))
            logger.info("LLM responded: %d text chars, %d tool_calls", cl, tc)
        except Exception as e:
            logger.error("LLM invocation failed: %s", e, exc_info=True)
            raise

        return {"messages": [response]}

    @staticmethod
    def _route(state: AgentState) -> str:
        """Route conditionally: tools if tool_calls present and under limit, else END."""
        last_message = state["messages"][-1]
        has_tools = bool(getattr(last_message, "tool_calls", None))
        tools_executed = _count_current_turn_tools(state["messages"])

        if has_tools and tools_executed < settings.max_sql_rounds_per_question:
            logger.info("-> Routing to tools (query #%d)", tools_executed + 1)
            return "tools"

        logger.info("-> Routing to END (synthesis complete or tool budget reached)")
        return END

    def _build_graph(self):
        """Construct and compile the LangGraph state machine with PostgreSQL memory."""
        tool_node = ToolNode(self.tools)

        builder = StateGraph(AgentState)
        builder.add_node("chatbot", self._chatbot)
        builder.add_node("tools", tool_node)

        builder.add_edge(START, "chatbot")
        builder.add_conditional_edges(
            "chatbot", self._route, {"tools": "tools", END: END}
        )
        builder.add_edge("tools", "chatbot")

        return builder.compile(checkpointer=self.checkpointer)

    # ── Visibility & Diagnostics ─────────────────────────────────────────

    def get_usage_stats(self) -> dict:
        """Return real-time pool metrics across all active providers."""
        return self.llm_pool.get_stats()

    # ── Public Chat API ──────────────────────────────────────────────────

    def chat_sync(self, message: str, thread_id: str = "default") -> str:
        """Synchronous chat processing with persistent PostgreSQL checkpointing."""
        logger.info("chat_sync(): thread=%s, msg='%s'", thread_id, message[:80])
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": settings.max_sql_rounds_per_question * 2 + 4,
        }
        try:
            result = self.graph.invoke(
                {"messages": [HumanMessage(content=message)]},
                config=config,
            )
            reply = _extract_text(result["messages"][-1].content)
            logger.info("chat_sync(): finished (%d chars)", len(reply))
            return reply
        except Exception as e:
            logger.error("chat_sync() failed: %s", e, exc_info=True)
            raise

    async def chat(self, message: str, thread_id: str = "default") -> str:
        """Asynchronous chat execution via thread worker for Windows event loop compatibility."""
        return await asyncio.to_thread(self.chat_sync, message, thread_id)

    def close(self) -> None:
        """Safely close PostgreSQL connection pools on shutdown."""
        try:
            self.pool.close()
            logger.info("PostgreSQL checkpointer pool closed cleanly")
        except Exception as e:
            logger.warning("Error closing checkpointer pool: %s", e)
