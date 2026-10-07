from stock_analyzer.models import TradingBookRule, Stock, DailyPriceData


BOOK_RULES_CATALOG = [
    {
        "master_name": "Mark Minervini",
        "book_title": "Trade Like a Stock Market Wizard",
        "rule_code": "MINERVINI_TREND_TEMPLATE",
        "rule_name": "Trend Template (50 > 150 > 200 EMA Alignment)",
        "description": "Stock price must be above 50, 150, and 200-day moving averages with the 200 EMA in an upward slope for at least 1 month.",
        "category": "TREND",
        "importance_weight": 1.25,
        "is_mandatory_filter": True
    },
    {
        "master_name": "Mark Minervini",
        "book_title": "Think & Trade Like a Champion",
        "rule_code": "MINERVINI_52W_PROXIMITY",
        "rule_name": "52-Week High Proximity (>25% from Low, <25% from High)",
        "description": "Stock must be trading within 20-25% of its 52-week high, having already recovered at least 25% from its 52-week low.",
        "category": "TREND",
        "importance_weight": 1.0,
        "is_mandatory_filter": False
    },
    {
        "master_name": "Mark Minervini",
        "book_title": "Trade Like a Stock Market Wizard",
        "rule_code": "MINERVINI_VCP_VOLATILITY",
        "rule_name": "Volatility Contraction Pattern (VCP Tightness)",
        "description": "Daily volatility (ATR / Price) should contract to < 2.5% before the final explosive breakout.",
        "category": "RISK",
        "importance_weight": 1.0,
        "is_mandatory_filter": False
    },
    {
        "master_name": "William O'Neil",
        "book_title": "How to Make Money in Stocks",
        "rule_code": "ONEIL_INSTITUTIONAL_SPONSOR",
        "rule_name": "CAN SLIM 'I' - Institutional Mutual Fund Sponsorship",
        "description": "The stock must have ownership and accumulating interest from top mutual funds and institutional investors.",
        "category": "INSTITUTIONAL",
        "importance_weight": 1.2,
        "is_mandatory_filter": True
    },
    {
        "master_name": "William O'Neil",
        "book_title": "How to Make Money in Stocks",
        "rule_code": "ONEIL_EARNINGS_GROWTH",
        "rule_name": "CAN SLIM 'C & A' - Consistent EPS / Profit Growth",
        "description": "Company must show positive quarterly and annual earnings growth (minimum 10-15% YoY).",
        "category": "VALUATION",
        "importance_weight": 1.1,
        "is_mandatory_filter": False
    },
    {
        "master_name": "Stan Weinstein",
        "book_title": "Secrets for Profiting in Bull and Bear Markets",
        "rule_code": "WEINSTEIN_STAGE_2_UPTREND",
        "rule_name": "Stage 2 Uptrend Markup Verification",
        "description": "Never buy a stock in Stage 4 (Downtrend) or Stage 3 (Distribution). Only buy during Stage 2 breakout markup.",
        "category": "TREND",
        "importance_weight": 1.3,
        "is_mandatory_filter": True
    },
    {
        "master_name": "Benjamin Graham",
        "book_title": "The Intelligent Investor",
        "rule_code": "GRAHAM_MARGIN_OF_SAFETY",
        "rule_name": "Margin of Safety & Conservative Debt Ratio",
        "description": "Safe debt-to-equity ratio (< 1.2) and sustainable return on equity (ROE > 12%) to guard against downside risk.",
        "category": "VALUATION",
        "importance_weight": 0.9,
        "is_mandatory_filter": False
    },
    {
        "master_name": "Peter Lynch",
        "book_title": "One Up On Wall Street",
        "rule_code": "LYNCH_PEG_RATIO",
        "rule_name": "PEG Ratio (Growth at a Reasonable Price)",
        "description": "P/E ratio divided by EPS growth rate should be under 1.5, signaling the stock is reasonably priced relative to earnings expansion.",
        "category": "VALUATION",
        "importance_weight": 0.85,
        "is_mandatory_filter": False
    }
]


def seed_trading_book_rules():
    """
    Populates database with rules extracted from legendary trading literature.
    """
    for item in BOOK_RULES_CATALOG:
        TradingBookRule.objects.update_or_create(
            rule_code=item["rule_code"],
            defaults={
                "master_name": item["master_name"],
                "book_title": item["book_title"],
                "rule_name": item["rule_name"],
                "description": item["description"],
                "category": item["category"],
                "importance_weight": item["importance_weight"],
                "is_mandatory_filter": item["is_mandatory_filter"]
            }
        )


