# market_predictor/strategy.py
# ============================================================
# Trade Types (v1): Pullback Trend, Breakout Trend, No-Trade
# Designed for: 1H trend filter + 15m execution timeframe
# Enhanced: Adds Trend Summary + Pattern Matching (Top 2 in alerts)
# ============================================================

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from market_predictor.patterns import detect_patterns


# ---------------------------
# Config (tune here)
# ---------------------------
@dataclass(frozen=True)
class StrategyConfig:
    # Regime
    adx_no_trade_below: float = 18.0
    adx_trend_strong: float = 25.0

    # Pullback zone (ATR based)
    pullback_zone_atr_mult: float = 0.60
    pullback_deep_break_ema50: bool = True

    # Breakout validation
    breakout_lookback: int = 20
    breakout_requires_atr_expansion: bool = True
    atr_expansion_mult: float = 1.05

    # Confirmation rules
    pullback_confirm_min_signals: int = 2
    breakout_confirm_min_signals: int = 2

    # Confidence thresholds
    min_conf_pullback: int = 70
    min_conf_breakout: int = 72

    # Trade levels
    rr_ratio_pullback: float = 2.0
    rr_ratio_breakout: float = 2.2
    sl_atr_buffer: float = 0.30

    # Neutral zone
    neutral_confidence: int = 50


CFG = StrategyConfig()


# ---------------------------
# Helpers: safe access
# ---------------------------
def _last(df, col: str):
    return float(df[col].iloc[-1])


def _prev(df, col: str):
    return float(df[col].iloc[-2])


def _rolling_max(df, col: str, n: int, shift: int = 1) -> float:
    return float(df[col].rolling(n).max().shift(shift).iloc[-1])


def _rolling_min(df, col: str, n: int, shift: int = 1) -> float:
    return float(df[col].rolling(n).min().shift(shift).iloc[-1])


def _atr_avg_14(df) -> float:
    return float(df["atr"].rolling(14).mean().iloc[-1])


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# ---------------------------
# Trend summaries (EMA20 vs EMA50)
# ---------------------------
def _ema_trend_state(df) -> Tuple[str, str]:
    """
    Returns:
      state: Bullish | Bearish | Sideways
      comp: EMA20>EMA50 | EMA20<EMA50 | EMA20≈EMA50
    """
    ema20 = _last(df, "ema20")
    ema50 = _last(df, "ema50")
    price = _last(df, "Close")
    tol = max(price * 0.0005, 1e-9)  # ~0.05% of price
    if abs(ema20 - ema50) <= tol:
        return "Sideways", "EMA20≈EMA50"
    if ema20 > ema50:
        return "Bullish", "EMA20>EMA50"
    return "Bearish", "EMA20<EMA50"


def _trend_line(df, tf: str) -> Tuple[str, str]:
    state, comp = _ema_trend_state(df)
    return state, f"{tf} Trend: {state} ({comp})"


def _alignment(tf_a: str, state_a: str, tf_b: str, state_b: str) -> str:
    if "Sideways" in (state_a, state_b):
        return f"Trend Alignment: {tf_a} vs {tf_b}: Neutral (Sideways involved)"
    if state_a == state_b:
        return f"Trend Alignment: {tf_a} vs {tf_b}: Aligned {state_a} ✅"
    return f"Trend Alignment: {tf_a} vs {tf_b}: Conflict ⚠️ ({state_a} vs {state_b})"


# ---------------------------
# Core: 1H trend + regime
# ---------------------------
def trend_direction_1h(df_1h) -> Tuple[str, List[str]]:
    reasons = []
    ema20 = _last(df_1h, "ema20")
    ema50 = _last(df_1h, "ema50")

    if ema20 > ema50:
        reasons.append("1H trend bullish (EMA20 > EMA50)")
        return "BULL", reasons
    if ema20 < ema50:
        reasons.append("1H trend bearish (EMA20 < EMA50)")
        return "BEAR", reasons

    reasons.append("1H trend unclear (EMA20 ~= EMA50)")
    return "NONE", reasons


