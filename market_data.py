"""
IndiaQuant MCP 4 — Module 1: Market Data Engine
Fetch live NSE/BSE prices using yfinance. Pull OHLC historical data.
Support Nifty 50, Bank Nifty, and individual stocks. Cache data efficiently.
"""

import time
import yfinance as yf
import pandas as pd
from config import (
    CACHE_TTL_PRICE, CACHE_TTL_HISTORICAL,
    NIFTY_50, BANK_NIFTY, SECTORS
)

# ─── In-Memory Cache ────────────────────────────────────────────────────────
_cache = {}


def _get_cached(key: str, ttl: int):
    """Return cached value if still valid, else None."""
    if key in _cache:
        value, timestamp = _cache[key]
        if time.time() - timestamp < ttl:
            return value
    return None


def _set_cache(key: str, value):
    """Store value in cache with current timestamp."""
    _cache[key] = (value, time.time())


def _format_symbol(symbol: str) -> str:
    """Ensure symbol has .NS suffix for NSE."""
    symbol = symbol.strip().upper()
    if symbol in ("NIFTY", "NIFTY50", "NIFTY_50"):
        return "^NSEI"
    if symbol in ("BANKNIFTY", "BANK_NIFTY", "BANKNIFTY50"):
        return "^NSEBANK"
    if not symbol.endswith(".NS") and not symbol.endswith(".BO") and not symbol.startswith("^"):
        return f"{symbol}.NS"
    return symbol


def get_live_price(symbol: str) -> dict:
    """
    Fetch live price for an NSE/BSE stock.
    Returns: price, change%, volume, open, high, low, prev_close, market_cap, name
    """
    cache_key = f"price:{symbol}"
    cached = _get_cached(cache_key, CACHE_TTL_PRICE)
    if cached:
        return cached

    formatted = _format_symbol(symbol)
    ticker = yf.Ticker(formatted)

    try:
        info = ticker.fast_info
        hist = ticker.history(period="2d")

        if hist.empty:
            return {"error": f"No data found for {symbol}. Market may be closed or symbol invalid."}

        current_price = float(hist["Close"].iloc[-1])

        # Calculate change from previous close
        if len(hist) >= 2:
            prev_close = float(hist["Close"].iloc[-2])
        else:
            prev_close = current_price

        change = current_price - prev_close
        change_pct = (change / prev_close * 100) if prev_close != 0 else 0.0

        volume = int(hist["Volume"].iloc[-1]) if "Volume" in hist.columns else 0
        open_price = float(hist["Open"].iloc[-1]) if "Open" in hist.columns else current_price
        high_price = float(hist["High"].iloc[-1]) if "High" in hist.columns else current_price
        low_price = float(hist["Low"].iloc[-1]) if "Low" in hist.columns else current_price

        result = {
            "symbol": symbol.upper().replace(".NS", "").replace(".BO", ""),
            "price": round(current_price, 2),
            "change": round(change, 2),
            "change_percent": round(change_pct, 2),
            "volume": volume,
            "open": round(open_price, 2),
            "high": round(high_price, 2),
            "low": round(low_price, 2),
            "prev_close": round(prev_close, 2),
            "timestamp": str(hist.index[-1]),
        }

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        return {"error": f"Failed to fetch price for {symbol}: {str(e)}"}


def get_historical_ohlc(symbol: str, period: str = "1mo", interval: str = "1d") -> dict:
    """
    Fetch OHLC historical data for any symbol.
    period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
    interval: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
    """
    cache_key = f"ohlc:{symbol}:{period}:{interval}"
    cached = _get_cached(cache_key, CACHE_TTL_HISTORICAL)
    if cached:
        return cached

    formatted = _format_symbol(symbol)
    ticker = yf.Ticker(formatted)

    try:
        hist = ticker.history(period=period, interval=interval)

        if hist.empty:
            return {"error": f"No historical data for {symbol}."}

        records = []
        for idx, row in hist.iterrows():
            records.append({
                "date": str(idx),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })

        result = {
            "symbol": symbol.upper().replace(".NS", "").replace(".BO", ""),
            "period": period,
            "interval": interval,
            "data_points": len(records),
            "data": records,
        }

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        return {"error": f"Failed to fetch historical data for {symbol}: {str(e)}"}


def get_sector_heatmap() -> dict:
    """
    Compute sector performance heatmap.
    Returns all sectors with average % change of their constituents.
    """
    cache_key = "sector_heatmap"
    cached = _get_cached(cache_key, CACHE_TTL_PRICE)
    if cached:
        return cached

    heatmap = {}

    for sector_name, symbols in SECTORS.items():
        changes = []
        stock_details = []

        for sym in symbols:
            price_data = get_live_price(sym)
            if "error" not in price_data:
                changes.append(price_data["change_percent"])
                stock_details.append({
                    "symbol": sym,
                    "price": price_data["price"],
                    "change_percent": price_data["change_percent"],
                })

        avg_change = round(sum(changes) / len(changes), 2) if changes else 0.0

        heatmap[sector_name] = {
            "avg_change_percent": avg_change,
            "stocks_tracked": len(stock_details),
            "top_gainer": max(stock_details, key=lambda x: x["change_percent"])["symbol"] if stock_details else None,
            "top_loser": min(stock_details, key=lambda x: x["change_percent"])["symbol"] if stock_details else None,
            "stocks": stock_details,
        }

    # Sort sectors by performance
    sorted_sectors = dict(sorted(heatmap.items(), key=lambda x: x[1]["avg_change_percent"], reverse=True))

    result = {
        "sectors": sorted_sectors,
        "total_sectors": len(sorted_sectors),
        "market_breadth": {
            "positive_sectors": sum(1 for s in sorted_sectors.values() if s["avg_change_percent"] > 0),
            "negative_sectors": sum(1 for s in sorted_sectors.values() if s["avg_change_percent"] < 0),
            "neutral_sectors": sum(1 for s in sorted_sectors.values() if s["avg_change_percent"] == 0),
        }
    }

    _set_cache(cache_key, result)
    return result