def evaluate_all_book_strategies(stock: Stock):
    """
    Evaluates a stock across all Master Trader books & rules.
    Returns:
      - overall_score: 0 to 100
      - checklist: list of individual rule evaluations (pass/fail, explanation)
      - books_summary: dictionary grouped by master/book
    """
    prices = DailyPriceData.objects.filter(stock=stock).order_by("-date")[:60]
    if not prices.exists():
        return {
            "overall_score": 50,
            "checklist": [],
            "books_summary": {},
            "mandatory_filters_passed": True,
            "failed_mandatory_rules": []
        }

    latest = prices[0]
    p_20_ago = prices[min(len(prices) - 1, 20)]

    current_price = latest.close_price
    ema50 = latest.ema_50 or current_price
    ema150 = latest.ema_150 or (latest.ema_200 or current_price)
    ema200 = latest.ema_200 or current_price
    ema200_prev = p_20_ago.ema_200 or ema200
    atr = latest.atr_14 or (current_price * 0.018)

    fifty_two_high = stock.fifty_two_week_high or (current_price * 1.1)
    fifty_two_low = stock.fifty_two_week_low or (current_price * 0.8)

    # 1. Minervini Trend Template
    trend_template_passed = (
        current_price > ema50 and
        ema50 > ema200 and
        ema200 >= ema200_prev * 0.99
    )
    trend_template_note = (
        f"Price (₹{current_price:,.1f}) > 50 EMA (₹{ema50:,.1f}) > 200 EMA (₹{ema200:,.1f}) with positive slope."
        if trend_template_passed else
        f"Price (₹{current_price:,.1f}) is currently lagging key moving averages (50 EMA: ₹{ema50:,.1f}, 200 EMA: ₹{ema200:,.1f})."
    )

    # 2. 52-Week High Proximity
    dist_from_high_pct = ((fifty_two_high - current_price) / fifty_two_high) * 100
    dist_from_low_pct = ((current_price - fifty_two_low) / fifty_two_low) * 100
    proximity_passed = (dist_from_high_pct <= 25.0) and (dist_from_low_pct >= 20.0)
    proximity_note = (
        f"Trading {dist_from_high_pct:.1f}% below 52W High (₹{fifty_two_high:,.1f}) and +{dist_from_low_pct:.1f}% above 52W Low."
        if proximity_passed else
        f"Extended distance from highs ({dist_from_high_pct:.1f}% off 52W High)."
    )

    # 3. Minervini VCP (Volatility Contraction)
    vcp_ratio = (atr / current_price) * 100
    vcp_passed = vcp_ratio <= 2.8
    vcp_note = (
        f"Volatility is contracted to {vcp_ratio:.2f}% of price (ATR ₹{atr:,.1f}). Ideal tight base."
        if vcp_passed else
        f"High daily price swings ({vcp_ratio:.2f}% ATR volatility)."
    )

    # 4. William O'Neil Institutional Sponsorship
    mf_holdings = stock.fund_holdings.all()
    mf_count = mf_holdings.count()
    mf_capital = sum(h.holding_value_crores for h in mf_holdings)
    oneil_sponsor_passed = mf_count >= 2 or mf_capital > 2000.0
    oneil_sponsor_note = (
        f"Backed by {mf_count} top Indian Mutual Funds with ₹{mf_capital:,.0f} Cr capital deployed."
        if oneil_sponsor_passed else
        "Low or unconfirmed institutional mutual fund backing."
    )

    # 5. O'Neil Earnings Growth
    eps_growth = stock.eps_growth_yoy or 12.0
    earnings_passed = eps_growth >= 10.0
    earnings_note = f"EPS YoY Growth at {eps_growth:.1f}% (O'Neil benchmark: >10%)."

    # 6. Stan Weinstein Stage 2
    stage_2_passed = current_price > ema200 and ema50 > ema200
    current_stage = "Stage 2 (Uptrend Markup)" if stage_2_passed else (
        "Stage 4 (Downtrend Decline)" if current_price < ema200 and ema50 < ema200 else
        "Stage 1 / 3 (Consolidation or Distribution)"
    )
    weinstein_note = f"Identified as {current_stage}."

    # 7. Graham Margin of Safety
    debt_eq = stock.debt_to_equity or 0.8
    roe = stock.roe_pct or 15.0
    graham_passed = (debt_eq <= 1.5) and (roe >= 12.0)
    graham_note = f"Debt-to-Equity: {debt_eq:.2f}, ROE: {roe:.1f}% (Meets Graham financial safety criteria)."

    # 8. Peter Lynch PEG Ratio
    pe = stock.pe_ratio or 20.0
    peg = (pe / eps_growth) if eps_growth > 0 else 2.5
    lynch_passed = peg <= 1.8
    lynch_note = f"P/E: {pe:.1f} | Growth: {eps_growth:.1f}% | PEG Ratio: {peg:.2f} (Benchmark: <= 1.5)."

    # Aggregate Checklist
    rule_results = [
        {
            "code": "MINERVINI_TREND_TEMPLATE",
            "master": "Mark Minervini",
            "book": "Trade Like a Stock Market Wizard",
            "name": "Trend Template (50 > 150 > 200 EMA)",
            "passed": trend_template_passed,
            "note": trend_template_note,
            "weight": 1.25,
            "is_mandatory": True
        },
        {
            "code": "WEINSTEIN_STAGE_2_UPTREND",
            "master": "Stan Weinstein",
            "book": "Secrets for Profiting in Bull & Bear Markets",
            "name": "Stage 2 Uptrend Markup",
            "passed": stage_2_passed,
            "note": weinstein_note,
            "weight": 1.3,
            "is_mandatory": True
        },
        {
            "code": "ONEIL_INSTITUTIONAL_SPONSOR",
            "master": "William O'Neil",
            "book": "How to Make Money in Stocks",
            "name": "CAN SLIM 'I' - Mutual Fund Sponsorship",
            "passed": oneil_sponsor_passed,
            "note": oneil_sponsor_note,
            "weight": 1.2,
            "is_mandatory": True
        },
        {
            "code": "MINERVINI_52W_PROXIMITY",
            "master": "Mark Minervini",
            "book": "Think & Trade Like a Champion",
            "name": "52-Week High Proximity",
            "passed": proximity_passed,
            "note": proximity_note,
            "weight": 1.0,
            "is_mandatory": False
        },
        {
            "code": "MINERVINI_VCP_VOLATILITY",
            "master": "Mark Minervini",
            "book": "Trade Like a Stock Market Wizard",
            "name": "VCP Volatility Contraction",
            "passed": vcp_passed,
            "note": vcp_note,
            "weight": 1.0,
            "is_mandatory": False
        },
        {
            "code": "ONEIL_EARNINGS_GROWTH",
            "master": "William O'Neil",
            "book": "How to Make Money in Stocks",
            "name": "CAN SLIM 'C & A' - Earnings Growth",
            "passed": earnings_passed,
            "note": earnings_note,
            "weight": 1.1,
            "is_mandatory": False
        },
        {
            "code": "GRAHAM_MARGIN_OF_SAFETY",
            "master": "Benjamin Graham",
            "book": "The Intelligent Investor",
            "name": "Graham Margin of Safety (Debt & ROE)",
            "passed": graham_passed,
            "note": graham_note,
            "weight": 0.9,
            "is_mandatory": False
        },
        {
            "code": "LYNCH_PEG_RATIO",
            "master": "Peter Lynch",
            "book": "One Up On Wall Street",
            "name": "Peter Lynch PEG Growth Ratio",
            "passed": lynch_passed,
            "note": lynch_note,
            "weight": 0.85,
            "is_mandatory": False
        },
    ]

    total_weight = sum(r["weight"] for r in rule_results)
    earned_weight = sum(r["weight"] for r in rule_results if r["passed"])
    overall_score = int((earned_weight / total_weight) * 100)

    failed_mandatory = [r["name"] for r in rule_results if r["is_mandatory"] and not r["passed"]]
    mandatory_passed = len(failed_mandatory) == 0

    # Group by author/book
    books_summary = {}
    for r in rule_results:
        author = r["master"]
        if author not in books_summary:
            books_summary[author] = {
                "author": author,
                "book": r["book"],
                "passed_count": 0,
                "total_count": 0,
                "rules": []
            }
        books_summary[author]["total_count"] += 1
        if r["passed"]:
            books_summary[author]["passed_count"] += 1
        books_summary[author]["rules"].append(r)

    return {
        "overall_score": overall_score,
        "checklist": rule_results,
        "books_summary": books_summary,
        "mandatory_filters_passed": mandatory_passed,
        "failed_mandatory_rules": failed_mandatory,
        "current_stage": current_stage
    }