def regime_filter_15m(df_15m) -> Tuple[bool, int, List[str]]:
    reasons = []
    adx = _last(df_15m, "adx")

    if adx < CFG.adx_no_trade_below:
        reasons.append(f"ADX {adx:.2f} < {CFG.adx_no_trade_below} (choppy/ranging) -> NO_TRADE")
        return False, 55, reasons

    if adx < CFG.adx_trend_strong:
        reasons.append(f"ADX {adx:.2f} in {CFG.adx_no_trade_below}-{CFG.adx_trend_strong} (moderate trend)")
        return True, 75, reasons

    reasons.append(f"ADX {adx:.2f} >= {CFG.adx_trend_strong} (strong trend)")
    return True, 100, reasons


# ---------------------------
# Confirmation signals
# ---------------------------
def candle_engulfing(df) -> Tuple[int, str]:
    last = df.iloc[-1]
    prev = df.iloc[-2]

    if prev["Close"] < prev["Open"] and last["Close"] > last["Open"] \
       and last["Close"] > prev["Open"] and last["Open"] < prev["Close"]:
        return +1, "Bullish engulfing"

    if prev["Close"] > prev["Open"] and last["Close"] < last["Open"] \
       and last["Open"] > prev["Close"] and last["Close"] < prev["Open"]:
        return -1, "Bearish engulfing"

    return 0, "No engulfing"


def candle_strength(df) -> Tuple[bool, str]:
    last = df.iloc[-1]
    body = abs(last["Close"] - last["Open"])
    wick = (last["High"] - last["Low"]) - body
    if body > wick:
        return True, "Strong candle body"
    return False, "Weak candle body"


def rsi_recovery(df, direction: str) -> Tuple[bool, str]:
    rsi_now = _last(df, "rsi")
    rsi_prev = _prev(df, "rsi")

    if direction == "BULL":
        if rsi_now > rsi_prev and rsi_now >= 50:
            return True, "RSI recovering (>=50 and rising)"
        return False, "RSI not recovered for long"

    if direction == "BEAR":
        if rsi_now < rsi_prev and rsi_now <= 50:
            return True, "RSI weakening (<=50 and falling)"
        return False, "RSI not weakened for short"

    return False, "RSI not applicable (no trend)"


def macd_confirmation(df, direction: str) -> Tuple[bool, str]:
    macd_now = _last(df, "macd")
    macd_prev = _prev(df, "macd")

    if direction == "BULL":
        if macd_now > macd_prev:
            return True, "MACD improving (rising)"
        return False, "MACD not improving"

    if direction == "BEAR":
        if macd_now < macd_prev:
            return True, "MACD deteriorating (falling)"
        return False, "MACD not deteriorating"

    return False, "MACD not applicable (no trend)"


# ---------------------------
# Pullback module
# ---------------------------
def _in_pullback_zone(df_15m, direction: str) -> Tuple[bool, List[str]]:
    reasons = []
    price = _last(df_15m, "Close")
    atr = _last(df_15m, "atr")
    vwap = _last(df_15m, "vwap")
    ema20 = _last(df_15m, "ema20")
    ema50 = _last(df_15m, "ema50")

    tol = CFG.pullback_zone_atr_mult * atr

    near_vwap = abs(price - vwap) <= tol
    near_ema20 = abs(price - ema20) <= tol

    if near_vwap:
        reasons.append("Price in pullback zone (near VWAP)")
    if near_ema20:
        reasons.append("Price in pullback zone (near EMA20)")

    if not (near_vwap or near_ema20):
        return False, ["Not in pullback zone (VWAP/EMA20)"]

    if CFG.pullback_deep_break_ema50:
        if direction == "BULL" and price < ema50:
            return False, ["Pullback too deep (Close < EMA50)"]
        if direction == "BEAR" and price > ema50:
            return False, ["Pullback too deep (Close > EMA50)"]

    return True, reasons


