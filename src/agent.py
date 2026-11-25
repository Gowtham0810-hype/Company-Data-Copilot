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


def _build_context_digest(messages: list, max_past_turns: int = 4) -> str:
    """Extract structured SQL queries from completed previous turns.

    Injects previous queries into the prompt so the LLM retains full context of
    tables, joins, IDs, and filters used earlier, without duplicating the
    conversational text already present in clean_history.
    """
    last_human_idx = -1
    for i, m in enumerate(messages):
        if isinstance(m, HumanMessage):
            last_human_idx = i

    # No completed past turns exist if there is no previous human message
    if last_human_idx <= 0:
        return ""

    past_messages = messages[:last_human_idx]
    turns: list[dict] = []
    current_human: str = ""
    current_sqls: list[str] = []

    for m in past_messages:
        if isinstance(m, HumanMessage):
            if current_human and current_sqls:
                turns.append({"question": current_human, "sqls": current_sqls})
            current_human = _extract_text(m.content).strip()
            current_sqls = []
        elif isinstance(m, AIMessage):
            # Extract SQL from actual tool calls (execute_sql_query)
            tool_calls = getattr(m, "tool_calls", None) or []
            for tc in tool_calls:
                if tc.get("name") == "execute_sql_query":
                    query = tc.get("args", {}).get("query", "")
                    if query and query.strip() and query.strip() not in current_sqls:
                        current_sqls.append(query.strip())
            # Fallback to fenced markdown code blocks if tool_calls not present
            text = _extract_text(m.content).strip()
            if text:
                for block in _extract_sql_from_text(text):
                    if block.strip() and block.strip() not in current_sqls:
                        current_sqls.append(block.strip())

    if current_human and current_sqls:
        turns.append({"question": current_human, "sqls": current_sqls})

    if not turns:
        return ""

    recent_turns = turns[-max_past_turns:]
    lines = ["\n## Previous SQL Queries from Recent Turns:"]
    for i, t in enumerate(recent_turns, 1):
        lines.append(f"- Previous Question: \"{t['question']}\"")
        for sql in t["sqls"]:
            lines.append(f"  SQL Used: {sql}")
    lines.append("\nYou can directly reference the entities, IDs, and metrics from previous queries above.\n")
    return "\n".join(lines)


def _format_clean_history(messages: list, max_past_turns: int = 4) -> list:
    """Prepare conversation history for Groq and Gemini.

    Ensures strict Human -> AI turn alternation for all completed past turns
    (using the final AI response per turn and omitting intermediate tool calls),
    while leaving the current active turn's tool-call chain intact.
    """
    last_human_idx = 0
    for i, m in enumerate(messages):
        if isinstance(m, HumanMessage):
            last_human_idx = i

    past = messages[:last_human_idx]
    current = messages[last_human_idx:]

    cleaned_past = []
    current_human = None
    last_ai_text = ""

    for m in past:
        if isinstance(m, HumanMessage):
            if current_human is not None and last_ai_text:
                cleaned_past.append(current_human)
                cleaned_past.append(AIMessage(content=last_ai_text))
            current_human = m
            last_ai_text = ""
        elif isinstance(m, AIMessage):
            text = _extract_text(m.content).strip()
            if text:
                last_ai_text = text

    if current_human is not None and last_ai_text:
        cleaned_past.append(current_human)
        cleaned_past.append(AIMessage(content=last_ai_text))

    if len(cleaned_past) > max_past_turns * 2:
        cleaned_past = cleaned_past[-(max_past_turns * 2):]

    return cleaned_past + current


def _count_current_turn_sql_queries(messages: list) -> int:
    """Count how many execute_sql_query tool executions occurred in the active turn."""
    last_human_idx = 0
    for i, m in enumerate(messages):
        if isinstance(m, HumanMessage):
            last_human_idx = i

    current_turn = messages[last_human_idx:]
    count = 0
    for m in current_turn:
        is_tool = getattr(m, "type", "") == "tool" or hasattr(m, "tool_call_id")
        if is_tool and getattr(m, "name", "") == "execute_sql_query":
            count += 1
    return count


