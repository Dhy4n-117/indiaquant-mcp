# IndiaQuant MCP 4

> Real-time Indian stock market AI assistant built as an MCP (Model Context Protocol) server. Plugs into Claude Desktop and gives it full Indian stock market intelligence + virtual trading capabilities.

**No paid APIs. No scraping. No mock data. 100% live market data.**

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Claude Desktop                            │
│                     (MCP Client / AI Agent)                      │
└──────────────────────────┬───────────────────────────────────────┘
                           │ MCP Protocol (stdio)
┌──────────────────────────▼───────────────────────────────────────┐
│                    server.py (FastMCP)                            │
│              10 MCP Tools · Schema Validation · JSON Responses   │
├──────────────┬──────────────┬──────────────┬─────────────────────┤
│  Module 1    │   Module 2   │   Module 3   │     Module 4        │
│ Market Data  │  AI Trade    │   Options    │    Portfolio         │
│   Engine     │  Signal Gen  │   Analyzer   │  Risk Manager       │
├──────────────┼──────────────┼──────────────┼─────────────────────┤
│ • Live NSE   │ • RSI, MACD  │ • Options    │ • SQLite virtual    │
│   prices via │   Bollinger  │   chain via  │   portfolio         │
│   yfinance   │   Bands      │   yfinance   │ • Real-time P&L     │
│ • OHLC hist  │ • H&S, Dbl   │ • Black-     │   with live prices  │
│ • Sector     │   Top/Bottom │   Scholes    │ • Auto stop-loss    │
│   heatmap    │   patterns   │   from       │   & target mgmt     │
│ • TTL-based  │ • NewsAPI    │   scratch    │ • Volatility-based  │
│   caching    │   sentiment  │ • Max pain   │   risk scoring      │
│              │ • Composite  │ • OI spike   │   (1-10 scale)      │
│              │   signal     │   detection  │                     │
│              │   (0-100%)   │              │                     │
├──────────────┴──────────────┴──────────────┴─────────────────────┤
│                     Free API Stack (No paid APIs)                │
│  yfinance  │  NewsAPI.org  │  Alpha Vantage  │  Custom BS Model  │
└──────────────────────────────────────────────────────────────────┘
```

### Design Decisions

**Module Separation**: Each of the 5 modules is a standalone Python file with clear responsibilities. No circular imports — `server.py` imports from modules only at tool call time (lazy imports), keeping startup fast.

**Caching Strategy**: In-memory dict with TTL-based eviction. Trade-off: simple and fast, but no persistence across restarts. TTLs are tuned per data type:
| Data | TTL | Rationale |
|------|-----|-----------|
| Live prices | 30s | Balance freshness vs API load |
| Options chain | 60s | Changes less frequently |
| News/sentiment | 5min | Headlines stable over minutes |
| Historical OHLC | 10min | Doesn't change intraday |

**Signal Confidence**: Weighted combination of technicals (60%) and sentiment (40%). Each indicator contributes a bounded score, summed and mapped to BUY/SELL/HOLD with 0-100% confidence. Trade-off: equal weighting across indicators; a production system would backtest adaptive weights.

**Black-Scholes**: Implemented entirely from scratch using only Python's `math.erf` for the normal CDF. No scipy, no finance libraries. All formulas (d1, d2, Delta, Gamma, Theta, Vega) written from first principles.

**SQLite for Portfolio**: Zero-config, file-based database. Starting balance ₹10,00,000. Auto stop-loss at 5% below entry, target at 10% above. Risk score derived from annualized volatility mapped to 1-10 scale.

---

## 10 MCP Tools

| # | Tool | Inputs | Returns |
|---|------|--------|---------|
| 1 | `get_live_price` | `symbol` | price, change%, volume, OHLC |
| 2 | `get_options_chain` | `symbol`, `expiry` | strikes, CE/PE OI, PCR |
| 3 | `analyze_sentiment` | `symbol` | score (-1 to +1), headlines, signal |
| 4 | `generate_signal` | `symbol`, `timeframe` | BUY/SELL/HOLD, confidence 0-100% |
| 5 | `get_portfolio_pnl` | — | positions, total P&L, risk scores |
| 6 | `place_virtual_trade` | `symbol`, `qty`, `side` | order_id, status, stop-loss/target |
| 7 | `calculate_greeks` | `symbol`, `strike`, `expiry`, `option_type` | delta, gamma, theta, vega |
| 8 | `detect_unusual_activity` | `symbol` | alerts (vol/OI spikes), anomalies |
| 9 | `scan_market` | `filter_criteria` (JSON) | matching symbols with data |
| 10 | `get_sector_heatmap` | — | all sectors with avg % change |

All 10 tools return **live data** from free APIs — no hardcoded or mock responses.

---

## Free API Stack

| Purpose | API | Cost | Limits |
|---------|-----|------|--------|
| Live NSE/BSE prices | yfinance (Yahoo Finance) | Free | Unlimited |
| Historical OHLC data | yfinance | Free | Full history |
| Options chain data | yfinance options | Free | NSE supported |
| News & sentiment | NewsAPI.org | Free | 100 req/day |
| Macro indicators | Alpha Vantage | Free | 25 req/day |
| Technical analysis | pandas / numpy (TA-Lib formulas) | Free | Open source |
| Greeks calculation | Custom Black-Scholes | Free | From scratch |

No paid APIs. No broker accounts required. No web scraping.

---

## Setup Guide

### Prerequisites

- **Python 3.10+**
- **Claude Desktop** installed ([download](https://claude.ai/download))

### Step 1: Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/indiaquant-mcp.git
cd indiaquant-mcp
pip install -r requirements.txt
```

