# market_predictor/patterns.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ----------------------------
# Data structures
# ----------------------------
@dataclass
class PatternHit:
    name: str
    kind: str              # "Triangle" | "Wedge" | "Flag" | "H&S" | ...
    direction: str         # "Bullish" | "Bearish" | "Neutral"
    confidence: int        # 0-100
    meta: dict


# ----------------------------
# Helpers
# ----------------------------
def _require_cols(df: pd.DataFrame, cols: List[str]) -> bool:
    return df is not None and (not df.empty) and all(c in df.columns for c in cols)


def _linreg_slope(x: np.ndarray, y: np.ndarray) -> float:
    # slope of y = a + b*x
    if len(x) < 2:
        return 0.0
    b = np.polyfit(x, y, 1)[0]
    return float(b)


def _pct(a: float, b: float) -> float:
    # percent change from a to b
    if a == 0:
        return 0.0
    return ((b - a) / abs(a)) * 100.0


def _pivot_points(series: pd.Series, left: int = 3, right: int = 3, mode: str = "high") -> List[Tuple[int, float]]:
    """
    Simple pivot detector.
    mode="high": pivot high when current > neighbors
    mode="low":  pivot low  when current < neighbors
    Returns list of (index_position, value)
    """
    vals = series.values
    out = []
    n = len(vals)
    for i in range(left, n - right):
        window_left = vals[i - left:i]
        window_right = vals[i + 1:i + 1 + right]
        if mode == "high":
            if vals[i] > window_left.max() and vals[i] > window_right.max():
                out.append((i, float(vals[i])))
        else:
            if vals[i] < window_left.min() and vals[i] < window_right.min():
                out.append((i, float(vals[i])))
    return out


def _trend_ema(df: pd.DataFrame) -> Tuple[str, str]:
    """
    Returns ("Bullish"/"Bearish"/"Sideways", reason)
    """
    if not _require_cols(df, ["ema20", "ema50"]):
        return "Unknown", "EMA missing"
    ema20 = float(df["ema20"].iloc[-1])
    ema50 = float(df["ema50"].iloc[-1])
    if ema20 > ema50:
        return "Bullish", "EMA20>EMA50"
    if ema20 < ema50:
        return "Bearish", "EMA20<EMA50"
    return "Sideways", "EMA20≈EMA50"


# ----------------------------
# Pattern detectors (lightweight heuristics)
# These are intentionally conservative (avoid false positives).
# ----------------------------
def _detect_triangle(df: pd.DataFrame, lookback: int = 80) -> Optional[PatternHit]:
    """
    Detects: symmetrical / ascending / descending triangle (simplified).
    Uses pivot highs/lows and compares slopes.
    """
    if not _require_cols(df, ["High", "Low", "Close"]):
        return None
    if len(df) < lookback:
        return None

    d = df.tail(lookback).copy()
    highs = _pivot_points(d["High"], mode="high")
    lows = _pivot_points(d["Low"], mode="low")
    if len(highs) < 3 or len(lows) < 3:
        return None

    # take last 3 pivots
    hs = highs[-3:]
    ls = lows[-3:]

    xh = np.array([p[0] for p in hs], dtype=float)
    yh = np.array([p[1] for p in hs], dtype=float)
    xl = np.array([p[0] for p in ls], dtype=float)
    yl = np.array([p[1] for p in ls], dtype=float)

    sh = _linreg_slope(xh, yh)  # slope of highs
    sl = _linreg_slope(xl, yl)  # slope of lows

    # Normalize slopes relative to price scale
    price = float(d["Close"].iloc[-1])
    sh_pct = (sh / price) * 100.0
    sl_pct = (sl / price) * 100.0

    # Convergence requirement: highs down or flat, lows up or flat, and range shrinking
    range_start = float(d["High"].iloc[0] - d["Low"].iloc[0])
    range_end = float(d["High"].iloc[-1] - d["Low"].iloc[-1])
    if range_start <= 0:
        return None
    shrink = (range_end / range_start)

    if shrink > 0.85:
        return None  # not contracting enough

    # Classification
    name = None
    direction = "Neutral"
    kind = "Triangle"

    # thresholds in slope% per bar (very small numbers)
    # We just need relative sign/strength
    if sh_pct < -0.01 and sl_pct > 0.01:
        name = "Symmetrical Triangle"
        direction = "Neutral"
    elif abs(sh_pct) <= 0.01 and sl_pct > 0.01:
        name = "Ascending Triangle"
        direction = "Bullish"
    elif sh_pct < -0.01 and abs(sl_pct) <= 0.01:
        name = "Descending Triangle"
        direction = "Bearish"
    else:
        return None

    # Confidence: more contraction + better pivot consistency
    conf = 70
    conf += int(max(0, min(15, (1.0 - shrink) * 100)))  # stronger contraction => higher
    conf = min(conf, 88)

    return PatternHit(
        name=name,
        kind=kind,
        direction=direction,
        confidence=int(conf),
        meta={"lookback": lookback, "shrink": round(shrink, 3), "sh_pct": round(sh_pct, 4), "sl_pct": round(sl_pct, 4)},
    )


