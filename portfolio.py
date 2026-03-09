"""
IndiaQuant MCP 4 — Module 4: Portfolio Risk Manager
Maintain a virtual portfolio with positions and cash balance (SQLite).
Real-time P&L calculation using live prices.
Auto stop-loss and target management.
Risk score per position based on historical volatility.
"""

import sqlite3
import uuid
import math
import datetime
import numpy as np
from config import DB_PATH, INITIAL_CASH


# ─── Database Initialization ────────────────────────────────────────────────


def _get_db():
    """Get database connection and ensure tables exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Create tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS account (
            id INTEGER PRIMARY KEY DEFAULT 1,
            cash_balance REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            qty INTEGER NOT NULL,
            side TEXT NOT NULL,
            avg_price REAL NOT NULL,
            stop_loss REAL,
            target REAL,
            timestamp TEXT NOT NULL,
            status TEXT DEFAULT 'OPEN'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            qty INTEGER NOT NULL,
            side TEXT NOT NULL,
            price REAL NOT NULL,
            timestamp TEXT NOT NULL,
            order_id TEXT NOT NULL,
            status TEXT DEFAULT 'EXECUTED'
        )
    """)

    # Initialize account if not exists
    cursor.execute("SELECT COUNT(*) FROM account")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO account (id, cash_balance) VALUES (1, ?)", (INITIAL_CASH,))

    conn.commit()
    return conn


# ─── Virtual Trading ────────────────────────────────────────────────────────


def place_virtual_trade(symbol: str, qty: int, side: str,
                        stop_loss: float = None, target: float = None) -> dict:
    """
    Place a virtual trade.
    symbol: Stock symbol
    qty: Number of shares
    side: 'BUY' or 'SELL'
    stop_loss: Optional stop-loss price
    target: Optional target price
    Returns: order_id, status
    """
    from market_data import get_live_price

    side = side.upper()
    if side not in ("BUY", "SELL"):
        return {"error": "Side must be 'BUY' or 'SELL'"}

    if qty <= 0:
        return {"error": "Quantity must be positive"}

    # Get live price
    price_data = get_live_price(symbol)
    if "error" in price_data:
        return price_data

    current_price = price_data["price"]
    total_value = current_price * qty

    conn = _get_db()
    cursor = conn.cursor()

    try:
        # Check cash balance for BUY
        cursor.execute("SELECT cash_balance FROM account WHERE id = 1")
        cash = cursor.fetchone()["cash_balance"]

        if side == "BUY" and total_value > cash:
            conn.close()
            return {
                "error": f"Insufficient balance. Required: ₹{total_value:,.2f}, Available: ₹{cash:,.2f}"
            }

        # For SELL, check if position exists
        if side == "SELL":
            cursor.execute(
                "SELECT * FROM positions WHERE symbol = ? AND side = 'BUY' AND status = 'OPEN'",
                (symbol.upper(),)
            )
            position = cursor.fetchone()
            if not position or position["qty"] < qty:
                conn.close()
                return {"error": f"No sufficient open BUY position for {symbol} to sell {qty} shares."}

        order_id = str(uuid.uuid4())[:8].upper()
        position_id = str(uuid.uuid4())[:12].upper()
        now = datetime.datetime.now().isoformat()

        # Auto stop-loss: 5% below buy price if not specified
        if stop_loss is None and side == "BUY":
            stop_loss = round(current_price * 0.95, 2)

        # Auto target: 10% above buy price if not specified
        if target is None and side == "BUY":
            target = round(current_price * 1.10, 2)

        if side == "BUY":
            # Create position
            cursor.execute("""
                INSERT INTO positions (id, symbol, qty, side, avg_price, stop_loss, target, timestamp, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
            """, (position_id, symbol.upper(), qty, side, current_price, stop_loss, target, now))

            # Deduct cash
            cursor.execute("UPDATE account SET cash_balance = cash_balance - ? WHERE id = 1", (total_value,))

        elif side == "SELL":
            # Close or reduce position
            cursor.execute(
                "SELECT * FROM positions WHERE symbol = ? AND side = 'BUY' AND status = 'OPEN' ORDER BY timestamp",
                (symbol.upper(),)
            )
            positions = cursor.fetchall()

            remaining_qty = qty
            for pos in positions:
                if remaining_qty <= 0:
                    break
                if pos["qty"] <= remaining_qty:
                    cursor.execute("UPDATE positions SET status = 'CLOSED' WHERE id = ?", (pos["id"],))
                    remaining_qty -= pos["qty"]
                else:
                    cursor.execute("UPDATE positions SET qty = qty - ? WHERE id = ?", (remaining_qty, pos["id"]))
                    remaining_qty = 0

            # Add cash from sale
            cursor.execute("UPDATE account SET cash_balance = cash_balance + ? WHERE id = 1", (total_value,))

        # Record trade
        trade_id = str(uuid.uuid4())[:8].upper()
        cursor.execute("""
            INSERT INTO trades (id, symbol, qty, side, price, timestamp, order_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'EXECUTED')
        """, (trade_id, symbol.upper(), qty, side, current_price, now, order_id))

        conn.commit()

        result = {
            "order_id": order_id,
            "status": "EXECUTED",
            "symbol": symbol.upper(),
            "side": side,
            "qty": qty,
            "price": current_price,
            "total_value": round(total_value, 2),
            "stop_loss": stop_loss,
            "target": target,
            "timestamp": now,
        }

        # Get updated balance
        cursor.execute("SELECT cash_balance FROM account WHERE id = 1")
        result["remaining_cash"] = round(cursor.fetchone()["cash_balance"], 2)

        conn.close()
        return result

    except Exception as e:
        conn.close()
        return {"error": f"Trade execution failed: {str(e)}"}


