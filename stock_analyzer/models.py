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
    is_nifty50 = models.BooleanField(default=False)
    is_banknifty = models.BooleanField(default=False)
    last_updated = models.DateTimeField(auto_now=True)

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

    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name="predictions")
    prediction_date = models.DateField(db_index=True)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, default="STRONG_BUY")
    entry_price = models.FloatField()
    target_price = models.FloatField()
    stop_loss_price = models.FloatField()
    expected_return_pct = models.FloatField()
    max_risk_pct = models.FloatField()
    risk_reward_ratio = models.FloatField(default=2.0)
    timeframe_days = models.IntegerField(default=15)
    confidence_score = models.IntegerField(default=80)
    strategy_used = models.CharField(max_length=200, default="Minervini Trend & Smart Money Consensus")
    ai_thesis = models.TextField()
    
    technical_score = models.IntegerField(default=75)
    fundamental_score = models.IntegerField(default=75)
    smart_money_score = models.IntegerField(default=80)
    book_rules_score = models.IntegerField(default=85)
    
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="ACTIVE", db_index=True)
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
