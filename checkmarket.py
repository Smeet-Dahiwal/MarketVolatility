import argparse
from market_volatility import weekday_volatility


def print_daywise(daily_df):
    print("\n📊 Day-wise Market Movement\n")

    # Ensure proper order of days
    day_order = [
        "Monday", "Tuesday", "Wednesday",
        "Thursday", "Friday", "Saturday", "Sunday"
    ]

    for day in day_order:
        day_df = daily_df[daily_df["Day"] == day]

        if day_df.empty:
            continue

        print(f"\n🟦 {day}")
        print(
            day_df[[
                "Date", "Open", "Close", "Points", "Volatility"
            ]].to_string(index=False)
        )


def print_summary(summary_df):
    print("\n📌 Summary (Average Volatility by Weekday)\n")
    print(summary_df)

    # most_volatile_day = summary_df.index[0]
    most_volatile_day = summary_df["Day"].iloc[0]

    print(f"\n🔥 MOST VOLATILE DAY: {most_volatile_day}")


def main():
    parser = argparse.ArgumentParser(
        description="Market weekday volatility analysis"
    )

    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)

    args = parser.parse_args()

    daily, summary = weekday_volatility(
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end
    )

    print_daywise(daily)
    print_summary(summary)


if __name__ == "__main__":
    main()
