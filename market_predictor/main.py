# main.py
from datetime import datetime
from html import escape  # ✅ IMPORTANT
from data_fetcher import fetch_data
from indicators import add_indicators
from strategy import predict_next_candle
from alerts import send_telegram_alert

CONFIDENCE_THRESHOLD = 70


def format_alert(symbol: str, result: dict) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    trade = result.get("trade")

    # ✅ Escape dynamic fields
    safe_symbol = escape(symbol)
    safe_trade_type = escape(str(result.get("trade_type", "n/a")))
    safe_bias = escape(str(result.get("bias", "n/a")))
    safe_conf = escape(str(result.get("confidence", "n/a")))

    expected = result.get("expected_move", {}) or {}
    safe_dir = escape(str(expected.get("direction", "n/a")))
    safe_minp = escape(str(expected.get("min_points", "n/a")))
    safe_maxp = escape(str(expected.get("max_points", "n/a")))

    reasons = result.get("reasons", []) or []
    # ✅ Escape each reason (this fixes EMA20 < EMA50)
    reasons_text = "\n".join([f"- {escape(str(r))}" for r in reasons]) if reasons else "- (no reasons)"

    trade_text = ""
    if trade:
        trade_text = f"""
🎯 <b>TRADE LEVELS</b>
<b>Entry:</b> {escape(str(trade['entry']))}
<b>Stop Loss:</b> {escape(str(trade['stop_loss']))}
<b>Take Profit:</b> {escape(str(trade['take_profit']))}
<b>Risk:Reward:</b> 1:{escape(str(trade['rr']))}
"""

    return f"""
📊 <b>MARKET SIGNAL</b>
-------------------
<b>Time:</b> {escape(timestamp)}
<b>Symbol:</b> {safe_symbol}
<b>Trade Type:</b> {safe_trade_type}
<b>Bias:</b> {safe_bias}
<b>Confidence:</b> {safe_conf}%

📈 <b>Expected Move:</b> {safe_dir}
<b>Range:</b> {safe_minp} - {safe_maxp}

📌 <b>Reasons:</b>
{reasons_text}
{trade_text}
""".strip()


def main(symbol: str = "BTC-USD", return_result: bool = False):
    print(f"📥 Fetching market data for {symbol}...")

    df_15m = fetch_data(symbol, "15m", "5d", only_closed=True)
    df_1h = fetch_data(symbol, "1h", "10d", only_closed=True)

    if df_15m.empty or df_1h.empty:
        print("❌ Failed to fetch market data")
        return None

    df_15m = add_indicators(df_15m)
    df_1h = add_indicators(df_1h)

    result = predict_next_candle(df_15m, df_1h)

    print(f"\nSymbol: {symbol}")
    print(f"Trade Type: {result.get('trade_type')}")
    print(f"Bias: {result.get('bias')}, Confidence: {result.get('confidence')}%")
    print(f"Expected Move: {result.get('expected_move')}")
    print(f"Trade: {result.get('trade')}")

    trade_type = result.get("trade_type", "NO_TRADE")
    confidence = int(result.get("confidence", 0))
    trade = result.get("trade")

    if trade_type != "NO_TRADE" and confidence >= CONFIDENCE_THRESHOLD and trade:
        alert_message = format_alert(symbol, result)
        ok = send_telegram_alert(alert_message)
        if ok:
            print("✅ Telegram alert confirmed")
        else:
            print("❌ Telegram alert failed (see error above)")
    else:
        print("🔕 No alert sent (NO_TRADE or low confidence or missing trade plan)")

    if return_result:
        return result


if __name__ == "__main__":
    main()
