import pandas as pd
from indicators import add_indicators
from strategy import predict_next_candle

def backtest_expected_move(df_15m, df_1h, lookahead=1):
    results = []

    df_15m = add_indicators(df_15m)
    df_1h = add_indicators(df_1h)

    for i in range(50, len(df_15m) - lookahead):
        slice_15m = df_15m.iloc[:i]
        slice_1h = df_1h.iloc[:i // 4]  # approximate alignment

        prediction = predict_next_candle(slice_15m, slice_1h)

        exp = prediction['expected_move']
        close_price = slice_15m['Close'].iloc[-1]
        future_high = df_15m['High'].iloc[i:i+lookahead].max()
        future_low = df_15m['Low'].iloc[i:i+lookahead].min()

        hit = False

        if exp['direction'] == "up":
            hit = future_high >= close_price + exp['min_points']
        elif exp['direction'] == "down":
            hit = future_low <= close_price - exp['min_points']

        results.append({
            "confidence": prediction['confidence'],
            "direction": exp['direction'],
            "hit": hit
        })

    df = pd.DataFrame(results)
    accuracy = df['hit'].mean() * 100

    return round(accuracy, 2), df
