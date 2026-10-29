
import asyncio
import logging
import traceback

import chainlit as cl

from src.agent import DataCopilotAgent
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

    # Welcome message
    welcome_message = """# 📊 Company Data Copilot

Welcome! I'm your AI-powered data analyst for the **Stock Trading Platform**.

I can help you with:
- 📈 **Stock Analysis** — prices, trends, volumes, returns
- 💼 **Portfolio Insights** — holdings, P&L, diversification
- 🔄 **Trading Activity** — orders, trades, commissions
- 👥 **Client Analytics** — account values, risk profiles
- 📊 **Market Metrics** — indices, sector performance, dividends

### Example Questions:
> "What are the top 5 stocks by trading volume this month?"
> "Show me the portfolio allocation for client John Smith"
> "What's the total commission earned by each broker?"
> "Which stocks have the highest dividend yield?"
> "Compare the daily returns of AAPL vs MSFT"

Type your question below to get started! 🚀"""

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

    # Send an empty message that we'll update with the response
    msg = cl.Message(content="⏳ Thinking...")
    await msg.send()

    try:
        logger.info("Processing message: '%s'", message.content[:100])

        # Run with a timeout so the user isn't left waiting forever
        response = await asyncio.wait_for(
            agent.chat(message.content, thread_id=thread_id),
            timeout=120,  # 2 minute max
        )

        if response:
            msg.content = response
        else:
            msg.content = "⚠️ The AI returned an empty response. Please try rephrasing your question."

        await msg.update()
        logger.info("Response sent successfully (%d chars)", len(msg.content))

    except asyncio.TimeoutError:
        logger.error("Request timed out after 120s")
        msg.content = (
            "⏰ **Request Timed Out**\n\n"
            "The AI took too long to respond. This usually means:\n"
            "- The Gemini API is experiencing high demand (503 errors)\n"
            "- The query is too complex\n\n"
            "Please try again in a moment."
        )
        await msg.update()

    except Exception as e:
        tb = traceback.format_exc()
        logger.error("Error processing message: %s\n%s", e, tb)
        msg.content = (
            f"❌ **Error**: {e}\n\n"
            f"```\n{tb[-500:]}\n```\n\n"
            "Please try rephrasing your question."
        )
        await msg.update()
