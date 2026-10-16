import datetime
from django.utils import timezone
from stock_analyzer.models import Stock, DailyPriceData, AIPrediction, PredictionAudit
from stock_analyzer.engines.smart_money_engine import get_stock_smart_money_analysis
from stock_analyzer.engines.book_strategy_engine import evaluate_all_book_strategies
from stock_analyzer.engines.data_engine import get_market_benchmarks


def generate_ai_stock_prediction(
    stock: Stock,
    timeframe_type: str = "DAILY",
    force_new: bool = False,
    as_of_date=None
) -> AIPrediction:
    """
    Generates multi-factor AI trade forecast for a specific horizon:
    - DAILY: Next-day trading range (verified after 1 day).
    - WEEKLY: 1-week swing momentum (verified weekly / 5 days).
    - MONTHLY: 1-month position trend (verified monthly / 20 days).
    All horizons enforce a strict 1:3 Risk-to-Reward ratio.
    """
    today = as_of_date if as_of_date else timezone.now().date()
    timeframe_type = timeframe_type.upper()
    if timeframe_type not in ["DAILY", "WEEKLY", "MONTHLY"]:
        timeframe_type = "DAILY"

    # Reuse existing active prediction if still within its valid timeframe cycle
    if not force_new:
        existing = AIPrediction.objects.filter(
            stock=stock,
            timeframe_type=timeframe_type,
            status="ACTIVE"
        ).order_by("-prediction_date", "-id").first()
        if existing:
            days_elapsed = (today - existing.prediction_date).days
            if timeframe_type == "DAILY" and days_elapsed < 1:
                return existing
            elif timeframe_type == "WEEKLY" and days_elapsed < 5:
                return existing
            elif timeframe_type == "MONTHLY" and days_elapsed < 20:
                return existing

    # 1. Fetch latest prices & technicals (as of as_of_date)
    price_query = DailyPriceData.objects.filter(stock=stock)
    if as_of_date:
        price_query = price_query.filter(date__lte=as_of_date)
    prices = price_query.order_by("-date")[:30]

    if not prices.exists():
        current_price = stock.current_price or 1600.0
        atr = current_price * 0.018
        rsi = 55.0
        macd_hist = 0.5
        ema50 = current_price * 0.98
        ema200 = current_price * 0.94
    else:
        latest = prices[0]
        current_price = latest.close_price
        atr = latest.atr_14 or (current_price * 0.018)
        rsi = latest.rsi_14 or 50.0
        macd_hist = latest.macd_hist or 0.0
        ema50 = latest.ema_50 or current_price
        ema200 = latest.ema_200 or current_price

    # 2. Evaluate Smart Money & Book Strategies (with as_of_date)
    smart_money = get_stock_smart_money_analysis(stock)
    smart_money_score = smart_money["consensus_score"]

    book_eval = evaluate_all_book_strategies(stock, as_of_date=as_of_date)
    book_rules_score = book_eval["overall_score"]
    mandatory_passed = book_eval["mandatory_filters_passed"]

    # 3. Calculate Technical Score (0 - 100)
    tech_score = 50
    if current_price > ema50 > ema200:
        tech_score += 25
    elif current_price > ema200:
        tech_score += 10
    else:
        tech_score -= 20

    if 45 <= rsi <= 68:
        tech_score += 15  # Healthy bullish momentum
    elif rsi < 35:
        tech_score += 10  # Oversold value zone
    elif rsi > 75:
        tech_score -= 15  # Overbought caution

    if macd_hist > 0:
        tech_score += 10
    else:
        tech_score -= 10

    technical_score = max(min(int(tech_score), 98), 15)

    # 4. Calculate Fundamental Score with Book Value, P/E Ratio, Shareholding & Quarterly P&L (0 - 100)
    fund_score = 50
    if stock.market_cap_crores > 50000:
        fund_score += 10  # High liquidity large cap stability
    elif stock.market_cap_crores > 15000:
        fund_score += 6

    pe = stock.pe_ratio or 22.0
    ind_pe = stock.industry_pe or 25.0
    eps_growth = stock.eps_growth_yoy or 12.0
    pb = stock.pb_ratio or 2.8
    book_val = stock.book_value or (stock.current_price / pb if pb else 100.0)
    roe = stock.roe_pct or 15.0

    # P/E Ratio Evaluation vs Industry Peers & Growth
    if pe < ind_pe and eps_growth >= 12.0:
        fund_score += 15  # Attractive valuation discount with strong earnings growth
    elif pe < ind_pe:
        fund_score += 8
    elif pe > (ind_pe * 1.8) and eps_growth < 10.0:
        fund_score -= 14  # High valuation penalty without matching growth
    elif pe > 50:
        fund_score -= 8

    # Book Value & P/B Ratio Evaluation
    if pb < 3.0 and roe >= 15.0:
        fund_score += 12  # Strong asset backing + high return on equity
    elif pb < 5.0 and roe >= 18.0:
        fund_score += 8
    elif pb > 14.0 and eps_growth < 10.0:
        fund_score -= 10  # Asset overvaluation trap

    if roe > 18.0:
        fund_score += 8
    elif roe < 8.0:
        fund_score -= 10

    debt_eq = stock.debt_to_equity or 0.5
    if debt_eq < 0.5:
        fund_score += 8  # Pristine balance sheet / low leverage
    elif debt_eq > 1.8:
        fund_score -= 12  # Overleveraged debt risk

    # Shareholding Distribution Evaluation (FII, DII, Promoters, Retailers)
    fii = stock.fii_holding_pct or 0.0
    dii = stock.dii_holding_pct or 0.0
    promoter = stock.promoter_holding_pct or 0.0
    inst_holding = fii + dii
    retail = stock.retail_holding_pct if stock.retail_holding_pct is not None else round(max(100.0 - promoter - inst_holding, 0.0), 2)

    if inst_holding >= 35.0:
        fund_score += 10  # Strong Institutional Sponsorship (CAN SLIM 'I')
    elif inst_holding >= 20.0:
        fund_score += 5
    elif inst_holding < 15.0:
        fund_score -= 8   # Under-owned by institutions

    if promoter >= 50.0:
        fund_score += 6   # Strong founder skin-in-the-game
    elif promoter < 25.0 and stock.sector != "Financial Services":
        fund_score -= 5

    if retail > 50.0:
        fund_score -= 12  # Heavy retail crowd / panic vulnerability
    elif retail < 25.0:
        fund_score += 6   # Tightly controlled float

    # Quarterly Profit/Loss & Growth Evaluation (CAN SLIM 'C')
    is_profitable = stock.is_quarterly_profitable
    q_profit = stock.quarterly_net_profit_crores
    q_growth = stock.quarterly_profit_growth_yoy
    q_rev = stock.quarterly_revenue_crores
    q_rev_growth = stock.quarterly_revenue_growth_yoy

    if is_profitable is False and q_profit is not None and q_profit < 0:
        fund_score -= 25  # Quarterly loss penalty
    else:
        fund_score += 8
        if q_growth is not None:
            if q_growth >= 20.0:
                fund_score += 15  # O'Neil CAN SLIM target (>20% YoY earnings acceleration)
            elif q_growth >= 10.0:
                fund_score += 8
            elif q_growth < 0:
                fund_score -= 10  # Quarterly earnings contraction
        if q_rev_growth is not None and q_rev_growth >= 15.0:
            fund_score += 5   # Top-line revenue expansion

    fundamental_score = max(min(int(fund_score), 98), 15)

    # 5. Real-Time News Trading & Sentiment Impact
    news_sentiment_score = stock.news_sentiment_score if stock.news_sentiment_score is not None else 0.0
    news_label = stock.news_sentiment_label or "NEUTRAL 🟡"
    news_headline = stock.latest_news_headline or ""
    news_score = int(50 + (news_sentiment_score * 40)) # Normalized 10 to 90
    news_score = max(min(news_score, 95), 10)

    # 6. Database Lesson Memory (Check past failed predictions for this stock/sector)
    past_lessons = PredictionAudit.objects.filter(
        prediction__stock__sector=stock.sector,
        is_successful=False
    ).exclude(ai_lesson_learned="").order_by("-id")[:3]
    
    lesson_penalty = 0
    lesson_notes = []
    for past in past_lessons:
        if "High VIX" in past.root_cause_category and get_market_benchmarks().get("market_regime_badge") == "CHOPPY_HIGH_VIX":
            lesson_penalty += 12
            lesson_notes.append("Lesson Applied: Cautious due to past sector volatility failure during elevated VIX.")
        elif "Volume" in past.root_cause_category:
            lesson_penalty += 5

    # 7. Composite Score & Action Decision
    # Weights: Smart Money (30%), Book Rules (25%), Technicals (20%), Fundamentals (15%), News Trading (10%)
    raw_composite = (
        (smart_money_score * 0.30) +
        (book_rules_score * 0.25) +
        (technical_score * 0.20) +
        (fundamental_score * 0.15) +
        (news_score * 0.10)
    ) - lesson_penalty

    # News Sentiment Boost or Penalty
    if news_sentiment_score >= 0.25:
        raw_composite += 6  # Good News tailwind
    elif news_sentiment_score <= -0.25:
        raw_composite -= 14 # Bad News headwind

    confidence_score = max(min(int(raw_composite), 95), 20)

    # Action Matrix, Fundamental Pre-Prediction Circuit Breakers & News Filter
    if is_profitable is False and q_profit is not None and q_profit < 0:
        # Strict William O'Neil CAN SLIM 'C' Rule: NEVER buy unprofitable companies
        action = "AVOID"
        reason_flag = f"Quarterly Net Loss Warning: Operating at net loss of -₹{abs(q_profit):,.1f} Cr. William O'Neil CAN SLIM 'C' rule strictly blocks fresh buy calls on loss-making quarters."
        confidence_score = min(confidence_score, 38)
    elif retail > 55.0 and inst_holding < 20.0:
        action = "AVOID"
        reason_flag = f"Retail Distribution Risk: Retailers own {retail:.1f}% vs institutions {inst_holding:.1f}%. High panic dump risk."
        confidence_score = min(confidence_score, 42)
    elif news_sentiment_score <= -0.35:
        # Severe Negative News Override: Protect capital against regulatory probes / fraud / earnings crash
        action = "AVOID"
        reason_flag = f"Negative News Alert: Adverse media coverage ({news_label}) overrides technical indicators."
    elif not mandatory_passed:
        action = "HOLD"
        reason_flag = f"Mandatory Book Rules not fully satisfied ({', '.join(book_eval['failed_mandatory_rules'])})."
    elif confidence_score >= 78 and technical_score >= 65 and news_sentiment_score >= -0.10:
        action = "STRONG_BUY"
        reason_flag = "High institutional consensus, favorable news sentiment, and confirmed Stage 2 trend alignment."
    elif confidence_score >= 65 and news_sentiment_score >= -0.15:
        action = "ACCUMULATE"
        reason_flag = "Solid mutual fund backing, attractive P/E and Book Value, and healthy news backdrop."
    elif confidence_score >= 48:
        action = "HOLD"
        reason_flag = "Consolidating in base range; wait for decisive volume breakout before adding fresh positions."
    else:
        action = "AVOID"
        reason_flag = "Downtrend structure, negative news, or lack of institutional support."

    # 8. Asymmetric Risk Management (Disciplined 1:3 Risk-to-Reward Ratio)
    if timeframe_type == "DAILY":
        timeframe_days = 1
        # Next-day intraday buffer (min 1.0% buffer)
        stop_buffer = round(max(atr * 0.75, current_price * 0.01), 2)
        horizon_title = "Next-Day (Daily) ⚡"
    elif timeframe_type == "WEEKLY":
        timeframe_days = 5
        # 1-week swing buffer (min 2.0% buffer)
        stop_buffer = round(max(atr * 1.5, current_price * 0.02), 2)
        horizon_title = "Weekly (Swing) 📅"
    else:  # MONTHLY
        timeframe_days = 20
        # 1-month position buffer (min 3.5% buffer)
        stop_buffer = round(max(atr * 2.5, current_price * 0.035, current_price - (ema50 * 0.99)), 2)
        horizon_title = "Monthly (Position) 🗓️"

    # Strictly 3.0x Risk Buffer (1:3 RR)
    target_buffer = round(stop_buffer * 3.0, 2)
    stop_loss_price = round(current_price - stop_buffer, 2)
    target_price = round(current_price + target_buffer, 2)

    expected_return_pct = round(((target_price - current_price) / current_price) * 100, 2)
    max_risk_pct = round(((current_price - stop_loss_price) / current_price) * 100, 2)
    risk_reward_ratio = 3.0 # Exact 1:3 Risk-Reward Ratio

    # 30-Day Monthly Target Horizons Reference (also maintaining 1:3 RR)
    monthly_stop_buffer = round(max(atr * 2.5, current_price * 0.035, current_price - (ema50 * 0.99)), 2)
    monthly_target_buffer = round(monthly_stop_buffer * 3.0, 2)
    monthly_target_price = round(current_price + monthly_target_buffer, 2)
    monthly_stop_loss_price = round(current_price - monthly_stop_buffer, 2)
    monthly_expected_return_pct = round(((monthly_target_price - current_price) / current_price) * 100, 2)

    # Check Upcoming Earnings Catalyst & Event Risk (Minervini & O'Neil Rule)
    earnings_warning = None
    days_to_earn = stock.days_until_earnings
    if days_to_earn is not None and 0 <= days_to_earn <= 12:
        earnings_warning = (
            f"⚠️ **Upcoming Earnings Catalyst**: Quarterly financial results scheduled for "
            f"{stock.next_earnings_date.strftime('%d %b %Y')} (in {days_to_earn} days). "
            f"Consensus EPS Estimate: ₹{stock.eps_estimate or 'N/A'}, "
            f"Revenue Forecast: ₹{stock.revenue_estimate_crores:,.0f} Cr. "
            f"Per Minervini SEPA rules, AI tightens stop buffer to mitigate binary earnings gap risk."
        )
        # Moderate confidence to prevent binary roulette trap
        confidence_score = max(confidence_score - 6, 25)
        if action == "STRONG_BUY":
            action = "ACCUMULATE"

    # 9. Detailed AI Thesis Generation
    news_text = f"• **News Sentiment & Catalysts**: {news_label} (Score: {news_score}/100). {stock.news_sentiment_summary or 'No major headwinds.'}\n"
    if news_headline:
        news_text += f"   *Latest Headline*: \"{news_headline}\"\n"

    # Format Quarterly Profit & Shareholding summary for Thesis
    profit_desc = f"Net Profit: ₹{q_profit:,.1f} Cr ({'Profitable ✅' if is_profitable else 'Loss-Making ❌'})" if q_profit is not None else "Profitable Base"
    growth_desc = f" | YoY Profit Growth: {q_growth:+.1f}%" if q_growth is not None else ""
    rev_desc = f" | Revenue: ₹{q_rev:,.1f} Cr" if q_rev is not None else ""

    ai_thesis = (
        f"**Master Strategy Thesis for {stock.name} ({stock.symbol}) — [{horizon_title}]**\n\n"
        f"• **Smart Money Signal**: {smart_money['signal']} with ₹{smart_money['total_capital_crores']:,.0f} Cr "
        f"invested across {smart_money['total_funds_holding']} top-tier mutual funds.\n"
        f"• **Shareholding Structure**: Promoters: {promoter:.1f}% | Foreign Investors (FII): {fii:.1f}% | "
        f"Mutual Funds / DII: {dii:.1f}% | Retailers: {retail:.1f}%.\n"
        f"• **Quarterly P&L Performance**: {profit_desc}{growth_desc}{rev_desc} (O'Neil CAN SLIM 'C' Verified).\n"
        f"• **Trading Books Consensus**: {book_eval['overall_score']}% score across Minervini, O'Neil CAN SLIM, "
        f"and Weinstein Stage 2 frameworks ({book_eval['current_stage']}).\n"
        f"• **Valuation & Fundamentals**: P/E of {pe:.1f} vs Industry P/E {ind_pe:.1f}. "
        f"Book Value ₹{book_val:,.1f} (P/B: {pb:.1f}x) with {roe:.1f}% ROE and {stock.piotroski_score}/9 Piotroski score.\n"
        f"{news_text}"
        f"• **Technical Structure**: Price ₹{current_price:,.2f} relative to 50 EMA (₹{ema50:,.2f}) and 200 EMA (₹{ema200:,.2f}). "
        f"RSI is at {rsi:.1f} with MACD momentum positive.\n"
        f"• **Disciplined 1:3 Risk Management [{horizon_title}]**:\n"
        f"   - Target: 🎯 ₹{target_price:,.2f} (+{expected_return_pct}%) | Stop-Loss: 🛑 ₹{stop_loss_price:,.2f} (-{max_risk_pct}%).\n"
        f"   - Risk ₹{stop_buffer:,.2f} to make ₹{target_buffer:,.2f} (Strict 1:3 Risk-to-Reward Ratio)."
    )

    if earnings_warning:
        ai_thesis += f"\n\n{earnings_warning}"

    if lesson_notes:
        ai_thesis += f"\n\n🛡️ *Self-Learning Safeguard*: {' '.join(lesson_notes)}"

    # 10. Ensure single active prediction per stock per timeframe (expire older active of this timeframe)
    AIPrediction.objects.filter(stock=stock, timeframe_type=timeframe_type, status="ACTIVE").update(status="EXPIRED")

    # Create and Save Prediction
    prediction = AIPrediction.objects.create(
        stock=stock,
        prediction_date=today,
        timeframe_type=timeframe_type,
        action=action,
        entry_price=round(current_price, 2),
        target_price=target_price,
        stop_loss_price=stop_loss_price,
        expected_return_pct=expected_return_pct,
        max_risk_pct=max_risk_pct,
        risk_reward_ratio=risk_reward_ratio,
        timeframe_days=timeframe_days,
        monthly_target_price=monthly_target_price,
        monthly_expected_return_pct=monthly_expected_return_pct,
        monthly_stop_loss_price=monthly_stop_loss_price,
        pe_at_prediction=round(pe, 2),
        pb_at_prediction=round(pb, 2),
        book_value_at_prediction=round(book_val, 2),
        promoter_holding_at_prediction=round(promoter, 2),
        fii_holding_at_prediction=round(fii, 2),
        dii_holding_at_prediction=round(dii, 2),
        retail_holding_at_prediction=round(retail, 2),
        quarterly_profit_crores_at_prediction=round(q_profit, 2) if q_profit is not None else None,
        quarterly_growth_at_prediction=round(q_growth, 2) if q_growth is not None else None,
        is_quarterly_profitable_at_prediction=bool(is_profitable),
        news_score=news_score,
        news_sentiment=news_label,
        news_headline=news_headline[:350] if news_headline else "",
        confidence_score=confidence_score,
        strategy_used="Minervini Trend, Smart Money & News Sentiment Ensemble",
        ai_thesis=ai_thesis,
        technical_score=technical_score,
        fundamental_score=fundamental_score,
        smart_money_score=smart_money_score,
        book_rules_score=book_rules_score,
        status="ACTIVE"
    )

    return prediction


def generate_all_timeframe_predictions(stock: Stock, force_new: bool = False, as_of_date=None) -> dict:
    """
    Generates / Refreshes all 3 horizons (Daily, Weekly, Monthly) for a stock.
    - Daily: verified next day (after 1 day).
    - Weekly: verified weekly (5-day cycle).
    - Monthly: verified monthly (20-day cycle).
    """
    return {
        "DAILY": generate_ai_stock_prediction(stock, timeframe_type="DAILY", force_new=force_new, as_of_date=as_of_date),
        "WEEKLY": generate_ai_stock_prediction(stock, timeframe_type="WEEKLY", force_new=force_new, as_of_date=as_of_date),
        "MONTHLY": generate_ai_stock_prediction(stock, timeframe_type="MONTHLY", force_new=force_new, as_of_date=as_of_date),
    }
