"""
IndiaQuant MCP 4 — Module 3: Options Chain Analyzer
Pull live options chain using yfinance options API.
Implement Black-Scholes from scratch for Delta, Gamma, Theta, Vega.
Detect unusual activity via volume/OI spike detection.
Calculate max pain point for each expiry.
"""

import math
import time
import yfinance as yf
from config import RISK_FREE_RATE, CACHE_TTL_OPTIONS

# ─── Cache ──────────────────────────────────────────────────────────────────
_cache = {}


def _get_cached(key: str, ttl: int):
    if key in _cache:
        value, timestamp = _cache[key]
        if time.time() - timestamp < ttl:
            return value
    return None


def _set_cache(key: str, value):
    _cache[key] = (value, time.time())


def _format_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not symbol.endswith(".NS") and not symbol.endswith(".BO") and not symbol.startswith("^"):
        return f"{symbol}.NS"
    return symbol


# ─── Black-Scholes from Scratch ─────────────────────────────────────────────
# Pure mathematical implementation — no finance libraries used.


def _norm_cdf(x: float) -> float:
    """
    Cumulative distribution function of standard normal distribution.
    Implemented using Python's math.erf (standard library).
    N(x) = 0.5 * (1 + erf(x / sqrt(2)))
    """
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    """
    Probability density function of standard normal distribution.
    n(x) = (1 / sqrt(2π)) * e^(-x²/2)
    """
    return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)


def black_scholes_price(S: float, K: float, r: float, sigma: float, T: float, option_type: str) -> float:
    """
    Black-Scholes option pricing formula.
    S: Spot price
    K: Strike price
    r: Risk-free rate
    sigma: Volatility (annualized)
    T: Time to expiry (in years)
    option_type: 'CE' (Call) or 'PE' (Put)
    """
    if T <= 0:
        # At expiry
        if option_type.upper() == "CE":
            return max(S - K, 0)
        else:
            return max(K - S, 0)

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type.upper() == "CE":
        price = S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    else:
        price = K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)

    return price


def black_scholes_greeks(S: float, K: float, r: float, sigma: float, T: float, option_type: str) -> dict:
    """
    Calculate all Greeks from scratch using Black-Scholes.
    Returns: delta, gamma, theta, vega, option_price

    All formulas implemented from first principles:
    - d1 = (ln(S/K) + (r + σ²/2)T) / (σ√T)
    - d2 = d1 - σ√T
    - Delta (CE) = N(d1), Delta (PE) = N(d1) - 1
    - Gamma = n(d1) / (S · σ · √T)
    - Vega = S · n(d1) · √T
    - Theta (CE) = -(S·n(d1)·σ)/(2√T) - r·K·e^(-rT)·N(d2)
    - Theta (PE) = -(S·n(d1)·σ)/(2√T) + r·K·e^(-rT)·N(-d2)
    """
    if T <= 0:
        # At expiry — all greeks are 0 except delta at the money
        intrinsic = max(S - K, 0) if option_type.upper() == "CE" else max(K - S, 0)
        return {
            "delta": 1.0 if (option_type.upper() == "CE" and S > K) else (-1.0 if (option_type.upper() == "PE" and S < K) else 0.0),
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0,
            "option_price": round(intrinsic, 4),
            "inputs": {
                "spot_price": S, "strike_price": K, "risk_free_rate": r,
                "volatility": sigma, "time_to_expiry_years": T, "option_type": option_type.upper()
            }
        }

    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    nd1 = _norm_pdf(d1)   # n(d1) — PDF
    Nd1 = _norm_cdf(d1)   # N(d1) — CDF
    Nd2 = _norm_cdf(d2)   # N(d2)

    # ── Delta ──
    if option_type.upper() == "CE":
        delta = Nd1
    else:
        delta = Nd1 - 1.0

    # ── Gamma (same for calls and puts) ──
    gamma = nd1 / (S * sigma * sqrt_T)

    # ── Vega ──
    # Vega per 1% move = S * n(d1) * √T / 100
    vega = S * nd1 * sqrt_T / 100.0

    # ── Theta ──
    # Theta per day = (annual theta / 365)
    if option_type.upper() == "CE":
        theta_annual = (-(S * nd1 * sigma) / (2.0 * sqrt_T)
                        - r * K * math.exp(-r * T) * Nd2)
    else:
        theta_annual = (-(S * nd1 * sigma) / (2.0 * sqrt_T)
                        + r * K * math.exp(-r * T) * _norm_cdf(-d2))

    theta_daily = theta_annual / 365.0

    # ── Option Price ──
    price = black_scholes_price(S, K, r, sigma, T, option_type)

    return {
        "delta": round(delta, 6),
        "gamma": round(gamma, 6),
        "theta": round(theta_daily, 6),
        "vega": round(vega, 6),
        "option_price": round(price, 4),
        "inputs": {
            "spot_price": S,
            "strike_price": K,
            "risk_free_rate": r,
            "volatility": sigma,
            "time_to_expiry_years": round(T, 6),
            "option_type": option_type.upper()
        }
    }


