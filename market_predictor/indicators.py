import ta

def add_indicators(df):
    # =========================
    # Trend Indicators
    # =========================
    df['ema20'] = ta.trend.ema_indicator(df['Close'], window=20)
    df['ema50'] = ta.trend.ema_indicator(df['Close'], window=50)

    # =========================
    # Momentum Indicators
    # =========================
    df['rsi'] = ta.momentum.rsi(df['Close'], window=14)

    # Be explicit about MACD params for stability
    df['macd'] = ta.trend.macd_diff(
        df['Close'], window_slow=26, window_fast=12, window_sign=9
    )

    # =========================
    # Volatility Indicators
    # =========================
    df['adx'] = ta.trend.adx(df['High'], df['Low'], df['Close'], window=14)

    df['atr'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14)

    # Normalized ATR (optional but useful for accuracy)
    df['atr_pct'] = (df['atr'] / df['Close']) * 100

    # =========================
    # Volume / Institutional Indicator
    # =========================
    df['vwap'] = ta.volume.volume_weighted_average_price(
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        volume=df['Volume']
    )

    df.dropna(inplace=True)
    return df