def detect_pullback_trend(df_15m, df_1h, cap: int) -> Optional[Dict]:
    direction, trend_reasons = trend_direction_1h(df_1h)
    if direction not in ("BULL", "BEAR"):
        return None

    in_zone, zone_reasons = _in_pullback_zone(df_15m, direction)
    if not in_zone:
        return None

    conf_hits = 0
    conf_reasons = []

    engulf, engulf_reason = candle_engulfing(df_15m)
    strong, strong_reason = candle_strength(df_15m)
    rsi_ok, rsi_reason = rsi_recovery(df_15m, direction)
    macd_ok, macd_reason = macd_confirmation(df_15m, direction)

    if direction == "BULL" and engulf == +1:
        conf_hits += 1
        conf_reasons.append(engulf_reason)
    elif direction == "BEAR" and engulf == -1:
        conf_hits += 1
        conf_reasons.append(engulf_reason)

    if strong:
        conf_hits += 1
        conf_reasons.append(strong_reason)

    if rsi_ok:
        conf_hits += 1
        conf_reasons.append(rsi_reason)

    if macd_ok:
        conf_hits += 1
        conf_reasons.append(macd_reason)

    if conf_hits < CFG.pullback_confirm_min_signals:
        return None

    base = 70 if cap >= 75 else 62
    bonus = 0
    bonus += 6 if any("VWAP" in r for r in zone_reasons) else 0
    bonus += 6 if any("EMA20" in r for r in zone_reasons) else 0
    bonus += 4 * (conf_hits - CFG.pullback_confirm_min_signals + 1)

    conf = int(_clamp(base + bonus, 0, cap))
    if conf < CFG.min_conf_pullback:
        return None

    bias = "Bullish" if direction == "BULL" else "Bearish"
    reasons = trend_reasons + zone_reasons + conf_reasons
    trade = trade_levels_pullback(df_15m, bias, conf)

    return {
        "trade_type": "PULLBACK_TREND",
        "bias": bias,
        "confidence": conf,
        "expected_move": expected_move_projection(df_15m, conf, bias),
        "trade": trade,
        "reasons": reasons,
    }


# ---------------------------
# Breakout module
# ---------------------------
def _breakout_trigger(df_15m, direction: str) -> Tuple[bool, List[str], float, str]:
    reasons = []
    high = _last(df_15m, "High")
    low = _last(df_15m, "Low")
    close = _last(df_15m, "Close")

    prev_high = _rolling_max(df_15m, "High", CFG.breakout_lookback, shift=1)
    prev_low = _rolling_min(df_15m, "Low", CFG.breakout_lookback, shift=1)

    if direction == "BULL":
        level = prev_high
        if high > level and close > level:
            reasons.append(f"Breakout above {CFG.breakout_lookback}-candle high ({level:.2f})")
            return True, reasons, float(level), "ABOVE"
        return False, ["No bullish breakout trigger"], float(level), "ABOVE"

    if direction == "BEAR":
        level = prev_low
        if low < level and close < level:
            reasons.append(f"Breakdown below {CFG.breakout_lookback}-candle low ({level:.2f})")
            return True, reasons, float(level), "BELOW"
        return False, ["No bearish breakout trigger"], float(level), "BELOW"

    return False, ["Breakout not applicable (no trend)"], 0.0, "NA"