### Step 2: API Keys (Optional)

Get free API keys (only needed for sentiment analysis — all other 9 tools work without any keys):

- **NewsAPI**: [https://newsapi.org/register](https://newsapi.org/register) — 100 req/day free
- **Alpha Vantage**: [https://www.alphavantage.co/support/#api-key](https://www.alphavantage.co/support/#api-key) — 25 req/day free

Set as environment variables:

```bash
# Windows (PowerShell)
$env:NEWSAPI_KEY = "your-newsapi-key"
$env:ALPHA_VANTAGE_KEY = "your-alphavantage-key"

# Linux/Mac
export NEWSAPI_KEY="your-newsapi-key"
export ALPHA_VANTAGE_KEY="your-alphavantage-key"
```

### Step 3: Configure Claude Desktop

Add to your Claude Desktop config:

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "indiaquant": {
      "command": "python",
      "args": ["/absolute/path/to/indiaquant-mcp/server.py"],
      "env": {
        "NEWSAPI_KEY": "your-newsapi-key",
        "ALPHA_VANTAGE_KEY": "your-alphavantage-key"
      }
    }
  }
}
```

### Step 4: Restart Claude Desktop

After saving the config, restart Claude Desktop. The 10 IndiaQuant tools will appear in the tools menu.

---

## Example Conversations

After setup, try asking Claude:

| What to ask | Tool used |
|-------------|-----------|
| "What's the live price of Reliance?" | `get_live_price` |
| "Show me the options chain for NIFTY" | `get_options_chain` |
| "What's the sentiment around INFY?" | `analyze_sentiment` |
| "Should I buy HDFC Bank right now?" | `generate_signal` |
| "Show me my portfolio P&L" | `get_portfolio_pnl` |
| "Buy 50 shares of TCS" | `place_virtual_trade` |
| "Calculate Greeks for RELIANCE 2500 CE March expiry" | `calculate_greeks` |
| "Any unusual options activity on Infosys?" | `detect_unusual_activity` |
| "Find oversold IT stocks with RSI below 30" | `scan_market` |
| "Show me the sector heatmap" | `get_sector_heatmap` |

---

## Project Structure

```
indiaquant-mcp/
├── server.py           # Module 5: FastMCP server — 10 MCP tools registered
├── market_data.py      # Module 1: Live prices, OHLC history, sector heatmap
├── signals.py          # Module 2: RSI/MACD/BB, patterns, sentiment, signals
├── options.py          # Module 3: Options chain, Black-Scholes Greeks, max pain
├── portfolio.py        # Module 4: SQLite portfolio, P&L, stop-loss, risk
├── config.py           # API keys, Nifty 50/Bank Nifty, sector maps, constants
├── requirements.txt    # Python dependencies
├── .gitignore          # Git ignore rules
└── README.md           # This file
```

---

## Black-Scholes Implementation

Greeks are calculated from first principles — no financial libraries used:

```
d1 = (ln(S/K) + (r + σ²/2) × T) / (σ × √T)
d2 = d1 - σ × √T

Delta (Call)  = N(d1)
Delta (Put)   = N(d1) - 1
Gamma         = n(d1) / (S × σ × √T)
Theta (Call)  = -(S × n(d1) × σ)/(2√T) - r × K × e^(-rT) × N(d2)
Theta (Put)   = -(S × n(d1) × σ)/(2√T) + r × K × e^(-rT) × N(-d2)
Vega          = S × n(d1) × √T / 100
```

Where `N(x)` is the standard normal CDF (via `math.erf`) and `n(x)` is the standard normal PDF.

**Verified** against known values: S=K=100, r=5%, σ=20%, T=1yr → Delta=0.637, Gamma=0.019, Vega=0.375 ✓

---

## Limitations & Trade-offs

| Limitation | Impact | Mitigation |
|-----------|--------|------------|
| **Market hours only** | yfinance returns last close outside 9:15am-3:30pm IST | Clear timestamp in response |
| **yfinance options** | Not all NSE stocks have options data on Yahoo Finance | Graceful error messages |
| **NewsAPI free tier** | 100 requests/day limit | Caching (5min TTL), selective queries |
| **Alpha Vantage free tier** | 25 requests/day | Used only for macro data |
| **Pattern detection** | Simple local min/max algorithm, not ML-based | Bounded confidence scores |
| **Single-user** | In-memory cache, SQLite | Sufficient for MCP server use case |
| **Virtual trading only** | No real broker integration | By design — educational/analytical tool |

---

## Tech Stack

- **Language**: Python 3.10+
- **MCP SDK**: FastMCP (official `mcp` package)
- **Market Data**: yfinance
- **Technicals**: pandas + numpy (RSI, MACD, Bollinger Bands)
- **Sentiment**: NewsAPI.org + keyword-based scoring
- **Greeks**: Custom Black-Scholes (pure math)
- **Portfolio**: SQLite3
- **Transport**: stdio (Claude Desktop standard)
