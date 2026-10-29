"""Load and format YAML knowledge files for LLM prompt context.

The knowledge directory is expected to contain the following files:

* ``schema.yaml``   – table/column definitions
* ``metrics.yaml``  – business metric SQL templates
* ``joins.yaml``    – canonical join paths between tables
* ``glossary.yaml`` – business/trading domain terminology
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """Reads YAML knowledge artefacts and renders them as prompt-ready text."""

    def __init__(self, knowledge_dir: str = "knowledge") -> None:
        self.knowledge_dir = Path(knowledge_dir)
        self.schema: dict[str, Any] = self._load("schema.yaml")
        self.metrics: dict[str, Any] = self._load("metrics.yaml")
        self.joins: dict[str, Any] = self._load("joins.yaml")
        self.glossary: dict[str, Any] = self._load("glossary.yaml")

    # ── Private helpers ──────────────────────────────────────────────────

    def _load(self, filename: str) -> dict[str, Any]:
        """Load a single YAML file; return an empty dict on failure."""
        path = self.knowledge_dir / filename
        if not path.exists():
            logger.warning("Knowledge file not found: %s", path)
            return {}
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
                return data if isinstance(data, dict) else {}
        except Exception:
            logger.exception("Failed to parse %s", path)
            return {}

    # ── Public context formatters ────────────────────────────────────────

    def get_schema_context(self) -> str:
        """Format schema info for LLM prompt context.

        Produces a clear, table-by-table listing of columns with types,
        constraints, and descriptions.
        """
        if not self.schema:
            return "_No schema information available._"

        tables: list[dict[str, Any]] = self.schema.get("tables", [])
        if not tables:
            return "_No schema information available._"

        lines: list[str] = []
        for table in tables:
            tbl_name: str = table.get("name", "unknown")
            tbl_desc: str = table.get("description", "")
            lines.append(f"### Table: `{tbl_name}`")
            if tbl_desc:
                lines.append(f"{tbl_desc}")
            lines.append("")
            lines.append("| Column | Type | Nullable | Description |")
            lines.append("|--------|------|----------|-------------|")

            for col in table.get("columns", []):
                col_name = col.get("name", "")
                col_type = col.get("type", "")
                nullable = "YES" if col.get("nullable", True) else "NO"
                col_desc = col.get("description", "")
                lines.append(f"| `{col_name}` | {col_type} | {nullable} | {col_desc} |")

            # Primary key
            pk = table.get("primary_key")
            if pk:
                pk_str = ", ".join(pk) if isinstance(pk, list) else str(pk)
                lines.append(f"\n**Primary Key:** `{pk_str}`")

            # Indexes
            indexes = table.get("indexes", [])
            if indexes:
                idx_strs = [
                    f"`{idx.get('name', 'idx')}` on ({', '.join(idx.get('columns', []))})"
                    for idx in indexes
                ]
                lines.append(f"**Indexes:** {'; '.join(idx_strs)}")

            lines.append("")

        return "\n".join(lines)

    def get_metrics_context(self) -> str:
        """Format business metrics and their SQL templates."""
        if not self.metrics:
            return "_No metrics information available._"

        metrics_list: list[dict[str, Any]] = self.metrics.get("metrics", [])
        if not metrics_list:
            return "_No metrics information available._"

        lines: list[str] = []
        for metric in metrics_list:
            name = metric.get("name", "Unnamed Metric")
            description = metric.get("description", "")
            sql_template = metric.get("sql_template", metric.get("sql", ""))
            lines.append(f"### {name}")
            if description:
                lines.append(f"{description}")
            if sql_template:
                lines.append(f"\n```sql\n{sql_template.strip()}\n```")
            lines.append("")

        return "\n".join(lines)

    def get_joins_context(self) -> str:
        """Format canonical join paths between tables."""
        if not self.joins:
            return "_No join information available._"

        join_list: list[dict[str, Any]] = self.joins.get("joins", [])
        if not join_list:
            return "_No join information available._"

        lines: list[str] = []
        for join in join_list:
            left = join.get("from_table", join.get("left_table", "?"))
            right = join.get("to_table", join.get("right_table", "?"))
            join_type = join.get("join_type", join.get("type", "INNER JOIN"))
            condition = join.get("join_condition", join.get("on", ""))
            description = join.get("description", "")
            lines.append(
                f"- **{left}** ↔ **{right}**: "
                f"`{join_type}` ON `{condition}`"
            )
            if description:
                lines.append(f"  _{description}_")

        return "\n".join(lines)

    def get_glossary_context(self) -> str:
        """Format the business glossary as a definition list."""
        if not self.glossary:
            return "_No glossary available._"

        terms: list[dict[str, Any]] = self.glossary.get("terms", self.glossary.get("glossary", []))
        if not terms:
            return "_No glossary available._"

        lines: list[str] = []
        for term in terms:
            name = term.get("term", term.get("name", ""))
            definition = term.get("definition", term.get("description", ""))
            lines.append(f"- **{name}**: {definition}")

        return "\n".join(lines)

    def get_full_context(self) -> str:
        """Combine all knowledge sections into a single context string."""
        sections = [
            ("Database Schema", self.get_schema_context()),
            ("Business Metrics", self.get_metrics_context()),
            ("Join Relationships", self.get_joins_context()),
            ("Business Glossary", self.get_glossary_context()),
        ]
        parts: list[str] = []
        for title, body in sections:
            parts.append(f"## {title}\n\n{body}")
        return "\n\n---\n\n".join(parts)
