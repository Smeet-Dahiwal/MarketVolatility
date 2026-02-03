# data_fetcher.py
import yfinance as yf
from datetime import datetime, timezone
import pandas as pd


_INTERVAL_MINUTES = {
    "1m": 1, "2m": 2, "5m": 5, "15m": 15, "30m": 30,
    "60m": 60, "90m": 90,
    "1h": 60,
    "1d": 1440,
}


def _ensure_tz_naive_utc(ts: pd.Timestamp) -> pd.Timestamp:
    """
    Convert timestamp to UTC naive for consistent comparison.
    yfinance sometimes returns tz-aware; sometimes naive.
    """
    if ts.tzinfo is not None:
        return ts.tz_convert("UTC").tz_localize(None)
    return ts


def _now_utc_naive() -> pd.Timestamp:
    return pd.Timestamp(datetime.now(timezone.utc)).tz_localize(None)


def _floor_time_to_interval(ts: pd.Timestamp, interval_minutes: int) -> pd.Timestamp:
    # floor to the last completed interval boundary
    return ts.floor(f"{interval_minutes}min")


def fetch_data(symbol, interval, period, only_closed: bool = True):
    df = yf.download(symbol, interval=interval, period=period)

    # ✅ Flatten MultiIndex columns if present
    if isinstance(df.columns, tuple) or hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)

    df.dropna(inplace=True)

    if df.empty or not only_closed:
        return df

    if interval not in _INTERVAL_MINUTES:
        # If unknown interval, safest is: return as-is
        return df

    interval_minutes = _INTERVAL_MINUTES[interval]

    # yfinance index may be tz-aware; normalize
    df = df.sort_index()

    last_ts = pd.Timestamp(df.index[-1])
    last_ts = _ensure_tz_naive_utc(last_ts)

    now_utc = _now_utc_naive()
    last_closed_boundary = _floor_time_to_interval(now_utc, interval_minutes)

    # ✅ If last candle timestamp equals the current open candle boundary,
    # it is still forming -> drop it
    # Example: now=10:07, interval=15m -> boundary=10:00
    # candle starting at 10:00 is still forming until 10:15
    if last_ts >= last_closed_boundary:
        # drop the last row (forming candle)
        df = df.iloc[:-1]

    return df
