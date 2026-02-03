# backtester.py
import csv
import pandas as pd
from data_fetcher import fetch_data
from indicators import add_indicators
from strategy import predict_next_candle

SYMBOL = "BTC-USD"

TF_EXEC = "15m"
TF_TREND = "1h"

LOOKBACK_EXEC = "30d"
LOOKBACK_TREND = "60d"      # longer so 1H has enough history

CSV_FILE = "backtest_results.csv"

MIN_CONFIDENCE = 70
FUTURE_BARS = 5             # evaluate next 5x 15m candles
WARMUP_BARS_15M = 120        # allow indicators + rolling breakout lookbacks etc.


def _normalize_index(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure index is comparable across frames.
    yfinance may return tz-aware indexes; remove tz to compare safely.
    """
    if df is None or df.empty:
        return df
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_convert(None)
    return df


def run_backtest():
    # ----------------------------
    # 1) Fetch both timeframes
    # ----------------------------
    df_15m = fetch_data(SYMBOL, TF_EXEC, LOOKBACK_EXEC)
    df_1h = fetch_data(SYMBOL, TF_TREND, LOOKBACK_TREND)

    df_15m = _normalize_index(df_15m)
    df_1h = _normalize_index(df_1h)

    if df_15m.empty or df_1h.empty:
        print("❌ Failed to fetch data (15m or 1h empty).")
        return

    # ----------------------------
    # 2) Add indicators
    # ----------------------------
    df_15m = add_indicators(df_15m)
    df_1h = add_indicators(df_1h)

    if len(df_15m) < (WARMUP_BARS_15M + FUTURE_BARS + 5):
        print("❌ Not enough 15m candles after indicators. Increase LOOKBACK_EXEC.")
        return

    # Ensure 1H is sorted
    df_1h = df_1h.sort_index()
    df_15m = df_15m.sort_index()

    # ----------------------------
    # 3) Backtest loop
    # ----------------------------
    results = []
    wins = 0
    losses = 0

    for i in range(WARMUP_BARS_15M, len(df_15m) - FUTURE_BARS):
        t = df_15m.index[i]

        # 15m slice up to time t (inclusive)
        slice_15m = df_15m.loc[:t].copy()

        # 1h slice: only candles with timestamp <= t (latest completed 1H candle)
        slice_1h = df_1h.loc[:t].copy()

        # Need enough 1H candles for EMA50 + other indicators
        if len(slice_1h) < 60:
            continue

        # Predict based on historical data only
        result = predict_next_candle(slice_15m, slice_1h)

        trade_type = result.get("trade_type", "NO_TRADE")
        confidence = int(result.get("confidence", 0))
        bias = result.get("bias", "Neutral")
        trade = result.get("trade")

        # Only evaluate trades
        if trade_type == "NO_TRADE" or trade is None or confidence < MIN_CONFIDENCE:
            continue

        entry = float(trade["entry"])
        sl = float(trade["stop_loss"])
        tp = float(trade["take_profit"])

        future = df_15m.iloc[i:i + FUTURE_BARS]

        outcome = "NO HIT"
        exit_time = None

        # Execution simulation:
        # - Bullish: SL checked before TP within same candle (conservative)
        # - Bearish: SL checked before TP within same candle (conservative)
        for ts, row in future.iterrows():
            high = float(row["High"])
            low = float(row["Low"])

            if bias == "Bullish":
                if low <= sl:
                    outcome = "LOSS"
                    losses += 1
                    exit_time = ts
                    break
                if high >= tp:
                    outcome = "WIN"
                    wins += 1
                    exit_time = ts
                    break

            elif bias == "Bearish":
                if high >= sl:
                    outcome = "LOSS"
                    losses += 1
                    exit_time = ts
                    break
                if low <= tp:
                    outcome = "WIN"
                    wins += 1
                    exit_time = ts
                    break
            else:
                outcome = "SKIP"
                exit_time = ts
                break

        results.append([
            t, exit_time, SYMBOL, trade_type, bias, confidence,
            entry, sl, tp, outcome
        ])

    # ----------------------------
    # 4) Save results
    # ----------------------------
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "SignalTime", "ExitTime", "Symbol", "TradeType", "Bias", "Confidence",
            "Entry", "StopLoss", "TakeProfit", "Outcome"
        ])
        writer.writerows(results)

    total = wins + losses
    winrate = round((wins / total) * 100, 2) if total else 0.0

    print("📊 BACKTEST RESULTS (Proper 15m+1H aligned)")
    print("------------------------------------------")
    print(f"Symbol       : {SYMBOL}")
    print(f"Exec TF      : {TF_EXEC}")
    print(f"Trend TF     : {TF_TREND}")
    print(f"Lookback 15m : {LOOKBACK_EXEC}")
    print(f"Lookback 1h  : {LOOKBACK_TREND}")
    print(f"Min Conf     : {MIN_CONFIDENCE}")
    print(f"Future Bars  : {FUTURE_BARS}")
    print("")
    print(f"Trades Taken : {total}")
    print(f"Wins         : {wins}")
    print(f"Losses       : {losses}")
    print(f"Win Rate     : {winrate}%")
    print(f"CSV Saved    : {CSV_FILE}")


if __name__ == "__main__":
    run_backtest()
