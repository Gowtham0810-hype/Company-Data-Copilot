import chainlit as cl
from src.agent import DataCopilotAgent
from src.database import test_connection
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize agent once at module level
agent = None

@cl.on_chat_start
async def on_chat_start():
    """Initialize the agent and set up the chat session."""
    global agent
    
    # Test database connection
    db_connected = test_connection()
    
    if not db_connected:
        await cl.Message(
            content="⚠️ **Database Connection Failed**\n\nCould not connect to the PostgreSQL database. Please ensure:\n1. Docker containers are running (`docker-compose up -d`)\n2. Database credentials in `.env` are correct\n3. The database has been initialized with seed data\n\nPlease fix the connection and restart."
        ).send()
        return
    
    # Initialize agent if not already done
    if agent is None:
        try:
            agent = DataCopilotAgent()
            logger.info("DataCopilotAgent initialized successfully")
        except Exception as e:
            await cl.Message(content=f"❌ **Agent Initialization Failed**: {str(e)}").send()
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
        await cl.Message(content="❌ Agent not initialized. Please restart the application.").send()
        return
    
    thread_id = cl.user_session.get("thread_id", "default")
    
    # Show thinking indicator
    msg = cl.Message(content="")
    await msg.send()
    
    try:
        # Stream the response using LangGraph
        response = await agent.chat(message.content, thread_id=thread_id)
        msg.content = response
        await msg.update()
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        msg.content = f"❌ **Error**: {str(e)}\n\nPlease try rephrasing your question."
        await msg.update()
