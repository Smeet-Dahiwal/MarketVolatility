from django.db import models


class Stock(models.Model):
    symbol = models.CharField(max_length=30, unique=True, db_index=True)
    name = models.CharField(max_length=150)
    sector = models.CharField(max_length=100, default="Diversified")
    market_cap_crores = models.FloatField(default=0.0)
    current_price = models.FloatField(default=0.0)
    pe_ratio = models.FloatField(null=True, blank=True)
    pb_ratio = models.FloatField(null=True, blank=True)
    roe_pct = models.FloatField(null=True, blank=True)
    debt_to_equity = models.FloatField(null=True, blank=True)
    eps_growth_yoy = models.FloatField(null=True, blank=True)
    fifty_two_week_high = models.FloatField(null=True, blank=True)
    fifty_two_week_low = models.FloatField(null=True, blank=True)
    
    # Detailed Business & Shareholding Fundamentals
    book_value = models.FloatField(null=True, blank=True)
    dividend_yield_pct = models.FloatField(null=True, blank=True)
    promoter_holding_pct = models.FloatField(null=True, blank=True)
    fii_holding_pct = models.FloatField(null=True, blank=True)
    dii_holding_pct = models.FloatField(null=True, blank=True)
    retail_holding_pct = models.FloatField(null=True, blank=True)

    # Quarterly Financial Performance (Profit & Loss)
    quarterly_net_profit_crores = models.FloatField(null=True, blank=True)
    quarterly_revenue_crores = models.FloatField(null=True, blank=True)
    quarterly_profit_growth_yoy = models.FloatField(null=True, blank=True)
    quarterly_revenue_growth_yoy = models.FloatField(null=True, blank=True)
    is_quarterly_profitable = models.BooleanField(default=True)

    operating_margin_pct = models.FloatField(null=True, blank=True)
    profit_margin_pct = models.FloatField(null=True, blank=True)
    industry_pe = models.FloatField(null=True, blank=True)
    piotroski_score = models.IntegerField(default=8) # 0 to 9 financial health score

    # TradingView Financial Profile & Upcoming Earnings Factors
    next_earnings_date = models.DateField(null=True, blank=True)
    eps_estimate = models.FloatField(null=True, blank=True)
    revenue_estimate_crores = models.FloatField(null=True, blank=True)
    revenue_growth_yoy = models.FloatField(null=True, blank=True)
    full_time_employees = models.IntegerField(null=True, blank=True)
    headquarters_city = models.CharField(max_length=100, default="Mumbai")
    industry_name = models.CharField(max_length=120, default="Major Banks")
    business_summary = models.TextField(blank=True, default="")

    # Real-Time News Trading & Sentiment Factors
    latest_news_headline = models.CharField(max_length=350, blank=True, default="")
    news_sentiment_score = models.FloatField(default=0.0) # -1.0 (Bearish) to +1.0 (Bullish)
    news_sentiment_label = models.CharField(max_length=40, default="NEUTRAL 🟡")
    news_sentiment_summary = models.TextField(blank=True, default="")
    news_updated_at = models.DateTimeField(null=True, blank=True)

    is_nifty50 = models.BooleanField(default=False)
    is_banknifty = models.BooleanField(default=False)
    last_updated = models.DateTimeField(auto_now=True)

    @property
    def days_until_earnings(self):
        if not self.next_earnings_date:
            return None
        from django.utils import timezone
        return (self.next_earnings_date - timezone.now().date()).days

    def __str__(self):
        return f"{self.symbol} ({self.name})"


class DailyPriceData(models.Model):
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name="prices")
    date = models.DateField(db_index=True)
    open_price = models.FloatField()
    high_price = models.FloatField()
    low_price = models.FloatField()
    close_price = models.FloatField()
    volume = models.BigIntegerField()
    ema_20 = models.FloatField(null=True, blank=True)
    ema_50 = models.FloatField(null=True, blank=True)
    ema_150 = models.FloatField(null=True, blank=True)
    ema_200 = models.FloatField(null=True, blank=True)
    rsi_14 = models.FloatField(null=True, blank=True)
    macd_line = models.FloatField(null=True, blank=True)
    macd_signal = models.FloatField(null=True, blank=True)
    macd_hist = models.FloatField(null=True, blank=True)
    atr_14 = models.FloatField(null=True, blank=True)
    volatility_pct = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ("stock", "date")
        ordering = ["date"]

    def __str__(self):
        return f"{self.stock.symbol} - {self.date} (₹{self.close_price})"


