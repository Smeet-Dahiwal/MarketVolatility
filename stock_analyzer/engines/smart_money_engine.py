from stock_analyzer.models import Stock, MutualFund, MutualFundHolding


INITIAL_MUTUAL_FUNDS = [
    {
        "name": "Parag Parikh Flexi Cap Fund - Direct Growth",
        "amc_name": "PPFAS Mutual Fund",
        "category": "Flexi Cap",
        "aum_crores": 72450.0,
        "star_rating": 5,
        "one_year_return_pct": 28.4,
        "three_year_return_pct": 21.2,
        "holdings": {
            "HDFCBANK.NS": (8.25, "HEAVY_ACCUMULATION"),
            "ICICIBANK.NS": (6.90, "ACCUMULATING"),
            "AXISBANK.NS": (5.40, "ACCUMULATING"),
            "ITC.NS": (7.10, "STABLE"),
            "BAJFINANCE.NS": (4.80, "ACCUMULATING"),
            "TCS.NS": (4.50, "STABLE"),
        }
    },
    {
        "name": "HDFC Top 100 Fund - Direct Plan",
        "amc_name": "HDFC AMC",
        "category": "Large Cap",
        "aum_crores": 39800.0,
        "star_rating": 5,
        "one_year_return_pct": 31.2,
        "three_year_return_pct": 22.8,
        "holdings": {
            "HDFCBANK.NS": (9.80, "HEAVY_ACCUMULATION"),
            "ICICIBANK.NS": (8.40, "ACCUMULATING"),
            "RELIANCE.NS": (7.60, "STABLE"),
            "INFY.NS": (6.10, "ACCUMULATING"),
            "LT.NS": (5.90, "HEAVY_ACCUMULATION"),
            "AXISBANK.NS": (4.90, "ACCUMULATING"),
            "SBIN.NS": (4.20, "STABLE"),
        }
    },
    {
        "name": "SBI Bluechip Fund - Direct Plan",
        "amc_name": "SBI Mutual Fund",
        "category": "Large Cap",
        "aum_crores": 46500.0,
        "star_rating": 4,
        "one_year_return_pct": 24.6,
        "three_year_return_pct": 18.5,
        "holdings": {
            "HDFCBANK.NS": (8.90, "ACCUMULATING"),
            "ICICIBANK.NS": (7.80, "ACCUMULATING"),
            "RELIANCE.NS": (6.70, "STABLE"),
            "INFY.NS": (5.80, "STABLE"),
            "LT.NS": (5.50, "HEAVY_ACCUMULATION"),
            "BHARTIARTL.NS": (4.70, "ACCUMULATING"),
            "M&M.NS": (4.10, "HEAVY_ACCUMULATION"),
        }
    },
    {
        "name": "ICICI Prudential Bluechip Fund",
        "amc_name": "ICICI Prudential AMC",
        "category": "Large Cap",
        "aum_crores": 58200.0,
        "star_rating": 5,
        "one_year_return_pct": 29.8,
        "three_year_return_pct": 20.4,
        "holdings": {
            "ICICIBANK.NS": (9.10, "HEAVY_ACCUMULATION"),
            "HDFCBANK.NS": (8.40, "ACCUMULATING"),
            "RELIANCE.NS": (7.20, "STABLE"),
            "LT.NS": (6.40, "HEAVY_ACCUMULATION"),
            "INFY.NS": (5.50, "STABLE"),
            "BHARTIARTL.NS": (5.10, "ACCUMULATING"),
            "AXISBANK.NS": (4.60, "ACCUMULATING"),
        }
    },
    {
        "name": "Kotak Flexicap Fund - Direct Growth",
        "amc_name": "Kotak Mahindra AMC",
        "category": "Flexi Cap",
        "aum_crores": 44100.0,
        "star_rating": 4,
        "one_year_return_pct": 26.2,
        "three_year_return_pct": 19.1,
        "holdings": {
            "HDFCBANK.NS": (7.90, "ACCUMULATING"),
            "ICICIBANK.NS": (7.20, "ACCUMULATING"),
            "LT.NS": (6.10, "HEAVY_ACCUMULATION"),
            "RELIANCE.NS": (5.80, "STABLE"),
            "TCS.NS": (4.90, "STABLE"),
            "TITAN.NS": (4.40, "ACCUMULATING"),
            "AXISBANK.NS": (4.10, "ACCUMULATING"),
        }
    },
    {
        "name": "Nippon India Growth Fund",
        "amc_name": "Nippon India Mutual Fund",
        "category": "Mid & Large Cap",
        "aum_crores": 31500.0,
        "star_rating": 5,
        "one_year_return_pct": 34.8,
        "three_year_return_pct": 26.5,
        "holdings": {
            "HDFCBANK.NS": (6.50, "ACCUMULATING"),
            "AXISBANK.NS": (5.80, "HEAVY_ACCUMULATION"),
            "BHARTIARTL.NS": (5.20, "HEAVY_ACCUMULATION"),
            "SUNPHARMA.NS": (4.70, "ACCUMULATING"),
            "MARUTI.NS": (4.30, "ACCUMULATING"),
            "NTPC.NS": (3.90, "STABLE"),
        }
    }
]


