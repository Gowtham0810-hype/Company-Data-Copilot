# 📊 Company Data Copilot

A production-ready **LangGraph-based AI agent** that answers natural-language questions over a PostgreSQL stock trading platform database using **Multi-Provider LLM Orchestration (Groq & Google Gemini)**, **PostgreSQL Persistent Memory**, **OKF knowledge files**, and a **Chainlit chat UI**.

Ask complex financial and operational questions in plain English — the agent generates safe SQL, executes up to 3 queries per question with self-correction, persists conversation checkpoints in PostgreSQL, and delivers clean, actionable insights.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-green?logo=langchain&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue?logo=postgresql&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-GPT_OSS_120B-orange?logo=fastapi&logoColor=white)
![Gemini](https://img.shields.io/badge/Google_Gemini-Multi--Model-yellow?logo=google&logoColor=white)
![Chainlit](https://img.shields.io/badge/Chainlit-2.0+-purple)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Key Features & Priorities

| Feature | Description |
|---------|-------------|
| 🤖 **Natural Language SQL** | Ask questions in plain English → get SQL-powered answers with tables & insights |
| 🔀 **Multi-Provider LLM Pool (Groq + Gemini)** | Dual-provider architecture: Groq (30 RPM, 14,400 RPD) + Google Gemini with instant failover on 429 quota exhaustion or 503 errors |
| ⚡ **Priority 1: Multi-SQL Query Execution** | Allows the agent to run multiple SQL queries per question (up to 3 rounds) for progressive discovery, self-correction, and comparative analysis |
| 💾 **Priority 2: Persistent PostgreSQL Memory** | Replaces ephemeral in-memory savers with a PostgreSQL-backed checkpointer (`PostgresSaver`), persisting full chat history across restarts |
| 🧠 **Priority 3: Structured Context Digest** | Intelligently captures previously executed SQL queries, entity IDs, and metrics into a compact prompt digest without breaking API turn-alternation rules |
| 🛡️ **SQL Guardrails** | AST verification with `sqlparse`, statement whitelist (`SELECT` only), read-only transactions, parameter safety, and timeouts |
| 📚 **OKF Knowledge Files** | YAML-based schema definitions, metric templates, join paths, and financial glossary |
| 💬 **Chainlit Chat UI** | Modern dark-themed chat interface with real-time provider health, latency, and quota visibility |
| 🐳 **Docker-Ready** | One-command PostgreSQL setup with full trading platform seed data and checkpointer tables |
| 📊 **30 Real Stocks** | Pre-loaded data: AAPL, MSFT, GOOGL, TSLA, NVDA, JPM, RELIANCE, TCS, and more |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Chainlit Chat UI (app.py)                    │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                 LangGraph Agent (src/agent.py)                  │
│                                                                 │
│   ┌──────────┐      ┌──────────────┐      ┌──────────┐          │
│   │ Chatbot  │─────▶│  Tool Router │─────▶│  Tools   │          │
│   │  Node    │◀─────│ (up to 3x/q) │◀─────│  Node    │          │
│   └──────────┘      └──────────────┘      └──────────┘          │
│        │                                        │               │
│        ▼                                        ▼               │
│ ┌──────────────────────────────┐      ┌──────────────────┐      │
│ │   Multi-Provider LLM Pool    │      │  6 Agent Tools   │      │
│ │   ─────────────────────────  │      │  ─────────────   │      │
│ │   Primary: Groq (Llama 3.3)  │      │  execute_sql     │      │
│ │   Fallback: Gemini (Flash)   │      │  validate_sql    │      │
│ │   Auto Failover & Cooldown   │      │  get_table_info  │      │
│ └──────────────────────────────┘      │  get_metric_def  │      │
│                                       │  list_tables     │      │
│                                       │  search_glossary │      │
│                                       └────────┬─────────┘      │
└───────────────────────┬────────────────────────┼────────────────┘
                        │                        │
                        ▼                        ▼
     ┌──────────────────────────────────────────────────────┐
     │                PostgreSQL (Docker)                   │
     │  ──────────────────────────────────────────────────  │
     │  1. Business Data: stocks, trades, portfolios (Read) │
     │  2. LangGraph Memory: PostgresSaver Checkpoints      │
     └──────────────────────────────────────────────────────┘
```

---

## 🌟 Multi-Provider Architecture & Priorities in Detail

### 1. Multi-Provider Failover Pool (`src/llm_pool.py`)
- **Groq Primary**: Powered by `openai/gpt-oss-120b` (120B parameter model with tools & reasoning) and `openai/gpt-oss-20b` (fast 20B fallback), delivering **30 RPM and 14,400 RPD** free-tier capacity with ultra-fast latency.
- **Gemini Secondary / Fallback**: Powered by `gemini-3.1-flash-lite` and `gemini-3.5-flash`.
- **Automatic Circuit Breaking**: When a provider encounters a `429 RESOURCE_EXHAUSTED`, `404` (unavailable model), or `503 Unavailable` error, it is placed into a timed cooldown window while requests fail over seamlessly to the alternative provider without interrupting the user.

### 2. Priority 1: Multi-SQL Query Execution
- Complex questions (e.g., *"Compare the top trading broker with the highest volume stock"*) require multiple investigative queries.
- The agent can execute a query, inspect the results, formulate a follow-up query, and synthesize the final answer.
- Safety cap configured via `MAX_SQL_ROUNDS=3` prevents infinite loops.

### 3. Priority 2: Persistent Conversation Memory (`PostgresSaver`)
- Replaced ephemeral memory with `langgraph-checkpoint-postgres`.
- Every turn is checkpointed to `copilot_postgres` in the `checkpoints`, `checkpoint_blobs`, and `checkpoint_writes` tables.
- Sessions seamlessly resume across browser refreshes and server restarts using the session `thread_id`.

### 4. Priority 3: Structured Context Digest
- Prevents Gemini/Groq `400 INVALID_ARGUMENT` errors caused by malformed tool turn sequences.
- Extracts previous SQL queries, returned entities, and numerical summaries into a compact `[Structured History]` context header in the system prompt.

---

## 📁 Project Structure

```
Company Data Copilot/
├── app.py                      # Chainlit entry point with multi-provider visibility
├── docker-compose.yml          # PostgreSQL container setup
├── pyproject.toml              # Modern Python packaging with dependencies
├── requirements.txt            # Pip requirements
├── .env.example                # Multi-provider environment template
├── .gitignore
├── chainlit.md                 # Chat landing page
├── README.md                   # Full documentation
├── LICENSE                     # MIT License
│
├── db/
│   └── init.sql                # Schema + seed data (15 tables, 30 real stocks)
│
├── knowledge/                  # OKF Knowledge Files
│   ├── schema.yaml             # Table & column definitions
│   ├── metrics.yaml            # 20+ business metric SQL templates
│   ├── joins.yaml              # Valid join paths between tables
│   └── glossary.yaml           # Financial term definitions
│
├── src/
│   ├── __init__.py
│   ├── config.py               # Pydantic settings for Groq, Gemini & Postgres
│   ├── llm_pool.py             # Multi-provider failover pool & circuit breaker
│   ├── database.py             # SQLAlchemy read-only query engine
│   ├── knowledge_loader.py     # Compact & verbose YAML context loaders
│   ├── guardrails.py           # SQL safety validation & output sanitization
│   ├── prompts.py              # System prompts & multi-SQL instructions
│   ├── tools.py                # 6 LangGraph @tool definitions
│   └── agent.py                # LangGraph StateGraph, PostgresSaver & Context Digest
│
└── .chainlit/
    └── config.toml             # Chainlit UI configuration
```

---

## 🗄️ Database Schema

The stock trading platform database models **15 tables** with comprehensive relationships:

| Table | Description | Seed Records |
|-------|-------------|:------------:|
| `exchanges` | NYSE, NASDAQ, BSE, NSE, LSE | 5 |
| `sectors` | Technology, Finance, Healthcare, Energy, etc. | 10 |
| `stocks` | AAPL, MSFT, GOOGL, TSLA, NVDA, RELIANCE, TCS… | 30 |
| `stock_prices` | Daily OHLCV price data with trading dates | ~100 |
| `brokers` | Licensed trading brokers with commission rates | 5 |
| `clients` | Individual & institutional investors | 15 |
| `portfolios` | Named investment portfolios | 10 |
| `portfolio_holdings` | Stock positions with buy price & current value | ~30 |
| `orders` | Market, limit, and stop-loss orders | ~80 |
| `trades` | Executed buy/sell trade records with commissions | ~60 |
| `dividends` | Dividend declaration, record, and payment dates | 10 |
| `watchlists` | Client stock watchlists | 5 |
| `watchlist_items` | Individual stocks tracked on watchlists | ~15 |
| `market_indices` | S&P 500, DJIA, NIFTY 50, SENSEX, FTSE 100 | 5 |
| `index_compositions` | Index constituent weightings | ~20 |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Docker & Docker Compose**
- **Groq API Key** (Recommended primary) — [Get free API key from Groq Console](https://console.groq.com/keys)
- **Google AI API Key** (Fallback / alternative) — [Get free API key from Google AI Studio](https://aistudio.google.com/apikey)

### 1. Set Up Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and configure your API keys:

```env
# Multi-Provider Configuration
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
GROQ_FALLBACK_MODELS=openai/gpt-oss-120b,openai/gpt-oss-20b

GOOGLE_API_KEY=your_google_api_key_here
GEMINI_MODEL=gemini-3.1-flash-lite
GEMINI_FALLBACK_MODELS=gemini-3.1-flash-lite,gemini-3.5-flash

PRIMARY_PROVIDER=groq
MAX_SQL_ROUNDS=3

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=trading_platform
POSTGRES_USER=copilot_user
POSTGRES_PASSWORD=copilot_pass_2024
```

### 2. Start PostgreSQL with Docker

```bash
docker-compose up -d
```

Verify that the database is healthy:

```bash
docker exec -it copilot_postgres psql -U copilot_user -d trading_platform -c "SELECT COUNT(*) FROM stocks;"
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Launch the Chat Interface

```bash
chainlit run app.py -w
```

Open **http://localhost:8000** in your browser.

---

## 💬 Example Questions

| Category | Example Question |
|----------|-----------------|
| 📈 **Stock Analysis** | *"What are the top 5 stocks by market cap?"* |
| 📈 **Stock Analysis** | *"Give top 3 stocks of this week based on trading volume"* |
| 📈 **Comparative Multi-SQL** | *"Compare the closing prices of Apple and Microsoft over the latest trading days"* |
| 💼 **Portfolios** | *"What is the total value of John Smith's portfolio?"* |
| 💼 **Portfolios** | *"Show sector allocation across all portfolios"* |
| 🔄 **Trading Activity** | *"How many trades were executed today and what was the net amount?"* |
| 🔄 **Trading Activity** | *"What is the total commission earned by each broker?"* |
| 👥 **Clients & Accounts** | *"List the top 10 clients by account balance"* |
| 📊 **Market & Dividends** | *"Which stocks have the highest dividend yield?"* |
| 🔍 **Financial Glossary** | *"What does VWAP mean and how is it calculated?"* |

---

## 🛡️ Safety & Guardrails

| Layer | Implementation |
|-------|----------------|
| **Statement Whitelist** | AST verification with `sqlparse` — strictly permits `SELECT` statements only |
| **Keyword Blacklist** | Blocks mutation keywords (`DROP`, `DELETE`, `INSERT`, `UPDATE`, `ALTER`, `TRUNCATE`, `EXEC`) |
| **Injection Defense** | Rejects multi-statement batches (`;`), comments (`--`, `/* */`), and sleeping attacks (`pg_sleep`) |
| **Transaction Read-Only** | Every connection enforces `SET TRANSACTION READ ONLY` at the database session level |
| **Statement Timeout** | Query timeout enforced via `SET statement_timeout` |
| **Output Sanitization** | Automatic regex masking of sensitive data |
| **Row Truncation** | Caps query outputs to 100 rows to prevent memory exhaustion |

---

## ⚙️ Configuration Reference

All settings are managed via `.env` (loaded through Pydantic Settings):

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | `None` | Groq API Key (30 RPM, 14,400 RPD free tier) |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Primary Groq model (120B params) |
| `GROQ_FALLBACK_MODELS` | `openai/gpt-oss-120b,openai/gpt-oss-20b` | Comma-separated Groq fallback models |
| `GOOGLE_API_KEY` | `None` | Google AI Gemini API key |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` | Primary Gemini model identifier |
| `GEMINI_FALLBACK_MODELS` | `gemini-3.1-flash-lite,gemini-3.5-flash` | Comma-separated Gemini fallback models |
| `PRIMARY_PROVIDER` | `groq` | Preferred primary provider (`groq` or `gemini`) |
| `MAX_SQL_ROUNDS` | `3` | Maximum SQL execution rounds per question |
| `POSTGRES_HOST` | `localhost` | PostgreSQL host address |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `trading_platform` | Database name |
| `POSTGRES_USER` | `copilot_user` | Database user |
| `POSTGRES_PASSWORD` | `copilot_pass_2024` | Database password |
| `MAX_QUERY_ROWS` | `100` | Maximum rows returned per SQL query |
| `QUERY_TIMEOUT_SECONDS` | `30` | SQL statement timeout |

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
