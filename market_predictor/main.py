import time
from datetime import datetime
from data_fetcher import fetch_data
from indicators import add_indicators
from strategy import predict_next_candle
from alerts import send_whatsapp_alert
from alerts import send_telegram_alert

# ================= CONFIG =================
SYMBOL = "BTC-USD"
CONFIDENCE_THRESHOLD = 70   # Alert only if strong signal
RETRY_DELAY = 60            # seconds to wait before retrying if data fetch fails
# =========================================

def format_alert(result):
    """Helper to format alert messages for Telegram/WhatsApp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""
📊 <b>MARKET PREDICTION</b>
-------------------
<b>Time:</b> {timestamp}
<b>Symbol:</b> {SYMBOL}
<b>Bias:</b> {result['bias']}
<b>Confidence:</b> {result['confidence']}%

📌 <b>Reasons:</b>
""" + "\n".join([f"- {r}" for r in result['reasons']])


def main(return_result=False):
    print("📥 Fetching market data...")

    df_15m = fetch_data(SYMBOL, "15m", "5d")
    df_1h  = fetch_data(SYMBOL, "1h", "10d")

    # Retry if data is empty
    if df_15m.empty or df_1h.empty:
        print(f"❌ Failed to fetch market data, retrying in {RETRY_DELAY}s...")
        time.sleep(RETRY_DELAY)
        return None

    print("📊 Calculating indicators...")
    df_15m = add_indicators(df_15m)
    df_1h  = add_indicators(df_1h)

    print("🧠 Running prediction engine...")
    result = predict_next_candle(df_15m, df_1h)

    # -------- CONSOLE OUTPUT --------
    print("\n📊 MARKET PREDICTION")
    print("-------------------")
    print(f"Symbol     : {SYMBOL}")
    print(f"Bias       : {result['bias']}")
    print(f"Confidence : {result['confidence']}%")

    print("\n📌 Reasons:")
    for r in result['reasons']:
        print(f"- {r}")

    # -------- TELEGRAM ALERT --------
    if result['confidence'] >= CONFIDENCE_THRESHOLD:
        alert_message = format_alert(result)
        send_telegram_alert(alert_message)
        print("✅ Telegram alert sent")
    else:
        print(f"🔕 Telegram alert not sent (confidence {result['confidence']}% < {CONFIDENCE_THRESHOLD}%)")

    # -------- WHATSAPP ALERT (COMMENTED FOR FUTURE USE) --------
    # if result['confidence'] >= CONFIDENCE_THRESHOLD:
    #     alert_msg = format_alert(result)
    #     send_whatsapp_alert(alert_msg)
    # else:
    #     print("\n🔕 No alert sent (confidence too low)")

    if return_result:
        return {
            "symbol": SYMBOL,
            "bias": result['bias'],
            "confidence": result['confidence'],
            "reasons": result['reasons']
        }


if __name__ == "__main__":
    main()
