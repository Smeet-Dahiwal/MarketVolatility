# market_predictor/trade_refine.py
from typing import Tuple, Dict, Optional
import math


# ---------- TUNABLES ----------
RETEST_LOOKBACK = 6          # last 6x 5m candles (~30m) for retest swing
PULLBACK_LOOKBACK = 10       # last 10x 5m candles (~50m) for swing
BUFFER_ATR_MULT = 0.20       # SL buffer = 0.20 * ATR (5m)
BUFFER_PCT = 0.0010          # or 0.10% of price (whichever bigger)

MAX_RISK_ATR_MULT = 1.20     # if entry->SL risk > 1.2 * ATR => reject refinement (too wide)
MIN_RISK_ATR_MULT = 0.15     # if risk < 0.15 * ATR => bump risk (avoid too tight)

ROUND_DECIMALS = 2
# ------------------------------


def _last(df, col: str) -> float:
    return float(df[col].iloc[-1])


def _swing_low(df, lookback: int) -> float:
    return float(df["Low"].tail(lookback).min())


def _swing_high(df, lookback: int) -> float:
    return float(df["High"].tail(lookback).max())


def _buffer(price: float, atr: float) -> float:
    return max(BUFFER_ATR_MULT * atr, BUFFER_PCT * price)


def _round(x: float) -> float:
    return round(float(x), ROUND_DECIMALS)


def refine_trade_levels_with_5m(
    df_5m,
    base_trade: dict,
    bias: str,
    rr: float = 2.0,
    trade_type: Optional[str] = None,
    breakout_level: Optional[float] = None,
) -> Tuple[Optional[Dict], str]:
    """
    Refines entry/SL/TP using 5m structure for tighter execution.

    For BREAKOUT_TREND:
      - requires breakout_level
      - SL anchored to min/max(retest swing, breakout level) +/- buffer

    For PULLBACK_TREND (or unknown):
      - SL anchored to recent swing +/- buffer

    Returns (refined_trade_or_none, reason)
    """

    if df_5m is None or df_5m.empty or len(df_5m) < 30:
        return None, "5m not enough data to refine trade"

    if not base_trade:
        return None, "missing base_trade"

    if bias not in ("Bullish", "Bearish"):
        return None, "bias invalid"

    price = _last(df_5m, "Close")
    atr = _last(df_5m, "atr")
    if atr <= 0:
        return None, "ATR invalid"

    buf = _buffer(price, atr)

    # Default entry = last 5m close (retest + rejection should already be confirmed by entry_confirm)
    entry = float(price)

    # --- BREAKOUT STRUCTURE STOP ---
    if trade_type == "BREAKOUT_TREND":
        if breakout_level is None:
            return None, "breakout_level missing for breakout refinement"

        lvl = float(breakout_level)

        # Validate entry is on correct side of level (basic sanity)
        if bias == "Bullish" and entry <= lvl:
            return None, f"entry {entry:.2f} not above breakout level {lvl:.2f}"
        if bias == "Bearish" and entry >= lvl:
            return None, f"entry {entry:.2f} not below breakout level {lvl:.2f}"

        # Retest swing: last ~30m structure
        retest_low = _swing_low(df_5m, RETEST_LOOKBACK)
        retest_high = _swing_high(df_5m, RETEST_LOOKBACK)

        if bias == "Bullish":
            # Stop should be below support: below min(level, retest_low) - buffer
            support = min(lvl, retest_low)
            stop_loss = support - buf
        else:
            # Stop should be above resistance: above max(level, retest_high) + buffer
            resistance = max(lvl, retest_high)
            stop_loss = resistance + buf

        risk = abs(entry - stop_loss)

        # Risk sanity
        if risk > MAX_RISK_ATR_MULT * atr:
            return None, f"SL too wide for breakout (risk {risk:.2f} > {MAX_RISK_ATR_MULT}*ATR)"
        if risk < MIN_RISK_ATR_MULT * atr:
            # push SL slightly wider (avoid tiny stop-outs)
            if bias == "Bullish":
                stop_loss = entry - (MIN_RISK_ATR_MULT * atr)
            else:
                stop_loss = entry + (MIN_RISK_ATR_MULT * atr)
            risk = abs(entry - stop_loss)

        # TP from RR
        if bias == "Bullish":
            take_profit = entry + (risk * rr)
        else:
            take_profit = entry - (risk * rr)

        refined = {
            "entry": _round(entry),
            "stop_loss": _round(stop_loss),
            "take_profit": _round(take_profit),
            "rr": _round(rr),
            "note": f"Refined trade levels (BREAKOUT): level={lvl:.2f}, buf={buf:.2f}, risk={risk:.2f}",
        }
        return refined, refined["note"]

    # --- PULLBACK / GENERIC STOP ---
    # Use recent swing structure (more forgiving than breakout)
    if bias == "Bullish":
        swing = _swing_low(df_5m, PULLBACK_LOOKBACK)
        stop_loss = swing - buf
    else:
        swing = _swing_high(df_5m, PULLBACK_LOOKBACK)
        stop_loss = swing + buf

    risk = abs(entry - stop_loss)

    # Risk sanity
    if risk > MAX_RISK_ATR_MULT * atr:
        return None, f"SL too wide (risk {risk:.2f} > {MAX_RISK_ATR_MULT}*ATR)"
    if risk < MIN_RISK_ATR_MULT * atr:
        # widen a bit
        if bias == "Bullish":
            stop_loss = entry - (MIN_RISK_ATR_MULT * atr)
        else:
            stop_loss = entry + (MIN_RISK_ATR_MULT * atr)
        risk = abs(entry - stop_loss)

    # TP from RR
    if bias == "Bullish":
        take_profit = entry + (risk * rr)
    else:
        take_profit = entry - (risk * rr)

    refined = {
        "entry": _round(entry),
        "stop_loss": _round(stop_loss),
        "take_profit": _round(take_profit),
        "rr": _round(rr),
        "note": f"Refined trade levels (PULLBACK): buf={buf:.2f}, risk={risk:.2f}",
    }
    return refined, refined["note"]
