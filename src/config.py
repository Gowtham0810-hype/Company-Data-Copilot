"""Application configuration loaded from environment variables via pydantic-settings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the Company Data Copilot.

    All values are read from environment variables or a `.env` file located
    in the project root.
    """

    # ── Google Gemini ────────────────────────────────────────────────────
    google_api_key: str = Field(..., env="GOOGLE_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash", env="GEMINI_MODEL")

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra" : "ignore"}


settings = Settings()
