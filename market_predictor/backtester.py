# market_predictor/backtester.py
"""
Backtester (v1 - production-style, file-based)

What it does:
- Fetches 15m + 1h OHLCV for a symbol (yfinance via your data_fetcher.py)
- Adds indicators (your indicators.py)
- Walks forward candle-by-candle and calls your strategy:
    strategy.predict_next_candle(df_15m_slice, df_1h_slice)
- If strategy returns a trade (PULLBACK_TREND or BREAKOUT_TREND), it simulates execution:
    - Entry at next candle open (or current close – configurable)
    - SL/TP hit detection within next FUTURE_BARS candles
- Writes:
    - backtest_results.csv
- Optionally builds SQLite pattern library (patterns.db) if pattern modules exist.

How to run:
    python market_predictor/backtester.py
"""

from __future__ import annotations

import os
import math
import json
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple

import pandas as pd

# --- your project modules ---
from market_predictor.data_fetcher import fetch_data
from market_predictor.indicators import add_indicators
from market_predictor import strategy

# --- optional pattern library modules (only if you created them) ---
PATTERN_LIB_ENABLED = True
try:
    from market_predictor.pattern_embedding import make_embedding, FEATURE_VERSION
    from market_predictor.pattern_store import connect as pattern_connect, init_db as pattern_init_db, insert_pattern as pattern_insert
except Exception:
    PATTERN_LIB_ENABLED = False
    make_embedding = None
    FEATURE_VERSION = 0
    pattern_connect = None
    pattern_init_db = None
    pattern_insert = None


# ==========================
# CONFIG
# ==========================
SYMBOL = os.getenv("BACKTEST_SYMBOL", "BTC-USD")

# For a meaningful pattern library:
LOOKBACK_EXEC = os.getenv("LOOKBACK_EXEC", "180d")     # 15m history
LOOKBACK_TREND = os.getenv("LOOKBACK_TREND", "365d")   # 1h history

# Strategy gating
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "75"))

# Execution model
USE_NEXT_OPEN_FOR_ENTRY = True  # entry at next candle Open (more realistic)
FUTURE_BARS = int(os.getenv("FUTURE_BARS", "12"))      # next N 15m candles to check TP/SL
MAX_TRADES = int(os.getenv("MAX_TRADES", "0"))         # 0 = no limit

# Outputs
RESULTS_CSV = os.getenv("BACKTEST_RESULTS_CSV", "backtest_results.csv")

# Pattern library
PATTERN_DB_PATH = os.getenv("PATTERN_DB_PATH", "patterns.db")
EMBED_WINDOW = int(os.getenv("EMBED_WINDOW", "32"))    # last 32x15m candles ~ 8 hours
BATCH_COMMIT = int(os.getenv("PATTERN_BATCH_COMMIT", "200"))

# Timeframe labels used by your system
TF_EXEC = "15m"
TF_TREND = "1h"


# ==========================
# Helpers
# ==========================
def _ensure_flat_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def _safe_float(x, default=math.nan) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _simulate_tp_sl(
    future: pd.DataFrame,
    entry: float,
    sl: float,
    tp: float,
    direction: str,
) -> Tuple[str, int, float]:
    """
    Checks which hits first (TP/SL) using intrabar High/Low.
    Returns: (result, bars_to_hit, exit_price)
        result ∈ {"TP", "SL", "NO_HIT"}
    """
    # direction: "up" means long; "down" means short
    is_long = (direction == "up")

    for j, row in enumerate(future.itertuples(index=False), start=1):
        high = float(getattr(row, "High"))
        low = float(getattr(row, "Low"))

        if is_long:
            # SL hit if low <= sl, TP hit if high >= tp
            sl_hit = low <= sl
            tp_hit = high >= tp
        else:
            # short: SL hit if high >= sl, TP hit if low <= tp
            sl_hit = high >= sl
            tp_hit = low <= tp

        if sl_hit and tp_hit:
            # Conservative: assume SL first (worst-case) to avoid optimistic bias
            return "SL", j, sl
        if sl_hit:
            return "SL", j, sl
        if tp_hit:
            return "TP", j, tp

    # If nothing hit, exit at last close
    exit_price = float(future["Close"].iloc[-1]) if len(future) else entry
    return "NO_HIT", len(future), exit_price


