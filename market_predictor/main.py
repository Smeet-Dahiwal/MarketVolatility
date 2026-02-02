from datetime import datetime
from data_fetcher import fetch_data
from indicators import add_indicators
from strategy import predict_next_candle
from alerts import send_telegram_alert

SYMBOL = "BTC-USD"
CONFIDENCE_THRESHOLD = 70

def format_alert(result):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    move = result['expected_move']
    return f"""
📊 <b>MARKET PREDICTION</b>
-------------------
<b>Time:</b> {timestamp}
<b>Symbol:</b> {SYMBOL}
<b>Bias:</b> {result['bias']}
<b>Confidence:</b> {result['confidence']}%

📌 <b>Expected Move:</b>
Direction: {move['direction']}
Min Points: {move['min_points']}
Max Points: {move['max_points']}

📌 <b>Reasons:</b>
""" + "\n".join([f"- {r}" for r in result['reasons']])


def main(return_result=False):
    print("📥 Fetching market data...")
    df_15m = fetch_data(SYMBOL, "15m", "5d")
    df_1h = fetch_data(SYMBOL, "1h", "10d")

    if df_15m.empty or df_1h.empty:
        print("❌ Failed to fetch market data")
        return None

    df_15m = add_indicators(df_15m)
    df_1h = add_indicators(df_1h)

    result = predict_next_candle(df_15m, df_1h)

    print(f"\nSymbol: {SYMBOL}")
    print(f"Bias: {result['bias']}, Confidence: {result['confidence']}%")
    print(f"Expected Move: {result['expected_move']}")

    if result['confidence'] >= CONFIDENCE_THRESHOLD:
        alert_message = format_alert(result)
        send_telegram_alert(alert_message)
        print("✅ Telegram alert sent")
    else:
        print(f"🔕 Telegram alert not sent (confidence {result['confidence']}% < {CONFIDENCE_THRESHOLD}%)")

    if return_result:
        return result


if __name__ == "__main__":
    main()
