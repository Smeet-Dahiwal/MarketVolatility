from data_fetcher import fetch_data
from indicators import add_indicators
from strategy import predict_next_candle
from alerts import send_whatsapp_alert
from alerts import send_telegram_alert

# ================= CONFIG =================
SYMBOL = "BTC-USD"
CONFIDENCE_THRESHOLD = 30   # Alert only if strong signal
# =========================================


def main():
    print("📥 Fetching market data...")

    df_15m = fetch_data(SYMBOL, "15m", "5d")
    df_1h  = fetch_data(SYMBOL, "1h", "10d")

    if df_15m.empty or df_1h.empty:
        print("❌ Failed to fetch market data")
        return

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
    result_message = f"""
📊 <b>MARKET PREDICTION</b>
-------------------
<b>Symbol:</b> {SYMBOL}
<b>Bias:</b> {result['bias']}
<b>Confidence:</b> {result['confidence']}%

📌 <b>Reasons:</b>
""" + "\n".join([f"- {r}" for r in result['reasons']])

    send_telegram_alert(result_message)

    # -------- WHATSAPP ALERT (COMMENTED FOR FUTURE USE) --------
    # if result['confidence'] >= CONFIDENCE_THRESHOLD:
    #     alert_msg = f"""
    # 📊 MARKET ALERT
    #
    # Symbol     : {SYMBOL}
    # Bias       : {result['bias']}
    # Confidence : {result['confidence']}%
    #
    # Reasons:
    # """ + "\n".join(f"- {r}" for r in result['reasons'])
    #
    #     send_whatsapp_alert(alert_msg)
    # else:
    #     print("\n🔕 No alert sent (confidence too low)")


if __name__ == "__main__":
    main()