class MutualFund(models.Model):
    name = models.CharField(max_length=200, unique=True)
    amc_name = models.CharField(max_length=100)
    category = models.CharField(max_length=60, default="Flexi Cap")
    aum_crores = models.FloatField(default=0.0)
    star_rating = models.IntegerField(default=5)
    one_year_return_pct = models.FloatField(default=0.0)
    three_year_return_pct = models.FloatField(default=0.0)

    def __str__(self):
        return f"{self.name} (AUM: ₹{self.aum_crores:,.0f} Cr)"


class MutualFundHolding(models.Model):
    ACTION_CHOICES = [
        ("HEAVY_ACCUMULATION", "Heavy Accumulation 🚀"),
        ("ACCUMULATING", "Accumulating 📈"),
        ("STABLE", "Stable Hold ⚖️"),
        ("TRIMMING", "Trimming 📉"),
    ]

    fund = models.ForeignKey(MutualFund, on_delete=models.CASCADE, related_name="holdings")
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name="fund_holdings")
    weight_pct = models.FloatField(default=0.0)
    holding_value_crores = models.FloatField(default=0.0)
    mom_action = models.CharField(max_length=30, choices=ACTION_CHOICES, default="ACCUMULATING")

    class Meta:
        unique_together = ("fund", "stock")
        ordering = ["-weight_pct"]

    def __str__(self):
        return f"{self.fund.amc_name} -> {self.stock.symbol} ({self.weight_pct}%)"


class TradingBookRule(models.Model):
    CATEGORY_CHOICES = [
        ("TREND", "Trend & Moving Averages"),
        ("INSTITUTIONAL", "Institutional / Smart Money"),
        ("VALUATION", "Valuation & Fundamentals"),
        ("RISK", "Risk Management & Volatility"),
        ("VOLUME", "Volume & Price Action"),
    ]

    master_name = models.CharField(max_length=100)
    book_title = models.CharField(max_length=200)
    rule_code = models.CharField(max_length=60, unique=True)
    rule_name = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="TREND")
    importance_weight = models.FloatField(default=1.0)
    is_mandatory_filter = models.BooleanField(default=False)

    def __str__(self):
        return f"[{self.master_name}] {self.rule_name}"