def _detect_flag(df: pd.DataFrame, lookback: int = 60) -> Optional[PatternHit]:
    """
    Very rough flag detector:
    - strong impulse over last ~15 bars
    - then tight channel/sideways consolidation last ~20 bars
    """
    if not _require_cols(df, ["High", "Low", "Close", "atr"]):
        return None
    if len(df) < lookback:
        return None

    d = df.tail(lookback).copy()

    impulse = d.tail(15)
    cons = d.tail(25)

    imp_move = float(impulse["Close"].iloc[-1] - impulse["Close"].iloc[0])
    atr = float(d["atr"].iloc[-1])
    if atr <= 0:
        return None

    # impulse must be >= ~2 ATR
    if abs(imp_move) < 2.0 * atr:
        return None

    # consolidation range must be tight: <= ~1.5 ATR
    cons_range = float(cons["High"].max() - cons["Low"].min())
    if cons_range > 1.5 * atr:
        return None

    direction = "Bullish" if imp_move > 0 else "Bearish"
    name = "Bull Flag" if imp_move > 0 else "Bear Flag"

    conf = 72
    # stronger impulse -> higher
    conf += int(min(10, (abs(imp_move) / atr) * 2))
    conf = min(conf, 88)

    return PatternHit(
        name=name,
        kind="Flag",
        direction=direction,
        confidence=int(conf),
        meta={"impulse_atr": round(abs(imp_move) / atr, 2), "cons_range_atr": round(cons_range / atr, 2)},
    )


def _detect_head_shoulders(df: pd.DataFrame, lookback: int = 120) -> Optional[PatternHit]:
    """
    Simplified Head & Shoulders (bearish) / Inverse H&S (bullish):
    Uses pivot highs (or lows) and checks the middle pivot is the extreme.
    """
    if not _require_cols(df, ["High", "Low", "Close"]):
        return None
    if len(df) < lookback:
        return None

    d = df.tail(lookback).copy()

    highs = _pivot_points(d["High"], mode="high")
    lows = _pivot_points(d["Low"], mode="low")

    # Bearish H&S: 3 highs, middle is highest, shoulders similar height
    if len(highs) >= 3:
        a, b, c = highs[-3], highs[-2], highs[-1]
        la, lb, lc = a[1], b[1], c[1]
        if lb > la and lb > lc:
            shoulder_diff = abs(la - lc) / max(la, lc) * 100.0
            if shoulder_diff <= 1.8:  # shoulders similar
                conf = 74 if shoulder_diff < 1.0 else 70
                return PatternHit(
                    name="Head & Shoulders",
                    kind="H&S",
                    direction="Bearish",
                    confidence=int(min(86, conf)),
                    meta={"shoulder_diff_pct": round(shoulder_diff, 2)},
                )

    # Bullish inverse H&S: 3 lows, middle is lowest, shoulders similar
    if len(lows) >= 3:
        a, b, c = lows[-3], lows[-2], lows[-1]
        la, lb, lc = a[1], b[1], c[1]
        if lb < la and lb < lc:
            shoulder_diff = abs(la - lc) / max(abs(la), abs(lc)) * 100.0
            if shoulder_diff <= 1.8:
                conf = 74 if shoulder_diff < 1.0 else 70
                return PatternHit(
                    name="Inverse Head & Shoulders",
                    kind="H&S",
                    direction="Bullish",
                    confidence=int(min(86, conf)),
                    meta={"shoulder_diff_pct": round(shoulder_diff, 2)},
                )

    return None


# ----------------------------
# Public API
# ----------------------------
def detect_patterns(df: pd.DataFrame, tf: str) -> List[Dict]:
    """
    Returns list of dicts sorted by confidence desc.
    Output dict schema used by main.py:
      {"name","kind","direction","confidence","meta"}
    """
    hits: List[PatternHit] = []

    tri = _detect_triangle(df)
    if tri:
        hits.append(tri)

    flag = _detect_flag(df)
    if flag:
        hits.append(flag)

    hs = _detect_head_shoulders(df)
    if hs:
        hits.append(hs)

    # Sort and convert to dict
    hits.sort(key=lambda x: x.confidence, reverse=True)

    out: List[Dict] = []
    for h in hits:
        out.append(
            {
                "tf": tf,
                "name": h.name,
                "kind": h.kind,
                "direction": h.direction,
                "confidence": int(h.confidence),
                "meta": h.meta or {},
            }
        )
    return out
