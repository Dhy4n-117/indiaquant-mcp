"""
IndiaQuant MCP 4 — Configuration
Constants, API keys, sector mappings, and cache settings.
"""

import os

# ─── API Keys (from environment variables) ──────────────────────────────────
NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "")
ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "")

# ─── Cache TTL (seconds) ────────────────────────────────────────────────────
CACHE_TTL_PRICE = 30        # Live price cache
CACHE_TTL_OPTIONS = 60      # Options chain cache
CACHE_TTL_NEWS = 300        # News/sentiment cache
CACHE_TTL_HISTORICAL = 600  # Historical OHLC cache

# ─── Portfolio Defaults ─────────────────────────────────────────────────────
INITIAL_CASH = 1000000.0    # ₹10,00,000 starting balance

# ─── Black-Scholes Constants ────────────────────────────────────────────────
RISK_FREE_RATE = 0.0691     # India 10Y govt bond yield (~6.91%)

# ─── Nifty 50 Constituents ──────────────────────────────────────────────────
NIFTY_50 = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BPCL",
    "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY",
    "EICHERMOT", "ETERNAL", "GRASIM", "HCLTECH", "HDFCBANK",
    "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK",
    "ITC", "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK",
    "LT", "M&M", "MARUTI", "NTPC", "NESTLEIND",
    "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SBIN",
    "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL",
    "TECHM", "TITAN", "TRENT", "ULTRACEMCO", "WIPRO"
]

# ─── Bank Nifty Constituents ────────────────────────────────────────────────
BANK_NIFTY = [
    "HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN",
    "INDUSINDBK", "BANDHANBNK", "FEDERALBNK", "IDFCFIRSTB",
    "PNB", "BANKBARODA", "AUBANK"
]

# ─── Sector Mappings ────────────────────────────────────────────────────────
SECTORS = {
    "IT": ["INFY", "TCS", "WIPRO", "HCLTECH", "TECHM", "LTIM", "MPHASIS", "COFORGE"],
    "Banking": ["HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN", "INDUSINDBK", "PNB", "BANKBARODA"],
    "Pharma": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "APOLLOHOSP", "BIOCON", "LUPIN", "AUROPHARMA"],
    "Auto": ["TATAMOTORS", "MARUTI", "M&M", "BAJAJ-AUTO", "EICHERMOT", "HEROMOTOCO", "ASHOKLEY", "TVSMOTOR"],
    "Energy": ["RELIANCE", "ONGC", "BPCL", "COALINDIA", "NTPC", "POWERGRID", "ADANIGREEN", "TATAPOWER"],
    "FMCG": ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "TATACONSUM", "DABUR", "MARICO", "GODREJCP"],
    "Metals": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "SAIL", "NMDC", "NATIONALUM", "COALINDIA"],
    "Realty": ["DLF", "GODREJPROP", "OBEROIRLTY", "PHOENIXLTD", "PRESTIGE", "Brigade", "SOBHA", "SUNTECK"],
    "Infra": ["LT", "ADANIENT", "ADANIPORTS", "ULTRACEMCO", "GRASIM", "SHREECEM", "AMBUJACEM", "ACC"],
    "Finance": ["BAJFINANCE", "BAJAJFINSV", "HDFCLIFE", "SBILIFE", "ICICIPRULI", "CHOLAFIN", "MUTHOOTFIN", "MANAPPURAM"],
}

# ─── Database Path ──────────────────────────────────────────────────────────
import pathlib
DB_PATH = str(pathlib.Path(__file__).parent / "portfolio.db")
