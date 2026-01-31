from flask import Flask, render_template, request
from market_volatility import weekday_volatility

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    daily_data_records = []
    summary_data_records = []
    most_volatile_day = None

    if request.method == "POST":
        symbol = request.form.get("symbol")
        start_date = request.form.get("start")
        end_date = request.form.get("end")

        try:
            daily_data, summary_data = weekday_volatility(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date
            )

            # Convert DataFrames to list of dicts for Jinja
            daily_data_records = daily_data.to_dict(orient="records")
            summary_data_records = summary_data.to_dict(orient="records")

            # Most volatile day
            most_volatile_day = summary_data["Day"].iloc[0]

        except Exception as e:
            return f"<h2>Error: {e}</h2>"

    # ✅ Always return render_template
    return render_template(
        "index.html",
        daily=daily_data_records,
        summary=summary_data_records,
        most_volatile_day=most_volatile_day
    )

if __name__ == "__main__":
    app.run(debug=True)
