import time
from datetime import datetime
from main import main as get_prediction  # our updated main.py

# ================= CONFIG =================
SYMBOLS = ["BTC-USD"]  # You can add multiple symbols here
CONFIDENCE_THRESHOLD = 70
CHECK_INTERVAL_MINUTES = 5
LOG_FILE = "market_bot.log"


# =========================================

def log_message(msg):
    """Append log message to file with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:   # <-- specify UTF-8
        f.write(f"[{timestamp}] {msg}\n")
    print(f"[{timestamp}] {msg}")



def run_bot():
    log_message("🚀 Market Prediction Bot started")

    while True:
        for symbol in SYMBOLS:
            try:
                result = get_prediction(return_result=True)

                if result:
                    bias = result['bias']
                    confidence = result['confidence']
                    move = result['expected_move']

                    msg = (
                        f"Symbol: {symbol}, Bias: {bias}, Confidence: {confidence}%, "
                        f"Expected Move: {move['direction']} ({move['min_points']}-{move['max_points']} pts)"
                    )
                    log_message(msg)

                    if confidence >= CONFIDENCE_THRESHOLD:
                        log_message("✅ Strong signal detected, alert sent")
                    else:
                        log_message(f"🔕 Confidence below threshold, no alert sent")
                else:
                    log_message(f"❌ Failed to get prediction for {symbol}")

            except Exception as e:
                log_message(f"❌ Error for {symbol}: {str(e)}")

        log_message(f"⏳ Sleeping for {CHECK_INTERVAL_MINUTES} minutes...\n")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    run_bot()
