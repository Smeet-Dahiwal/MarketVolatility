import os
from main import main

DEFAULT_SYMBOL = os.getenv("SYMBOL", "BTC-USD")

def handler(event, context):
    symbol = (event or {}).get("symbol", DEFAULT_SYMBOL)
    result = main(symbol=symbol, return_result=True)
    return {"ok": True, "symbol": symbol, "result": result}