def detect_breakout_trend(df_15m, df_1h, cap: int) -> Optional[Dict]:
    direction, trend_reasons = trend_direction_1h(df_1h)
    if direction not in ("BULL", "BEAR"):
        return None

    trig, trig_reasons, breakout_level, breakout_side = _breakout_trigger(df_15m, direction)
    if not trig:
        return None

    conf_hits = 0
    conf_reasons = []

    strong, strong_reason = candle_strength(df_15m)
    if strong:
        conf_hits += 1
        conf_reasons.append(strong_reason)

    atr_now = _last(df_15m, "atr")
    atr_avg = _atr_avg_14(df_15m)
    atr_ok = True
    if CFG.breakout_requires_atr_expansion:
        atr_ok = atr_now >= (CFG.atr_expansion_mult * atr_avg)
    if atr_ok:
        conf_hits += 1
        conf_reasons.append("ATR expansion confirms breakout")
    else:
        conf_reasons.append("ATR expansion missing (fakeout risk)")

    price = _last(df_15m, "Close")
    vwap = _last(df_15m, "vwap")
    if direction == "BULL" and price > vwap:
        conf_hits += 1
        conf_reasons.append("Price above VWAP (breakout supported)")
    elif direction == "BEAR" and price < vwap:
        conf_hits += 1
        conf_reasons.append("Price below VWAP (breakdown supported)")
    else:
        conf_reasons.append("VWAP not aligned")

    if conf_hits < CFG.breakout_confirm_min_signals:
        return None

    base = 72 if cap >= 75 else 64
    bonus = 6 + 4 * (conf_hits - CFG.breakout_confirm_min_signals + 1)
    conf = int(_clamp(base + bonus, 0, cap))
    if conf < CFG.min_conf_breakout:
        return None

    bias = "Bullish" if direction == "BULL" else "Bearish"
    reasons = trend_reasons + trig_reasons + conf_reasons
    trade = trade_levels_breakout(df_15m, bias, conf)

    return {
        "trade_type": "BREAKOUT_TREND",
        "bias": bias,
        "confidence": conf,
        "expected_move": expected_move_projection(df_15m, conf, bias),
        "trade": trade,
        "reasons": reasons,
        "breakout_level": breakout_level,
        "breakout_side": breakout_side,
    }


# ---------------------------
# Expected move + trade levels
# ---------------------------
def expected_move_projection(df_15m, confidence: int, bias: str) -> Dict:
    atr = _last(df_15m, "atr")
    adx = _last(df_15m, "adx")

    if confidence < 65:
        conf_mult = 0.7
    elif confidence < 75:
        conf_mult = 1.0
    elif confidence < 85:
        conf_mult = 1.4
    else:
        conf_mult = 1.8

    if adx < 20:
        trend_mult = 0.6
    elif adx < 25:
        trend_mult = 1.0
    else:
        trend_mult = 1.4

    min_move = atr * conf_mult * 0.7
    max_move = atr * conf_mult * trend_mult

    direction = "range"
    if bias == "Bullish":
        direction = "up"
    elif bias == "Bearish":
        direction = "down"

    return {"min_points": round(min_move, 2), "max_points": round(max_move, 2), "direction": direction}


def _swing_low(df, lookback: int = 10) -> float:
    return float(df["Low"].tail(lookback).min())


def _swing_high(df, lookback: int = 10) -> float:
    return float(df["High"].tail(lookback).max())


def trade_levels_pullback(df_15m, bias: str, confidence: int) -> Optional[Dict]:
    if bias not in ("Bullish", "Bearish") or confidence < 65:
        return None

    price = _last(df_15m, "Close")
    atr = _last(df_15m, "atr")

    if bias == "Bullish":
        swing = _swing_low(df_15m, 10)
        stop_loss = min(price - atr, swing - (CFG.sl_atr_buffer * atr))
        take_profit = price + (price - stop_loss) * CFG.rr_ratio_pullback
    else:
        swing = _swing_high(df_15m, 10)
        stop_loss = max(price + atr, swing + (CFG.sl_atr_buffer * atr))
        take_profit = price - (stop_loss - price) * CFG.rr_ratio_pullback

    return {
        "entry": round(price, 2),
        "stop_loss": round(stop_loss, 2),
        "take_profit": round(take_profit, 2),
        "rr": round(CFG.rr_ratio_pullback, 2),
    }


def trade_levels_breakout(df_15m, bias: str, confidence: int) -> Optional[Dict]:
    if bias not in ("Bullish", "Bearish") or confidence < 65:
        return None

    price = _last(df_15m, "Close")
    atr = _last(df_15m, "atr")

    if bias == "Bullish":
        swing = _swing_low(df_15m, 8)
        stop_loss = min(price - 0.9 * atr, swing - (0.2 * atr))
        take_profit = price + (price - stop_loss) * CFG.rr_ratio_breakout
    else:
        swing = _swing_high(df_15m, 8)
        stop_loss = max(price + 0.9 * atr, swing + (0.2 * atr))
        take_profit = price - (stop_loss - price) * CFG.rr_ratio_breakout

    return {
        "entry": round(price, 2),
        "stop_loss": round(stop_loss, 2),
        "take_profit": round(take_profit, 2),
        "rr": round(CFG.rr_ratio_breakout, 2),
    }


