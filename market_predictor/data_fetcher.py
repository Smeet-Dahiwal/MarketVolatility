# market_predictor/data_fetcher.py
import time
import pandas as pd

import ccxt


# Map Yahoo style symbols -> Binance symbols
def _to_binance_symbol(symbol: str) -> str:
    # BTC-USD -> BTC/USDT
    if symbol.endswith("-USD"):
        base = symbol.replace("-USD", "")
        return f"{base}/USDT"
    # If user passes already "BTC/USDT", keep it
    if "/" in symbol:
        return symbol
    # Fallback: assume USDT quote
    return f"{symbol}/USDT"


def _days_from_period(period: str) -> int:
    """
    Accepts: "5d", "60d", "180d", "1y", "6mo"
    """
    p = period.strip().lower()
    if p.endswith("d"):
        return int(p[:-1])
    if p.endswith("mo"):
        return int(p[:-2]) * 30
    if p.endswith("y"):
        return int(p[:-1]) * 365
    # default
    return 30


def _drop_last_open_candle(df: pd.DataFrame) -> pd.DataFrame:
    # safest: last candle might still be forming
    if df is None or df.empty:
        return df
    return df.iloc[:-1].copy() if len(df) > 1 else df


def fetch_data(symbol: str, interval: str, period: str, only_closed: bool = True) -> pd.DataFrame:
    """
    CCXT-only fetcher (Binance spot).
    interval: "5m", "15m", "1h"
    period: "5d", "60d", "180d", "1y"
    """
    ex = ccxt.binance({"enableRateLimit": True})
    ccxt_symbol = _to_binance_symbol(symbol)

    timeframe_map = {"5m": "5m", "15m": "15m", "1h": "1h"}
    if interval not in timeframe_map:
        raise ValueError(f"Unsupported interval: {interval}. Use one of {list(timeframe_map.keys())}")

    tf = timeframe_map[interval]
    days = _days_from_period(period)

    since_ms = int((pd.Timestamp.utcnow() - pd.Timedelta(days=days)).timestamp() * 1000)

    all_rows = []
    limit = 1000  # Binance max per call typically 1000
    while True:
        ohlcv = ex.fetch_ohlcv(ccxt_symbol, timeframe=tf, since=since_ms, limit=limit)
        if not ohlcv:
            break

        all_rows.extend(ohlcv)

        last_ts = ohlcv[-1][0]
        since_ms = last_ts + 1

        # If returned less than limit, we likely reached “now”
        if len(ohlcv) < limit:
            break

        time.sleep(ex.rateLimit / 1000)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows, columns=["Datetime", "Open", "High", "Low", "Close", "Volume"])
    df["Datetime"] = pd.to_datetime(df["Datetime"], unit="ms", utc=True).dt.tz_convert(None)
    df.set_index("Datetime", inplace=True)
    df = df.sort_index()

    if only_closed:
        df = _drop_last_open_candle(df)

    return df
