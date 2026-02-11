# market_predictor/main.py
from datetime import datetime
from html import escape
import hashlib
import json

from market_predictor.data_fetcher import fetch_data
from market_predictor.indicators import add_indicators
from market_predictor.strategy import predict_next_candle
from market_predictor.alerts import send_telegram_alert
from market_predictor.entry_confirm import confirm_entry_5m, confirm_breakout_retest_5m
from market_predictor.trade_refine import refine_trade_levels_with_5m

from market_predictor.db import (
    init_db,
    insert_signal,
    insert_trade,
    insert_alert,
    should_send_alert,
)

DB_PATH = "market_predictor.db"

CONFIDENCE_THRESHOLD = 70
SEND_SETUP_ALERT = True

# Cooldowns (dedup)
SETUP_COOLDOWN_MIN = 30
ENTRY_COOLDOWN_MIN = 60


def _snap_indicators(df, tf: str) -> list[str]:
    if df is None or df.empty:
        return [f"{tf}: (no data)"]

    last = df.iloc[-1]
    close = float(last["Close"])

    def g(name, default="n/a"):
        try:
            v = last[name]
            if v is None:
                return default
            return float(v)
        except Exception:
            return default

    ema20 = g("ema20")
    ema50 = g("ema50")
    rsi = g("rsi")
    adx = g("adx")
    atr = g("atr")
    vwap = g("vwap")

    lines = [f"{tf} Close: {close:.2f}"]
    if ema20 != "n/a" and ema50 != "n/a":
        lines.append(f"{tf} EMA20/EMA50: {ema20:.2f} / {ema50:.2f}")
    if rsi != "n/a":
        lines.append(f"{tf} RSI(14): {rsi:.2f}")
    if adx != "n/a":
        lines.append(f"{tf} ADX(14): {adx:.2f}")
    if atr != "n/a":
        atr_pct = (atr / close) * 100 if close else 0.0
        lines.append(f"{tf} ATR(14): {atr:.2f} ({atr_pct:.2f}%)")
    if vwap != "n/a":
        vwap_dist = ((close - vwap) / close) * 100 if close else 0.0
        lines.append(f"{tf} VWAP: {vwap:.2f} (dist {vwap_dist:.2f}%)")
    return lines


def _indicators_dict(df_1h, df_15m, df_5m=None) -> dict:
    """Store key indicator values (numbers) into DB for analysis."""
    def last_vals(df):
        if df is None or df.empty:
            return {}
        row = df.iloc[-1]
        out = {}
        for k in ["Close", "ema20", "ema50", "rsi", "adx", "atr", "vwap", "macd"]:
            if k in df.columns:
                try:
                    out[k] = float(row[k])
                except Exception:
                    pass
        return out

    d = {"1H": last_vals(df_1h), "15m": last_vals(df_15m)}
    if df_5m is not None:
        d["5m"] = last_vals(df_5m)
    return d


def _fingerprint(result: dict) -> str:
    """Stable fingerprint for dedup (trade_type + bias + entry+sl approx)."""
    trade_type = result.get("trade_type", "NO_TRADE")
    bias = result.get("bias", "Neutral")
    trade = result.get("trade") or {}
    entry = trade.get("entry")
    sl = trade.get("stop_loss")

    try:
        entry = round(float(entry), 2)
    except Exception:
        entry = "na"
    try:
        sl = round(float(sl), 2)
    except Exception:
        sl = "na"

    return f"{trade_type}|{bias}|{entry}|{sl}"


