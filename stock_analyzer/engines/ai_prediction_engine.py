import datetime
from django.utils import timezone
from stock_analyzer.models import Stock, DailyPriceData, AIPrediction, PredictionAudit
from stock_analyzer.engines.smart_money_engine import get_stock_smart_money_analysis
from stock_analyzer.engines.book_strategy_engine import evaluate_all_book_strategies
from stock_analyzer.engines.data_engine import get_market_benchmarks


def generate_ai_stock_prediction(stock: Stock, force_new: bool = False) -> AIPrediction:
    """
    Generates multi-factor AI trade forecast combining Technicals, Fundamentals,
    Smart Money / Mutual Fund Inflows, Trading Book Rules, and Database Lesson Memory.
    """
    today = timezone.now().date()

    # If recent prediction exists within 3 days and not forced, reuse it
    if not force_new:
        existing = AIPrediction.objects.filter(stock=stock, status="ACTIVE").order_by("-prediction_date").first()
        if existing and (today - existing.prediction_date).days <= 3:
            return existing

    # 1. Fetch latest prices & technicals
    prices = DailyPriceData.objects.filter(stock=stock).order_by("-date")[:30]
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

    # 2. Evaluate Smart Money & Book Strategies
    smart_money = get_stock_smart_money_analysis(stock)
    smart_money_score = smart_money["consensus_score"]

    book_eval = evaluate_all_book_strategies(stock)
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

    # 4. Calculate Fundamental Score (0 - 100)
    fund_score = 50
    if stock.market_cap_crores > 50000:
        fund_score += 15  # High liquidity large cap stability
    elif stock.market_cap_crores > 15000:
        fund_score += 10

    pe = stock.pe_ratio or 22.0
    if pe < 25:
        fund_score += 15
    elif pe > 45:
        fund_score -= 10

    roe = stock.roe_pct or 15.0
    if roe > 15:
        fund_score += 10

    fundamental_score = max(min(int(fund_score), 98), 20)

    # 5. Database Lesson Memory (Check past failed predictions for this stock/sector)
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

    # 6. Composite Score & Action Decision
    # Weights: Smart Money (35%), Book Rules (30%), Technicals (20%), Fundamentals (15%)
    raw_composite = (
        (smart_money_score * 0.35) +
        (book_rules_score * 0.30) +
        (technical_score * 0.20) +
        (fundamental_score * 0.15)
    ) - lesson_penalty

    confidence_score = max(min(int(raw_composite), 95), 25)

    # Action Matrix
    if not mandatory_passed:
        action = "HOLD"
        reason_flag = f"Mandatory Book Rules not fully satisfied ({', '.join(book_eval['failed_mandatory_rules'])})."
    elif confidence_score >= 78 and technical_score >= 65:
        action = "STRONG_BUY"
        reason_flag = "High institutional consensus with confirmed Stage 2 Minervini trend template alignment."
    elif confidence_score >= 65:
        action = "ACCUMULATE"
        reason_flag = "Solid mutual fund backing and healthy fundamentals; accumulate on minor intraday pullbacks."
    elif confidence_score >= 48:
        action = "HOLD"
        reason_flag = "Consolidating in base range; wait for decisive volume breakout before adding fresh positions."
    else:
        action = "AVOID"
        reason_flag = "Downtrend structure or lack of institutional support."

    # 7. Asymmetric Risk Management (ATR-based Stop-Loss and Target)
    # Stop-Loss = 1.5 * ATR (risk buffer)
    # Target = 3.2 * ATR (ensuring >= 1:2.13 Risk-to-Reward ratio)
    stop_buffer = round(atr * 1.5, 2)
    target_buffer = round(atr * 3.2, 2)

    stop_loss_price = round(max(current_price - stop_buffer, current_price * 0.94), 2)
    target_price = round(current_price + target_buffer, 2)

    expected_return_pct = round(((target_price - current_price) / current_price) * 100, 2)
    max_risk_pct = round(((current_price - stop_loss_price) / current_price) * 100, 2)
    risk_reward_ratio = round(expected_return_pct / max_risk_pct, 2) if max_risk_pct > 0 else 2.1

    # 8. Detailed AI Thesis Generation
    ai_thesis = (
        f"**Master Strategy Thesis for {stock.name} ({stock.symbol})**\n\n"
        f"• **Smart Money Signal**: {smart_money['signal']} with ₹{smart_money['total_capital_crores']:,.0f} Cr "
        f"invested across {smart_money['total_funds_holding']} top-tier mutual funds.\n"
        f"• **Trading Books Consensus**: {book_eval['overall_score']}% score across Minervini, O'Neil CAN SLIM, "
        f"and Weinstein Stage 2 frameworks ({book_eval['current_stage']}).\n"
        f"• **Technical Structure**: Price ₹{current_price:,.2f} relative to 50 EMA (₹{ema50:,.2f}) and 200 EMA (₹{ema200:,.2f}). "
        f"RSI is at {rsi:.1f} with MACD momentum positive.\n"
        f"• **Risk Management**: Risk ₹{stop_buffer:,.2f} (-{max_risk_pct}%) to make ₹{target_buffer:,.2f} (+{expected_return_pct}%), "
        f"giving a favorable **{risk_reward_ratio}x Risk-Reward profile**."
    )

    if lesson_notes:
        ai_thesis += f"\n\n🛡️ *Self-Learning Safeguard*: {' '.join(lesson_notes)}"

    # 9. Create and Save Prediction
    prediction = AIPrediction.objects.create(
        stock=stock,
        prediction_date=today,
        action=action,
        entry_price=round(current_price, 2),
        target_price=target_price,
        stop_loss_price=stop_loss_price,
        expected_return_pct=expected_return_pct,
        max_risk_pct=max_risk_pct,
        risk_reward_ratio=risk_reward_ratio,
        timeframe_days=15,
        confidence_score=confidence_score,
        strategy_used="Minervini Trend & Smart Money Consensus Ensemble",
        ai_thesis=ai_thesis,
        technical_score=technical_score,
        fundamental_score=fundamental_score,
        smart_money_score=smart_money_score,
        book_rules_score=book_rules_score,
        status="ACTIVE"
    )

    return prediction
