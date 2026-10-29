-- ============================================================================
-- Stock Trading Platform Database Schema
-- Comprehensive schema for a multi-exchange stock trading platform
-- ============================================================================

-- ============================================================================
-- ENUM TYPES
-- ============================================================================

CREATE TYPE account_type_enum AS ENUM ('individual', 'institutional', 'joint');
CREATE TYPE risk_tolerance_enum AS ENUM ('low', 'medium', 'high', 'aggressive');
CREATE TYPE order_type_enum AS ENUM ('market', 'limit', 'stop_loss', 'stop_limit');
CREATE TYPE order_side_enum AS ENUM ('buy', 'sell');
CREATE TYPE order_status_enum AS ENUM ('pending', 'filled', 'partially_filled', 'cancelled', 'rejected');

-- ============================================================================
-- TABLES
-- ============================================================================

-- Stock exchanges around the world
CREATE TABLE exchanges (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    code            VARCHAR(10) NOT NULL UNIQUE,
    country         VARCHAR(60) NOT NULL,
    timezone        VARCHAR(50) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE exchanges IS 'Stock exchanges (NYSE, NASDAQ, BSE, NSE, LSE, etc.)';

-- Industry sectors for stock classification
CREATE TABLE sectors (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE sectors IS 'Industry sectors used to classify listed stocks';

-- Listed stocks / equities
CREATE TABLE stocks (
    id              SERIAL PRIMARY KEY,
    ticker_symbol   VARCHAR(20) NOT NULL,
    company_name    VARCHAR(200) NOT NULL,
    sector_id       INT NOT NULL REFERENCES sectors(id),
    exchange_id     INT NOT NULL REFERENCES exchanges(id),
    market_cap      NUMERIC(20,2),
    ipo_date        DATE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE stocks IS 'Equities listed on exchanges';
CREATE UNIQUE INDEX idx_stocks_ticker_exchange ON stocks (ticker_symbol, exchange_id);
CREATE INDEX idx_stocks_sector ON stocks (sector_id);
CREATE INDEX idx_stocks_exchange ON stocks (exchange_id);

-- Daily OHLCV price data for stocks
CREATE TABLE stock_prices (
    id              BIGSERIAL PRIMARY KEY,
    stock_id        INT NOT NULL REFERENCES stocks(id),
    trade_date      DATE NOT NULL,
    open_price      NUMERIC(12,4) NOT NULL,
    high_price      NUMERIC(12,4) NOT NULL,
    low_price       NUMERIC(12,4) NOT NULL,
    close_price     NUMERIC(12,4) NOT NULL,
    adjusted_close  NUMERIC(12,4) NOT NULL,
    volume          BIGINT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (stock_id, trade_date)
);
COMMENT ON TABLE stock_prices IS 'Daily OHLCV price history for each stock';
CREATE INDEX idx_stock_prices_date ON stock_prices (trade_date);
CREATE INDEX idx_stock_prices_stock_date ON stock_prices (stock_id, trade_date DESC);

-- Registered brokers
CREATE TABLE brokers (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    license_number  VARCHAR(50) NOT NULL UNIQUE,
    email           VARCHAR(150) NOT NULL UNIQUE,
    phone           VARCHAR(30),
    commission_rate NUMERIC(5,4) NOT NULL DEFAULT 0.0010,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE brokers IS 'Registered brokerage firms and individual brokers';

-- Trading clients / investor accounts
CREATE TABLE clients (
    id              SERIAL PRIMARY KEY,
    first_name      VARCHAR(60) NOT NULL,
    last_name       VARCHAR(60) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    phone           VARCHAR(30),
    date_of_birth   DATE,
    account_type    account_type_enum NOT NULL DEFAULT 'individual',
    risk_tolerance  risk_tolerance_enum NOT NULL DEFAULT 'medium',
    broker_id       INT REFERENCES brokers(id),
    account_balance NUMERIC(16,2) NOT NULL DEFAULT 0.00,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE clients IS 'Trading clients / investor accounts';
CREATE INDEX idx_clients_broker ON clients (broker_id);

-- Investment portfolios owned by clients
CREATE TABLE portfolios (
    id              SERIAL PRIMARY KEY,
    client_id       INT NOT NULL REFERENCES clients(id),
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE portfolios IS 'Named investment portfolios belonging to clients';
CREATE INDEX idx_portfolios_client ON portfolios (client_id);

-- Individual stock holdings inside a portfolio
CREATE TABLE portfolio_holdings (
    id              SERIAL PRIMARY KEY,
    portfolio_id    INT NOT NULL REFERENCES portfolios(id),
    stock_id        INT NOT NULL REFERENCES stocks(id),
    quantity        INT NOT NULL CHECK (quantity > 0),
    average_buy_price NUMERIC(12,4) NOT NULL,
    current_value   NUMERIC(16,2) NOT NULL DEFAULT 0.00,
    last_updated    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (portfolio_id, stock_id)
);
COMMENT ON TABLE portfolio_holdings IS 'Per-stock holdings within a portfolio';
CREATE INDEX idx_portfolio_holdings_stock ON portfolio_holdings (stock_id);

-- Client orders (buy / sell)
CREATE TABLE orders (
    id              SERIAL PRIMARY KEY,
    client_id       INT NOT NULL REFERENCES clients(id),
    stock_id        INT NOT NULL REFERENCES stocks(id),
    order_type      order_type_enum NOT NULL DEFAULT 'market',
    side            order_side_enum NOT NULL,
    quantity        INT NOT NULL CHECK (quantity > 0),
    price           NUMERIC(12,4),
    status          order_status_enum NOT NULL DEFAULT 'pending',
    filled_quantity INT DEFAULT 0,
    filled_price    NUMERIC(12,4),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE orders IS 'Buy and sell orders placed by clients';
CREATE INDEX idx_orders_client ON orders (client_id);
CREATE INDEX idx_orders_stock ON orders (stock_id);
CREATE INDEX idx_orders_status ON orders (status);
CREATE INDEX idx_orders_created ON orders (created_at DESC);

-- Executed trades (fills)
CREATE TABLE trades (
    id              SERIAL PRIMARY KEY,
    order_id        INT NOT NULL REFERENCES orders(id),
    stock_id        INT NOT NULL REFERENCES stocks(id),
    client_id       INT NOT NULL REFERENCES clients(id),
    broker_id       INT NOT NULL REFERENCES brokers(id),
    side            order_side_enum NOT NULL,
    quantity        INT NOT NULL CHECK (quantity > 0),
    price           NUMERIC(12,4) NOT NULL,
    total_amount    NUMERIC(16,2) NOT NULL,
    commission      NUMERIC(12,4) NOT NULL DEFAULT 0.00,
    net_amount      NUMERIC(16,2) NOT NULL,
    trade_date      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    settlement_date DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE trades IS 'Executed trade records (order fills)';
CREATE INDEX idx_trades_order ON trades (order_id);
CREATE INDEX idx_trades_client ON trades (client_id);
CREATE INDEX idx_trades_stock ON trades (stock_id);
CREATE INDEX idx_trades_broker ON trades (broker_id);
CREATE INDEX idx_trades_date ON trades (trade_date DESC);

-- Dividend declarations for stocks
CREATE TABLE dividends (
    id                  SERIAL PRIMARY KEY,
    stock_id            INT NOT NULL REFERENCES stocks(id),
    declaration_date    DATE NOT NULL,
    ex_dividend_date    DATE NOT NULL,
    record_date         DATE NOT NULL,
    payment_date        DATE NOT NULL,
    dividend_per_share  NUMERIC(10,4) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE dividends IS 'Dividend declaration and payment records';
CREATE INDEX idx_dividends_stock ON dividends (stock_id);
CREATE INDEX idx_dividends_ex_date ON dividends (ex_dividend_date);

-- Client watchlists
CREATE TABLE watchlists (
    id              SERIAL PRIMARY KEY,
    client_id       INT NOT NULL REFERENCES clients(id),
    name            VARCHAR(100) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE watchlists IS 'Named watchlists maintained by clients';
CREATE INDEX idx_watchlists_client ON watchlists (client_id);

-- Stocks in a watchlist
CREATE TABLE watchlist_items (
    id              SERIAL PRIMARY KEY,
    watchlist_id    INT NOT NULL REFERENCES watchlists(id),
    stock_id        INT NOT NULL REFERENCES stocks(id),
    added_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (watchlist_id, stock_id)
);
COMMENT ON TABLE watchlist_items IS 'Individual stock items on a watchlist';

-- Major market indices
CREATE TABLE market_indices (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    code            VARCHAR(20) NOT NULL UNIQUE,
    exchange_id     INT NOT NULL REFERENCES exchanges(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE market_indices IS 'Market indices (S&P 500, DJIA, NIFTY 50, etc.)';

-- Stocks that compose an index
CREATE TABLE index_compositions (
    id                  SERIAL PRIMARY KEY,
    index_id            INT NOT NULL REFERENCES market_indices(id),
    stock_id            INT NOT NULL REFERENCES stocks(id),
    weight_percentage   NUMERIC(6,3) NOT NULL,
    added_date          DATE NOT NULL DEFAULT CURRENT_DATE,
    removed_date        DATE
);
COMMENT ON TABLE index_compositions IS 'Constituent stocks and weights for each market index';
CREATE INDEX idx_index_comp_index ON index_compositions (index_id);
CREATE INDEX idx_index_comp_stock ON index_compositions (stock_id);

-- ============================================================================
-- SEED DATA
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Exchanges
-- ---------------------------------------------------------------------------
INSERT INTO exchanges (id, name, code, country, timezone) VALUES
(1, 'New York Stock Exchange',  'NYSE',   'United States', 'America/New_York'),
(2, 'NASDAQ Stock Market',      'NASDAQ', 'United States', 'America/New_York'),
(3, 'Bombay Stock Exchange',    'BSE',    'India',         'Asia/Kolkata'),
(4, 'National Stock Exchange',  'NSE',    'India',         'Asia/Kolkata'),
(5, 'London Stock Exchange',    'LSE',    'United Kingdom','Europe/London');

-- ---------------------------------------------------------------------------
-- Sectors
-- ---------------------------------------------------------------------------
INSERT INTO sectors (id, name, description) VALUES
(1,  'Technology',          'Information technology, software, hardware, and semiconductors'),
(2,  'Healthcare',          'Pharmaceuticals, biotechnology, medical devices, and healthcare services'),
(3,  'Finance',             'Banking, insurance, asset management, and financial services'),
(4,  'Energy',              'Oil & gas, renewable energy, and energy infrastructure'),
(5,  'Consumer Goods',      'Consumer staples and discretionary products'),
(6,  'Industrials',         'Aerospace, defense, machinery, and industrial conglomerates'),
(7,  'Utilities',           'Electric, gas, water utilities, and renewable power generation'),
(8,  'Real Estate',         'REITs, property developers, and real estate services'),
(9,  'Telecommunications',  'Wireless, broadband, and communication services'),
(10, 'Materials',           'Chemicals, metals, mining, and construction materials');

-- ---------------------------------------------------------------------------
-- Stocks (30 real tickers)
-- ---------------------------------------------------------------------------
INSERT INTO stocks (id, ticker_symbol, company_name, sector_id, exchange_id, market_cap, ipo_date) VALUES
-- US / NYSE
( 1, 'AAPL',       'Apple Inc.',                             1, 1, 2950000000000.00, '1980-12-12'),
( 2, 'MSFT',       'Microsoft Corporation',                  1, 1, 2800000000000.00, '1986-03-13'),
( 3, 'JPM',        'JPMorgan Chase & Co.',                   3, 1,  540000000000.00, '1969-03-05'),
( 4, 'GS',         'Goldman Sachs Group Inc.',               3, 1,  150000000000.00, '1999-05-04'),
( 5, 'BAC',        'Bank of America Corporation',            3, 1,  310000000000.00, '1972-01-03'),
( 6, 'JNJ',        'Johnson & Johnson',                      2, 1,  420000000000.00, '1944-09-25'),
( 7, 'PFE',        'Pfizer Inc.',                            2, 1,  160000000000.00, '1942-06-01'),
( 8, 'XOM',        'Exxon Mobil Corporation',                4, 1,  460000000000.00, '1970-01-02'),
( 9, 'CVX',        'Chevron Corporation',                    4, 1,  300000000000.00, '1970-01-02'),
(10, 'WMT',        'Walmart Inc.',                           5, 1,  550000000000.00, '1970-10-01'),
(11, 'KO',         'The Coca-Cola Company',                  5, 1,  270000000000.00, '1919-09-05'),
(12, 'PG',         'Procter & Gamble Co.',                   5, 1,  380000000000.00, '1890-01-01'),
(13, 'DIS',        'The Walt Disney Company',                5, 1,  170000000000.00, '1957-11-12'),
(14, 'V',          'Visa Inc.',                              3, 1,  530000000000.00, '2008-03-19'),
(15, 'MA',         'Mastercard Incorporated',                3, 1,  420000000000.00, '2006-05-25'),
-- US / NASDAQ
(16, 'GOOGL',      'Alphabet Inc.',                          1, 2, 1750000000000.00, '2004-08-19'),
(17, 'AMZN',       'Amazon.com Inc.',                        1, 2, 1850000000000.00, '1997-05-15'),
(18, 'TSLA',       'Tesla Inc.',                             6, 2,  780000000000.00, '2010-06-29'),
(19, 'NVDA',       'NVIDIA Corporation',                     1, 2, 3100000000000.00, '1999-01-22'),
(20, 'META',       'Meta Platforms Inc.',                     1, 2, 1250000000000.00, '2012-05-18'),
(21, 'NFLX',       'Netflix Inc.',                           1, 2,  270000000000.00, '2002-05-23'),
(22, 'INTC',       'Intel Corporation',                      1, 2,  120000000000.00, '1971-10-13'),
(23, 'AMD',        'Advanced Micro Devices Inc.',            1, 2,  230000000000.00, '1972-09-27'),
(24, 'CRM',        'Salesforce Inc.',                        1, 2,  280000000000.00, '2004-06-23'),
(25, 'ORCL',       'Oracle Corporation',                     1, 2,  330000000000.00, '1986-03-12'),
-- India / BSE & NSE
(26, 'RELIANCE',   'Reliance Industries Limited',            4, 3, 19000000000000.00,'1977-01-01'),
(27, 'TCS',        'Tata Consultancy Services Limited',      1, 3, 15000000000000.00,'2004-08-25'),
(28, 'INFY',       'Infosys Limited',                        1, 4,  7500000000000.00,'1993-02-01'),
(29, 'HDFCBANK',   'HDFC Bank Limited',                      3, 4, 12000000000000.00,'1995-01-01'),
(30, 'TATAMOTORS', 'Tata Motors Limited',                    6, 4,  3200000000000.00,'1998-01-01');

-- Reset sequence after explicit IDs
SELECT setval('exchanges_id_seq', (SELECT MAX(id) FROM exchanges));
SELECT setval('sectors_id_seq', (SELECT MAX(id) FROM sectors));
SELECT setval('stocks_id_seq', (SELECT MAX(id) FROM stocks));

-- ---------------------------------------------------------------------------
-- Brokers
-- ---------------------------------------------------------------------------
INSERT INTO brokers (id, name, license_number, email, phone, commission_rate) VALUES
(1, 'Alpha Securities',     'BRK-2024-00101', 'contact@alphasec.com',     '+1-212-555-1001', 0.0012),
(2, 'Prime Brokerage Inc.', 'BRK-2024-00202', 'info@primebrokerage.com',  '+1-212-555-1002', 0.0010),
(3, 'Global Trade Partners', 'BRK-2024-00303','support@globaltp.com',     '+1-312-555-1003', 0.0015),
(4, 'Eastern Capital',      'BRK-2024-00404', 'hello@easterncapital.in',  '+91-22-5555-2001', 0.0008),
(5, 'Vertex Investments',   'BRK-2024-00505', 'desk@vertexinvest.co.uk',  '+44-20-5555-3001', 0.0011);

SELECT setval('brokers_id_seq', (SELECT MAX(id) FROM brokers));

-- ---------------------------------------------------------------------------
-- Clients (15)
-- ---------------------------------------------------------------------------
INSERT INTO clients (id, first_name, last_name, email, phone, date_of_birth, account_type, risk_tolerance, broker_id, account_balance) VALUES
( 1, 'James',    'Mitchell',   'james.mitchell@example.com',    '+1-646-555-0101', '1985-03-14', 'individual',    'high',       1,   250000.00),
( 2, 'Sophia',   'Chen',       'sophia.chen@example.com',       '+1-415-555-0102', '1990-07-22', 'individual',    'aggressive', 2,   480000.00),
( 3, 'Robert',   'Williams',   'robert.williams@example.com',   '+1-312-555-0103', '1978-11-30', 'individual',    'medium',     1,   175000.00),
( 4, 'Emily',    'Johnson',    'emily.johnson@example.com',     '+1-213-555-0104', '1992-05-08', 'individual',    'high',       3,   320000.00),
( 5, 'David',    'Brown',      'david.brown@example.com',       '+1-617-555-0105', '1968-01-19', 'individual',    'low',        2,    95000.00),
( 6, 'Priya',    'Sharma',     'priya.sharma@example.com',      '+91-98-5555-0106','1988-09-12', 'individual',    'medium',     4,   1500000.00),
( 7, 'Arjun',    'Patel',      'arjun.patel@example.com',       '+91-99-5555-0107','1995-04-25', 'individual',    'aggressive', 4,   2200000.00),
( 8, 'Oliver',   'Smith',      'oliver.smith@example.com',      '+44-77-5555-0108','1982-12-03', 'individual',    'medium',     5,   185000.00),
( 9, 'Isabella', 'Garcia',     'isabella.garcia@example.com',   '+1-305-555-0109', '1975-06-17', 'individual',    'low',        3,   120000.00),
(10, 'Liam',     'Anderson',   'liam.anderson@example.com',     '+1-206-555-0110', '1998-02-28', 'individual',    'high',       1,   410000.00),
(11, 'Pinnacle Fund LP',  'Institutional',  'ops@pinnaclefund.com',   '+1-212-555-0111', NULL,         'institutional', 'aggressive', 2, 15000000.00),
(12, 'Meridian Capital',  'Institutional',  'trading@meridiancap.com','+1-312-555-0112', NULL,         'institutional', 'high',       3,  8500000.00),
(13, 'Alice',    'Thompson',   'alice.thompson@example.com',    '+1-503-555-0113', '1989-10-05', 'joint',         'medium',     1,   290000.00),
(14, 'Chen',     'Wei',        'chen.wei@example.com',          '+1-408-555-0114', '1993-08-11', 'individual',    'high',       2,   375000.00),
(15, 'Sarah',    'O''Brien',   'sarah.obrien@example.com',      '+44-78-5555-0115','1980-03-30', 'individual',    'medium',     5,   210000.00);

SELECT setval('clients_id_seq', (SELECT MAX(id) FROM clients));

-- ---------------------------------------------------------------------------
-- Portfolios (10)
-- ---------------------------------------------------------------------------
INSERT INTO portfolios (id, client_id, name, description) VALUES
( 1,  1, 'Tech Growth',           'High-growth technology stocks'),
( 2,  2, 'Aggressive Alpha',      'High-risk, high-reward concentrated positions'),
( 3,  3, 'Balanced Core',         'Diversified mix of sectors'),
( 4,  4, 'Blue Chip Select',      'Large-cap established companies'),
( 5,  5, 'Dividend Income',       'Income-focused dividend-paying stocks'),
( 6,  6, 'India Focus',           'Indian equity exposure'),
( 7,  7, 'India Growth',          'Growth-oriented Indian and global tech stocks'),
( 8, 10, 'FAANG Plus',            'Big tech mega-cap portfolio'),
( 9, 11, 'Pinnacle Core Equity',  'Institutional diversified equity allocation'),
(10, 13, 'Joint Retirement',      'Long-term retirement portfolio');

SELECT setval('portfolios_id_seq', (SELECT MAX(id) FROM portfolios));

-- ---------------------------------------------------------------------------
-- Portfolio Holdings
-- ---------------------------------------------------------------------------
INSERT INTO portfolio_holdings (portfolio_id, stock_id, quantity, average_buy_price, current_value) VALUES
-- Portfolio 1: Tech Growth
(1,  1,  150, 172.5000,  33150.00),
(1,  2,  100, 380.2000,  42400.00),
(1, 19,  50,  450.0000,  62500.00),
(1, 24,  80,  260.0000,  22400.00),
-- Portfolio 2: Aggressive Alpha
(2, 19,  200, 310.0000, 250000.00),
(2, 18,  100, 210.0000,  24800.00),
(2, 23,  300, 110.0000,  46500.00),
-- Portfolio 3: Balanced Core
(3,  1,   50, 165.0000,  11050.00),
(3,  6,   40, 160.0000,   6480.00),
(3, 10,   60, 155.0000,  10200.00),
(3, 11,   80, 58.0000,    4960.00),
-- Portfolio 4: Blue Chip Select
(4,  3,   70, 175.0000,  14350.00),
(4, 14,   45, 265.0000,  12825.00),
(4, 15,   35, 410.0000,  15925.00),
(4, 12,   50, 155.0000,   8250.00),
-- Portfolio 5: Dividend Income
(5,  8,   80, 105.0000,   9200.00),
(5, 11,  120,  55.0000,   7440.00),
(5, 12,   60, 148.0000,   9900.00),
(5,  6,   45, 162.0000,   7335.00),
-- Portfolio 6: India Focus
(6, 26,  100, 2500.0000, 268000.00),
(6, 29,  200, 1650.0000, 340000.00),
(6, 30,  500,  600.0000, 355000.00),
-- Portfolio 7: India Growth
(7, 27,  150, 3400.0000, 540000.00),
(7, 28,  300, 1500.0000, 480000.00),
(7, 19,   30,  550.0000,  37500.00),
-- Portfolio 8: FAANG Plus
(8,  1,  200, 178.0000,  44200.00),
(8, 16,  120, 140.0000,  18960.00),
(8, 17,  100, 175.0000,  19200.00),
(8, 20,   80, 320.0000,  39200.00),
(8, 21,   60, 450.0000,  37200.00),
-- Portfolio 9: Pinnacle Core Equity
(9,  1,  500, 170.0000, 110500.00),
(9,  2,  400, 370.0000, 169600.00),
(9,  3,  200, 178.0000,  41000.00),
(9, 14,  300, 270.0000,  85500.00),
(9,  8,  250, 108.0000,  28750.00),
-- Portfolio 10: Joint Retirement
(10,  6,  100, 158.0000,  16200.00),
(10, 10,   80, 150.0000,  13600.00),
(10, 14,   50, 272.0000,  14250.00),
(10, 11,  150,  56.0000,   9300.00);

-- ---------------------------------------------------------------------------
-- Stock Prices (~100 rows – last ~5 trading days for 20 stocks)
-- ---------------------------------------------------------------------------
INSERT INTO stock_prices (stock_id, trade_date, open_price, high_price, low_price, close_price, adjusted_close, volume) VALUES
-- AAPL (id=1)
( 1, '2024-10-21', 220.0000, 222.3000, 218.5000, 221.1000, 221.1000, 58200000),
( 1, '2024-10-22', 221.3000, 223.7000, 220.1000, 222.6000, 222.6000, 53100000),
( 1, '2024-10-23', 222.0000, 224.1000, 221.0000, 223.4000, 223.4000, 49800000),
( 1, '2024-10-24', 223.5000, 225.8000, 222.8000, 225.0000, 225.0000, 61300000),
( 1, '2024-10-25', 224.8000, 226.5000, 223.6000, 225.9000, 225.9000, 55700000),
-- MSFT (id=2)
( 2, '2024-10-21', 420.0000, 423.5000, 418.2000, 421.8000, 421.8000, 22300000),
( 2, '2024-10-22', 422.0000, 425.1000, 420.5000, 424.3000, 424.3000, 20800000),
( 2, '2024-10-23', 424.5000, 427.0000, 423.1000, 426.2000, 426.2000, 19500000),
( 2, '2024-10-24', 426.0000, 429.5000, 425.3000, 428.7000, 428.7000, 23100000),
( 2, '2024-10-25', 428.5000, 430.2000, 427.0000, 429.5000, 429.5000, 21600000),
-- GOOGL (id=16)
(16, '2024-10-21', 158.0000, 160.2000, 157.1000, 159.5000, 159.5000, 25600000),
(16, '2024-10-22', 159.8000, 161.5000, 158.5000, 160.8000, 160.8000, 23400000),
(16, '2024-10-23', 160.5000, 163.0000, 160.0000, 162.2000, 162.2000, 27100000),
(16, '2024-10-24', 162.5000, 164.1000, 161.3000, 163.5000, 163.5000, 24800000),
(16, '2024-10-25', 163.0000, 165.0000, 162.5000, 164.3000, 164.3000, 22900000),
-- AMZN (id=17)
(17, '2024-10-21', 188.0000, 190.5000, 187.0000, 189.8000, 189.8000, 45200000),
(17, '2024-10-22', 190.0000, 192.3000, 189.1000, 191.5000, 191.5000, 41800000),
(17, '2024-10-23', 191.2000, 193.5000, 190.5000, 192.8000, 192.8000, 43600000),
(17, '2024-10-24', 193.0000, 195.0000, 192.0000, 194.2000, 194.2000, 47100000),
(17, '2024-10-25', 194.5000, 196.2000, 193.8000, 195.5000, 195.5000, 44300000),
-- TSLA (id=18)
(18, '2024-10-21', 245.0000, 250.5000, 242.0000, 248.3000, 248.3000, 98200000),
(18, '2024-10-22', 248.0000, 253.2000, 246.5000, 251.0000, 251.0000, 95700000),
(18, '2024-10-23', 251.5000, 255.0000, 249.8000, 253.5000, 253.5000, 88400000),
(18, '2024-10-24', 253.0000, 258.0000, 252.0000, 256.8000, 256.8000, 102300000),
(18, '2024-10-25', 257.0000, 260.5000, 255.5000, 259.2000, 259.2000, 97500000),
-- NVDA (id=19)
(19, '2024-10-21', 1220.0000, 1245.0000, 1210.0000, 1238.0000, 1238.0000, 35600000),
(19, '2024-10-22', 1240.0000, 1260.0000, 1230.0000, 1255.0000, 1255.0000, 38200000),
(19, '2024-10-23', 1255.0000, 1275.0000, 1248.0000, 1270.0000, 1270.0000, 36900000),
(19, '2024-10-24', 1270.0000, 1290.0000, 1265.0000, 1285.0000, 1285.0000, 40100000),
(19, '2024-10-25', 1285.0000, 1300.0000, 1278.0000, 1295.0000, 1295.0000, 37800000),
-- META (id=20)
(20, '2024-10-21', 580.0000, 588.0000, 576.0000, 585.0000, 585.0000, 16800000),
(20, '2024-10-22', 586.0000, 592.0000, 583.0000, 590.0000, 590.0000, 15900000),
(20, '2024-10-23', 590.5000, 596.0000, 588.0000, 594.0000, 594.0000, 17200000),
(20, '2024-10-24', 594.0000, 600.0000, 592.0000, 598.0000, 598.0000, 18100000),
(20, '2024-10-25', 598.0000, 603.0000, 595.0000, 601.0000, 601.0000, 16500000),
-- JPM (id=3)
( 3, '2024-10-21', 205.0000, 207.5000, 203.8000, 206.5000, 206.5000, 8900000),
( 3, '2024-10-22', 206.8000, 208.5000, 205.5000, 207.8000, 207.8000, 8200000),
( 3, '2024-10-23', 208.0000, 210.0000, 207.0000, 209.2000, 209.2000, 9100000),
( 3, '2024-10-24', 209.5000, 211.5000, 208.5000, 210.8000, 210.8000, 9500000),
( 3, '2024-10-25', 211.0000, 212.5000, 210.0000, 211.5000, 211.5000, 8700000),
-- XOM (id=8)
( 8, '2024-10-21', 115.0000, 117.0000, 114.2000, 116.2000, 116.2000, 14200000),
( 8, '2024-10-22', 116.5000, 118.0000, 115.5000, 117.0000, 117.0000, 13800000),
( 8, '2024-10-23', 117.2000, 119.0000, 116.5000, 118.2000, 118.2000, 15100000),
( 8, '2024-10-24', 118.0000, 120.0000, 117.5000, 119.5000, 119.5000, 14600000),
( 8, '2024-10-25', 119.5000, 121.0000, 118.8000, 120.2000, 120.2000, 13900000),
-- WMT (id=10)
(10, '2024-10-21', 168.0000, 170.5000, 167.2000, 169.5000, 169.5000, 7800000),
(10, '2024-10-22', 170.0000, 171.8000, 169.0000, 170.8000, 170.8000, 7200000),
(10, '2024-10-23', 171.0000, 173.0000, 170.2000, 172.2000, 172.2000, 8100000),
(10, '2024-10-24', 172.0000, 174.0000, 171.5000, 173.5000, 173.5000, 7600000),
(10, '2024-10-25', 173.5000, 175.0000, 172.8000, 174.2000, 174.2000, 7400000),
-- KO (id=11)
(11, '2024-10-21', 61.5000, 62.3000, 61.0000, 62.0000, 62.0000, 11200000),
(11, '2024-10-22', 62.2000, 63.0000, 61.8000, 62.7000, 62.7000, 10800000),
(11, '2024-10-23', 62.5000, 63.5000, 62.0000, 63.2000, 63.2000, 11500000),
(11, '2024-10-24', 63.0000, 64.0000, 62.5000, 63.8000, 63.8000, 10900000),
(11, '2024-10-25', 63.5000, 64.2000, 63.0000, 63.9000, 63.9000, 10500000),
-- V (id=14)
(14, '2024-10-21', 280.0000, 283.0000, 278.5000, 281.5000, 281.5000, 6800000),
(14, '2024-10-22', 282.0000, 284.5000, 280.5000, 283.0000, 283.0000, 6500000),
(14, '2024-10-23', 283.5000, 286.0000, 282.5000, 285.0000, 285.0000, 7100000),
(14, '2024-10-24', 285.0000, 287.5000, 284.0000, 286.8000, 286.8000, 6900000),
(14, '2024-10-25', 286.5000, 288.5000, 285.5000, 287.5000, 287.5000, 6600000),
-- NFLX (id=21)
(21, '2024-10-21', 690.0000, 698.0000, 685.0000, 695.0000, 695.0000, 5200000),
(21, '2024-10-22', 696.0000, 705.0000, 693.0000, 702.0000, 702.0000, 5800000),
(21, '2024-10-23', 703.0000, 710.0000, 700.0000, 708.0000, 708.0000, 5500000),
(21, '2024-10-24', 708.0000, 715.0000, 705.0000, 712.0000, 712.0000, 6100000),
(21, '2024-10-25', 712.0000, 718.0000, 710.0000, 716.0000, 716.0000, 5400000),
-- AMD (id=23)
(23, '2024-10-21', 155.0000, 158.0000, 153.5000, 156.5000, 156.5000, 42100000),
(23, '2024-10-22', 157.0000, 160.0000, 155.5000, 158.8000, 158.8000, 39800000),
(23, '2024-10-23', 159.0000, 162.0000, 157.5000, 161.0000, 161.0000, 44200000),
(23, '2024-10-24', 161.0000, 164.0000, 160.0000, 163.2000, 163.2000, 41500000),
(23, '2024-10-25', 163.5000, 165.5000, 162.0000, 164.5000, 164.5000, 40100000),
-- RELIANCE (id=26)
(26, '2024-10-21', 2650.0000, 2685.0000, 2640.0000, 2678.0000, 2678.0000, 8500000),
(26, '2024-10-22', 2680.0000, 2710.0000, 2670.0000, 2700.0000, 2700.0000, 9200000),
(26, '2024-10-23', 2705.0000, 2730.0000, 2695.0000, 2722.0000, 2722.0000, 8800000),
(26, '2024-10-24', 2720.0000, 2745.0000, 2715.0000, 2740.0000, 2740.0000, 9100000),
(26, '2024-10-25', 2742.0000, 2760.0000, 2730.0000, 2755.0000, 2755.0000, 8600000),
-- TCS (id=27)
(27, '2024-10-21', 3550.0000, 3580.0000, 3530.0000, 3570.0000, 3570.0000, 3200000),
(27, '2024-10-22', 3575.0000, 3600.0000, 3560.0000, 3590.0000, 3590.0000, 3100000),
(27, '2024-10-23', 3595.0000, 3620.0000, 3580.0000, 3610.0000, 3610.0000, 3400000),
(27, '2024-10-24', 3615.0000, 3640.0000, 3605.0000, 3635.0000, 3635.0000, 3300000),
(27, '2024-10-25', 3640.0000, 3660.0000, 3625.0000, 3650.0000, 3650.0000, 3000000),
-- INFY (id=28)
(28, '2024-10-21', 1580.0000, 1600.0000, 1570.0000, 1595.0000, 1595.0000, 5800000),
(28, '2024-10-22', 1598.0000, 1615.0000, 1590.0000, 1610.0000, 1610.0000, 5500000),
(28, '2024-10-23', 1612.0000, 1630.0000, 1605.0000, 1625.0000, 1625.0000, 6100000),
(28, '2024-10-24', 1628.0000, 1645.0000, 1620.0000, 1640.0000, 1640.0000, 5900000),
(28, '2024-10-25', 1642.0000, 1655.0000, 1635.0000, 1650.0000, 1650.0000, 5600000),
-- HDFCBANK (id=29)
(29, '2024-10-21', 1700.0000, 1720.0000, 1690.0000, 1715.0000, 1715.0000, 7200000),
(29, '2024-10-22', 1718.0000, 1735.0000, 1710.0000, 1730.0000, 1730.0000, 6800000),
(29, '2024-10-23', 1732.0000, 1750.0000, 1725.0000, 1745.0000, 1745.0000, 7500000),
(29, '2024-10-24', 1748.0000, 1762.0000, 1740.0000, 1758.0000, 1758.0000, 7100000),
(29, '2024-10-25', 1760.0000, 1775.0000, 1752.0000, 1770.0000, 1770.0000, 6900000),
-- PG (id=12)
(12, '2024-10-21', 163.0000, 165.5000, 162.0000, 164.5000, 164.5000, 6200000),
(12, '2024-10-22', 165.0000, 166.8000, 164.0000, 166.0000, 166.0000, 5900000),
(12, '2024-10-23', 166.2000, 168.0000, 165.5000, 167.5000, 167.5000, 6400000),
(12, '2024-10-24', 167.5000, 169.5000, 167.0000, 169.0000, 169.0000, 6100000),
(12, '2024-10-25', 169.0000, 170.5000, 168.5000, 170.0000, 170.0000, 5800000);

-- ---------------------------------------------------------------------------
-- Orders (80)
-- ---------------------------------------------------------------------------
INSERT INTO orders (id, client_id, stock_id, order_type, side, quantity, price, status, filled_quantity, filled_price, created_at) VALUES
-- Client 1
( 1,  1,  1, 'market', 'buy',  150, NULL,      'filled',            150, 172.5000, '2024-06-10 09:30:00-04'),
( 2,  1,  2, 'market', 'buy',  100, NULL,      'filled',            100, 380.2000, '2024-06-12 10:15:00-04'),
( 3,  1, 19, 'limit',  'buy',   50, 450.0000,  'filled',             50, 450.0000, '2024-07-01 11:00:00-04'),
( 4,  1, 24, 'market', 'buy',   80, NULL,      'filled',             80, 260.0000, '2024-07-15 09:45:00-04'),
( 5,  1,  1, 'limit',  'sell',  30, 225.0000,  'pending',             0, NULL,     '2024-10-25 14:00:00-04'),
-- Client 2
( 6,  2, 19, 'market', 'buy',  200, NULL,      'filled',            200, 310.0000, '2024-04-05 10:00:00-04'),
( 7,  2, 18, 'market', 'buy',  100, NULL,      'filled',            100, 210.0000, '2024-05-20 11:30:00-04'),
( 8,  2, 23, 'limit',  'buy',  300, 115.0000,  'filled',            300, 110.0000, '2024-06-01 09:30:00-04'),
( 9,  2, 19, 'stop_loss','sell', 50, 1200.0000, 'pending',             0, NULL,     '2024-10-24 15:30:00-04'),
(10,  2, 18, 'limit',  'sell',  50, 270.0000,  'pending',             0, NULL,     '2024-10-25 10:00:00-04'),
-- Client 3
(11,  3,  1, 'market', 'buy',   50, NULL,      'filled',             50, 165.0000, '2024-05-15 09:35:00-04'),
(12,  3,  6, 'market', 'buy',   40, NULL,      'filled',             40, 160.0000, '2024-05-20 10:00:00-04'),
(13,  3, 10, 'market', 'buy',   60, NULL,      'filled',             60, 155.0000, '2024-06-10 11:15:00-04'),
(14,  3, 11, 'limit',  'buy',   80, 58.0000,   'filled',             80,  58.0000, '2024-06-15 09:30:00-04'),
(15,  3, 11, 'limit',  'sell',  20, 64.0000,   'pending',             0, NULL,     '2024-10-25 13:45:00-04'),
-- Client 4
(16,  4,  3, 'market', 'buy',   70, NULL,      'filled',             70, 175.0000, '2024-05-01 10:30:00-04'),
(17,  4, 14, 'market', 'buy',   45, NULL,      'filled',             45, 265.0000, '2024-05-10 09:30:00-04'),
(18,  4, 15, 'limit',  'buy',   35, 415.0000,  'filled',             35, 410.0000, '2024-06-20 11:00:00-04'),
(19,  4, 12, 'market', 'buy',   50, NULL,      'filled',             50, 155.0000, '2024-07-05 10:45:00-04'),
(20,  4,  3, 'limit',  'sell',  20, 212.0000,  'pending',             0, NULL,     '2024-10-25 14:30:00-04'),
-- Client 5
(21,  5,  8, 'market', 'buy',   80, NULL,      'filled',             80, 105.0000, '2024-04-15 09:30:00-04'),
(22,  5, 11, 'market', 'buy',  120, NULL,      'filled',            120,  55.0000, '2024-04-20 10:00:00-04'),
(23,  5, 12, 'market', 'buy',   60, NULL,      'filled',             60, 148.0000, '2024-05-05 11:30:00-04'),
(24,  5,  6, 'market', 'buy',   45, NULL,      'filled',             45, 162.0000, '2024-05-12 09:45:00-04'),
(25,  5,  8, 'limit',  'sell',  20, 122.0000,  'pending',             0, NULL,     '2024-10-25 11:00:00-04'),
-- Client 6
(26,  6, 26, 'market', 'buy',  100, NULL,      'filled',            100, 2500.0000,'2024-05-01 09:30:00+05:30'),
(27,  6, 29, 'market', 'buy',  200, NULL,      'filled',            200, 1650.0000,'2024-05-15 10:00:00+05:30'),
(28,  6, 30, 'limit',  'buy',  500, 620.0000,  'filled',            500,  600.0000,'2024-06-01 11:00:00+05:30'),
(29,  6, 26, 'limit',  'sell',  25, 2800.0000, 'pending',             0, NULL,     '2024-10-25 14:00:00+05:30'),
(30,  6, 30, 'stop_loss','sell',100, 550.0000,  'pending',             0, NULL,     '2024-10-25 14:30:00+05:30'),
-- Client 7
(31,  7, 27, 'market', 'buy',  150, NULL,      'filled',            150, 3400.0000,'2024-04-10 09:30:00+05:30'),
(32,  7, 28, 'market', 'buy',  300, NULL,      'filled',            300, 1500.0000,'2024-04-20 10:15:00+05:30'),
(33,  7, 19, 'market', 'buy',   30, NULL,      'filled',             30,  550.0000,'2024-05-05 10:00:00-04'),
(34,  7, 27, 'limit',  'sell',  50, 3700.0000, 'pending',             0, NULL,     '2024-10-24 15:00:00+05:30'),
(35,  7, 28, 'limit',  'sell', 100, 1680.0000, 'cancelled',           0, NULL,     '2024-10-20 11:00:00+05:30'),
-- Client 8
(36,  8,  2, 'market', 'buy',   40, NULL,      'filled',             40, 375.0000, '2024-06-05 08:30:00+00'),
(37,  8, 14, 'market', 'buy',   30, NULL,      'filled',             30, 270.0000, '2024-06-15 09:00:00+00'),
(38,  8, 12, 'limit',  'buy',   25, 160.0000,  'filled',             25, 158.0000, '2024-07-01 10:30:00+00'),
(39,  8,  2, 'limit',  'sell',  10, 432.0000,  'pending',             0, NULL,     '2024-10-25 09:00:00+00'),
(40,  8, 16, 'market', 'buy',   50, NULL,      'filled',             50, 152.0000, '2024-08-10 10:00:00+00'),
-- Client 9
(41,  9, 10, 'market', 'buy',   30, NULL,      'filled',             30, 160.0000, '2024-06-01 10:00:00-04'),
(42,  9, 11, 'market', 'buy',   50, NULL,      'filled',             50,  59.0000, '2024-06-05 09:30:00-04'),
(43,  9,  6, 'market', 'buy',   20, NULL,      'filled',             20, 165.0000, '2024-07-10 11:00:00-04'),
(44,  9, 10, 'limit',  'sell',  10, 175.0000,  'pending',             0, NULL,     '2024-10-25 13:00:00-04'),
(45,  9,  8, 'market', 'buy',   25, NULL,      'filled',             25, 112.0000, '2024-08-01 10:30:00-04'),
-- Client 10
(46, 10,  1, 'market', 'buy',  200, NULL,      'filled',            200, 178.0000, '2024-04-01 09:30:00-04'),
(47, 10, 16, 'market', 'buy',  120, NULL,      'filled',            120, 140.0000, '2024-04-15 10:00:00-04'),
(48, 10, 17, 'market', 'buy',  100, NULL,      'filled',            100, 175.0000, '2024-05-01 11:00:00-04'),
(49, 10, 20, 'market', 'buy',   80, NULL,      'filled',             80, 320.0000, '2024-05-20 09:45:00-04'),
(50, 10, 21, 'market', 'buy',   60, NULL,      'filled',             60, 450.0000, '2024-06-01 10:30:00-04'),
-- Client 11 (Institutional)
(51, 11,  1, 'market', 'buy',  500, NULL,      'filled',            500, 170.0000, '2024-03-15 09:30:00-04'),
(52, 11,  2, 'market', 'buy',  400, NULL,      'filled',            400, 370.0000, '2024-03-20 10:00:00-04'),
(53, 11,  3, 'market', 'buy',  200, NULL,      'filled',            200, 178.0000, '2024-04-01 11:00:00-04'),
(54, 11, 14, 'market', 'buy',  300, NULL,      'filled',            300, 270.0000, '2024-04-10 09:30:00-04'),
(55, 11,  8, 'market', 'buy',  250, NULL,      'filled',            250, 108.0000, '2024-04-20 10:30:00-04'),
(56, 11,  1, 'limit',  'sell', 100, 228.0000,  'pending',             0, NULL,     '2024-10-25 14:00:00-04'),
(57, 11,  2, 'stop_limit','sell',100,420.0000,  'pending',             0, NULL,     '2024-10-25 14:15:00-04'),
-- Client 12 (Institutional)
(58, 12,  3, 'market', 'buy',  150, NULL,      'filled',            150, 180.0000, '2024-04-05 09:30:00-04'),
(59, 12, 14, 'market', 'buy',  200, NULL,      'filled',            200, 268.0000, '2024-04-15 10:00:00-04'),
(60, 12,  8, 'market', 'buy',  180, NULL,      'filled',            180, 110.0000, '2024-05-01 11:00:00-04'),
(61, 12, 10, 'market', 'buy',  100, NULL,      'filled',            100, 158.0000, '2024-05-10 09:30:00-04'),
(62, 12, 14, 'limit',  'sell',  50, 290.0000,  'pending',             0, NULL,     '2024-10-25 15:00:00-04'),
-- Client 13
(63, 13,  6, 'market', 'buy',  100, NULL,      'filled',            100, 158.0000, '2024-05-15 09:30:00-04'),
(64, 13, 10, 'market', 'buy',   80, NULL,      'filled',             80, 150.0000, '2024-05-20 10:00:00-04'),
(65, 13, 14, 'market', 'buy',   50, NULL,      'filled',             50, 272.0000, '2024-06-01 11:00:00-04'),
(66, 13, 11, 'market', 'buy',  150, NULL,      'filled',            150,  56.0000, '2024-06-10 09:45:00-04'),
-- Client 14
(67, 14,  1, 'market', 'buy',   75, NULL,      'filled',             75, 180.0000, '2024-05-01 09:30:00-04'),
(68, 14, 19, 'market', 'buy',   25, NULL,      'filled',             25, 480.0000, '2024-06-01 10:00:00-04'),
(69, 14, 16, 'limit',  'buy',   60, 155.0000,  'filled',             60, 152.0000, '2024-06-15 11:00:00-04'),
(70, 14, 17, 'market', 'buy',   40, NULL,      'filled',             40, 180.0000, '2024-07-01 09:30:00-04'),
(71, 14, 19, 'limit',  'sell',  10, 1300.0000, 'pending',             0, NULL,     '2024-10-25 14:30:00-04'),
-- Client 15
(72, 15,  2, 'market', 'buy',   30, NULL,      'filled',             30, 382.0000, '2024-06-01 08:30:00+00'),
(73, 15, 12, 'market', 'buy',   40, NULL,      'filled',             40, 160.0000, '2024-06-10 09:00:00+00'),
(74, 15, 14, 'market', 'buy',   25, NULL,      'filled',             25, 275.0000, '2024-06-20 10:30:00+00'),
(75, 15,  2, 'limit',  'sell',  10, 435.0000,  'pending',             0, NULL,     '2024-10-25 09:00:00+00'),
-- Extra partially filled & rejected & cancelled orders
(76,  1, 19, 'limit',  'buy',  100, 1250.0000, 'partially_filled',   40, 1250.0000,'2024-10-23 10:00:00-04'),
(77,  4, 15, 'limit',  'buy',   20, 400.0000,  'rejected',            0, NULL,     '2024-10-22 09:30:00-04'),
(78,  2, 23, 'stop_loss','sell',100, 140.0000,  'cancelled',           0, NULL,     '2024-10-21 14:00:00-04'),
(79, 10, 20, 'limit',  'sell',  30, 610.0000,  'pending',             0, NULL,     '2024-10-25 15:00:00-04'),
(80, 12,  3, 'stop_limit','sell',50, 200.0000,  'pending',             0, NULL,     '2024-10-25 15:30:00-04');

SELECT setval('orders_id_seq', (SELECT MAX(id) FROM orders));

-- ---------------------------------------------------------------------------
-- Trades (60)
-- ---------------------------------------------------------------------------
INSERT INTO trades (id, order_id, stock_id, client_id, broker_id, side, quantity, price, total_amount, commission, net_amount, trade_date, settlement_date) VALUES
-- Client 1
( 1,  1,  1,  1, 1, 'buy',  150, 172.5000,  25875.00, 31.0500,  25906.05, '2024-06-10 09:30:15-04', '2024-06-12'),
( 2,  2,  2,  1, 1, 'buy',  100, 380.2000,  38020.00, 45.6240,  38065.62, '2024-06-12 10:15:08-04', '2024-06-14'),
( 3,  3, 19,  1, 1, 'buy',   50, 450.0000,  22500.00, 27.0000,  22527.00, '2024-07-01 11:00:22-04', '2024-07-03'),
( 4,  4, 24,  1, 1, 'buy',   80, 260.0000,  20800.00, 24.9600,  20824.96, '2024-07-15 09:45:11-04', '2024-07-17'),
-- Client 2
( 5,  6, 19,  2, 2, 'buy',  200, 310.0000,  62000.00, 62.0000,  62062.00, '2024-04-05 10:00:05-04', '2024-04-09'),
( 6,  7, 18,  2, 2, 'buy',  100, 210.0000,  21000.00, 21.0000,  21021.00, '2024-05-20 11:30:18-04', '2024-05-22'),
( 7,  8, 23,  2, 2, 'buy',  300, 110.0000,  33000.00, 33.0000,  33033.00, '2024-06-01 09:30:45-04', '2024-06-05'),
-- Client 3
( 8, 11,  1,  3, 1, 'buy',   50, 165.0000,   8250.00,  9.9000,   8259.90, '2024-05-15 09:35:22-04', '2024-05-17'),
( 9, 12,  6,  3, 1, 'buy',   40, 160.0000,   6400.00,  7.6800,   6407.68, '2024-05-20 10:00:33-04', '2024-05-22'),
(10, 13, 10,  3, 1, 'buy',   60, 155.0000,   9300.00, 11.1600,   9311.16, '2024-06-10 11:15:09-04', '2024-06-12'),
(11, 14, 11,  3, 1, 'buy',   80,  58.0000,   4640.00,  5.5680,   4645.57, '2024-06-15 09:30:55-04', '2024-06-19'),
-- Client 4
(12, 16,  3,  4, 3, 'buy',   70, 175.0000,  12250.00, 18.3750,  12268.38, '2024-05-01 10:30:12-04', '2024-05-03'),
(13, 17, 14,  4, 3, 'buy',   45, 265.0000,  11925.00, 17.8875,  11942.89, '2024-05-10 09:30:44-04', '2024-05-14'),
(14, 18, 15,  4, 3, 'buy',   35, 410.0000,  14350.00, 21.5250,  14371.53, '2024-06-20 11:00:28-04', '2024-06-24'),
(15, 19, 12,  4, 3, 'buy',   50, 155.0000,   7750.00, 11.6250,   7761.63, '2024-07-05 10:45:17-04', '2024-07-09'),
-- Client 5
(16, 21,  8,  5, 2, 'buy',   80, 105.0000,   8400.00,  8.4000,   8408.40, '2024-04-15 09:30:33-04', '2024-04-17'),
(17, 22, 11,  5, 2, 'buy',  120,  55.0000,   6600.00,  6.6000,   6606.60, '2024-04-20 10:00:19-04', '2024-04-22'),
(18, 23, 12,  5, 2, 'buy',   60, 148.0000,   8880.00,  8.8800,   8888.88, '2024-05-05 11:30:41-04', '2024-05-07'),
(19, 24,  6,  5, 2, 'buy',   45, 162.0000,   7290.00,  7.2900,   7297.29, '2024-05-12 09:45:55-04', '2024-05-14'),
-- Client 6
(20, 26, 26,  6, 4, 'buy',  100, 2500.0000, 250000.00, 200.0000, 250200.00, '2024-05-01 09:30:10+05:30','2024-05-03'),
(21, 27, 29,  6, 4, 'buy',  200, 1650.0000, 330000.00, 264.0000, 330264.00, '2024-05-15 10:00:25+05:30','2024-05-17'),
(22, 28, 30,  6, 4, 'buy',  500,  600.0000, 300000.00, 240.0000, 300240.00, '2024-06-01 11:00:38+05:30','2024-06-05'),
-- Client 7
(23, 31, 27,  7, 4, 'buy',  150, 3400.0000, 510000.00, 408.0000, 510408.00, '2024-04-10 09:30:15+05:30','2024-04-12'),
(24, 32, 28,  7, 4, 'buy',  300, 1500.0000, 450000.00, 360.0000, 450360.00, '2024-04-20 10:15:30+05:30','2024-04-22'),
(25, 33, 19,  7, 4, 'buy',   30,  550.0000,  16500.00,  13.2000,  16513.20, '2024-05-05 10:00:45-04',   '2024-05-07'),
-- Client 8
(26, 36,  2,  8, 5, 'buy',   40, 375.0000,  15000.00, 16.5000,  15016.50, '2024-06-05 08:30:12+00', '2024-06-07'),
(27, 37, 14,  8, 5, 'buy',   30, 270.0000,   8100.00,  8.9100,   8108.91, '2024-06-15 09:00:22+00', '2024-06-19'),
(28, 38, 12,  8, 5, 'buy',   25, 158.0000,   3950.00,  4.3450,   3954.35, '2024-07-01 10:30:33+00', '2024-07-03'),
(29, 40, 16,  8, 5, 'buy',   50, 152.0000,   7600.00,  8.3600,   7608.36, '2024-08-10 10:00:11+00', '2024-08-14'),
-- Client 9
(30, 41, 10,  9, 3, 'buy',   30, 160.0000,   4800.00,  7.2000,   4807.20, '2024-06-01 10:00:18-04', '2024-06-05'),
(31, 42, 11,  9, 3, 'buy',   50,  59.0000,   2950.00,  4.4250,   2954.43, '2024-06-05 09:30:27-04', '2024-06-07'),
(32, 43,  6,  9, 3, 'buy',   20, 165.0000,   3300.00,  4.9500,   3304.95, '2024-07-10 11:00:44-04', '2024-07-12'),
(33, 45,  8,  9, 3, 'buy',   25, 112.0000,   2800.00,  4.2000,   2804.20, '2024-08-01 10:30:55-04', '2024-08-05'),
-- Client 10
(34, 46,  1, 10, 1, 'buy',  200, 178.0000,  35600.00, 42.7200,  35642.72, '2024-04-01 09:30:08-04', '2024-04-03'),
(35, 47, 16, 10, 1, 'buy',  120, 140.0000,  16800.00, 20.1600,  16820.16, '2024-04-15 10:00:22-04', '2024-04-17'),
(36, 48, 17, 10, 1, 'buy',  100, 175.0000,  17500.00, 21.0000,  17521.00, '2024-05-01 11:00:33-04', '2024-05-03'),
(37, 49, 20, 10, 1, 'buy',   80, 320.0000,  25600.00, 30.7200,  25630.72, '2024-05-20 09:45:44-04', '2024-05-22'),
(38, 50, 21, 10, 1, 'buy',   60, 450.0000,  27000.00, 32.4000,  27032.40, '2024-06-01 10:30:55-04', '2024-06-05'),
-- Client 11 (Institutional)
(39, 51,  1, 11, 2, 'buy',  500, 170.0000,  85000.00, 85.0000,  85085.00, '2024-03-15 09:30:05-04', '2024-03-19'),
(40, 52,  2, 11, 2, 'buy',  400, 370.0000, 148000.00,148.0000, 148148.00, '2024-03-20 10:00:15-04', '2024-03-22'),
(41, 53,  3, 11, 2, 'buy',  200, 178.0000,  35600.00, 35.6000,  35635.60, '2024-04-01 11:00:25-04', '2024-04-03'),
(42, 54, 14, 11, 2, 'buy',  300, 270.0000,  81000.00, 81.0000,  81081.00, '2024-04-10 09:30:35-04', '2024-04-12'),
(43, 55,  8, 11, 2, 'buy',  250, 108.0000,  27000.00, 27.0000,  27027.00, '2024-04-20 10:30:45-04', '2024-04-22'),
-- Client 12 (Institutional)
(44, 58,  3, 12, 3, 'buy',  150, 180.0000,  27000.00, 40.5000,  27040.50, '2024-04-05 09:30:12-04', '2024-04-09'),
(45, 59, 14, 12, 3, 'buy',  200, 268.0000,  53600.00, 80.4000,  53680.40, '2024-04-15 10:00:28-04', '2024-04-17'),
(46, 60,  8, 12, 3, 'buy',  180, 110.0000,  19800.00, 29.7000,  19829.70, '2024-05-01 11:00:38-04', '2024-05-03'),
(47, 61, 10, 12, 3, 'buy',  100, 158.0000,  15800.00, 23.7000,  15823.70, '2024-05-10 09:30:48-04', '2024-05-14'),
-- Client 13
(48, 63,  6, 13, 1, 'buy',  100, 158.0000,  15800.00, 18.9600,  15818.96, '2024-05-15 09:30:18-04', '2024-05-17'),
(49, 64, 10, 13, 1, 'buy',   80, 150.0000,  12000.00, 14.4000,  12014.40, '2024-05-20 10:00:28-04', '2024-05-22'),
(50, 65, 14, 13, 1, 'buy',   50, 272.0000,  13600.00, 16.3200,  13616.32, '2024-06-01 11:00:38-04', '2024-06-05'),
(51, 66, 11, 13, 1, 'buy',  150,  56.0000,   8400.00, 10.0800,   8410.08, '2024-06-10 09:45:48-04', '2024-06-12'),
-- Client 14
(52, 67,  1, 14, 2, 'buy',   75, 180.0000,  13500.00, 13.5000,  13513.50, '2024-05-01 09:30:08-04', '2024-05-03'),
(53, 68, 19, 14, 2, 'buy',   25, 480.0000,  12000.00, 12.0000,  12012.00, '2024-06-01 10:00:18-04', '2024-06-05'),
(54, 69, 16, 14, 2, 'buy',   60, 152.0000,   9120.00,  9.1200,   9129.12, '2024-06-15 11:00:28-04', '2024-06-19'),
(55, 70, 17, 14, 2, 'buy',   40, 180.0000,   7200.00,  7.2000,   7207.20, '2024-07-01 09:30:38-04', '2024-07-03'),
-- Client 15
(56, 72,  2, 15, 5, 'buy',   30, 382.0000,  11460.00, 12.6060,  11472.61, '2024-06-01 08:30:08+00', '2024-06-05'),
(57, 73, 12, 15, 5, 'buy',   40, 160.0000,   6400.00,  7.0400,   6407.04, '2024-06-10 09:00:18+00', '2024-06-12'),
(58, 74, 14, 15, 5, 'buy',   25, 275.0000,   6875.00,  7.5625,   6882.56, '2024-06-20 10:30:28+00', '2024-06-24'),
-- Partial fill for order 76
(59, 76, 19,  1, 1, 'buy',   40, 1250.0000, 50000.00, 60.0000,  50060.00, '2024-10-23 10:00:30-04', '2024-10-25'),
-- Additional trade
(60, 33, 19,  7, 4, 'buy',   30,  550.0000, 16500.00,  13.2000, 16513.20, '2024-05-05 10:01:00-04', '2024-05-07');

SELECT setval('trades_id_seq', (SELECT MAX(id) FROM trades));

-- ---------------------------------------------------------------------------
-- Dividends (10)
-- ---------------------------------------------------------------------------
INSERT INTO dividends (stock_id, declaration_date, ex_dividend_date, record_date, payment_date, dividend_per_share) VALUES
( 1, '2024-07-25', '2024-08-12', '2024-08-12', '2024-08-15', 0.2500),
( 1, '2024-10-28', '2024-11-11', '2024-11-11', '2024-11-14', 0.2500),
( 2, '2024-06-12', '2024-08-15', '2024-08-15', '2024-09-12', 0.7500),
( 3, '2024-07-15', '2024-07-30', '2024-07-31', '2024-08-31', 1.1500),
(11, '2024-06-20', '2024-06-28', '2024-06-28', '2024-07-15', 0.4850),
(12, '2024-07-18', '2024-07-25', '2024-07-25', '2024-08-15', 1.0065),
( 8, '2024-07-25', '2024-08-14', '2024-08-15', '2024-09-10', 0.9500),
( 6, '2024-07-16', '2024-08-26', '2024-08-27', '2024-09-10', 1.2400),
(14, '2024-08-20', '2024-08-30', '2024-09-02', '2024-09-03', 0.5200),
(26, '2024-07-19', '2024-08-22', '2024-08-22', '2024-09-05', 9.0000);

-- ---------------------------------------------------------------------------
-- Watchlists (5)
-- ---------------------------------------------------------------------------
INSERT INTO watchlists (id, client_id, name) VALUES
(1,  1, 'AI & Semiconductor Picks'),
(2,  2, 'Momentum Stocks'),
(3,  6, 'Indian Blue Chips'),
(4, 10, 'Tech Megacaps'),
(5, 13, 'Dividend Watchlist');

SELECT setval('watchlists_id_seq', (SELECT MAX(id) FROM watchlists));

-- ---------------------------------------------------------------------------
-- Watchlist Items
-- ---------------------------------------------------------------------------
INSERT INTO watchlist_items (watchlist_id, stock_id) VALUES
-- Watchlist 1: AI & Semiconductor Picks
(1, 19), (1, 23), (1, 22), (1, 16),
-- Watchlist 2: Momentum Stocks
(2, 18), (2, 19), (2, 21), (2, 20), (2, 17),
-- Watchlist 3: Indian Blue Chips
(3, 26), (3, 27), (3, 28), (3, 29), (3, 30),
-- Watchlist 4: Tech Megacaps
(4,  1), (4,  2), (4, 16), (4, 17), (4, 19), (4, 20),
-- Watchlist 5: Dividend Watchlist
(5, 11), (5, 12), (5,  6), (5,  8), (5, 14);

-- ---------------------------------------------------------------------------
-- Market Indices (3)
-- ---------------------------------------------------------------------------
INSERT INTO market_indices (id, name, code, exchange_id) VALUES
(1, 'S&P 500',           'SP500',   1),
(2, 'Dow Jones Industrial Average', 'DJIA', 1),
(3, 'NIFTY 50',          'NIFTY50', 4);

SELECT setval('market_indices_id_seq', (SELECT MAX(id) FROM market_indices));

-- ---------------------------------------------------------------------------
-- Index Compositions
-- ---------------------------------------------------------------------------
INSERT INTO index_compositions (index_id, stock_id, weight_percentage, added_date) VALUES
-- S&P 500 (select constituents with illustrative weights)
(1,  1,  7.100, '2020-01-01'),
(1,  2,  6.800, '2020-01-01'),
(1, 16,  3.900, '2020-01-01'),
(1, 17,  3.500, '2020-01-01'),
(1, 19,  3.200, '2020-01-01'),
(1, 20,  2.100, '2020-01-01'),
(1, 18,  1.800, '2020-01-01'),
(1,  3,  1.400, '2020-01-01'),
(1, 14,  1.300, '2020-01-01'),
(1,  6,  1.200, '2020-01-01'),
(1,  8,  1.100, '2020-01-01'),
(1, 10,  0.900, '2020-01-01'),
-- DJIA
(2,  1,  5.500, '2020-01-01'),
(2,  2,  5.200, '2020-01-01'),
(2,  3,  3.800, '2020-01-01'),
(2, 14,  3.500, '2020-01-01'),
(2,  6,  2.800, '2020-01-01'),
(2, 10,  2.500, '2020-01-01'),
(2, 11,  2.200, '2020-01-01'),
(2, 13,  2.000, '2020-01-01'),
-- NIFTY 50
(3, 26,  9.500, '2020-01-01'),
(3, 27,  5.200, '2020-01-01'),
(3, 28,  4.800, '2020-01-01'),
(3, 29,  8.200, '2020-01-01'),
(3, 30,  2.100, '2020-01-01');

-- ============================================================================
-- USEFUL VIEWS (optional helpers)
-- ============================================================================

-- Latest closing price per stock
CREATE OR REPLACE VIEW v_latest_stock_prices AS
SELECT DISTINCT ON (sp.stock_id)
    sp.stock_id,
    s.ticker_symbol,
    s.company_name,
    sp.trade_date,
    sp.close_price,
    sp.volume
FROM stock_prices sp
JOIN stocks s ON s.id = sp.stock_id
ORDER BY sp.stock_id, sp.trade_date DESC;

-- Portfolio summary with market values
CREATE OR REPLACE VIEW v_portfolio_summary AS
SELECT
    p.id            AS portfolio_id,
    p.name          AS portfolio_name,
    c.first_name || ' ' || c.last_name AS client_name,
    COUNT(ph.id)    AS num_holdings,
    SUM(ph.current_value) AS total_value
FROM portfolios p
JOIN clients c ON c.id = p.client_id
LEFT JOIN portfolio_holdings ph ON ph.portfolio_id = p.id
GROUP BY p.id, p.name, c.first_name, c.last_name;

-- ============================================================================
-- Done. Database is ready.
-- ============================================================================
