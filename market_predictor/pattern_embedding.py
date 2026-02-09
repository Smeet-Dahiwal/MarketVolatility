import numpy as np

FEATURE_VERSION = 1

def make_embedding(df, window: int = 32) -> np.ndarray:
    if len(df) < window + 2:
        raise ValueError("Not enough rows for embedding")

    w = df.tail(window).copy()

    close = w["Close"].astype(float).values
    high  = w["High"].astype(float).values
    low   = w["Low"].astype(float).values
    open_ = w["Open"].astype(float).values

    last_close = float(close[-1])
    atr = float(w["atr"].iloc[-1]) if "atr" in w.columns else 1.0
    atr = atr if atr and atr > 0 else 1.0

    rets = np.diff(close) / np.maximum(close[:-1], 1e-12)
    rets = np.pad(rets, (window - len(rets), 0), constant_values=0.0)

    ranges = (high - low) / atr
    bodies = np.abs(close - open_) / np.maximum(high - low, 1e-12)

    ema20 = float(w["ema20"].iloc[-1])
    ema50 = float(w["ema50"].iloc[-1])
    vwap  = float(w["vwap"].iloc[-1])
    rsi   = float(w["rsi"].iloc[-1])
    adx   = float(w["adx"].iloc[-1])

    ema_gap = (ema20 - ema50) / max(last_close, 1e-12)
    vwap_dist = (last_close - vwap) / max(last_close, 1e-12)
    atr_pct = atr / max(last_close, 1e-12)

    features = np.concatenate([
        rets,
        ranges,
        bodies,
        np.array([ema_gap, vwap_dist, rsi/100.0, adx/100.0, atr_pct], dtype=float)
    ]).astype(np.float32)

    norm = np.linalg.norm(features)
    if norm > 0:
        features = features / norm
    return features
