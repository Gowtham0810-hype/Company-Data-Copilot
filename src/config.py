"""Application configuration loaded from environment variables via pydantic-settings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the Company Data Copilot.

    All values are read from environment variables or a `.env` file located
    in the project root.
    """

    # ── Multi-Provider LLM Configuration (Groq & Google Gemini) ───────────
    # Google Gemini
    google_api_key: str | None = Field(default=None, env="GOOGLE_API_KEY")
    gemini_model: str = Field(default="gemini-3.1-flash-lite", env="GEMINI_MODEL")
    gemini_fallback_models: str = Field(
        default="gemini-3.1-flash-lite,gemini-3.5-flash",
        env="GEMINI_FALLBACK_MODELS",
    )

    # Groq (High-performance open weights models with fast inference & tool support)
    groq_api_key: str | None = Field(default=None, env="GROQ_API_KEY")
    groq_model: str = Field(default="openai/gpt-oss-120b", env="GROQ_MODEL")
    groq_fallback_models: str = Field(
        default="openai/gpt-oss-120b,openai/gpt-oss-20b",
        env="GROQ_FALLBACK_MODELS",
    )

    # Primary provider preference: "groq" or "gemini" (auto-detected if only one key is set)
    primary_provider: str = Field(default="groq", env="PRIMARY_PROVIDER")

    # Multi-SQL execution limit per question
    max_sql_rounds_per_question: int = Field(default=3, env="MAX_SQL_ROUNDS")

    # ── PostgreSQL ───────────────────────────────────────────────────────
    postgres_host: str = Field(default="localhost", env="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, env="POSTGRES_PORT")
    postgres_db: str = Field(default="trading_platform", env="POSTGRES_DB")
    postgres_user: str = Field(default="copilot_user", env="POSTGRES_USER")
    postgres_password: str = Field(default="copilot_pass_2024", env="POSTGRES_PASSWORD")

    # ── Application ──────────────────────────────────────────────────────
    max_query_rows: int = Field(default=100, env="MAX_QUERY_ROWS")
    query_timeout_seconds: int = Field(default=30, env="QUERY_TIMEOUT_SECONDS")

    # ── Derived connection strings ───────────────────────────────────────
    @property
    def postgres_conn_string(self) -> str:
        """Raw PostgreSQL connection string for psycopg connection pools."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url(self) -> str:
        """SQLAlchemy sync connection URL (psycopg driver)."""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_async(self) -> str:
        """SQLAlchemy async connection URL (asyncpg driver)."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
