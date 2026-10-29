# 📊 Company Data Copilot

A **LangGraph-based AI agent** that answers natural-language questions over a PostgreSQL stock trading platform database using **Google Gemini**, **OKF knowledge files**, and a **Chainlit chat UI**.

Ask questions in plain English — the agent generates safe SQL, executes it against your database, and returns formatted, insightful answers.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-green?logo=langchain&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue?logo=postgresql&logoColor=white)
![Gemini](https://img.shields.io/badge/Google_Gemini-2.0_Flash-orange?logo=google&logoColor=white)
![Chainlit](https://img.shields.io/badge/Chainlit-1.3+-purple)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🤖 **Natural Language SQL** | Ask questions in English → get SQL-powered answers |
| 🛡️ **SQL Guardrails** | Read-only enforcement, blocked keywords, injection prevention, query timeout |
| 📚 **OKF Knowledge Files** | YAML-based schema definitions, metric templates, join paths, business glossary |
| 🔧 **Tool-Based Architecture** | LangGraph agent with 6 specialized tools for SQL execution, validation, and knowledge lookup |
| 💬 **Chainlit Chat UI** | Modern, dark-themed chat interface with conversation memory |
| 🐳 **Docker-Ready** | One-command PostgreSQL setup with seed data |
| 📊 **30 Real Stocks** | Pre-loaded data: AAPL, MSFT, GOOGL, TSLA, NVDA, JPM, RELIANCE, TCS, and more |
| 🔄 **Multi-Turn Memory** | Conversation context preserved across messages via LangGraph checkpointer |

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
│   ┌──────────┐                    ┌──────────────────┐  │
│   │  Gemini  │                    │  6 Agent Tools   │  │
│   │  2.0     │                    │  ─────────────   │  │
│   │  Flash   │                    │  execute_sql     │  │
│   └──────────┘                    │  validate_sql    │  │
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
├── app.py                      # Chainlit entry point
├── docker-compose.yml          # PostgreSQL container setup
├── pyproject.toml              # Modern Python packaging
├── requirements.txt            # Pip dependencies
├── .env.example                # Environment template
├── .gitignore
├── chainlit.md                 # Chat landing page
├── README.md
│
├── db/
│   └── init.sql                # Full schema + seed data (837 lines)
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
│   ├── knowledge_loader.py     # YAML loader + prompt formatter
│   ├── guardrails.py           # SQL safety validation
│   ├── prompts.py              # System & task prompts
│   ├── tools.py                # 6 LangGraph @tool definitions
│   └── agent.py                # LangGraph StateGraph agent
│
└── .chainlit/
    └── config.toml             # Chainlit UI configuration
```

---

## 🗄️ Database Schema

The stock trading platform database includes **15 tables** with realistic seed data:

| Table | Description | Seed Records |
|-------|-------------|:------------:|
| `exchanges` | NYSE, NASDAQ, BSE, NSE, LSE | 5 |
| `sectors` | Technology, Finance, Healthcare, etc. | 10 |
| `stocks` | AAPL, MSFT, GOOGL, TSLA, RELIANCE, TCS… | 30 |
| `stock_prices` | Daily OHLCV price data | ~100 |
| `brokers` | Licensed trading brokers | 5 |
| `clients` | Individual & institutional investors | 15 |
| `portfolios` | Named investment portfolios | 10 |
| `portfolio_holdings` | Stock positions in portfolios | ~30 |
| `orders` | Market, limit, stop-loss orders | ~80 |
| `trades` | Executed trade records | ~60 |
| `dividends` | Dividend payment history | 10 |
| `watchlists` | Client stock watchlists | 5 |
| `watchlist_items` | Stocks in watchlists | ~15 |
| `market_indices` | S&P 500, DJIA, NIFTY 50, SENSEX, FTSE 100 | 3–5 |
| `index_compositions` | Index constituent stocks | ~20 |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Docker & Docker Compose**
- **Google API Key** (for Gemini) — [Get one here](https://aistudio.google.com/apikey)

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
GOOGLE_API_KEY=your_actual_google_api_key
GEMINI_MODEL=gemini-3.5-flash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=trading_platform
POSTGRES_USER=copilot_user
POSTGRES_PASSWORD=copilot_pass_2024
MAX_QUERY_ROWS=100
QUERY_TIMEOUT_SECONDS=30
```

### 3. Start PostgreSQL

```bash
docker-compose up -d
```

Wait ~30 seconds for the database to initialize with seed data. Verify:

```bash
docker exec -it copilot_postgres psql -U copilot_user -d trading_platform -c "SELECT COUNT(*) FROM stocks;"
```

### 4. Install Python Dependencies

```bash
# Using pip
pip install -r requirements.txt

# Or using pyproject.toml (recommended)
pip install -e .

# Or with dev dependencies
pip install -e ".[dev]"
```

### 5. Launch the App

```bash
chainlit run app.py -w
```

Open **http://localhost:8000** in your browser. Start asking questions! 🎉

---

## 💬 Example Questions

| Category | Example Question |
|----------|-----------------|
| 📈 Stock Analysis | *"What are the top 5 stocks by trading volume?"* |
| 📈 Stock Analysis | *"Show AAPL's price history for the last 30 days"* |
| 📈 Stock Analysis | *"Which stocks have gained the most this month?"* |
| 💼 Portfolio | *"What's the total value of John Smith's portfolio?"* |
| 💼 Portfolio | *"Show me the sector allocation across all portfolios"* |
| 🔄 Trading | *"How many trades were executed today? What was the total volume?"* |
| 🔄 Trading | *"What's the total commission earned by each broker?"* |
| 🔄 Trading | *"Show me all pending orders"* |
| 👥 Clients | *"List the top 10 clients by account balance"* |
| 👥 Clients | *"How many institutional vs individual accounts do we have?"* |
| 📊 Market | *"Which sector has the highest total market cap?"* |
| 📊 Market | *"Show me all stocks with a dividend yield above 3%"* |
| 🔍 Glossary | *"What does VWAP mean?"* |

---

## 🛡️ Safety & Guardrails

The system enforces multiple layers of protection:

| Layer | Protection |
|-------|------------|
| **SQL Parsing** | Only `SELECT` statements allowed (via `sqlparse`) |
| **Keyword Blocking** | `DROP`, `DELETE`, `INSERT`, `UPDATE`, `ALTER`, `CREATE`, `TRUNCATE`, and 15+ more |
| **Pattern Detection** | Multi-statement injection, SQL comments, `pg_sleep`, system catalog access |
| **Read-Only Transactions** | `SET TRANSACTION READ ONLY` on every query |
| **Statement Timeout** | Configurable timeout (default: 30s) prevents runaway queries |
| **Row Limits** | Maximum 100 rows returned per query |
| **Query Length Limit** | Max 2000 characters per query |
| **Output Sanitization** | SSN and credit card patterns automatically redacted |

---

## 📚 OKF Knowledge Files

The agent uses **Organizational Knowledge Files** (YAML) to understand the database without needing to introspect it at runtime:

### `knowledge/schema.yaml`
Complete table and column definitions with types, nullability, primary keys, and business descriptions.

### `knowledge/metrics.yaml`
20+ pre-defined business metrics with SQL templates:
- Portfolio total value, return %, unrealized P&L
- Daily trading volume, commission earned, average trade size
- Stock daily return, volatility, VWAP
- Dividend yield, order fill rate, sector allocation
- And more…

### `knowledge/joins.yaml`
All valid join paths between tables, including multi-hop paths (e.g., `trades → stocks → sectors`).

### `knowledge/glossary.yaml`
Business term definitions: AUM, P&L, VWAP, Market Cap, IPO, Settlement, Fill Rate, Liquidity, Volatility, etc.

---

## 🔧 Agent Tools

The LangGraph agent has 6 tools at its disposal:

| Tool | Description |
|------|-------------|
| `execute_sql_query` | Validate and execute a read-only SQL query, return formatted results |
| `validate_sql` | Check a SQL query for safety without executing it |
| `get_table_info` | Look up detailed schema info for a specific table |
| `get_metric_definition` | Find metric definitions and SQL templates by name/keyword |
| `list_available_tables` | List all tables with descriptions |
| `search_glossary` | Look up financial/trading term definitions |

---

## ⚙️ Configuration

All configuration is via environment variables (`.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | *(required)* | Google AI API key for Gemini |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model to use |
| `POSTGRES_HOST` | `localhost` | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `trading_platform` | Database name |
| `POSTGRES_USER` | `copilot_user` | Database user |
| `POSTGRES_PASSWORD` | `copilot_pass_2024` | Database password |
| `MAX_QUERY_ROWS` | `100` | Max rows returned per query |
| `QUERY_TIMEOUT_SECONDS` | `30` | SQL statement timeout |

---

## 🧰 Tech Stack

| Layer | Technology |
|-------|-----------|
| **LLM** | Google Gemini 2.0 Flash |
| **Agent Framework** | LangGraph + LangChain |
| **Database** | PostgreSQL 16 |
| **ORM / DB Driver** | SQLAlchemy 2.0 + psycopg 3 |
| **Knowledge Format** | YAML (OKF) |
| **Chat UI** | Chainlit |
| **Config** | Pydantic Settings |
| **SQL Safety** | sqlparse + custom guardrails |
| **Containerization** | Docker Compose |
| **Language** | Python 3.11+ |

---

## 🧪 Development

### Run with auto-reload

```bash
chainlit run app.py -w
```

### Install dev dependencies

```bash
pip install -e ".[dev]"
```

### Lint & format

```bash
ruff check src/ app.py
ruff format src/ app.py
```

### Type checking

```bash
mypy src/
```

---

## 🗺️ Roadmap

- [ ] Streaming responses in Chainlit
- [ ] Query result visualization (charts via Plotly)
- [ ] Export results to CSV/Excel
- [ ] Multi-database support
- [ ] Authentication & role-based access
- [ ] Query history & bookmarking
- [ ] Async database driver (asyncpg)
- [ ] Rate limiting for API calls

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  Built with ❤️ using <strong>LangGraph</strong> · <strong>Google Gemini</strong> · <strong>PostgreSQL</strong> · <strong>Chainlit</strong>
</p>
