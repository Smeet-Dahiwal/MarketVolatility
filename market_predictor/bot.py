import time
from datetime import datetime
from main import main as get_prediction

# ================= CONFIG =================
CHECK_INTERVAL_MINUTES = 5  # Check market every 15 minutes
LOG_FILE = "market_bot.log"
CONFIDENCE_THRESHOLD = 70
# =========================================

def log_message(msg):
    """Append log message to file with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:   # <-- FIX: UTF-8 encoding
        f.write(f"[{timestamp}] {msg}\n")
    print(f"[{timestamp}] {msg}")


def run_bot():
    log_message("🚀 Market Prediction Bot started")

    while True:
        try:
            # Fetch prediction from main.py
            result = get_prediction(return_result=True)

            if result:
                msg = f"Symbol: {result['symbol']}, Bias: {result['bias']}, Confidence: {result['confidence']}%"
                log_message(msg)

                # Alert only if confidence ≥ threshold (handled inside main.py)
                if result['confidence'] >= CONFIDENCE_THRESHOLD:
                    log_message("✅ Strong signal detected, alert sent")
                else:
                    log_message(f"🔕 Confidence below threshold ({result['confidence']}% < {CONFIDENCE_THRESHOLD}%), no alert sent")
            else:
                log_message("❌ Failed to get prediction")

        except Exception as e:
            log_message(f"❌ Error: {str(e)}")

        log_message(f"⏳ Sleeping for {CHECK_INTERVAL_MINUTES} minutes...\n")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    run_bot()
