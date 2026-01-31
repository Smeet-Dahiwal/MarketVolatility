import yfinance as yf
import pandas as pd


def weekday_volatility(
    symbol: str,
    start_date: str,
    end_date: str
):
    """
    Returns:
    1. Daily data with weekday
    2. Summary showing most volatile weekday
    """

    df = yf.download(
        symbol,
        start=start_date,
        end=end_date,
        interval="1d",
        progress=False
    )

    if df.empty:
        raise ValueError("No market data found")

    # 🔑 FIX: flatten multi-index columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()

    # Add weekday
    df["Day"] = df["Date"].dt.day_name()

    # Calculations
    df["Points"] = (df["Close"] - df["Open"]).round(2)
    df["Volatility"] = (df["High"] - df["Low"]).round(2)

    # Daily output
    daily_data = df[
        ["Date", "Day", "Open", "Close", "Points", "Volatility"]
    ]

    # Summary per weekday
    summary = (
        daily_data
        .groupby("Day", as_index=False)
        .agg(
            Avg_Points=("Points", "mean"),
            Avg_Volatility=("Volatility", "mean"),
            Days_Count=("Date", "count")
        )
        .round(2)
        .sort_values("Avg_Volatility", ascending=False)
    )

    return daily_data, summary