def seed_mutual_fund_data():
    """
    Initializes top Indian mutual funds and their stock holdings.
    """
    for fund_data in INITIAL_MUTUAL_FUNDS:
        fund, _ = MutualFund.objects.update_or_create(
            name=fund_data["name"],
            defaults={
                "amc_name": fund_data["amc_name"],
                "category": fund_data["category"],
                "aum_crores": fund_data["aum_crores"],
                "star_rating": fund_data["star_rating"],
                "one_year_return_pct": fund_data["one_year_return_pct"],
                "three_year_return_pct": fund_data["three_year_return_pct"],
            }
        )

        for symbol, (weight, action) in fund_data["holdings"].items():
            stock = Stock.objects.filter(symbol=symbol).first()
            if not stock:
                # Create minimal placeholder until full fetch
                stock = Stock.objects.create(
                    symbol=symbol,
                    name=symbol.replace(".NS", ""),
                    current_price=1500.0,
                    market_cap_crores=100000.0
                )

            holding_val = (fund.aum_crores * weight) / 100.0
            MutualFundHolding.objects.update_or_create(
                fund=fund,
                stock=stock,
                defaults={
                    "weight_pct": weight,
                    "holding_value_crores": round(holding_val, 2),
                    "mom_action": action
                }
            )


def get_stock_smart_money_analysis(stock: Stock):
    """
    Computes institutional consensus score, total invested AUM, and funds list for a stock.
    """
    holdings = MutualFundHolding.objects.filter(stock=stock).select_related("fund")
    
    total_funds_count = holdings.count()
    total_capital_cr = sum(h.holding_value_crores for h in holdings)
    avg_weight = (sum(h.weight_pct for h in holdings) / total_funds_count) if total_funds_count > 0 else 0.0
    
    heavy_buyers = holdings.filter(mom_action="HEAVY_ACCUMULATION").count()
    accumulators = holdings.filter(mom_action="ACCUMULATING").count()
    
    # Calculate Smart Money Consensus Score (0 - 100)
    # 60% based on fund count & weight, 40% based on accumulation momentum
    fund_breadth_score = min(total_funds_count * 16, 60)
    weight_bonus = min(avg_weight * 4, 20)
    momentum_score = min((heavy_buyers * 12) + (accumulators * 6), 20)
    
    consensus_score = min(int(fund_breadth_score + weight_bonus + momentum_score), 98)
    if total_funds_count == 0:
        consensus_score = 40  # Neutral baseline for unlisted MF tracking

    if consensus_score >= 80:
        signal = "Heavy Institutional Accumulation (Strong Smart Money Inflow)"
        badge_class = "success"
    elif consensus_score >= 60:
        signal = "Moderate Institutional Holding (Healthy SIP Deployment)"
        badge_class = "primary"
    elif consensus_score >= 45:
        signal = "Selective Institutional Presence"
        badge_class = "warning"
    else:
        signal = "Low Mutual Fund Allocation"
        badge_class = "danger"

    return {
        "consensus_score": consensus_score,
        "signal": signal,
        "badge_class": badge_class,
        "total_funds_holding": total_funds_count,
        "total_capital_crores": round(total_capital_cr, 2),
        "avg_weight_pct": round(avg_weight, 2),
        "holdings_list": holdings
    }


def get_top_consensus_stocks():
    """
    Returns all Indian stocks sorted by mutual fund consensus and total capital invested.
    """
    from django.db.models import Count, Sum, Avg
    
    stocks = Stock.objects.annotate(
        funds_count=Count("fund_holdings"),
        total_mf_capital=Sum("fund_holdings__holding_value_crores"),
        avg_mf_weight=Avg("fund_holdings__weight_pct")
    ).filter(funds_count__gt=0).order_by("-total_mf_capital")

    return stocks
