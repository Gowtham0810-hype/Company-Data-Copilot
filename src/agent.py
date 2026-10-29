"""LangGraph-based Data Copilot agent.

Orchestrates the conversation loop:
    User → Chatbot node → (optional) Tool node → Chatbot node → … → END
"""

from __future__ import annotations

import logging
from typing import Annotated, TypedDict

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

def _extract_text(content) -> str:
    """Extract plain text from LLM response content.

    Newer Gemini models return content as a list of dicts
    [{'type': 'text', 'text': '...', ...}] instead of a plain string.
    This helper normalizes both formats to a single string.
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
    
class AgentState(TypedDict):
    """Typed state that flows through the LangGraph nodes."""

    messages: Annotated[list, add_messages]


class DataCopilotAgent:
    """High-level wrapper around the compiled LangGraph.

    Usage::

        agent = DataCopilotAgent()
        answer = agent.chat_sync("Show me the top 10 trades by volume today.")
    """

    def __init__(self) -> None:
        self.knowledge_base = KnowledgeBase()

        self.tools = [
            execute_sql_query,
            get_table_info,
            get_metric_definition,
            validate_sql,
            list_available_tables,
            search_glossary,
        ]

        self.llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.google_api_key,
            temperature=0,
            max_retries=2,
        )
        self.llm_with_tools = self.llm.bind_tools(self.tools)

        self.graph = self._build_graph()

    # ── Graph construction ───────────────────────────────────────────────

    def _get_system_prompt(self) -> str:
        """Render the system prompt with live knowledge-base content."""
        return SYSTEM_PROMPT.format(
            schema_context=self.knowledge_base.get_schema_context(),
            metrics_context=self.knowledge_base.get_metrics_context(),
            joins_context=self.knowledge_base.get_joins_context(),
            glossary_context=self.knowledge_base.get_glossary_context(),
        )

    def _chatbot(self, state: AgentState) -> dict:
        """Main chatbot node — invokes the LLM (with tools bound)."""
        system_message = {"role": "system", "content": self._get_system_prompt()}
        messages = [system_message] + state["messages"]
        response = self.llm_with_tools.invoke(messages)
        return {"messages": [response]}

    @staticmethod
    def _route(state: AgentState) -> str:
        """Conditional edge: if the last message has tool calls, route to tools."""
        last_message = state["messages"][-1]
        if getattr(last_message, "tool_calls", None):
            return "tools"
        return END

    def _build_graph(self) -> StateGraph:
        """Construct and compile the LangGraph state machine."""
        tool_node = ToolNode(self.tools)

        builder = StateGraph(AgentState)
        builder.add_node("chatbot", self._chatbot)
        builder.add_node("tools", tool_node)

        builder.add_edge(START, "chatbot")
        builder.add_conditional_edges(
            "chatbot",
            self._route,
            {"tools": "tools", END: END},
        )
        builder.add_edge("tools", "chatbot")

        memory = MemorySaver()
        return builder.compile(checkpointer=memory)

    # ── Public chat API ──────────────────────────────────────────────────

    async def chat(self, message: str, thread_id: str = "default") -> str:
        """Process a user message asynchronously and return the assistant reply.

        Parameters
        ----------
        message:
            The natural-language question from the user.
        thread_id:
            Conversation thread identifier (enables multi-turn memory).
        """
        config = {"configurable": {"thread_id": thread_id}}
        result = await self.graph.ainvoke(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
        )
        return result["messages"][-1].content

    def chat_sync(self, message: str, thread_id: str = "default") -> str:
        """Synchronous version of :meth:`chat`.

        Parameters
        ----------
        message:
            The natural-language question from the user.
        thread_id:
            Conversation thread identifier (enables multi-turn memory).
        """
        config = {"configurable": {"thread_id": thread_id}}
        result = self.graph.invoke(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
        )
        return result["messages"][-1].content
