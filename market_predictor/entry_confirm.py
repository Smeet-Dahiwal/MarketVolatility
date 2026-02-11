# market_predictor/entry_confirm.py
from typing import Tuple, List


def _last(df, col: str) -> float:
    return float(df[col].iloc[-1])


def _prev(df, col: str) -> float:
    return float(df[col].iloc[-2])


def _candle_strength(df) -> Tuple[bool, str]:
    last = df.iloc[-1]
    body = abs(last["Close"] - last["Open"])
    wick = (last["High"] - last["Low"]) - body
    if body > wick:
        return True, "5m strong candle body"
    return False, "5m weak candle body"


def _bullish_engulfing(df) -> bool:
    last = df.iloc[-1]
    prev = df.iloc[-2]
    return (
        prev["Close"] < prev["Open"]
        and last["Close"] > last["Open"]
        and last["Close"] > prev["Open"]
        and last["Open"] < prev["Close"]
    )


def _bearish_engulfing(df) -> bool:
    last = df.iloc[-1]
    prev = df.iloc[-2]
    return (
        prev["Close"] > prev["Open"]
        and last["Close"] < last["Open"]
        and last["Open"] > prev["Close"]
        and last["Close"] < prev["Open"]
    )


def confirm_entry_5m(df_5m, bias: str) -> Tuple[bool, List[str]]:
    """
    Returns (entry_ok, reasons)
    Rule: require 2-of-3 confirmations on 5m:
      1) Strong candle / engulfing in direction
      2) RSI direction + midline
      3) EMA20 reclaim/break in direction
    """
    reasons: List[str] = []
    if df_5m is None or df_5m.empty or len(df_5m) < 30:
        return False, ["5m not enough data for entry confirmation"]

    hits = 0

    # 1) Candle confirmation
    strong, strong_reason = _candle_strength(df_5m)
    if bias == "Bullish":
        if _bullish_engulfing(df_5m):
            hits += 1
            reasons.append("5m bullish engulfing")
        elif strong and _last(df_5m, "Close") > _last(df_5m, "Open"):
            hits += 1
            reasons.append(strong_reason + " (bullish close)")
        else:
            reasons.append("5m candle not confirming long")

    elif bias == "Bearish":
        if _bearish_engulfing(df_5m):
            hits += 1
            reasons.append("5m bearish engulfing")
        elif strong and _last(df_5m, "Close") < _last(df_5m, "Open"):
            hits += 1
            reasons.append(strong_reason + " (bearish close)")
        else:
            reasons.append("5m candle not confirming short")

    # 2) RSI confirmation
    rsi_now = _last(df_5m, "rsi")
    rsi_prev = _prev(df_5m, "rsi")
    if bias == "Bullish":
        if rsi_now > rsi_prev and rsi_now >= 50:
            hits += 1
            reasons.append("5m RSI rising and >= 50")
        else:
            reasons.append("5m RSI not confirming long")
    elif bias == "Bearish":
        if rsi_now < rsi_prev and rsi_now <= 50:
            hits += 1
            reasons.append("5m RSI falling and <= 50")
        else:
            reasons.append("5m RSI not confirming short")

    # 3) EMA20 reclaim/break
    close_now = _last(df_5m, "Close")
    ema20_now = _last(df_5m, "ema20")
    ema20_prev = _prev(df_5m, "ema20")
    close_prev = _prev(df_5m, "Close")

    if bias == "Bullish":
        # reclaim = was below EMA20, now above EMA20
        if close_prev < ema20_prev and close_now > ema20_now:
            hits += 1
            reasons.append("5m reclaimed EMA20 upward")
        else:
            reasons.append("5m no EMA20 reclaim for long")
    elif bias == "Bearish":
        # break = was above EMA20, now below EMA20
        if close_prev > ema20_prev and close_now < ema20_now:
            hits += 1
            reasons.append("5m broke below EMA20 downward")
        else:
            reasons.append("5m no EMA20 break for short")

    entry_ok = hits >= 2
    reasons.insert(0, f"5m entry confirmations: {hits}/3")
    return entry_ok, reasons


def confirm_breakout_retest_5m(df_5m, bias: str, breakout_level: float) -> Tuple[bool, List[str]]:
    """
    Breakout retest entry logic (exact entry):

    - Retest must happen on PRIOR candles (not the same candle as rejection)
    - Latest candle must show rejection in the trade direction

    Bullish breakout:
      - previous candles retest level (touch near)
      - last candle closes back ABOVE level
      - plus confirm_entry_5m (2-of-3)

    Bearish breakdown:
      - previous candles retest level (touch near)
      - last candle closes back BELOW level
      - plus confirm_entry_5m (2-of-3)
    """
    if df_5m is None or df_5m.empty or len(df_5m) < 50:
        return False, ["5m not enough data for breakout retest confirmation"]

    level = float(breakout_level)
    last = df_5m.iloc[-1]

    close_now = float(last["Close"])
    atr5 = _last(df_5m, "atr")

    # retest tolerance: 0.25 ATR or 0.10% price (whichever larger)
    tol = max(0.25 * atr5, 0.001 * close_now)

    # Step 1: Retest must occur BEFORE the rejection candle
    # Check previous 3 candles (exclude last)
    recent_prev = df_5m.iloc[-4:-1]
    touched = False
    for _, r in recent_prev.iterrows():
        lo = float(r["Low"])
        hi = float(r["High"])
        if lo <= level + tol and hi >= level - tol:
            touched = True
            break

    if not touched:
        return False, [f"No retest near breakout level {level:.2f} (tol {tol:.2f}) on prior candles"]

    reasons: List[str] = [f"Retest detected near level {level:.2f} (tol {tol:.2f})"]

    # Step 2: Rejection close must be on LAST candle
    if bias == "Bullish":
        if close_now <= level:
            return False, reasons + [f"Rejection not confirmed (close {close_now:.2f} <= level {level:.2f})"]
        reasons.append(f"Rejection confirmed (close {close_now:.2f} > level {level:.2f})")

    elif bias == "Bearish":
        if close_now >= level:
            return False, reasons + [f"Rejection not confirmed (close {close_now:.2f} >= level {level:.2f})"]
        reasons.append(f"Rejection confirmed (close {close_now:.2f} < level {level:.2f})")

    else:
        return False, ["Neutral bias cannot confirm breakout retest"]

    # Step 3: Standard 5m confirmations (2-of-3)
    ok, sub = confirm_entry_5m(df_5m, bias=bias)
    if not ok:
        return False, reasons + sub

    return True, reasons + sub