def calculate_greeks(symbol: str, strike: float, expiry: str, option_type: str,
                     spot_price: float = None, volatility: float = None) -> dict:
    """
    Calculate Greeks for a specific option contract.
    If spot_price not provided, fetches live price.
    If volatility not provided, calculates historical volatility.
    """
    from market_data import get_live_price, get_historical_ohlc
    import datetime

    # Get spot price if not provided
    if spot_price is None:
        price_data = get_live_price(symbol)
        if "error" in price_data:
            return price_data
        spot_price = price_data["price"]

    # Calculate historical volatility if not provided
    if volatility is None:
        hist = get_historical_ohlc(symbol, period="3mo", interval="1d")
        if "error" in hist:
            volatility = 0.25  # Default 25% if can't calculate
        else:
            import numpy as np
            closes = [d["close"] for d in hist["data"]]
            if len(closes) > 1:
                returns = np.diff(np.log(closes))
                volatility = float(np.std(returns) * math.sqrt(252))
            else:
                volatility = 0.25

    # Calculate time to expiry in years
    try:
        if isinstance(expiry, str):
            expiry_date = datetime.datetime.strptime(expiry, "%Y-%m-%d").date()
        else:
            expiry_date = expiry
        today = datetime.date.today()
        days_to_expiry = (expiry_date - today).days
        T = max(days_to_expiry / 365.0, 1 / 365.0)  # Minimum 1 day
    except Exception:
        T = 30 / 365.0  # Default 30 days if parsing fails

    greeks = black_scholes_greeks(spot_price, strike, RISK_FREE_RATE, volatility, T, option_type)
    greeks["symbol"] = symbol.upper()
    greeks["days_to_expiry"] = days_to_expiry if 'days_to_expiry' in dir() else 30

    return greeks


# ─── Options Chain ──────────────────────────────────────────────────────────


def get_options_chain(symbol: str, expiry: str = None) -> dict:
    """
    Pull live options chain using yfinance options API.
    Returns strikes, CE/PE data with OI, volume, last price.
    """
    cache_key = f"options:{symbol}:{expiry}"
    cached = _get_cached(cache_key, CACHE_TTL_OPTIONS)
    if cached:
        return cached

    formatted = _format_symbol(symbol)
    ticker = yf.Ticker(formatted)

    try:
        # Get available expiry dates
        expiries = ticker.options
        if not expiries:
            return {"error": f"No options data available for {symbol}. yfinance may not have options for this NSE symbol."}

        # Select expiry
        if expiry and expiry in expiries:
            selected_expiry = expiry
        else:
            selected_expiry = expiries[0]  # Nearest expiry

        # Fetch option chain
        chain = ticker.option_chain(selected_expiry)
        calls_df = chain.calls
        puts_df = chain.puts

        calls = []
        for _, row in calls_df.iterrows():
            calls.append({
                "strike": float(row.get("strike", 0)),
                "lastPrice": float(row.get("lastPrice", 0)),
                "bid": float(row.get("bid", 0)),
                "ask": float(row.get("ask", 0)),
                "volume": int(row.get("volume", 0)) if not (isinstance(row.get("volume"), float) and math.isnan(row.get("volume", 0))) else 0,
                "openInterest": int(row.get("openInterest", 0)) if not (isinstance(row.get("openInterest"), float) and math.isnan(row.get("openInterest", 0))) else 0,
                "impliedVolatility": round(float(row.get("impliedVolatility", 0)), 4),
            })

        puts = []
        for _, row in puts_df.iterrows():
            puts.append({
                "strike": float(row.get("strike", 0)),
                "lastPrice": float(row.get("lastPrice", 0)),
                "bid": float(row.get("bid", 0)),
                "ask": float(row.get("ask", 0)),
                "volume": int(row.get("volume", 0)) if not (isinstance(row.get("volume"), float) and math.isnan(row.get("volume", 0))) else 0,
                "openInterest": int(row.get("openInterest", 0)) if not (isinstance(row.get("openInterest"), float) and math.isnan(row.get("openInterest", 0))) else 0,
                "impliedVolatility": round(float(row.get("impliedVolatility", 0)), 4),
            })

        result = {
            "symbol": symbol.upper(),
            "expiry": selected_expiry,
            "available_expiries": list(expiries),
            "calls": calls,
            "puts": puts,
            "total_call_oi": sum(c["openInterest"] for c in calls),
            "total_put_oi": sum(p["openInterest"] for p in puts),
            "pcr": round(sum(p["openInterest"] for p in puts) / max(sum(c["openInterest"] for c in calls), 1), 4),
        }

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        return {"error": f"Failed to fetch options chain for {symbol}: {str(e)}"}