# ─── Portfolio P&L ──────────────────────────────────────────────────────────


def get_portfolio_pnl() -> dict:
    """
    Real-time P&L calculation using live prices.
    Returns positions and total P&L with auto stop-loss management.
    """
    from market_data import get_live_price, get_historical_ohlc

    conn = _get_db()
    cursor = conn.cursor()

    try:
        # Get cash balance
        cursor.execute("SELECT cash_balance FROM account WHERE id = 1")
        cash = cursor.fetchone()["cash_balance"]

        # Get all open positions
        cursor.execute("SELECT * FROM positions WHERE status = 'OPEN'")
        positions = cursor.fetchall()

        position_details = []
        total_invested = 0.0
        total_current = 0.0
        total_pnl = 0.0

        for pos in positions:
            symbol = pos["symbol"]
            qty = pos["qty"]
            avg_price = pos["avg_price"]
            stop_loss = pos["stop_loss"]
            target = pos["target"]

            # Fetch live price
            price_data = get_live_price(symbol)
            if "error" in price_data:
                continue

            current_price = price_data["price"]
            invested = avg_price * qty
            current_value = current_price * qty
            pnl = current_value - invested
            pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

            # Auto stop-loss check
            stop_loss_hit = False
            target_hit = False
            if stop_loss and current_price <= stop_loss:
                stop_loss_hit = True
                # Auto-close position
                cursor.execute("UPDATE positions SET status = 'CLOSED_SL' WHERE id = ?", (pos["id"],))
                cursor.execute("UPDATE account SET cash_balance = cash_balance + ? WHERE id = 1", (current_value,))
                conn.commit()

            if target and current_price >= target:
                target_hit = True

            # Calculate risk score based on historical volatility
            risk_score = _calculate_risk_score(symbol)

            total_invested += invested
            total_current += current_value
            total_pnl += pnl

            position_details.append({
                "position_id": pos["id"],
                "symbol": symbol,
                "qty": qty,
                "side": pos["side"],
                "avg_price": round(avg_price, 2),
                "current_price": round(current_price, 2),
                "invested_value": round(invested, 2),
                "current_value": round(current_value, 2),
                "pnl": round(pnl, 2),
                "pnl_percent": round(pnl_pct, 2),
                "stop_loss": stop_loss,
                "target": target,
                "stop_loss_hit": stop_loss_hit,
                "target_hit": target_hit,
                "risk_score": risk_score,
                "opened_at": pos["timestamp"],
            })

        # Get recent trades
        cursor.execute("SELECT * FROM trades ORDER BY timestamp DESC LIMIT 10")
        recent_trades = [dict(t) for t in cursor.fetchall()]

        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0

        result = {
            "portfolio_summary": {
                "total_positions": len(position_details),
                "total_invested": round(total_invested, 2),
                "total_current_value": round(total_current, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_percent": round(total_pnl_pct, 2),
                "cash_balance": round(cash, 2),
                "portfolio_value": round(cash + total_current, 2),
            },
            "positions": position_details,
            "recent_trades": recent_trades,
        }

        conn.close()
        return result

    except Exception as e:
        conn.close()
        return {"error": f"Failed to compute portfolio P&L: {str(e)}"}


# ─── Risk Score Calculation ─────────────────────────────────────────────────


def _calculate_risk_score(symbol: str) -> dict:
    """
    Risk score per position based on historical volatility.
    annualized_volatility = std(daily_returns) × √252
    Score mapped to 1-10 scale.
    """
    from market_data import get_historical_ohlc

    hist = get_historical_ohlc(symbol, period="3mo", interval="1d")
    if "error" in hist or len(hist.get("data", [])) < 10:
        return {"score": 5, "volatility": "N/A", "label": "MODERATE (insufficient data)"}

    closes = [d["close"] for d in hist["data"]]
    returns = np.diff(np.log(closes))
    daily_vol = float(np.std(returns))
    annualized_vol = daily_vol * math.sqrt(252)

    # Map volatility to 1-10 score
    # < 15% → Low (1-3), 15-30% → Moderate (4-6), 30-50% → High (7-8), > 50% → Very High (9-10)
    if annualized_vol < 0.10:
        score = 1
        label = "VERY LOW"
    elif annualized_vol < 0.15:
        score = 2
        label = "LOW"
    elif annualized_vol < 0.20:
        score = 3
        label = "LOW-MODERATE"
    elif annualized_vol < 0.25:
        score = 4
        label = "MODERATE"
    elif annualized_vol < 0.30:
        score = 5
        label = "MODERATE"
    elif annualized_vol < 0.35:
        score = 6
        label = "MODERATE-HIGH"
    elif annualized_vol < 0.40:
        score = 7
        label = "HIGH"
    elif annualized_vol < 0.50:
        score = 8
        label = "HIGH"
    elif annualized_vol < 0.60:
        score = 9
        label = "VERY HIGH"
    else:
        score = 10
        label = "EXTREME"

    return {
        "score": score,
        "annualized_volatility": round(annualized_vol * 100, 2),
        "daily_volatility": round(daily_vol * 100, 4),
        "label": label,
    }
