import pandas as pd
import yfinance as yf
import ccxt
from datetime import datetime, timedelta, timezone

def _is_yahoo_symbol(symbol: str) -> bool:
    # Yahoo patterns: XAUUSD=X, GC=F, AAPL, GOLDBEES.NS, etc.
    return (
        ("=" in symbol) or
        symbol.endswith(".NS") or
        symbol.endswith(".BO")
    )

def _yf_allowed_period(tf: str, requested: str) -> str:
    """
    yfinance has limits for intraday:
      - 1m: up to 7d
      - 2m/5m/15m/30m/60m/90m: up to 60d
      - 1h/1d: much longer (years)
    We'll cap automatically so your backtest doesn't crash.
    """
    tf = tf.lower()
    intraday = tf in ("1m","2m","5m","15m","30m","60m","90m","1h")

    if tf == "1m":
        return "7d"
    if tf in ("2m","5m","15m","30m","60m","90m"):
        return "60d"
    # 1h and above can use requested safely (keep your requested)
    return requested if requested else "365d"

def fetch_data(symbol: str, timeframe: str, period: str, only_closed: bool = True):
    timeframe = timeframe.lower()

    # ---------- YFINANCE PATH ----------
    if _is_yahoo_symbol(symbol):
        yf_period = _yf_allowed_period(timeframe, period)
        df = yf.download(
            symbol,
            period=yf_period,
            interval=timeframe,
            auto_adjust=False,
            progress=False,
            threads=True,
        )

        if df is None or df.empty:
            return pd.DataFrame()

        # yfinance index can be tz-aware; normalize
        df = df.copy()
        df.index = pd.to_datetime(df.index)
        df = df.rename(columns=lambda c: c.strip().title())

        # Keep only expected cols
        keep = [c for c in ["Open","High","Low","Close","Volume"] if c in df.columns]
        df = df[keep].dropna()

        # only_closed: last candle might be still forming, drop it for safety
        if only_closed and len(df) > 1:
            df = df.iloc[:-1]

        return df

    # ---------- CCXT PATH (CRYPTO) ----------
    ex = ccxt.binance({"enableRateLimit": True})

    # If user already passed "BTC/USDT" keep it, else default to /USDT
    if "/" in symbol:
        ccxt_symbol = symbol
    else:
        ccxt_symbol = f"{symbol}/USDT"

    # period like "180d" -> since_ms
    days = int(period.replace("d", "")) if period and period.endswith("d") else 60
    since = datetime.now(timezone.utc) - timedelta(days=days)
    since_ms = int(since.timestamp() * 1000)

    limit = 1000
    all_rows = []
    while True:
        ohlcv = ex.fetch_ohlcv(ccxt_symbol, timeframe=timeframe, since=since_ms, limit=limit)
        if not ohlcv:
            break
        all_rows.extend(ohlcv)
        since_ms = ohlcv[-1][0] + 1
        if len(ohlcv) < limit:
            break

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows, columns=["Timestamp","Open","High","Low","Close","Volume"])
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="ms", utc=True)
    df.set_index("Timestamp", inplace=True)
    df = df.astype(float)

    if only_closed and len(df) > 1:
        df = df.iloc[:-1]

    return df