# ─── Max Pain Calculation ───────────────────────────────────────────────────


def calculate_max_pain(symbol: str, expiry: str = None) -> dict:
    """
    Calculate max pain point for an expiry.
    Max pain = strike where option writers (sellers) have minimum total loss.
    For each strike K:
      - Call writer loss at price P: sum over all call strikes S <= P of (P - S) * call_OI_at_S
      - Put writer loss at price P: sum over all put strikes S >= P of (S - P) * put_OI_at_S
      - Total pain at K = call_writer_loss + put_writer_loss
    Max pain = strike with minimum total pain.
    """
    chain = get_options_chain(symbol, expiry)
    if "error" in chain:
        return chain

    calls = chain["calls"]
    puts = chain["puts"]

    if not calls and not puts:
        return {"error": "No options data to calculate max pain."}

    # Get all unique strikes
    all_strikes = sorted(set(
        [c["strike"] for c in calls] + [p["strike"] for p in puts]
    ))

    min_pain = float("inf")
    max_pain_strike = 0
    pain_by_strike = []

    for test_price in all_strikes:
        total_pain = 0.0

        # Pain from call options (losses for call writers if price > strike)
        for call in calls:
            if test_price > call["strike"]:
                total_pain += (test_price - call["strike"]) * call["openInterest"]

        # Pain from put options (losses for put writers if price < strike)
        for put in puts:
            if test_price < put["strike"]:
                total_pain += (put["strike"] - test_price) * put["openInterest"]

        pain_by_strike.append({
            "strike": test_price,
            "total_pain": round(total_pain, 2)
        })

        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = test_price

    return {
        "symbol": symbol.upper(),
        "expiry": chain["expiry"],
        "max_pain_strike": max_pain_strike,
        "total_call_oi": chain["total_call_oi"],
        "total_put_oi": chain["total_put_oi"],
        "pcr": chain["pcr"],
        "pain_by_strike": pain_by_strike,
    }


# ─── Unusual Activity Detection ────────────────────────────────────────────


def detect_unusual_activity(symbol: str) -> dict:
    """
    Detect unusual options activity via volume/OI spike detection.
    Flags strikes where:
    - volume > 2× average volume across all strikes
    - OI is significantly higher than mean (> 2 standard deviations)
    """
    chain = get_options_chain(symbol)
    if "error" in chain:
        return chain

    alerts = []

    for option_type, options in [("CE", chain["calls"]), ("PE", chain["puts"])]:
        if not options:
            continue

        volumes = [o["volume"] for o in options]
        ois = [o["openInterest"] for o in options]

        avg_volume = sum(volumes) / len(volumes) if volumes else 0
        avg_oi = sum(ois) / len(ois) if ois else 0

        # Standard deviation for OI
        if len(ois) > 1:
            mean_oi = sum(ois) / len(ois)
            variance = sum((x - mean_oi) ** 2 for x in ois) / len(ois)
            std_oi = variance ** 0.5
        else:
            std_oi = 0

        for opt in options:
            anomalies = []

            # Volume spike: volume > 2× average
            if avg_volume > 0 and opt["volume"] > 2 * avg_volume:
                anomalies.append(f"Volume spike: {opt['volume']} vs avg {round(avg_volume)}")

            # OI spike: OI > mean + 2σ
            if std_oi > 0 and opt["openInterest"] > avg_oi + 2 * std_oi:
                anomalies.append(f"OI spike: {opt['openInterest']} vs avg {round(avg_oi)} (2σ = {round(2 * std_oi)})")

            if anomalies:
                alerts.append({
                    "strike": opt["strike"],
                    "type": option_type,
                    "volume": opt["volume"],
                    "openInterest": opt["openInterest"],
                    "lastPrice": opt["lastPrice"],
                    "impliedVolatility": opt["impliedVolatility"],
                    "anomalies": anomalies,
                })

    return {
        "symbol": symbol.upper(),
        "expiry": chain["expiry"],
        "total_alerts": len(alerts),
        "alerts": alerts,
        "summary": f"Found {len(alerts)} unusual activity alerts for {symbol.upper()}" if alerts else f"No unusual activity detected for {symbol.upper()}",
    }