class AIPrediction(models.Model):
    ACTION_CHOICES = [
        ("STRONG_BUY", "STRONG BUY 🟢"),
        ("ACCUMULATE", "ACCUMULATE 📈"),
        ("HOLD", "HOLD / WAIT 🟡"),
        ("AVOID", "AVOID 🔴"),
    ]

    STATUS_CHOICES = [
        ("ACTIVE", "Active ⏳"),
        ("TARGET_HIT", "Target Hit 🎯"),
        ("STOP_LOSS_HIT", "Stop Loss Hit 🛑"),
        ("EXPIRED", "Expired ⏱️"),
    ]

    TIMEFRAME_CHOICES = [
        ("DAILY", "Next-Day (Daily) ⚡"),
        ("WEEKLY", "Weekly (Swing) 📅"),
        ("MONTHLY", "Monthly (Position) 🗓️"),
    ]

    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name="predictions")
    prediction_date = models.DateField(db_index=True)
    timeframe_type = models.CharField(max_length=20, choices=TIMEFRAME_CHOICES, default="DAILY", db_index=True)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, default="STRONG_BUY")
    entry_price = models.FloatField()
    target_price = models.FloatField()
    stop_loss_price = models.FloatField()
    expected_return_pct = models.FloatField()
    max_risk_pct = models.FloatField()
    risk_reward_ratio = models.FloatField(default=3.0) # Disciplined 1:3 Risk-to-Reward Ratio
    timeframe_days = models.IntegerField(default=1) # 1 for Daily, 5 for Weekly, 20 for Monthly
    
    # 30-Day Monthly Target Horizons
    monthly_target_price = models.FloatField(null=True, blank=True)
    monthly_expected_return_pct = models.FloatField(null=True, blank=True)
    monthly_stop_loss_price = models.FloatField(null=True, blank=True)

    # Fundamental & Valuation Snapshot at Prediction
    pe_at_prediction = models.FloatField(null=True, blank=True)
    pb_at_prediction = models.FloatField(null=True, blank=True)
    book_value_at_prediction = models.FloatField(null=True, blank=True)

    # Shareholding & Quarterly Financial Performance Snapshot
    promoter_holding_at_prediction = models.FloatField(null=True, blank=True)
    fii_holding_at_prediction = models.FloatField(null=True, blank=True)
    dii_holding_at_prediction = models.FloatField(null=True, blank=True)
    retail_holding_at_prediction = models.FloatField(null=True, blank=True)
    quarterly_profit_crores_at_prediction = models.FloatField(null=True, blank=True)
    quarterly_growth_at_prediction = models.FloatField(null=True, blank=True)
    is_quarterly_profitable_at_prediction = models.BooleanField(default=True)

    # News Trading & Sentiment Impact
    news_score = models.IntegerField(default=50) # 0 to 100
    news_sentiment = models.CharField(max_length=40, default="NEUTRAL 🟡")
    news_headline = models.CharField(max_length=350, blank=True, default="")

    confidence_score = models.IntegerField(default=80)
    strategy_used = models.CharField(max_length=200, default="Minervini Trend & Smart Money Consensus")
    ai_thesis = models.TextField()
    
    technical_score = models.IntegerField(default=75)
    fundamental_score = models.IntegerField(default=75)
    smart_money_score = models.IntegerField(default=80)
    book_rules_score = models.IntegerField(default=85)
    
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="ACTIVE", db_index=True)
    
    # Resolution Tracking (Exact day target or stop-loss was hit)
    resolved_date = models.DateField(null=True, blank=True, db_index=True)
    resolution_day = models.IntegerField(null=True, blank=True) # Holding day number when hit (e.g., Day 4)
    exit_price = models.FloatField(null=True, blank=True)
    pnl_percentage = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-prediction_date", "-id"]

    def __str__(self):
        return f"{self.stock.symbol} ({self.action}) on {self.prediction_date} [Status: {self.status}]"


class PredictionAudit(models.Model):
    prediction = models.OneToOneField(AIPrediction, on_delete=models.CASCADE, related_name="audit")
    resolved_date = models.DateField(null=True, blank=True)
    exit_price = models.FloatField(null=True, blank=True)
    pnl_percentage = models.FloatField(null=True, blank=True)
    is_successful = models.BooleanField(null=True, blank=True)
    duration_days = models.IntegerField(default=0)
    root_cause_category = models.CharField(max_length=100, blank=True)
    what_went_wrong_analysis = models.TextField(blank=True)
    violated_book_rule = models.ForeignKey(TradingBookRule, null=True, blank=True, on_delete=models.SET_NULL)
    ai_lesson_learned = models.TextField(blank=True)
    system_weight_adjustment = models.TextField(blank=True)

    def __str__(self):
        result = "WIN" if self.is_successful else ("LOSS" if self.is_successful is False else "PENDING")
        return f"Audit for {self.prediction.stock.symbol} - {result} ({self.pnl_percentage or 0:.2f}%)"


class DailyVerificationLog(models.Model):
    audit_date = models.DateField(unique=True, db_index=True)
    active_predictions_count = models.IntegerField(default=0)
    targets_hit_today = models.IntegerField(default=0)
    stop_losses_hit_today = models.IntegerField(default=0)
    cumulative_win_rate_pct = models.FloatField(default=0.0)
    total_completed_trades = models.IntegerField(default=0)
    best_performing_strategy = models.CharField(max_length=200, default="Minervini Trend & Smart Money Consensus")
    market_regime_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-audit_date"]

    def __str__(self):
        return f"Verification on {self.audit_date}: {self.cumulative_win_rate_pct:.1f}% Win Rate"
