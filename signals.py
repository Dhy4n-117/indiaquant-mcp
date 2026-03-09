"""
IndiaQuant MCP 4 — Module 2: AI Trade Signal Generator
Compute RSI, MACD, Bollinger Bands using TA-Lib / pandas-ta logic.
Detect chart patterns: Head & Shoulders, Double Top/Bottom.
Run sentiment analysis on NewsAPI headlines.
Output BUY/SELL/HOLD signal with confidence score (0-100%).

Note: Technical indicators are implemented directly with pandas/numpy
for maximum compatibility (TA-Lib/pandas-ta formulas, no external TA dependency).
"""

import time
import requests
import pandas as pd
import numpy as np
from config import NEWSAPI_KEY, CACHE_TTL_NEWS

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


# ─── Technical Indicator Implementations ────────────────────────────────────
# RSI, MACD, Bollinger Bands — standard TA-Lib formulas computed with pandas/numpy.


def _compute_rsi(closes: pd.Series, length: int = 14) -> pd.Series:
    """RSI (Relative Strength Index) — Wilder's smoothing method."""
    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1.0 / length, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1.0 / length, min_periods=length).mean()

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def _compute_macd(closes: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD (Moving Average Convergence Divergence)."""
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _compute_bollinger(closes: pd.Series, length: int = 20, std_dev: float = 2.0):
    """Bollinger Bands (SMA ± n standard deviations)."""
    middle = closes.rolling(window=length).mean()
    rolling_std = closes.rolling(window=length).std()
    upper = middle + std_dev * rolling_std
    lower = middle - std_dev * rolling_std
    return upper, middle, lower


# ─── Technical Analysis ────────────────────────────────────────────────────


def compute_technicals(symbol: str, period: str = "3mo", interval: str = "1d") -> dict:
    """
    Compute RSI, MACD, Bollinger Bands.
    Returns indicator values and their interpretations.
    """
    from market_data import get_historical_ohlc

    hist = get_historical_ohlc(symbol, period=period, interval=interval)
    if "error" in hist:
        return hist

    data = hist["data"]
    if len(data) < 30:
        return {"error": f"Insufficient data for technical analysis ({len(data)} points, need 30+)."}

    df = pd.DataFrame(data)
    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["volume"] = df["volume"].astype(float)

    # RSI (14-period)
    rsi_series = _compute_rsi(df["close"], length=14)
    current_rsi = round(float(rsi_series.iloc[-1]), 2) if not rsi_series.empty and not pd.isna(rsi_series.iloc[-1]) else None

    # MACD (12, 26, 9)
    macd_line_s, signal_line_s, histogram_s = _compute_macd(df["close"], 12, 26, 9)
    if not macd_line_s.empty and not pd.isna(macd_line_s.iloc[-1]):
        macd_line = round(float(macd_line_s.iloc[-1]), 4)
        macd_signal = round(float(signal_line_s.iloc[-1]), 4)
        macd_histogram = round(float(histogram_s.iloc[-1]), 4)

        prev_macd_line = round(float(macd_line_s.iloc[-2]), 4) if len(macd_line_s) >= 2 else macd_line
        prev_macd_signal = round(float(signal_line_s.iloc[-2]), 4) if len(signal_line_s) >= 2 else macd_signal

        macd_crossover = "BULLISH" if (prev_macd_line <= prev_macd_signal and macd_line > macd_signal) else \
                         "BEARISH" if (prev_macd_line >= prev_macd_signal and macd_line < macd_signal) else "NONE"
    else:
        macd_line = macd_histogram = macd_signal = None
        macd_crossover = "NONE"

    # Bollinger Bands (20, 2σ)
    bb_upper_s, bb_middle_s, bb_lower_s = _compute_bollinger(df["close"], 20, 2.0)
    if not bb_upper_s.empty and not pd.isna(bb_upper_s.iloc[-1]):
        bb_upper = round(float(bb_upper_s.iloc[-1]), 2)
        bb_middle = round(float(bb_middle_s.iloc[-1]), 2)
        bb_lower = round(float(bb_lower_s.iloc[-1]), 2)
        current_price = float(df["close"].iloc[-1])

        if current_price > bb_upper:
            bb_signal = "OVERBOUGHT"
        elif current_price < bb_lower:
            bb_signal = "OVERSOLD"
        else:
            bb_signal = "NEUTRAL"

        bb_width = round((bb_upper - bb_lower) / bb_middle * 100, 2) if bb_middle > 0 else 0
    else:
        bb_upper = bb_middle = bb_lower = None
        bb_signal = "NEUTRAL"
        bb_width = 0

    # RSI interpretation
    if current_rsi is not None:
        if current_rsi < 30:
            rsi_signal = "OVERSOLD"
        elif current_rsi > 70:
            rsi_signal = "OVERBOUGHT"
        else:
            rsi_signal = "NEUTRAL"
    else:
        rsi_signal = "UNKNOWN"

    return {
        "symbol": symbol.upper(),
        "rsi": {"value": current_rsi, "signal": rsi_signal},
        "macd": {
            "macd_line": macd_line,
            "signal_line": macd_signal,
            "histogram": macd_histogram,
            "crossover": macd_crossover,
        },
        "bollinger_bands": {
            "upper": bb_upper,
            "middle": bb_middle,
            "lower": bb_lower,
            "signal": bb_signal,
            "bandwidth_pct": bb_width,
        },
        "current_price": round(float(df["close"].iloc[-1]), 2),
    }


# ─── Chart Pattern Detection ───────────────────────────────────────────────


def detect_patterns(symbol: str) -> dict:
    """
    Detect chart patterns: Head & Shoulders, Double Top/Bottom.
    Uses local minima/maxima on close prices.
    """
    from market_data import get_historical_ohlc

    hist = get_historical_ohlc(symbol, period="6mo", interval="1d")
    if "error" in hist:
        return hist

    closes = [d["close"] for d in hist["data"]]
    if len(closes) < 30:
        return {"patterns": [], "message": "Insufficient data for pattern detection."}

    patterns = []

    # Find local maxima and minima (using 5-day window)
    window = 5
    maxima = []
    minima = []

    for i in range(window, len(closes) - window):
        if closes[i] == max(closes[i - window:i + window + 1]):
            maxima.append((i, closes[i]))
        if closes[i] == min(closes[i - window:i + window + 1]):
            minima.append((i, closes[i]))

    # ── Double Top Detection ──
    for i in range(len(maxima) - 1):
        idx1, peak1 = maxima[i]
        idx2, peak2 = maxima[i + 1]

        if abs(peak1 - peak2) / peak1 < 0.02 and idx2 - idx1 > 10:
            trough = min(closes[idx1:idx2])
            if trough < peak1 * 0.95:
                patterns.append({
                    "pattern": "DOUBLE_TOP",
                    "signal": "BEARISH",
                    "confidence": round(min(85, 70 + (1 - abs(peak1 - peak2) / peak1) * 50), 1),
                    "peak1_price": round(peak1, 2),
                    "peak2_price": round(peak2, 2),
                    "trough_price": round(trough, 2),
                    "description": f"Double top detected at ~₹{round(peak1, 2)}. Bearish reversal signal.",
                })

    # ── Double Bottom Detection ──
    for i in range(len(minima) - 1):
        idx1, trough1 = minima[i]
        idx2, trough2 = minima[i + 1]

        if abs(trough1 - trough2) / trough1 < 0.02 and idx2 - idx1 > 10:
            peak = max(closes[idx1:idx2])
            if peak > trough1 * 1.05:
                patterns.append({
                    "pattern": "DOUBLE_BOTTOM",
                    "signal": "BULLISH",
                    "confidence": round(min(85, 70 + (1 - abs(trough1 - trough2) / trough1) * 50), 1),
                    "trough1_price": round(trough1, 2),
                    "trough2_price": round(trough2, 2),
                    "peak_price": round(peak, 2),
                    "description": f"Double bottom detected at ~₹{round(trough1, 2)}. Bullish reversal signal.",
                })

    # ── Head & Shoulders Detection ──
    for i in range(len(maxima) - 2):
        idx1, left_shoulder = maxima[i]
        idx2, head = maxima[i + 1]
        idx3, right_shoulder = maxima[i + 2]

        if (head > left_shoulder and head > right_shoulder and
                abs(left_shoulder - right_shoulder) / left_shoulder < 0.05 and
                idx3 - idx1 > 20):
            patterns.append({
                "pattern": "HEAD_AND_SHOULDERS",
                "signal": "BEARISH",
                "confidence": round(min(90, 75 + (head - max(left_shoulder, right_shoulder)) / head * 100), 1),
                "left_shoulder": round(left_shoulder, 2),
                "head": round(head, 2),
                "right_shoulder": round(right_shoulder, 2),
                "description": f"Head & Shoulders at head ₹{round(head, 2)}. Strong bearish reversal.",
            })

    # ── Inverse Head & Shoulders ──
    for i in range(len(minima) - 2):
        idx1, left_shoulder = minima[i]
        idx2, head = minima[i + 1]
        idx3, right_shoulder = minima[i + 2]

        if (head < left_shoulder and head < right_shoulder and
                abs(left_shoulder - right_shoulder) / left_shoulder < 0.05 and
                idx3 - idx1 > 20):
            patterns.append({
                "pattern": "INVERSE_HEAD_AND_SHOULDERS",
                "signal": "BULLISH",
                "confidence": round(min(90, 75 + (min(left_shoulder, right_shoulder) - head) / head * 100), 1),
                "left_shoulder": round(left_shoulder, 2),
                "head": round(head, 2),
                "right_shoulder": round(right_shoulder, 2),
                "description": f"Inverse H&S at head ₹{round(head, 2)}. Strong bullish reversal.",
            })

    return {
        "symbol": symbol.upper(),
        "patterns_detected": len(patterns),
        "patterns": patterns,
    }


# ─── Sentiment Analysis ────────────────────────────────────────────────────

POSITIVE_WORDS = [
    "surge", "rally", "gain", "profit", "growth", "bullish", "upgrade", "outperform",
    "beat", "record", "high", "strong", "positive", "boom", "soar", "rise", "up",
    "buy", "opportunity", "momentum", "breakout", "recovery", "dividend", "expansion",
    "revenue", "earnings", "target", "recommend", "optimistic", "favorable"
]

NEGATIVE_WORDS = [
    "crash", "fall", "loss", "bearish", "downgrade", "underperform", "miss", "low",
    "weak", "negative", "decline", "drop", "sell", "risk", "warning", "debt",
    "cut", "slash", "concern", "fear", "volatile", "plunge", "slump", "recession",
    "default", "fraud", "investigation", "penalty", "lawsuit", "bankruptcy"
]


def analyze_sentiment(symbol: str) -> dict:
    """
    Run sentiment analysis on NewsAPI headlines.
    Returns sentiment score (-1.0 to +1.0), headlines, and signal.
    """
    cache_key = f"sentiment:{symbol}"
    cached = _get_cached(cache_key, CACHE_TTL_NEWS)
    if cached:
        return cached

    if not NEWSAPI_KEY:
        return {
            "error": "NEWSAPI_KEY not set. Please set the NEWSAPI_KEY environment variable with your free NewsAPI.org key.",
            "symbol": symbol.upper(),
        }

    company_name = symbol.replace(".NS", "").replace(".BO", "").upper()
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": f"{company_name} stock India",
        "apiKey": NEWSAPI_KEY,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 20,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if data.get("status") != "ok":
            return {"error": f"NewsAPI error: {data.get('message', 'Unknown error')}", "symbol": symbol.upper()}

        articles = data.get("articles", [])
        if not articles:
            return {
                "symbol": symbol.upper(),
                "sentiment_score": 0.0,
                "signal": "NEUTRAL",
                "headlines": [],
                "articles_analyzed": 0,
                "message": "No recent news found.",
            }

        scored_headlines = []
        total_score = 0.0

        for article in articles:
            title = article.get("title", "") or ""
            description = article.get("description", "") or ""
            text = (title + " " + description).lower()

            pos_count = sum(1 for w in POSITIVE_WORDS if w in text)
            neg_count = sum(1 for w in NEGATIVE_WORDS if w in text)

            if pos_count + neg_count > 0:
                score = (pos_count - neg_count) / (pos_count + neg_count)
            else:
                score = 0.0

            total_score += score
            scored_headlines.append({
                "title": title,
                "source": article.get("source", {}).get("name", "Unknown"),
                "published_at": article.get("publishedAt", ""),
                "sentiment": round(score, 3),
                "url": article.get("url", ""),
            })

        avg_score = total_score / len(articles) if articles else 0.0
        avg_score = max(-1.0, min(1.0, avg_score))

        if avg_score > 0.15:
            signal = "BULLISH"
        elif avg_score < -0.15:
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"

        result = {
            "symbol": symbol.upper(),
            "sentiment_score": round(avg_score, 4),
            "signal": signal,
            "articles_analyzed": len(articles),
            "positive_mentions": sum(1 for h in scored_headlines if h["sentiment"] > 0),
            "negative_mentions": sum(1 for h in scored_headlines if h["sentiment"] < 0),
            "neutral_mentions": sum(1 for h in scored_headlines if h["sentiment"] == 0),
            "headlines": scored_headlines[:10],
        }

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        return {"error": f"Failed to fetch news for {symbol}: {str(e)}", "symbol": symbol.upper()}


# ─── Composite Signal Generator ────────────────────────────────────────────


def generate_signal(symbol: str, timeframe: str = "1d") -> dict:
    """
    Generate BUY/SELL/HOLD signal with confidence score (0-100%).
    Combines technicals (60%) + sentiment (40%).
    """
    timeframe_map = {
        "1d": ("3mo", "1d"),
        "1h": ("1mo", "1h"),
        "15m": ("5d", "15m"),
        "5m": ("1d", "5m"),
        "1wk": ("1y", "1wk"),
    }
    period, interval = timeframe_map.get(timeframe, ("3mo", "1d"))

    technicals = compute_technicals(symbol, period=period, interval=interval)
    if "error" in technicals:
        return technicals

    sentiment = analyze_sentiment(symbol)
    patterns = detect_patterns(symbol)

    # ── Technical Score: -100 to +100 ──
    tech_score = 0.0
    tech_signals = []

    # RSI contribution
    rsi_data = technicals["rsi"]
    if rsi_data["value"] is not None:
        if rsi_data["signal"] == "OVERSOLD":
            tech_score += 30
            tech_signals.append(f"RSI {rsi_data['value']} (Oversold → Bullish)")
        elif rsi_data["signal"] == "OVERBOUGHT":
            tech_score -= 30
            tech_signals.append(f"RSI {rsi_data['value']} (Overbought → Bearish)")
        else:
            rsi_adj = (50 - rsi_data["value"]) * 0.3
            tech_score += rsi_adj
            tech_signals.append(f"RSI {rsi_data['value']} (Neutral)")

    # MACD contribution
    macd_data = technicals["macd"]
    if macd_data["crossover"] == "BULLISH":
        tech_score += 35
        tech_signals.append("MACD Bullish Crossover")
    elif macd_data["crossover"] == "BEARISH":
        tech_score -= 35
        tech_signals.append("MACD Bearish Crossover")
    elif macd_data["histogram"] is not None:
        if macd_data["histogram"] > 0:
            tech_score += 10
            tech_signals.append("MACD Histogram Positive")
        else:
            tech_score -= 10
            tech_signals.append("MACD Histogram Negative")

    # Bollinger Bands contribution
    bb_data = technicals["bollinger_bands"]
    if bb_data["signal"] == "OVERSOLD":
        tech_score += 25
        tech_signals.append("Price below lower Bollinger Band (Oversold)")
    elif bb_data["signal"] == "OVERBOUGHT":
        tech_score -= 25
        tech_signals.append("Price above upper Bollinger Band (Overbought)")

    # Pattern contribution
    if "patterns" in patterns:
        for p in patterns.get("patterns", []):
            if p["signal"] == "BULLISH":
                tech_score += 20
                tech_signals.append(f"Pattern: {p['pattern']} (Bullish)")
            elif p["signal"] == "BEARISH":
                tech_score -= 20
                tech_signals.append(f"Pattern: {p['pattern']} (Bearish)")

    tech_score = max(-100, min(100, tech_score))

    # ── Sentiment Score ──
    sent_score = 0.0
    if "error" not in sentiment:
        sent_score = sentiment.get("sentiment_score", 0.0) * 100

    # ── Weighted Combination: 60% technicals + 40% sentiment ──
    combined_score = tech_score * 0.6 + sent_score * 0.4

    # ── Signal and Confidence ──
    if combined_score > 15:
        signal = "BUY"
        confidence = min(100, int(50 + combined_score * 0.5))
    elif combined_score < -15:
        signal = "SELL"
        confidence = min(100, int(50 + abs(combined_score) * 0.5))
    else:
        signal = "HOLD"
        confidence = int(50 + abs(combined_score) * 0.3)

    confidence = max(0, min(100, confidence))

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "signal": signal,
        "confidence": confidence,
        "combined_score": round(combined_score, 2),
        "technical_score": round(tech_score, 2),
        "sentiment_score": round(sent_score, 2),
        "technical_weight": "60%",
        "sentiment_weight": "40%",
        "technical_signals": tech_signals,
        "technicals": technicals,
        "sentiment": sentiment if "error" not in sentiment else {"message": sentiment.get("error", "Sentiment unavailable")},
        "patterns": patterns.get("patterns", []),
        "current_price": technicals.get("current_price"),
    }


# ─── Market Scanner ────────────────────────────────────────────────────────


def scan_market(filter_criteria: dict) -> dict:
    """
    Scan the market based on filter criteria.
    Supported filters:
    - rsi_below, rsi_above, sector, signal, min_change_pct, max_change_pct
    """
    from market_data import get_live_price
    from config import SECTORS, NIFTY_50

    sector = filter_criteria.get("sector")
    if sector and sector in SECTORS:
        universe = SECTORS[sector]
    else:
        universe = NIFTY_50

    rsi_below = filter_criteria.get("rsi_below")
    rsi_above = filter_criteria.get("rsi_above")
    signal_filter = filter_criteria.get("signal")
    min_change = filter_criteria.get("min_change_pct")
    max_change = filter_criteria.get("max_change_pct")

    matches = []

    for sym in universe:
        try:
            price_data = get_live_price(sym)
            if "error" in price_data:
                continue

            # Change% filters
            change_pct = price_data["change_percent"]
            if min_change is not None and change_pct < min_change:
                continue
            if max_change is not None and change_pct > max_change:
                continue

            # RSI filter
            rsi_val = None
            if rsi_below is not None or rsi_above is not None:
                tech = compute_technicals(sym)
                if "error" in tech:
                    continue
                rsi_val = tech["rsi"]["value"]
                if rsi_val is None:
                    continue
                if rsi_below is not None and rsi_val >= rsi_below:
                    continue
                if rsi_above is not None and rsi_val <= rsi_above:
                    continue

            # Signal filter
            if signal_filter:
                sig = generate_signal(sym)
                if "error" in sig or sig["signal"] != signal_filter.upper():
                    continue
                matches.append({
                    "symbol": sym,
                    "signal": sig["signal"],
                    "confidence": sig["confidence"],
                    "price": sig.get("current_price"),
                    "rsi": sig["technicals"]["rsi"]["value"],
                })
            else:
                match_info = {
                    "symbol": sym,
                    "price": price_data["price"],
                    "change_percent": price_data["change_percent"],
                }
                if rsi_val is not None:
                    match_info["rsi"] = rsi_val
                matches.append(match_info)

        except Exception:
            continue

    return {
        "filter_criteria": filter_criteria,
        "total_scanned": len(universe),
        "matches_found": len(matches),
        "matches": matches,
    }
