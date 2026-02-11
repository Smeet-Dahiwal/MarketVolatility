# market_predictor/backtester.py
"""
Backtester (Phase 1)
- CCXT/Binance data via market_predictor.data_fetcher.fetch_data (no yfinance)
- Strategy decision: 1H trend + 15m setup (strategy.predict_next_candle)
- Entry timing: 5m confirm (entry_confirm.confirm_entry_5m)
- Trade refinement: 5m SL/TP (trade_refine.refine_trade_levels_with_5m)
- Simulation on 5m candles forward
- Stores trades into SQLite: market_predictor.db (table: backtest_trades)
- Exports CSV + prints metrics
"""

import csv
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple

import pandas as pd

from market_predictor.data_fetcher import fetch_data
from market_predictor.indicators import add_indicators
from market_predictor.strategy import predict_next_candle
from market_predictor.entry_confirm import confirm_entry_5m
from market_predictor.trade_refine import refine_trade_levels_with_5m
from market_predictor.db import init_db


# ---------------- CONFIG ----------------
DB_PATH = "market_predictor.db"
CSV_OUT = "backtest_results.csv"

SYMBOL = "BTC-USD"

# Backtest horizon
SETUP_PERIOD = "180d"   # 15m
TREND_PERIOD = "365d"   # 1h (more context)
ENTRY_PERIOD = "180d"   # 5m

# Strategy gate
CONFIDENCE_THRESHOLD = 70

# Simulation
MAX_HOLD_5M_BARS = 72   # 72 * 5m = 6 hours max hold
WORST_CASE_IF_BOTH_HIT_SAME_CANDLE = True  # conservative

# Minimum rows required before evaluating
MIN_15M_ROWS = 120
MIN_1H_ROWS = 80
MIN_5M_ROWS = 200
# --------------------------------------


@dataclass
class BTTrade:
    entry_time: str
    exit_time: str
    symbol: str
    trade_type: str
    bias: str
    confidence: int
    entry: float
    stop_loss: float
    take_profit: float
    rr: float
    outcome: str  # WIN/LOSS/NO_HIT
    r_multiple: float
    bars_held_5m: int
    meta: Dict[str, Any]


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    return con


