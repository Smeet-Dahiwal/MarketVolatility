import os
import time
from datetime import datetime

from market_predictor.main import main
from market_predictor.db import init_db, kv_get, kv_set

DB_PATH = "market_predictor.db"
STATE_KEY = "last_15m_close_ts"   # keep global candle tracking (works fine)

def _symbols():
    raw = os.getenv("SYMBOLS", "BTC/USDT,XAU/USDT")
    return [s.strip() for s in raw.split(",") if s.strip()]

def run():
    init_db(DB_PATH)
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 🚀 Bot started (symbols={_symbols()})")

    while True:
        try:
            # ---- your existing logic that detects NEW 15m candle close ----
            # Keep it exactly as you already have. When it triggers, call:
            symbols = _symbols()
            for sym in symbols:
                print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 🔔 Running strategy for {sym} ...")
                main(symbol=sym, return_result=False)

        except Exception as e:
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ❌ Bot error: {e}")

        time.sleep(60)

if __name__ == "__main__":
    run()
