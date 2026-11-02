"""SQL safety validation and output sanitization.

Ensures that only safe, read-only ``SELECT`` queries are executed against
the database and that result data is sanitized before being returned to
the user.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import sqlparse

logger = logging.getLogger(__name__)

# Maximum allowed query length in characters.
_MAX_QUERY_LENGTH = 2000

# Regex to detect common sensitive data patterns (e.g. SSN, credit-card-like).
_SENSITIVE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),          # SSN
    re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),  # Credit card
]


class SQLGuardrails:
    """Static helper that validates SQL queries and sanitizes outputs."""

    # Keywords that must NOT appear in a user-generated query.
    BLOCKED_KEYWORDS: list[str] = [
        "DROP",
        "DELETE",
        "INSERT",
        "UPDATE",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "GRANT",
        "REVOKE",
        "EXEC",
        "EXECUTE",
        "COPY",
        "VACUUM",
        "REINDEX",
        "CLUSTER",
        "COMMENT",
        "LOCK",
        "NOTIFY",
        "LISTEN",
        "LOAD",
        "SECURITY",
        "SET ROLE",
        "RESET",
        "DISCARD",
    ]

    # Regex patterns that indicate potentially dangerous constructs.
    BLOCKED_PATTERNS: list[str] = [
        r";\s*\w",            # Multiple statements
        r"--",                # SQL line comments (could hide injection)
        r"/\*",               # Block comments
        r"pg_sleep",          # Time-based attacks
        r"information_schema",  # Schema enumeration
        r"pg_catalog",        # System catalog access
        r"INTO\s+OUTFILE",    # File writes
        r"LOAD_FILE",         # File reads
    ]

    # ── Public API ───────────────────────────────────────────────────────

    @classmethod
    def validate(cls, sql: str) -> tuple[bool, str]:
        """Validate an SQL string for safety.

        Parameters
        ----------
        sql:
            The raw SQL string to validate.

        Returns
        -------
        tuple[bool, str]
            ``(True, "Query validated")`` when safe, or
            ``(False, "<reason>")`` when unsafe.
        """
        if not sql or not sql.strip():
            return False, "Empty query provided."

        # 1. Length check
        if len(sql) > _MAX_QUERY_LENGTH:
            return False, (
                f"Query exceeds maximum allowed length of {_MAX_QUERY_LENGTH} characters "
                f"({len(sql)} provided)."
            )

        # 2. Parse with sqlparse and verify it is a SELECT statement.
        try:
            parsed_statements = sqlparse.parse(sql)
        except Exception as exc:
            return False, f"Failed to parse SQL: {exc}"

        if not parsed_statements:
            return False, "Could not parse any SQL statement."

        # We only allow a single statement.
        if len(parsed_statements) > 1:
            return False, "Multiple SQL statements are not allowed."

        stmt = parsed_statements[0]
        stmt_type = stmt.get_type()
        if stmt_type and stmt_type.upper() != "SELECT":
            return False, f"Only SELECT statements are allowed (detected: {stmt_type})."

        # 3. Blocked keywords (case-insensitive, whole-word match).
        sql_upper = sql.upper()
        for keyword in cls.BLOCKED_KEYWORDS:
            # Use word-boundary matching to avoid false positives
            # (e.g. "CREATED_AT" should not match "CREATE").
            pattern = rf"\b{re.escape(keyword)}\b"
            if re.search(pattern, sql_upper):
                return False, f"Blocked keyword detected: {keyword}"

        # 4. Blocked regex patterns.
        for pattern in cls.BLOCKED_PATTERNS:
            if re.search(pattern, sql, re.IGNORECASE):
                return False, f"Blocked pattern detected: {pattern}"

        # 5. All checks passed.
        return True, "Query validated"

    @classmethod
    def sanitize_output(
        cls,
        results: list[dict[str, Any]],
        max_rows: int = 100,
    ) -> list[dict[str, Any]]:
        """Truncate results and mask sensitive data patterns.

        Parameters
        ----------
        results:
            Raw query result rows as dicts.
        max_rows:
            Maximum number of rows to return.

        Returns
        -------
        list[dict[str, Any]]
            Sanitized, truncated results.
        """
        truncated = results[:max_rows]

        sanitized: list[dict[str, Any]] = []
        for row in truncated:
            clean_row: dict[str, Any] = {}
            for key, value in row.items():
                if isinstance(value, str):
                    masked = value
                    for pat in _SENSITIVE_PATTERNS:
                        masked = pat.sub("***REDACTED***", masked)
                    clean_row[key] = masked
                else:
                    clean_row[key] = value
            sanitized.append(clean_row)

        return sanitized
