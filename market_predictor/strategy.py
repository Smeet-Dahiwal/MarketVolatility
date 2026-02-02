# strategy.py

def trend_score_1h(df):
    last = df.iloc[-1]

    if last['ema20'] > last['ema50']:
        return 30, "Bullish 1H trend"

    elif last['ema20'] < last['ema50']:
        return -30, "Bearish 1H trend"

    return 15, "Sideways 1H trend"


def candle_score(df):
    last = df.iloc[-1]
    body = abs(last['Close'] - last['Open'])
    wick = (last['High'] - last['Low']) - body

    if body > wick:
        return 25, "Strong candle"

    return 10, "Weak candle"


def atr_score(df):
    atr = df.iloc[-1]['atr']
    avg_atr = df['atr'].mean()

    if atr > avg_atr:
        return 20, "High volatility expected"

    return 10, "Low volatility"


def support_resistance_score(df):
    last_price = df.iloc[-1]['Close']
    recent_low = df['Low'].tail(20).min()
    recent_high = df['High'].tail(20).max()

    if abs(last_price - recent_low) / last_price < 0.003:
        return 25, "Near support"

    if abs(last_price - recent_high) / last_price < 0.003:
        return -25, "Near resistance"

    return 10, "Mid-range price"

def ema_trend_score(df):
    if df['ema20'].iloc[-1] > df['ema50'].iloc[-1]:
        return 15, "EMA bullish crossover"
    elif df['ema20'].iloc[-1] < df['ema50'].iloc[-1]:
        return -15, "EMA bearish crossover"
    return 0, "EMA neutral"

def rsi_score(df):
    rsi = df['rsi'].iloc[-1]

    if rsi < 30:
        return 10, "RSI oversold (bounce possible)"
    elif rsi > 70:
        return -10, "RSI overbought (pullback possible)"
    elif 45 < rsi < 55:
        return 0, "RSI neutral"
    elif rsi > 55:
        return 5, "RSI bullish momentum"
    else:
        return -5, "RSI bearish momentum"


def macd_score(df):
    if df['macd'].iloc[-1] > 0:
        return 10, "MACD bullish momentum"
    else:
        return -10, "MACD bearish momentum"


def adx_score(df):
    adx = df['adx'].iloc[-1]

    if adx > 25:
        return 10, "Strong trend (ADX)"
    else:
        return -5, "Weak / choppy market"


def candle_pattern_score(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Bullish Engulfing
    if prev['Close'] < prev['Open'] and last['Close'] > last['Open'] \
       and last['Close'] > prev['Open'] and last['Open'] < prev['Close']:
        return 20, "Bullish engulfing"

    # Bearish Engulfing
    if prev['Close'] > prev['Open'] and last['Close'] < last['Open'] \
       and last['Open'] > prev['Close'] and last['Close'] < prev['Open']:
        return -20, "Bearish engulfing"

    return 0, "No strong candle pattern"


def vwap_score(df):
    price = df['Close'].iloc[-1]
    vwap = df['vwap'].iloc[-1]

    if price > vwap:
        return 10, "Price above VWAP (institutional bullish)"
    else:
        return -10, "Price below VWAP (institutional bearish)"


def market_regime_score(df):
    adx = df['adx'].iloc[-1]

    if adx < 20:
        return -15, "Ranging market (avoid trend trades)"
    elif 20 <= adx <= 25:
        return 0, "Market transitioning"
    else:
        return 10, "Trending market"

def breakout_score(df):
    high = df['High'].iloc[-1]
    prev_high = df['High'].rolling(20).max().iloc[-2]
    atr = df['atr'].iloc[-1]
    atr_avg = df['atr'].rolling(14).mean().iloc[-1]

    if high > prev_high and atr > atr_avg:
        return 15, "Valid breakout (ATR confirmed)"
    elif high > prev_high:
        return -10, "Fake breakout risk"
    return 0, "No breakout"


def rsi_divergence_score(df):
    price_now = df['Close'].iloc[-1]
    price_prev = df['Close'].iloc[-5]
    rsi_now = df['rsi'].iloc[-1]
    rsi_prev = df['rsi'].iloc[-5]

    if price_now < price_prev and rsi_now > rsi_prev:
        return 15, "Bullish RSI divergence"
    elif price_now > price_prev and rsi_now < rsi_prev:
        return -15, "Bearish RSI divergence"

    return 0, "No RSI divergence"

def conflict_filter(reasons):
    bull = sum(1 for r in reasons if "bullish" in r.lower())
    bear = sum(1 for r in reasons if "bearish" in r.lower())

    if bull >= 3 and bear >= 3:
        return -20, "High signal conflict (no trade zone)"
    return 0, "Signals aligned"


def predict_next_candle(df_15m, df_1h):
    score = 50  # start neutral
    reasons = []

    for fn in [
        market_regime_score,
        trend_score_1h,
        support_resistance_score,
        ema_trend_score,
        vwap_score,
        rsi_score,
        macd_score,
        rsi_divergence_score,
        breakout_score,
        candle_pattern_score,
        atr_score
    ]:
        s, r = fn(df_15m if fn != trend_score_1h else df_1h)
        score += s
        reasons.append(r)

    score = max(0, min(score, 100))

    bias = "Neutral"
    if score >= 65:
        bias = "Bullish"
    elif score <= 35:
        bias = "Bearish"

    return {
        "bias": bias,
        "confidence": score,
        "reasons": reasons
    }
