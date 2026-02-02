import yfinance as yf

def fetch_data(symbol, interval, period):
    df = yf.download(symbol, interval=interval, period=period)

    # ✅ FIX: Flatten MultiIndex columns if present
    if isinstance(df.columns, tuple) or hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)

    df.dropna(inplace=True)
    return df
