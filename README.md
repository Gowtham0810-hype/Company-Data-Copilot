# 📊 Company Data Copilot

A modern **LangGraph-based AI agent** that answers natural-language questions over a PostgreSQL stock trading platform database using **Google Gemini**, **OKF knowledge files**, and a **Chainlit chat UI**.

Ask questions in plain English — the agent generates safe SQL, executes it against your database, and returns formatted, insightful answers.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-green?logo=langchain&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue?logo=postgresql&logoColor=white)
![Gemini](https://img.shields.io/badge/Google_Gemini-3.1_Flash_Lite-orange?logo=google&logoColor=white)
![Chainlit](https://img.shields.io/badge/Chainlit-2.0+-purple)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🤖 **Natural Language SQL** | Ask questions in plain English → get SQL-powered answers with tables & insights |
| 🛡️ **SQL Guardrails** | Read-only enforcement, blocked keywords, injection prevention, query timeouts |
| 📚 **OKF Knowledge Files** | YAML-based schema definitions, metric templates, join paths, business glossary |
| 🔧 **Tool-Based Architecture** | LangGraph agent with specialized tools for SQL execution, validation, and knowledge lookup |
| ⚡ **Quota & Rate Management** | Built-in sliding-window rate limiter (4 RPM cap) optimized for Gemini Free Tier |
| 🔄 **Robust Multi-Turn Memory** | Context-sanitized conversation history preventing Gemini turn-order validation errors |
| 💬 **Chainlit Chat UI** | Modern dark-themed chat interface with real-time latency and quota visibility |
| 🐳 **Docker-Ready** | One-command PostgreSQL setup with full trading platform seed data |
| 📊 **30 Real Stocks** | Pre-loaded data: AAPL, MSFT, GOOGL, TSLA, NVDA, JPM, RELIANCE, TCS, and more |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Chainlit Chat UI                      │
│                      (app.py)                            │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                 LangGraph Agent                          │
│              (src/agent.py)                               │
│                                                          │
│   ┌──────────┐    ┌──────────────┐    ┌──────────┐      │
│   │ Chatbot  │───▶│  Tool Router │───▶│  Tools   │      │
│   │  Node    │◀───│ (conditional)│◀───│  Node    │      │
│   └──────────┘    └──────────────┘    └──────────┘      │
│        │                                    │            │
│        ▼                                    ▼            │
│   ┌───────────────┐               ┌──────────────────┐  │
│   │ Rate Limiter  │               │  6 Agent Tools   │  │
│   │ & Gemini 3.1  │               │  ─────────────   │  │
│   │  Flash Lite   │               │  execute_sql     │  │
│   └───────────────┘               │  validate_sql    │  │
│                                   │  get_table_info  │  │
│                                   │  get_metric_def  │  │
│                                   │  list_tables     │  │
│                                   │  search_glossary │  │
│                                   └────────┬─────────┘  │
└────────────────────────────────────────────┼────────────┘
                                             │
                    ┌────────────────────────┼──────────────┐
                    │                        │              │
                    ▼                        ▼              ▼
          ┌──────────────┐        ┌──────────────┐  ┌────────────┐
          │  PostgreSQL  │        │  Guardrails  │  │  OKF       │
          │  Database    │        │  Validator   │  │  Knowledge │
          │  (Read-Only) │        │              │  │  Files     │
          └──────────────┘        └──────────────┘  └────────────┘
```

---

## 📁 Project Structure

```
Company Data Copilot/
├── app.py                      # Chainlit entry point with usage visibility
├── docker-compose.yml          # PostgreSQL container setup
├── pyproject.toml              # Modern Python packaging
├── requirements.txt            # Pip dependencies
├── .env.example                # Environment template
├── .gitignore
├── chainlit.md                 # Chat landing page
├── README.md                   # Full documentation
├── LICENSE                     # MIT License
│
├── db/
│   └── init.sql                # Full schema + seed data (837 lines, 15 tables)
│
├── knowledge/                  # OKF Knowledge Files
│   ├── schema.yaml             # Table & column definitions
│   ├── metrics.yaml            # 20+ business metric SQL templates
│   ├── joins.yaml              # Valid join paths between tables
│   └── glossary.yaml           # Financial term definitions
│
├── src/
│   ├── __init__.py
│   ├── config.py               # Pydantic settings from .env
│   ├── database.py             # SQLAlchemy read-only query engine
│   ├── knowledge_loader.py     # Compact & verbose YAML context loaders
│   ├── guardrails.py           # SQL safety validation & output sanitization
│   ├── prompts.py              # System prompts & database date context
│   ├── tools.py                # 6 LangGraph @tool definitions
│   └── agent.py                # StateGraph agent, rate limiter & context sanitizer
│
└── .chainlit/
    └── config.toml             # Chainlit UI configuration
```

---

## 🗄️ Database Schema

The stock trading platform database models **15 tables** with comprehensive relationships and realistic data:

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
- **Google AI API Key** — [Get an API key from Google AI Studio](https://aistudio.google.com/apikey)

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/company-data-copilot.git
cd company-data-copilot
```

### 2. Set Up Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and add your Google API key:

```env
# LLM
GOOGLE_API_KEY=your_actual_google_api_key
GEMINI_MODEL=gemini-3.1-flash-lite

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=trading_platform
POSTGRES_USER=copilot_user
POSTGRES_PASSWORD=copilot_pass_2024

# App Settings
MAX_QUERY_ROWS=100
QUERY_TIMEOUT_SECONDS=30
```

### 3. Start PostgreSQL with Docker

```bash
docker-compose up -d
```

Verify that the database is populated:

```bash
docker exec -it copilot_postgres psql -U copilot_user -d trading_platform -c "SELECT COUNT(*) FROM stocks;"
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Launch the Chat Interface

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
| 📈 **Stock Analysis** | *"Show Apple (AAPL) price history and daily returns"* |
| 💼 **Portfolios** | *"What is the total value of John Smith's portfolio?"* |
| 💼 **Portfolios** | *"Show sector allocation across all portfolios"* |
| 🔄 **Trading Activity** | *"How many trades were executed today and what was the net amount?"* |
| 🔄 **Trading Activity** | *"What is the total commission earned by each broker?"* |
| 👥 **Clients & Accounts** | *"List the top 10 clients by account balance"* |
| 📊 **Market & Dividends** | *"Which stocks have the highest dividend yield?"* |
| 🔍 **Financial Glossary** | *"What does VWAP mean and how is it calculated?"* |

---

## ⚡ Performance & Quota Optimization

To run smoothly on the Gemini Free Tier (5 RPM limit), the system implements several architectural optimizations:

1. **Sliding-Window Rate Limiter**: Automatically paces requests to a maximum of 4 calls per 60 seconds, preventing `429 RESOURCE_EXHAUSTED` errors.
2. **Compact Prompt Injection**: Generates concise, single-line table schemas (`table(col TYPE PK, col TYPE FK->ref)`), reducing system prompt size from ~45,000 to ~10,000 characters.
3. **Multi-Turn Turn Sanitizer**: Collapses historical chat turns into clean `User ↔ Assistant` text pairs, stripping out old intermediate tool-call records. This prevents Gemini's `400 INVALID_ARGUMENT` turn-alternation errors and eliminates token inflation.
4. **Guaranteed 2-Step Execution**: Once an SQL query executes, the agent immediately synthesizes the answer, eliminating runaway multi-step loops and recursion errors.
5. **Real-Time Visibility Footer**: Each response displays API call latency and quota consumption:
   > *⏱️ 2.4s | 📊 Free-tier API calls: 2/4 RPM used (2 available) · Total: 4 calls*

---

## 🛡️ Safety & Guardrails

The application enforces multiple defense-in-depth security layers:

| Layer | Implementation |
|-------|----------------|
| **Statement Whitelist** | AST verification with `sqlparse` — strictly permits `SELECT` statements only |
| **Keyword Blacklist** | Blocks mutation and admin keywords (`DROP`, `DELETE`, `INSERT`, `UPDATE`, `ALTER`, `TRUNCATE`, `EXEC`, `VACUUM`) |
| **Injection Defense** | Rejects multi-statement batches (`;`), SQL comments (`--`, `/* */`), and sleeping attacks (`pg_sleep`) |
| **Transaction Read-Only** | Every connection enforces `SET TRANSACTION READ ONLY` at the database session level |
| **Statement Timeout** | PostgreSQL query execution timeout enforced via `SET statement_timeout` |
| **Output Sanitization** | Automatic regex masking of sensitive data (SSNs, credit card numbers) |
| **Row Truncation** | Caps query outputs to 100 rows to prevent memory exhaustion |

---

## 📚 OKF Knowledge Files

The agent references **Organizational Knowledge Files (OKF)** formatted in YAML:

- **`knowledge/schema.yaml`**: Complete catalog of tables, column data types, foreign keys, and business descriptions.
- **`knowledge/metrics.yaml`**: Pre-defined financial KPIs and SQL templates (AUM, P&L, VWAP, Sharpe ratio, dividend yield, fill rate, etc.).
- **`knowledge/joins.yaml`**: Valid join paths between entities, including multi-hop relations (e.g. `trades -> orders -> clients`).
- **`knowledge/glossary.yaml`**: Financial terminology definitions for analyst reference.

---

## 🔧 Agent Tools

The LangGraph agent utilizes 6 specialized tools:

| Tool | Purpose |
|------|---------|
| `execute_sql_query` | Validates and executes read-only SQL queries and returns Markdown tables |
| `validate_sql` | Validates SQL against guardrail rules without database execution |
| `get_table_info` | Retrieves detailed column-level schema definitions for a specific table |
| `get_metric_definition` | Retrieves metric calculations and parameterized SQL templates |
| `list_available_tables` | Lists all tables in the database with short descriptions |
| `search_glossary` | Looks up financial definitions and trading concepts |

---

## ⚙️ Configuration Reference

All settings are managed via `.env` (loaded through Pydantic Settings):

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | *(required)* | Google AI Gemini API key |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` | Gemini model identifier |
| `POSTGRES_HOST` | `localhost` | PostgreSQL host address |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `trading_platform` | Database name |
| `POSTGRES_USER` | `copilot_user` | Database user |
| `POSTGRES_PASSWORD` | `copilot_pass_2024` | Database password |
| `MAX_QUERY_ROWS` | `100` | Maximum rows returned per SQL query |
| `QUERY_TIMEOUT_SECONDS` | `30` | SQL statement timeout |

---

## 🧰 Tech Stack

| Layer | Technology |
|-------|------------|
| **LLM** | Google Gemini 3.1 Flash Lite via `langchain-google-genai` |
| **Agent Framework** | LangGraph + LangChain Core |
| **Database** | PostgreSQL 16 |
| **ORM / Connection Engine** | SQLAlchemy 2.0 + psycopg 3 |
| **Knowledge System** | YAML (Organizational Knowledge Files) |
| **Chat Interface** | Chainlit 2.0+ |
| **Configuration** | Pydantic Settings 2.0+ |
| **SQL Safety & Parsing** | sqlparse |
| **Containerization** | Docker & Docker Compose |
| **Language** | Python 3.11+ |

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
