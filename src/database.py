"""Database connection manager using SQLAlchemy (synchronous engine).

Provides read-only query execution with guardrails such as statement
timeouts, row limits, and read-only transactions.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings

logger = logging.getLogger(__name__)

# ── Engine (module-level singleton) ──────────────────────────────────────
_engine: Engine | None = None


def _get_engine() -> Engine:
    """Return the module-level SQLAlchemy engine, creating it on first call."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
        )
    return _engine


_SessionFactory: sessionmaker | None = None


def _get_session_factory() -> sessionmaker:
    """Return a sessionmaker bound to the engine singleton."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=_get_engine())
    return _SessionFactory


@contextmanager
def _readonly_session() -> Generator[Session, None, None]:
    """Context manager that yields a read-only database session.

    The session is configured with:
    * ``SET TRANSACTION READ ONLY``
    * ``SET statement_timeout`` based on application settings
    """
    session: Session = _get_session_factory()()
    try:
        session.execute(text("SET TRANSACTION READ ONLY"))
        session.execute(
            text(f"SET statement_timeout = '{settings.query_timeout_seconds * 1000}'")
        )
        yield session
    finally:
        session.close()


def execute_readonly_query(
    sql: str,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Execute a read-only SQL statement and return results as a list of dicts.

    Parameters
    ----------
    sql:
        The SQL SELECT statement to execute.
    params:
        Optional bind-parameters for the query.

    Returns
    -------
    list[dict[str, Any]]
        Each element maps column names to their values.  The list is
        truncated to ``settings.max_query_rows`` entries.

    Raises
    ------
    RuntimeError
        Wraps any database-level exception with a user-friendly message.
    """
    try:
        with _readonly_session() as session:
            result = session.execute(text(sql), params or {})
            columns = list(result.keys())
            rows = result.fetchmany(settings.max_query_rows)
            return [dict(zip(columns, row)) for row in rows]
    except Exception as exc:
        logger.exception("Query execution failed")
        raise RuntimeError(f"Database query failed: {exc}") from exc


def test_connection() -> bool:
    """Return ``True`` if the database is reachable, ``False`` otherwise."""
    try:
        with _get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Database connectivity check failed")
        return False
