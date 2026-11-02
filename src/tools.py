"""LangGraph tool definitions for the Data Copilot agent.

Each tool is decorated with ``@tool`` so LangGraph / LangChain can
automatically bind it to the LLM and route tool-call messages.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

from src.config import settings
from src.database import execute_readonly_query
from src.guardrails import SQLGuardrails
from src.knowledge_loader import KnowledgeBase

logger = logging.getLogger(__name__)

# ── Module-level singleton for the knowledge base ────────────────────────
_kb: KnowledgeBase | None = None


def _get_kb() -> KnowledgeBase:
    """Return (and lazily create) the KnowledgeBase singleton."""
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb


# ── Helpers ──────────────────────────────────────────────────────────────

def _format_results_table(results: list[dict[str, Any]]) -> str:
    """Render a list of row-dicts as a Markdown table with a row count."""
    if not results:
        return "_(no rows)_"

    sanitized = SQLGuardrails.sanitize_output(results, max_rows=settings.max_query_rows)
    columns = list(sanitized[0].keys())

    # Header
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"

    # Rows
    rows: list[str] = []
    for row in sanitized:
        cells = " | ".join(str(row.get(c, "")) for c in columns)
        rows.append(f"| {cells} |")

    count_line = f"\n_({len(sanitized)} row{'s' if len(sanitized) != 1 else ''} returned)_"
    return "\n".join([header, separator, *rows]) + count_line


def _fuzzy_match(needle: str, haystack: str) -> bool:
    """Case-insensitive substring match."""
    return needle.lower() in haystack.lower()


# ── Tools ────────────────────────────────────────────────────────────────


@tool
def execute_sql_query(query: str) -> str:
    """Execute a read-only SQL query against the trading platform database.

    The query must be a SELECT statement only. Returns results as formatted
    Markdown text.

    Args:
        query: A valid PostgreSQL SELECT query.
    """
    # 1. Validate with guardrails
    is_safe, message = SQLGuardrails.validate(query)
    if not is_safe:
        return f"❌ Query blocked: {message}"

    # 2. Execute query
    try:
        results = execute_readonly_query(query)
    except RuntimeError as exc:
        return f"❌ Query error: {exc}"

    if not results:
        return "Query executed successfully but returned no results."

    # 3. Format results
    return _format_results_table(results)


@tool
def get_table_info(table_name: str) -> str:
    """Get detailed schema information about a specific table.

    Args:
        table_name: Name of the database table to inspect.
    """
    kb = _get_kb()
    tables = kb.schema.get("tables", [])

    for table in tables:
        if table.get("name", "").lower() == table_name.strip().lower():
            lines: list[str] = []
            lines.append(f"## Table: `{table['name']}`")
            desc = table.get("description", "")
            if desc:
                lines.append(desc)
            lines.append("")
            lines.append("| Column | Type | Nullable | Description |")
            lines.append("|--------|------|----------|-------------|")
            for col in table.get("columns", []):
                nullable = "YES" if col.get("nullable", True) else "NO"
                lines.append(
                    f"| `{col.get('name', '')}` "
                    f"| {col.get('type', '')} "
                    f"| {nullable} "
                    f"| {col.get('description', '')} |"
                )
            pk = table.get("primary_key")
            if pk:
                pk_str = ", ".join(pk) if isinstance(pk, list) else str(pk)
                lines.append(f"\n**Primary Key:** `{pk_str}`")
            return "\n".join(lines)

    # Fallback: table not found in knowledge base
    available = ", ".join(f"`{t.get('name', '?')}`" for t in tables)
    return (
        f"Table `{table_name}` not found in the knowledge base.\n"
        f"Available tables: {available or '_none loaded_'}"
    )


@tool
def get_metric_definition(metric_name: str) -> str:
    """Look up the definition and SQL template for a business metric.

    Args:
        metric_name: Name or keyword of the metric to look up.
    """
    kb = _get_kb()
    metrics_list = kb.metrics.get("metrics", [])

    matches: list[dict] = []
    for metric in metrics_list:
        name = metric.get("name", "")
        description = metric.get("description", "")
        if _fuzzy_match(metric_name, name) or _fuzzy_match(metric_name, description):
            matches.append(metric)

    if not matches:
        available = ", ".join(f"`{m.get('name', '?')}`" for m in metrics_list)
        return (
            f"No metric matching `{metric_name}` found.\n"
            f"Available metrics: {available or '_none loaded_'}"
        )

    lines: list[str] = []
    for m in matches:
        lines.append(f"### {m.get('name', 'Unnamed')}")
        if m.get("description"):
            lines.append(m["description"])
        if m.get("sql_template"):
            lines.append(f"\n```sql\n{m['sql_template'].strip()}\n```")
        elif m.get("sql"):
            lines.append(f"\n```sql\n{m['sql'].strip()}\n```")
        lines.append("")

    return "\n".join(lines)


@tool
def validate_sql(query: str) -> str:
    """Validate a SQL query for safety without executing it.

    Args:
        query: SQL query to validate.
    """
    is_safe, message = SQLGuardrails.validate(query)
    if is_safe:
        return f"✅ {message}"
    return f"❌ {message}"


@tool
def list_available_tables() -> str:
    """List all available tables in the database with their descriptions."""
    kb = _get_kb()
    tables = kb.schema.get("tables", [])

    if not tables:
        return "No table information is currently loaded in the knowledge base."

    lines: list[str] = ["| Table | Description |", "|-------|-------------|"]
    for table in tables:
        name = table.get("name", "?")
        desc = table.get("description", "")
        lines.append(f"| `{name}` | {desc} |")
    return "\n".join(lines)


@tool
def search_glossary(term: str) -> str:
    """Search the business glossary for a trading/finance term.

    Args:
        term: The business term to look up.
    """
    kb = _get_kb()
    terms_list = kb.glossary.get("terms", kb.glossary.get("glossary", []))

    matches: list[dict] = []
    for entry in terms_list:
        entry_term = entry.get("term", entry.get("name", ""))
        entry_def = entry.get("definition", entry.get("description", ""))
        if _fuzzy_match(term, entry_term) or _fuzzy_match(term, entry_def):
            matches.append(entry)

    if not matches:
        available = ", ".join(
            f"`{t.get('term', t.get('name', '?'))}`" for t in terms_list
        )
        return (
            f"No glossary entry matching `{term}` found.\n"
            f"Available terms: {available or '_none loaded_'}"
        )

    lines: list[str] = []
    for entry in matches:
        entry_term = entry.get("term", entry.get("name", ""))
        entry_def = entry.get("definition", entry.get("description", ""))
        lines.append(f"- **{entry_term}**: {entry_def}")

    return "\n".join(lines)
