"""
IndiaQuant MCP 4 — Module 5: MCP Tools Layer
Expose all 10 capabilities as proper MCP tools.
Follow MCP protocol spec for tool registration, schema, and error handling.
Return clean structured JSON responses.
Must connect and work with Claude Desktop.
"""

import json
from mcp.server.fastmcp import FastMCP

# Initialize MCP Server
mcp = FastMCP(
    "IndiaQuant MCP 4",
    instructions="Real-time Indian stock market AI assistant with live data, "
                 "trade signals, options analysis, virtual trading, and portfolio management."
)


# ─── Tool 1: get_live_price ─────────────────────────────────────────────────


@mcp.tool()
def get_live_price(symbol: str) -> str:
    """
    Get live NSE/BSE stock price with change%, volume, and key price levels.

    Args:
        symbol: Stock symbol (e.g., RELIANCE, INFY, TCS, HDFCBANK).
                Nifty 50 index: use 'NIFTY'. Bank Nifty: use 'BANKNIFTY'.
    """
    from market_data import get_live_price as _get_live_price
    result = _get_live_price(symbol)
    return json.dumps(result, indent=2, default=str)


# ─── Tool 2: get_options_chain ───────────────────────────────────────────────


@mcp.tool()
def get_options_chain(symbol: str, expiry: str = "") -> str:
    """
    Get live options chain data with strikes, CE/PE premiums, OI, and volume.

    Args:
        symbol: Stock symbol (e.g., RELIANCE, INFY, TCS).
        expiry: Optional expiry date (YYYY-MM-DD). If empty, uses nearest expiry.
    """
    from options import get_options_chain as _get_options_chain
    result = _get_options_chain(symbol, expiry if expiry else None)
    return json.dumps(result, indent=2, default=str)


# ─── Tool 3: analyze_sentiment ──────────────────────────────────────────────


@mcp.tool()
def analyze_sentiment(symbol: str) -> str:
    """
    Run sentiment analysis on recent news headlines for a stock.
    Returns sentiment score (-1 to +1), signal (BULLISH/BEARISH/NEUTRAL),
    and scored headlines from NewsAPI.

    Args:
        symbol: Stock symbol (e.g., RELIANCE, INFY, TCS).
    """
    from signals import analyze_sentiment as _analyze_sentiment
    result = _analyze_sentiment(symbol)
    return json.dumps(result, indent=2, default=str)


# ─── Tool 4: generate_signal ────────────────────────────────────────────────


@mcp.tool()
def generate_signal(symbol: str, timeframe: str = "1d") -> str:
    """
    Generate a BUY/SELL/HOLD signal with confidence score (0-100%).
    Combines technical analysis (RSI, MACD, Bollinger Bands, patterns) at 60% weight
    with sentiment analysis at 40% weight.

    Args:
        symbol: Stock symbol (e.g., RELIANCE, INFY, TCS).
        timeframe: Analysis timeframe - '1d' (daily), '1h' (hourly),
                   '15m' (15-min), '5m' (5-min), '1wk' (weekly).
    """
    from signals import generate_signal as _generate_signal
    result = _generate_signal(symbol, timeframe)
    return json.dumps(result, indent=2, default=str)


# ─── Tool 5: get_portfolio_pnl ──────────────────────────────────────────────


@mcp.tool()
def get_portfolio_pnl() -> str:
    """
    Get real-time portfolio P&L with all open positions, current values,
    risk scores, and auto stop-loss status. No arguments needed.
    """
    from portfolio import get_portfolio_pnl as _get_portfolio_pnl
    result = _get_portfolio_pnl()
    return json.dumps(result, indent=2, default=str)


# ─── Tool 6: place_virtual_trade ────────────────────────────────────────────


@mcp.tool()
def place_virtual_trade(symbol: str, qty: int, side: str) -> str:
    """
    Place a virtual trade (BUY or SELL) in the simulated portfolio.
    Starting cash balance: ₹10,00,000. Auto stop-loss at -5%, target at +10%.

    Args:
        symbol: Stock symbol (e.g., RELIANCE, INFY, TCS).
        qty: Number of shares.
        side: Trade direction - 'BUY' or 'SELL'.
    """
    from portfolio import place_virtual_trade as _place_virtual_trade
    result = _place_virtual_trade(symbol, qty, side)
    return json.dumps(result, indent=2, default=str)


# ─── Tool 7: calculate_greeks ───────────────────────────────────────────────


@mcp.tool()
def calculate_greeks(symbol: str, strike: float, expiry: str,
                     option_type: str, spot_price: float = 0) -> str:
    """
    Calculate option Greeks using Black-Scholes model (implemented from scratch).
    Returns Delta, Gamma, Theta, Vega, and theoretical option price.

    Args:
        symbol: Stock symbol (e.g., RELIANCE, INFY).
        strike: Strike price of the option.
        expiry: Expiry date in YYYY-MM-DD format.
        option_type: 'CE' for Call or 'PE' for Put.
        spot_price: Optional current spot price. If 0, fetches live price.
    """
    from options import calculate_greeks as _calculate_greeks
    result = _calculate_greeks(
        symbol, strike, expiry, option_type,
        spot_price=spot_price if spot_price > 0 else None
    )
    return json.dumps(result, indent=2, default=str)


# ─── Tool 8: detect_unusual_activity ────────────────────────────────────────


@mcp.tool()
def detect_unusual_activity(symbol: str) -> str:
    """
    Detect unusual options activity by identifying volume and OI spikes.
    Flags strikes where volume > 2x average or OI > 2 standard deviations from mean.

    Args:
        symbol: Stock symbol (e.g., RELIANCE, INFY, TCS).
    """
    from options import detect_unusual_activity as _detect_unusual_activity
    result = _detect_unusual_activity(symbol)
    return json.dumps(result, indent=2, default=str)


# ─── Tool 9: scan_market ────────────────────────────────────────────────────


@mcp.tool()
def scan_market(filter_criteria: str) -> str:
    """
    Scan the market for stocks matching given filter criteria.
    Scans Nifty 50 universe by default, or a specific sector.

    Args:
        filter_criteria: JSON string with filter parameters. Supported filters:
            - "rsi_below": number (e.g., 30 for oversold stocks)
            - "rsi_above": number (e.g., 70 for overbought stocks)
            - "sector": string (e.g., "IT", "Banking", "Pharma", "Auto", "Energy", "FMCG")
            - "signal": string ("BUY", "SELL", or "HOLD")
            - "min_change_pct": number (minimum % change today)
            - "max_change_pct": number (maximum % change today)
            Example: '{"sector": "IT", "rsi_below": 30}'
    """
    from signals import scan_market as _scan_market

    try:
        if isinstance(filter_criteria, str):
            criteria = json.loads(filter_criteria)
        else:
            criteria = filter_criteria
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON in filter_criteria. Example: '{\"rsi_below\": 30, \"sector\": \"IT\"}'"},
                          indent=2)

    result = _scan_market(criteria)
    return json.dumps(result, indent=2, default=str)


# ─── Tool 10: get_sector_heatmap ────────────────────────────────────────────


@mcp.tool()
def get_sector_heatmap() -> str:
    """
    Get a sector-wise performance heatmap of the Indian stock market.
    Shows average change% for each sector (IT, Banking, Pharma, Auto, Energy, etc.)
    with top gainers and losers per sector. No arguments needed.
    """
    from market_data import get_sector_heatmap as _get_sector_heatmap
    result = _get_sector_heatmap()
    return json.dumps(result, indent=2, default=str)


# ─── Server Entry Point ─────────────────────────────────────────────────────


if __name__ == "__main__":
    mcp.run()
