"""Chainlit chat application for the Company Data Copilot."""

import asyncio
import logging
import time
import traceback

import chainlit as cl

from src.agent import DataCopilotAgent
from src.config import settings
from src.database import test_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Module-level agent singleton
agent: DataCopilotAgent | None = None


@cl.on_chat_start
async def on_chat_start():
    """Initialize the agent and set up the chat session."""
    global agent

    # Test database connection
    logger.info("Testing database connection...")
    db_connected = test_connection()
    logger.info("Database connected: %s", db_connected)

    if not db_connected:
        await cl.Message(
            content=(
                "⚠️ **Database Connection Failed**\n\n"
                "Could not connect to the PostgreSQL database. Please ensure:\n"
                "1. Docker containers are running (`docker-compose up -d`)\n"
                "2. Database credentials in `.env` are correct\n"
                "3. The database has been initialized with seed data\n\n"
                "Please fix the connection and restart."
            )
        ).send()
        return

    # Initialize agent if not already done
    if agent is None:
        try:
            logger.info("Initializing DataCopilotAgent...")
            agent = DataCopilotAgent()
            logger.info("DataCopilotAgent initialized successfully")
        except Exception as e:
            logger.error("Agent init failed: %s", e, exc_info=True)
            await cl.Message(
                content=f"❌ **Agent Initialization Failed**: {e}"
            ).send()
            return

    # Store thread ID for conversation memory
    cl.user_session.set("thread_id", cl.context.session.id)

    # Welcome message with multi-provider pool visibility
    stats = agent.get_usage_stats()
    providers_str = stats.get("providers_str", "Groq / Gemini")
    active_models = ", ".join({e["model"] for e in stats.get("endpoints", [])}) or settings.gemini_model
    welcome_message = f"""# 📊 Company Data Copilot

Welcome! I'm your AI-powered data analyst for the **Stock Trading Platform**.

I can help you with:
- 📈 **Stock Analysis** — prices, trends, volumes, returns
- 💼 **Portfolio Insights** — holdings, P&L, diversification
- 🔄 **Trading Activity** — orders, trades, commissions
- 👥 **Client Analytics** — account values, risk profiles
- 📊 **Market Metrics** — indices, sector performance, dividends

### Example Questions:
> "What are the top 5 stocks by market cap?"
> "What are the top 3 stocks of this week based on volume of purchases?"
> "Which stocks have the highest dividend yield?"
> "Show me the portfolio allocation for client John Smith"
> "What's the total commission earned by each broker?"

---
*⚡ Providers: **{providers_str}** | Models: `{active_models}` | Pool: {stats['active_endpoints']}/{stats['total_endpoints']} Active · {stats['total_capacity_1m']} RPM Combined Capacity*
"""

    await cl.Message(content=welcome_message).send()


@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming user messages."""
    global agent

    if agent is None:
        await cl.Message(
            content="❌ Agent not initialized. Please restart the application."
        ).send()
        return

    thread_id = cl.user_session.get("thread_id", "default")

    # Send an initial thinking message
    msg = cl.Message(content="⏳ Analyzing question and generating SQL...")
    await msg.send()

    start_time = time.time()
    try:
        logger.info("Processing message: '%s'", message.content[:100])

        # Run with timeout
        response = await asyncio.wait_for(
            agent.chat(message.content, thread_id=thread_id),
            timeout=120,
        )

        elapsed = time.time() - start_time
        stats = agent.get_usage_stats()

        # Multi-provider pool usage & quota visibility footer
        providers_label = stats.get("providers_str", "Active")
        footer = (
            f"\n\n---\n"
            f"*⏱️ {elapsed:.1f}s | 🌐 Providers: {providers_label} ({stats['active_endpoints']}/{stats['total_endpoints']} active) | "
            f"📊 Load: {stats['total_recent_1m']}/{stats['total_capacity_1m']} RPM · Total: {stats['total_calls']} calls*"
        )

        if response:
            msg.content = response + footer
        else:
            msg.content = "⚠️ The AI returned an empty response. Please try rephrasing your question."

        await msg.update()
        logger.info("Response sent successfully (%d chars, %.1fs)", len(msg.content), elapsed)

    except asyncio.TimeoutError:
        logger.error("Request timed out after 120s")
        msg.content = (
            "⏰ **Request Timed Out**\n\n"
            "The AI took too long to respond. This usually means:\n"
            "- All configured providers are cooling down\n"
            "- Upstream LLM providers are experiencing transient demand\n\n"
            "Please wait a few seconds and try again."
        )
        await msg.update()

    except Exception as e:
        tb = traceback.format_exc()
        logger.error("Error processing message: %s\n%s", e, tb)

        err_str = str(e)
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            msg.content = (
                "⏳ **Free-Tier Rate Limit Reached Across Providers**\n\n"
                "All configured LLM endpoints have reached their rate limit for the current minute.\n\n"
                "The pool will automatically pace and recover. You can configure both `GROQ_API_KEY` (30 RPM free) and `GOOGLE_API_KEY` in `.env` for seamless multi-provider failover!"
            )
        else:
            msg.content = (
                f"❌ **Error**: {e}\n\n"
                f"```\n{tb[-500:]}\n```\n\n"
                "Please try rephrasing your question."
            )
        await msg.update()
