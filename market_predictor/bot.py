# market_predictor/bot.py
import time
from datetime import datetime

from market_predictor.data_fetcher import fetch_data
from market_predictor.db import init_db, kv_get, kv_set

try:
    from main import main as run_once
except Exception:
    from market_predictor.main import main as run_once


# ================= CONFIG =================
SYMBOLS = ["BTC-USD"]
CHECK_INTERVAL_SECONDS = 60  # check every 1 minute
LOG_FILE = "market_bot.log"
DB_PATH = "market_predictor.db"
# =========================================


def log_message(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def last_closed_15m(symbol: str) -> str | None:
    df = fetch_data(symbol, "15m", "2d", only_closed=True)
    if df is None or df.empty:
        return None
    return str(df.index[-1])


def run_bot():
    init_db(DB_PATH)
    log_message("🚀 Bot started (1-min loop, triggers only on NEW 15m candle close, state in SQLite)")

    while True:
        for symbol in SYMBOLS:
            try:
                last15 = last_closed_15m(symbol)
                if not last15:
                    log_message(f"❌ {symbol}: cannot detect last closed 15m candle")
                    continue

                key = f"last_15m_closed::{symbol}"
                prev15 = kv_get(key, DB_PATH)

                if prev15 == last15:
                    # no new candle close -> do nothing
                    continue

                kv_set(key, last15, DB_PATH)
                log_message(f"⏱️ New 15m candle closed for {symbol} at {last15}. Running strategy...")

                # main() handles alerts + DB writes (signals/alerts/trades)
                run_once(symbol=symbol, return_result=False)

            except Exception as e:
                log_message(f"❌ {symbol}: error: {e}")

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_bot()
