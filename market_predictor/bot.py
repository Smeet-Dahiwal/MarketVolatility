# bot.py
import time
from datetime import datetime
try:
    from main import main as get_prediction
except:
    from market_predictor.main import main as get_prediction

# ================= CONFIG =================
SYMBOLS = ["BTC-USD"]  # Add more: ["BTC-USD", "ETH-USD"]
CONFIDENCE_THRESHOLD = 70
CHECK_INTERVAL_MINUTES = 5
LOG_FILE = "market_bot.log"
# =========================================


def log_message(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {msg}\n")
    print(f"[{timestamp}] {msg}")


def run_bot():
    log_message("🚀 Market Prediction Bot started")

    while True:
        for symbol in SYMBOLS:
            try:
                result = get_prediction(symbol=symbol, return_result=True)

                if result:
                    trade_type = result.get("trade_type", "NO_TRADE")
                    bias = result.get("bias", "Neutral")
                    confidence = int(result.get("confidence", 0))
                    move = result.get("expected_move", {})

                    msg = (
                        f"Symbol: {symbol}, TradeType: {trade_type}, Bias: {bias}, Confidence: {confidence}%, "
                        f"Expected Move: {move.get('direction')} ({move.get('min_points')}-{move.get('max_points')} pts)"
                    )
                    log_message(msg)

                    if trade_type != "NO_TRADE" and confidence >= CONFIDENCE_THRESHOLD:
                        log_message("✅ Strong setup detected (alert handled in main.py)")
                    else:
                        log_message("🔕 No strong setup / no trade")
                else:
                    log_message(f"❌ Failed to get prediction for {symbol}")

            except Exception as e:
                log_message(f"❌ Error for {symbol}: {str(e)}")

        log_message(f"⏳ Sleeping for {CHECK_INTERVAL_MINUTES} minutes...\n")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    run_bot()