def _r_multiple(entry: float, sl: float, exit_price: float, direction: str) -> float:
    """
    R multiple based on initial risk.
    Long: risk = entry - sl
    Short: risk = sl - entry
    """
    is_long = (direction == "up")
    risk = (entry - sl) if is_long else (sl - entry)
    if risk <= 0:
        return 0.0

    pnl = (exit_price - entry) if is_long else (entry - exit_price)
    return pnl / risk


def _pick_last_closed_1h(ts_15m: pd.Timestamp, df_1h: pd.DataFrame) -> Optional[pd.Timestamp]:
    """Pick the last 1H candle with timestamp <= current 15m candle timestamp."""
    # assumes df_1h index is datetime sorted
    eligible = df_1h.index[df_1h.index <= ts_15m]
    if len(eligible) == 0:
        return None
    return eligible[-1]


# ==========================
# Main backtest
# ==========================
def run_backtest(symbol: str = SYMBOL) -> pd.DataFrame:
    print(f"📥 Backtesting {symbol} | exec={TF_EXEC}({LOOKBACK_EXEC}) trend={TF_TREND}({LOOKBACK_TREND})")

    # Fetch data
    df_15m = fetch_data(symbol, interval=TF_EXEC, period=LOOKBACK_EXEC, only_closed=True)
    df_1h = fetch_data(symbol, interval=TF_TREND, period=LOOKBACK_TREND, only_closed=True)

    if df_15m is None or df_15m.empty or df_1h is None or df_1h.empty:
        raise RuntimeError("❌ Failed to fetch market data for backtest")

    df_15m = _ensure_flat_columns(df_15m)
    df_1h = _ensure_flat_columns(df_1h)

    # Add indicators
    df_15m = add_indicators(df_15m)
    df_1h = add_indicators(df_1h)

    # Ensure sorted
    df_15m = df_15m.sort_index()
    df_1h = df_1h.sort_index()

    # Optional pattern DB
    con = None
    insert_count = 0
    if PATTERN_LIB_ENABLED and PATTERN_LIB_ENABLED:
        try:
            con = pattern_connect(PATTERN_DB_PATH)
            pattern_init_db(con)
            print(f"✅ Pattern DB enabled: {PATTERN_DB_PATH}")
        except Exception as e:
            print(f"⚠️ Pattern DB disabled (init failed): {e}")
            con = None

    # Walk forward
    results: List[Dict[str, Any]] = []
    trade_counter = 0

    # start after enough candles to compute embedding + indicators
    start_i = max(EMBED_WINDOW + 5, 60)

    for i in range(start_i, len(df_15m) - (FUTURE_BARS + 2)):
        ts = df_15m.index[i]

        # 1H slice up to last closed 1H candle at/behind this timestamp
        ts_1h = _pick_last_closed_1h(ts, df_1h)
        if ts_1h is None:
            continue

        df_15m_slice = df_15m.iloc[: i + 1].copy()
        df_1h_slice = df_1h.loc[: ts_1h].copy()

        # Call your strategy
        try:
            pred = strategy.predict_next_candle(df_15m_slice, df_1h_slice)
        except Exception:
            continue

        if not isinstance(pred, dict):
            continue

        trade_type = pred.get("trade_type") or pred.get("Trade Type") or "NO_TRADE"
        bias = pred.get("bias") or pred.get("Bias") or "Neutral"
        confidence = _safe_float(pred.get("confidence") or pred.get("Confidence"), default=0.0)

        if trade_type in ("NO_TRADE", None):
            continue
        if confidence < MIN_CONFIDENCE:
            continue

        trade = pred.get("trade") or {}
        expected = pred.get("expected_move") or {}

        entry = _safe_float(trade.get("entry"), default=math.nan)
        sl = _safe_float(trade.get("stop_loss"), default=math.nan)
        tp = _safe_float(trade.get("take_profit"), default=math.nan)

        direction = expected.get("direction")
        if direction not in ("up", "down"):
            # fallback from bias
            direction = "up" if str(bias).lower().startswith("bull") else "down"

        # If strategy didn't give valid levels, skip
        if any(math.isnan(x) for x in (entry, sl, tp)):
            continue

        # Execution: entry at next candle open or current close
        if USE_NEXT_OPEN_FOR_ENTRY:
            entry_price = float(df_15m["Open"].iloc[i + 1])
            entry_ts = df_15m.index[i + 1]
        else:
            entry_price = float(df_15m["Close"].iloc[i])
            entry_ts = ts

        future = df_15m.iloc[i + 1 : i + 1 + FUTURE_BARS].copy()
        result, bars_to_hit, exit_price = _simulate_tp_sl(future, entry_price, sl, tp, direction)
        r = _r_multiple(entry_price, sl, exit_price, direction)

        row = {
            "symbol": symbol,
            "tf": TF_EXEC,
            "signal_ts": str(ts),
            "entry_ts": str(entry_ts),
            "trade_type": trade_type,
            "bias": bias,
            "confidence": confidence,
            "direction": direction,
            "entry": entry_price,
            "sl": sl,
            "tp": tp,
            "result": result,
            "bars_to_hit": bars_to_hit,
            "exit_price": exit_price,
            "r_multiple": r,
        }
        results.append(row)

        # Store pattern (optional)
        if con is not None and make_embedding is not None:
            try:
                emb = make_embedding(df_15m_slice, window=EMBED_WINDOW).tolist()
                outcome = {
                    "win": (result == "TP"),
                    "result": result,
                    "r_multiple": float(r),
                    "future_return": float((exit_price - entry_price) / entry_price) if direction == "up"
                                    else float((entry_price - exit_price) / entry_price),
                }
                pattern_insert(
                    con=con,
                    symbol=symbol,
                    tf=TF_EXEC,
                    ts=str(entry_ts),
                    trade_type=trade_type,
                    bias=str(bias),
                    feature_version=int(FEATURE_VERSION),
                    window=int(EMBED_WINDOW),
                    embedding=emb,
                    outcome=outcome,
                )
                insert_count += 1
                if insert_count % BATCH_COMMIT == 0:
                    con.commit()
            except Exception:
                pass

        trade_counter += 1
        if MAX_TRADES > 0 and trade_counter >= MAX_TRADES:
            break

    if con is not None:
        con.commit()
        con.close()
        print(f"✅ patterns.db updated: {PATTERN_DB_PATH} | patterns stored: {insert_count}")

    df_res = pd.DataFrame(results)
    if not df_res.empty:
        df_res.to_csv(RESULTS_CSV, index=False)
        print(f"✅ Backtest saved: {RESULTS_CSV} | trades: {len(df_res)}")
        _print_summary(df_res)
    else:
        print("⚠️ No trades generated under current rules/thresholds.")

    return df_res


def _print_summary(df_res: pd.DataFrame) -> None:
    total = len(df_res)
    tp = int((df_res["result"] == "TP").sum())
    sl = int((df_res["result"] == "SL").sum())
    no_hit = int((df_res["result"] == "NO_HIT").sum())
    win_rate = (tp / max(total, 1)) * 100.0
    avg_r = float(df_res["r_multiple"].mean()) if total else 0.0

    print("\n===== BACKTEST SUMMARY =====")
    print(f"Trades: {total}")
    print(f"TP: {tp} | SL: {sl} | NO_HIT: {no_hit}")
    print(f"Win rate (TP-only): {win_rate:.2f}%")
    print(f"Avg R: {avg_r:.3f}")
    print("============================\n")


if __name__ == "__main__":
    run_backtest(SYMBOL)