def _count_current_turn_tools(messages: list) -> int:
    """Count total tool results executed in the active turn."""
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

        # Cache static schema, joins, and metrics in base system prompt
        self.base_system_prompt = SYSTEM_PROMPT.format(
            schema_context=self.knowledge_base.get_compact_schema(),
            joins_context=self.knowledge_base.get_compact_joins(),
            metrics_list=self.knowledge_base.get_compact_metrics_list(),
        )

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

    def _build_system_prompt(self, messages: list) -> str:
        """Render system prompt with cached base context and dynamic context digest."""
        context_digest = _build_context_digest(messages, max_past_turns=4)
        if context_digest:
            return f"{self.base_system_prompt}\n{context_digest}"
        return self.base_system_prompt

    # ── Graph Nodes ──────────────────────────────────────────────────────

    def _chatbot(self, state: AgentState) -> dict:
        """Main chatbot node supporting multi-step SQL queries and self-correction."""
        all_messages = state["messages"]
        clean_history = _format_clean_history(all_messages)
        sql_executed = _count_current_turn_sql_queries(clean_history)
        total_tools_executed = _count_current_turn_tools(clean_history)

        max_allowed_sql = settings.max_sql_rounds_per_question
        max_total_tools = max_allowed_sql * 2  # Safety cap for non-SQL tools

        # Allow tools only if under both SQL query budget and total tool limit
        can_use_tools = (sql_executed < max_allowed_sql) and (total_tools_executed < max_total_tools)

        logger.info(
            "Chatbot node: sql_executed=%d (max=%d), total_tools=%d (max=%d), can_use_tools=%s",
            sql_executed,
            max_allowed_sql,
            total_tools_executed,
            max_total_tools,
            can_use_tools,
        )

        system_prompt = self._build_system_prompt(all_messages)
        system_message = SystemMessage(content=system_prompt)
        messages_to_send = [system_message] + clean_history

        try:
            response = self.llm_pool.invoke(messages_to_send, with_tools=can_use_tools)
        except Exception as e:
            logger.error("LLM invocation failed: %s", e, exc_info=True)
            raise

        # Strictly enforce tool execution limits on response.tool_calls
        raw_tool_calls = getattr(response, "tool_calls", None) or []
        if not can_use_tools:
            if raw_tool_calls:
                logger.warning("Clearing %d tool calls because tools were disabled", len(raw_tool_calls))
                response.tool_calls = []
                if hasattr(response, "additional_kwargs") and "tool_calls" in response.additional_kwargs:
                    response.additional_kwargs.pop("tool_calls", None)
        elif raw_tool_calls:
            allowed_tool_calls = []
            curr_sql = sql_executed
            curr_total = total_tools_executed

            for tc in raw_tool_calls:
                is_sql = tc.get("name") == "execute_sql_query"
                if is_sql:
                    if curr_sql < max_allowed_sql and curr_total < max_total_tools:
                        allowed_tool_calls.append(tc)
                        curr_sql += 1
                        curr_total += 1
                    else:
                        logger.warning(
                            "Dropping tool call '%s' - SQL query limit reached (%d/%d)",
                            tc.get("name"),
                            curr_sql,
                            max_allowed_sql,
                        )
                else:
                    if curr_total < max_total_tools:
                        allowed_tool_calls.append(tc)
                        curr_total += 1
                    else:
                        logger.warning(
                            "Dropping tool call '%s' - total tool limit reached (%d/%d)",
                            tc.get("name"),
                            curr_total,
                            max_total_tools,
                        )
            response.tool_calls = allowed_tool_calls
            if hasattr(response, "additional_kwargs") and "tool_calls" in response.additional_kwargs:
                allowed_ids = {tc.get("id") for tc in allowed_tool_calls}
                response.additional_kwargs["tool_calls"] = [
                    tc for tc in response.additional_kwargs["tool_calls"]
                    if tc.get("id") in allowed_ids
                ]

        tc = len(response.tool_calls) if getattr(response, "tool_calls", None) else 0
        cl = len(_extract_text(response.content))
        logger.info("LLM responded: %d text chars, %d tool_calls accepted", cl, tc)

        return {"messages": [response]}

    @staticmethod
    def _route(state: AgentState) -> str:
        """Route conditionally: tools if tool_calls present, else END."""
        last_message = state["messages"][-1]
        has_tools = bool(getattr(last_message, "tool_calls", None))

        if has_tools:
            logger.info("-> Routing to tools (%d tool call(s))", len(last_message.tool_calls))
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
            "recursion_limit": settings.max_sql_rounds_per_question * 2 + 6,
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
 