def _hash_message(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def format_alert(symbol: str, result: dict, alert_kind: str, extra_lines=None, indicator_lines=None) -> str:
    extra_lines = extra_lines or []
    indicator_lines = indicator_lines or []

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    trade = result.get("trade")

    safe_symbol = escape(symbol)
    safe_trade_type = escape(str(result.get("trade_type", "n/a")))
    safe_bias = escape(str(result.get("bias", "n/a")))
    safe_conf = escape(str(result.get("confidence", "n/a")))

    expected = result.get("expected_move", {}) or {}
    safe_dir = escape(str(expected.get("direction", "n/a")))
    safe_minp = escape(str(expected.get("min_points", "n/a")))
    safe_maxp = escape(str(expected.get("max_points", "n/a")))

    reasons = result.get("reasons", []) or []
    reasons_text = "\n".join([f"- {escape(str(r))}" for r in reasons]) if reasons else "- (no reasons)"

    entry_text = "\n".join([f"- {escape(str(x))}" for x in extra_lines]) if extra_lines else "- (not checked)"
    ind_text = "\n".join([f"- {escape(str(x))}" for x in indicator_lines]) if indicator_lines else "- (not available)"

    header = "✅ <b>ENTRY ALERT</b>" if alert_kind == "ENTRY" else "🟡 <b>SETUP ALERT</b>"

    trade_text = ""
    if trade and alert_kind == "ENTRY":
        trade_text = f"""
🎯 <b>TRADE LEVELS</b>
<b>Entry:</b> {escape(str(trade.get('entry')))}
<b>Stop Loss:</b> {escape(str(trade.get('stop_loss')))}
<b>Take Profit:</b> {escape(str(trade.get('take_profit')))}
<b>Risk:Reward:</b> 1:{escape(str(trade.get('rr')))}
"""
        if trade.get("note"):
            trade_text += f"\n<b>Note:</b> {escape(str(trade.get('note')))}\n"

    return f"""
{header}
-------------------
<b>Time:</b> {escape(timestamp)}
<b>Symbol:</b> {safe_symbol}
<b>Trade Type:</b> {safe_trade_type}
<b>Bias:</b> {safe_bias}
<b>Confidence:</b> {safe_conf}%

📈 <b>Expected Move:</b> {safe_dir}
<b>Range:</b> {safe_minp} - {safe_maxp}

📌 <b>Key Indicators:</b>
{ind_text}

📌 <b>Reasons:</b>
{reasons_text}

🔎 <b>Entry Timing (5m):</b>
{entry_text}
{trade_text}
""".strip()


def main(symbol: str = "BTC-USD", return_result: bool = False):
    init_db(DB_PATH)

    print(f"📥 Fetching market data for {symbol}...")

    df_15m = fetch_data(symbol, "15m", "10d", only_closed=True)
    df_1h = fetch_data(symbol, "1h", "60d", only_closed=True)

    if df_15m.empty or df_1h.empty:
        print("❌ Failed to fetch market data")
        return None

    df_15m = add_indicators(df_15m)
    df_1h = add_indicators(df_1h)

    indicator_lines = []
    indicator_lines += _snap_indicators(df_1h, "1H")
    indicator_lines += _snap_indicators(df_15m, "15m")

    result = predict_next_candle(df_15m, df_1h)

    trade_type = result.get("trade_type", "NO_TRADE")
    bias = result.get("bias", "Neutral")
    confidence = int(result.get("confidence", 0))
    trade = result.get("trade")

    expected = result.get("expected_move", {}) or {}
    fp = _fingerprint(result)
    ts = int(datetime.now().timestamp())

    # Always store SIGNAL to DB (even NO_TRADE)
    sig_payload = {
        "ts": ts,
        "symbol": symbol,
        "tf_trend": "1h",
        "tf_setup": "15m",
        "tf_entry": "5m",
        "trade_type": trade_type,
        "bias": bias,
        "confidence": confidence,
        "expected_direction": expected.get("direction"),
        "expected_min": expected.get("min_points"),
        "expected_max": expected.get("max_points"),
        "reasons": result.get("reasons", []) or [],
        "indicators": _indicators_dict(df_1h, df_15m),
        "fingerprint": fp,
    }
    insert_signal(sig_payload, DB_PATH)

    print(f"\nSymbol: {symbol}")
    print(f"Trade Type: {trade_type}")
    print(f"Bias: {bias}, Confidence: {confidence}%")
    print(f"Expected Move: {expected}")
    print(f"Trade: {trade}")

    # If no setup, stop here (we still stored the signal)
    if trade_type == "NO_TRADE" or not trade or confidence < CONFIDENCE_THRESHOLD:
        print("🔕 No alert sent (NO_TRADE or low confidence or missing trade plan)")
        return result if return_result else None

    # 5m entry timing check (only when setup exists)
    df_5m = fetch_data(symbol, "5m", "5d", only_closed=True)
    if df_5m.empty:
        if SEND_SETUP_ALERT:
            kind = "SETUP"
            if should_send_alert(symbol, kind, fp, SETUP_COOLDOWN_MIN, DB_PATH):
                msg = format_alert(symbol, result, alert_kind="SETUP", extra_lines=["5m data fetch failed"], indicator_lines=indicator_lines)
                ok = send_telegram_alert(msg)
                insert_alert(
                    {
                        "ts": ts,
                        "symbol": symbol,
                        "kind": kind,
                        "fingerprint": fp,
                        "status": "SENT" if ok else "FAILED",
                        "error": None if ok else "telegram_send_failed",
                        "message_hash": _hash_message(msg),
                    },
                    DB_PATH,
                )
            else:
                insert_alert(
                    {"ts": ts, "symbol": symbol, "kind": kind, "fingerprint": fp, "status": "SKIPPED", "error": "cooldown", "message_hash": None},
                    DB_PATH,
                )
        return result if return_result else None

    df_5m = add_indicators(df_5m)
    indicator_lines += _snap_indicators(df_5m, "5m")

    # Update signal indicators with 5m snapshot (optional but useful)
    sig_payload["indicators"] = _indicators_dict(df_1h, df_15m, df_5m)
    # Store another row? For simplicity, we keep the initial signal row as is.

    # ENTRY CONFIRMATION:
    # - Pullback: normal 5m confirmation
    # - Breakout: breakout retest + rejection + confirmation
    if trade_type == "BREAKOUT_TREND":
        level = result.get("breakout_level")
        if level is None:
            entry_ok, entry_reasons = False, ["Missing breakout_level from strategy (cannot enforce retest)"]
        else:
            entry_ok, entry_reasons = confirm_breakout_retest_5m(df_5m, bias=bias, breakout_level=float(level))
    else:
        entry_ok, entry_reasons = confirm_entry_5m(df_5m, bias=bias)

    refined_trade, refine_reason = refine_trade_levels_with_5m(
        df_5m=df_5m,
        base_trade=result.get("trade"),
        bias=bias,
        rr=float(result.get("trade", {}).get("rr", 2.0)),
        trade_type=trade_type,
        breakout_level=result.get("breakout_level"),
    )

    if refined_trade:
        result["trade"] = refined_trade
        entry_reasons.insert(1, refine_reason)
    else:
        entry_reasons.insert(1, f"Entry refinement failed: {refine_reason}")
        entry_ok = False

    # Save trade plan if exists (even for SETUP; it helps analysis)
    if result.get("trade"):
        t = result["trade"]
        insert_trade(
            {
                "ts": ts,
                "symbol": symbol,
                "trade_type": trade_type,
                "bias": bias,
                "entry": t.get("entry"),
                "stop_loss": t.get("stop_loss"),
                "take_profit": t.get("take_profit"),
                "rr": t.get("rr"),
                "note": t.get("note"),
                "fingerprint": fp,
            },
            DB_PATH,
        )

    # Decide alert kind and apply DB cooldown
    if entry_ok:
        kind = "ENTRY"
        cooldown = ENTRY_COOLDOWN_MIN
        alert_kind = "ENTRY"
    else:
        kind = "SETUP"
        cooldown = SETUP_COOLDOWN_MIN
        alert_kind = "SETUP"

    if kind == "SETUP" and not SEND_SETUP_ALERT:
        insert_alert(
            {"ts": ts, "symbol": symbol, "kind": kind, "fingerprint": fp, "status": "SKIPPED", "error": "setup_alert_disabled", "message_hash": None},
            DB_PATH,
        )
        return result if return_result else None

    if should_send_alert(symbol, kind, fp, cooldown, DB_PATH):
        msg = format_alert(symbol, result, alert_kind=alert_kind, extra_lines=entry_reasons, indicator_lines=indicator_lines)
        ok = send_telegram_alert(msg)
        insert_alert(
            {
                "ts": ts,
                "symbol": symbol,
                "kind": kind,
                "fingerprint": fp,
                "status": "SENT" if ok else "FAILED",
                "error": None if ok else "telegram_send_failed",
                "message_hash": _hash_message(msg),
            },
            DB_PATH,
        )
        print("✅ Telegram alert sent" if ok else "❌ Telegram alert failed")
    else:
        insert_alert(
            {"ts": ts, "symbol": symbol, "kind": kind, "fingerprint": fp, "status": "SKIPPED", "error": "cooldown", "message_hash": None},
            DB_PATH,
        )
        print("🔁 Alert skipped due to cooldown (already sent recently)")

    return result if return_result else None


if __name__ == "__main__":
    main()