def _insert_backtest_trade(t: BTTrade) -> None:
    con = _connect()
    try:
        con.execute(
            """
            INSERT INTO backtest_trades(
                ts, symbol, trade_type, bias,
                entry, stop_loss, take_profit, rr,
                outcome, r_multiple, meta_json
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(time.time()),
                t.symbol,
                t.trade_type,
                t.bias,
                float(t.entry),
                float(t.stop_loss),
                float(t.take_profit),
                float(t.rr),
                t.outcome,
                float(t.r_multiple),
                json.dumps(
                    {
                        **t.meta,
                        "entry_time": t.entry_time,
                        "exit_time": t.exit_time,
                        "confidence": t.confidence,
                        "bars_held_5m": t.bars_held_5m,
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        con.commit()
    finally:
        con.close()


def _write_csv(trades: List[BTTrade], path: str = CSV_OUT) -> None:
    headers = [
        "entry_time", "exit_time", "symbol", "trade_type", "bias", "confidence",
        "entry", "stop_loss", "take_profit", "rr",
        "outcome", "r_multiple", "bars_held_5m", "meta_json"
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for t in trades:
            w.writerow({
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "symbol": t.symbol,
                "trade_type": t.trade_type,
                "bias": t.bias,
                "confidence": t.confidence,
                "entry": t.entry,
                "stop_loss": t.stop_loss,
                "take_profit": t.take_profit,
                "rr": t.rr,
                "outcome": t.outcome,
                "r_multiple": t.r_multiple,
                "bars_held_5m": t.bars_held_5m,
                "meta_json": json.dumps(t.meta, ensure_ascii=False),
            })


def _print_metrics(symbol: str = SYMBOL) -> None:
    con = _connect()
    try:
        rows = con.execute(
            """
            SELECT trade_type, bias,
                   COUNT(*) as n,
                   AVG(CASE WHEN outcome='WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
                   AVG(r_multiple) as avg_r
            FROM backtest_trades
            WHERE symbol=?
            GROUP BY trade_type, bias
            ORDER BY n DESC
            """,
            (symbol,),
        ).fetchall()

        print("\n===== BACKTEST METRICS (from SQLite) =====")
        if not rows:
            print("No trades stored yet.")
            return

        for trade_type, bias, n, win_rate, avg_r in rows:
            print(f"{trade_type:14s} {bias:7s} | n={n:4d} | win={win_rate*100:5.1f}% | avgR={avg_r: .3f}")

        overall = con.execute(
            """
            SELECT COUNT(*),
                   AVG(CASE WHEN outcome='WIN' THEN 1.0 ELSE 0.0 END),
                   AVG(r_multiple)
            FROM backtest_trades
            WHERE symbol=?
            """,
            (symbol,),
        ).fetchone()

        print(f"\nOVERALL | n={overall[0]} | win={overall[1]*100:.1f}% | avgR={overall[2]:.3f}")

    finally:
        con.close()


def _simulate_trade_on_5m(
    df_5m_full: pd.DataFrame,
    entry_ts: pd.Timestamp,
    bias: str,
    entry: float,
    sl: float,
    tp: float,
    max_bars: int = MAX_HOLD_5M_BARS,
) -> Tuple[str, float, str, int]:
    """
    Returns: (outcome, r_multiple, exit_time_str, bars_held)
    outcome: WIN / LOSS / NO_HIT
    r_multiple: +rr for win, -1 for loss, 0 for no hit
    """

    # locate entry index
    idx = df_5m_full.index.searchsorted(entry_ts)
    # if exact match, start checking from next candle
    if idx < len(df_5m_full) and df_5m_full.index[idx] == entry_ts:
        start = idx + 1
    else:
        start = idx  # next available candle after entry_ts

    end = min(start + max_bars, len(df_5m_full))

    risk = abs(entry - sl)
    if risk <= 0:
        return "NO_HIT", 0.0, str(entry_ts), 0

    rr = abs(tp - entry) / risk

    for j in range(start, end):
        row = df_5m_full.iloc[j]
        hi = float(row["High"])
        lo = float(row["Low"])
        candle_ts = df_5m_full.index[j]

        if bias == "Bullish":
            hit_sl = lo <= sl
            hit_tp = hi >= tp
            if hit_sl and hit_tp:
                if WORST_CASE_IF_BOTH_HIT_SAME_CANDLE:
                    return "LOSS", -1.0, str(candle_ts), j - start + 1
                else:
                    return "WIN", float(rr), str(candle_ts), j - start + 1
            if hit_sl:
                return "LOSS", -1.0, str(candle_ts), j - start + 1
            if hit_tp:
                return "WIN", float(rr), str(candle_ts), j - start + 1

        elif bias == "Bearish":
            hit_sl = hi >= sl
            hit_tp = lo <= tp
            if hit_sl and hit_tp:
                if WORST_CASE_IF_BOTH_HIT_SAME_CANDLE:
                    return "LOSS", -1.0, str(candle_ts), j - start + 1
                else:
                    return "WIN", float(rr), str(candle_ts), j - start + 1
            if hit_sl:
                return "LOSS", -1.0, str(candle_ts), j - start + 1
            if hit_tp:
                return "WIN", float(rr), str(candle_ts), j - start + 1

        else:
            return "NO_HIT", 0.0, str(entry_ts), 0

    # timeout
    return "NO_HIT", 0.0, str(df_5m_full.index[end - 1] if end - 1 >= 0 else entry_ts), max(0, end - start)


def run_backtest(symbol: str = SYMBOL) -> None:
    init_db(DB_PATH)

    print(f"📥 Backtesting {symbol} | setup=15m({SETUP_PERIOD}) trend=1h({TREND_PERIOD}) entry=5m({ENTRY_PERIOD})")

    # Fetch raw data
    df_15m = fetch_data(symbol, "15m", SETUP_PERIOD, only_closed=True)
    df_1h = fetch_data(symbol, "1h", TREND_PERIOD, only_closed=True)
    df_5m = fetch_data(symbol, "5m", ENTRY_PERIOD, only_closed=True)

    if df_15m.empty or df_1h.empty or df_5m.empty:
        raise RuntimeError("❌ Failed to fetch market data for backtest (ccxt)")

    # Add indicators on full datasets
    df_15m = add_indicators(df_15m)
    df_1h = add_indicators(df_1h)
    df_5m = add_indicators(df_5m)

    trades: List[BTTrade] = []
    total_checks = 0
    setups_found = 0
    entries_found = 0

    # Iterate over 15m candles (as "decision points")
    for i in range(MIN_15M_ROWS, len(df_15m)):
        total_checks += 1
        t15 = df_15m.index[i]

        # Slice up to this candle for each timeframe (closed candles only)
        df15_slice = df_15m.iloc[: i + 1]
        df1h_slice = df_1h[df_1h.index <= t15]
        df5m_slice = df_5m[df_5m.index <= t15]

        if len(df1h_slice) < MIN_1H_ROWS or len(df5m_slice) < MIN_5M_ROWS:
            continue

        # Strategy decision (1H + 15m)
        res = predict_next_candle(df15_slice, df1h_slice)

        trade_type = res.get("trade_type", "NO_TRADE")
        bias = res.get("bias", "Neutral")
        conf = int(res.get("confidence", 0))
        base_trade = res.get("trade")

        if trade_type == "NO_TRADE" or conf < CONFIDENCE_THRESHOLD or not base_trade:
            continue

        setups_found += 1

        # Entry confirmation (5m)
        entry_ok, entry_reasons = confirm_entry_5m(df5m_slice, bias=bias)
        if not entry_ok:
            continue

        # Refine levels using 5m
        refined_trade, refine_reason = refine_trade_levels_with_5m(
            df_5m=df5m_slice,
            base_trade=base_trade,
            bias=bias,
            rr=float(base_trade.get("rr", 2.0)),
            trade_type=trade_type,
            breakout_level=res.get("breakout_level"),
        )

        if not refined_trade:
            continue

        entries_found += 1

        entry_price = float(refined_trade["entry"])
        sl = float(refined_trade["stop_loss"])
        tp = float(refined_trade["take_profit"])
        rr = float(refined_trade.get("rr", 2.0))

        entry_ts = df5m_slice.index[-1]  # last closed 5m candle at/<= t15

        outcome, r_mult, exit_time, bars_held = _simulate_trade_on_5m(
            df_5m_full=df_5m,
            entry_ts=entry_ts,
            bias=bias,
            entry=entry_price,
            sl=sl,
            tp=tp,
            max_bars=MAX_HOLD_5M_BARS,
        )

        meta = {
            "decision_time_15m": str(t15),
            "entry_confirm": entry_reasons,
            "refine_reason": refine_reason,
            "expected_move": res.get("expected_move", {}),
            "reasons": res.get("reasons", []),
        }

        bt = BTTrade(
            entry_time=str(entry_ts),
            exit_time=exit_time,
            symbol=symbol,
            trade_type=trade_type,
            bias=bias,
            confidence=conf,
            entry=entry_price,
            stop_loss=sl,
            take_profit=tp,
            rr=rr,
            outcome=outcome,
            r_multiple=float(r_mult),
            bars_held_5m=int(bars_held),
            meta=meta,
        )

        trades.append(bt)
        _insert_backtest_trade(bt)

    # Export + report
    _write_csv(trades, CSV_OUT)

    print("\n✅ Backtest complete")
    print(f"Total checks (15m closes evaluated): {total_checks}")
    print(f"Setups found (passed 1H+15m+confidence): {setups_found}")
    print(f"Entries found (passed 5m confirm + refine): {entries_found}")
    print(f"Trades executed (stored): {len(trades)}")
    print(f"CSV exported: {os.path.abspath(CSV_OUT)}")
    print(f"SQLite DB: {os.path.abspath(DB_PATH)}")

    _print_metrics(symbol)


if __name__ == "__main__":
    # Run as: python -m market_predictor.backtester
    run_backtest(SYMBOL)