# ---------------------------
# Pattern + Trend enrichment
# ---------------------------
def _pattern_lines(patterns, label: str, top_n: int = 2):
    """
    patterns: list[dict] returned by market_predictor.patterns.detect_patterns()
    """
    lines = []
    if not patterns or not isinstance(patterns, list):
        return lines

    for p in patterns[:top_n]:
        if not isinstance(p, dict):
            continue
        name = p.get("name", "Unknown")
        kind = p.get("kind", "")
        direction = p.get("direction", "")
        conf = p.get("confidence", "")
        lines.append(f"{label} Pattern: {name} ({kind}) – {direction} ({conf}%)")
    return lines


def _top2(patterns) -> List[Dict]:
    if not patterns or not isinstance(patterns, list):
        return []
    # already sorted by patterns.py, but keep safe
    patterns_sorted = sorted(patterns, key=lambda x: int(x.get("confidence", 0)) if isinstance(x, dict) else 0, reverse=True)
    return patterns_sorted[:2]


# ---------------------------
# Master selector (priority order)
# Added: Trend Summary + Pattern Matching (does not change trade decision)
# ---------------------------
def predict_next_candle(df_15m, df_1h, df_5m=None) -> Dict:
    reasons: List[str] = []

    # Trend summary lines
    s1h, line_1h = _trend_line(df_1h, "1H")
    s15, line_15 = _trend_line(df_15m, "15m")
    reasons.extend([line_1h, line_15, _alignment("15m", s15, "1H", s1h)])

    # 15m patterns always (setup quality info)
    patterns_15m = detect_patterns(df_15m, tf="15m")
    if patterns_15m:
        reasons.extend(_pattern_lines(patterns_15m, "15m", top_n=2))

    # 5m optional enrichment
    patterns_5m = []
    if df_5m is not None and getattr(df_5m, "empty", True) is False and len(df_5m) >= 80:
        s5, line_5 = _trend_line(df_5m, "5m")
        reasons.extend([line_5, _alignment("5m", s5, "15m", s15)])
        patterns_5m = detect_patterns(df_5m, tf="5m")
        if patterns_5m:
            reasons.extend(_pattern_lines(patterns_5m, "5m", top_n=2))

    eligible, cap, reg_reasons = regime_filter_15m(df_15m)
    reasons.extend(reg_reasons)

    patterns_payload = {
        "15m": _top2(patterns_15m),
        "5m": _top2(patterns_5m),
    }

    if not eligible:
        conf = min(CFG.neutral_confidence, cap)
        return {
            "trade_type": "NO_TRADE",
            "bias": "Neutral",
            "confidence": conf,
            "expected_move": expected_move_projection(df_15m, conf, "Neutral"),
            "trade": None,
            "reasons": reasons,
            "patterns": patterns_payload,
        }

    pull = detect_pullback_trend(df_15m, df_1h, cap)
    if pull:
        pull["reasons"] = reasons + pull["reasons"]
        pull["patterns"] = patterns_payload
        return pull

    brk = detect_breakout_trend(df_15m, df_1h, cap)
    if brk:
        brk["reasons"] = reasons + brk["reasons"]
        brk["patterns"] = patterns_payload
        return brk

    reasons.append("No high-quality setup detected (pullback/breakout filters not satisfied)")
    return {
        "trade_type": "NO_TRADE",
        "bias": "Neutral",
        "confidence": CFG.neutral_confidence,
        "expected_move": expected_move_projection(df_15m, CFG.neutral_confidence, "Neutral"),
        "trade": None,
        "reasons": reasons,
        "patterns": patterns_payload,
    }
