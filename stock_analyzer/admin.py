from django.contrib import admin
from .models import (
    Stock,
    DailyPriceData,
    MutualFund,
    MutualFundHolding,
    TradingBookRule,
    AIPrediction,
    PredictionAudit,
    DailyVerificationLog
)


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = (
        "symbol",
        "name",
        "sector",
        "current_price",
        "pe_ratio",
        "industry_pe",
        "roe_pct",
        "piotroski_score",
        "next_earnings_date",
        "eps_estimate",
        "revenue_growth_yoy",
        "last_updated",
    )
    search_fields = ("symbol", "name", "sector", "industry_name", "headquarters_city")
    list_filter = ("sector", "is_nifty50", "is_banknifty", "piotroski_score")
    readonly_fields = ("last_updated",)
    fieldsets = (
        ("Core Identity", {
            "fields": ("symbol", "name", "sector", "industry_name", "headquarters_city", "is_nifty50", "is_banknifty", "last_updated")
        }),
        ("Market Pricing & Technical Range", {
            "fields": ("current_price", "market_cap_crores", "fifty_two_week_high", "fifty_two_week_low")
        }),
        ("Valuation & Solvency Fundamentals", {
            "fields": (
                "pe_ratio", "industry_pe", "pb_ratio", "book_value", "dividend_yield_pct",
                "roe_pct", "debt_to_equity", "operating_margin_pct", "profit_margin_pct",
                "piotroski_score", "eps_growth_yoy"
            )
        }),
        ("Shareholding Pattern (Institutional & Promoters)", {
            "fields": ("promoter_holding_pct", "fii_holding_pct", "dii_holding_pct")
        }),
        ("TradingView Intelligence & Upcoming Earnings", {
            "fields": (
                "next_earnings_date", "eps_estimate", "revenue_estimate_crores",
                "revenue_growth_yoy", "full_time_employees", "business_summary"
            )
        }),
    )


@admin.register(DailyPriceData)
class DailyPriceDataAdmin(admin.ModelAdmin):
    list_display = ("stock", "date", "close_price", "open_price", "high_price", "low_price", "volume", "rsi_14", "volatility_pct")
    search_fields = ("stock__symbol", "stock__name")
    list_filter = ("date",)
    date_hierarchy = "date"


@admin.register(MutualFund)
class MutualFundAdmin(admin.ModelAdmin):
    list_display = ("name", "amc_name", "category", "aum_crores", "star_rating", "one_year_return_pct", "three_year_return_pct")
    search_fields = ("name", "amc_name", "category")
    list_filter = ("amc_name", "category", "star_rating")


@admin.register(MutualFundHolding)
class MutualFundHoldingAdmin(admin.ModelAdmin):
    list_display = ("fund", "stock", "weight_pct", "holding_value_crores", "mom_action")
    search_fields = ("fund__name", "stock__symbol", "stock__name")
    list_filter = ("mom_action", "fund__amc_name")


@admin.register(TradingBookRule)
class TradingBookRuleAdmin(admin.ModelAdmin):
    list_display = ("rule_code", "rule_name", "master_name", "book_title", "category", "importance_weight", "is_mandatory_filter")
    search_fields = ("rule_code", "rule_name", "master_name", "book_title")
    list_filter = ("category", "master_name", "is_mandatory_filter")


@admin.register(AIPrediction)
class AIPredictionAdmin(admin.ModelAdmin):
    list_display = (
        "stock",
        "prediction_date",
        "action",
        "entry_price",
        "target_price",
        "stop_loss_price",
        "confidence_score",
        "risk_reward_ratio",
        "status",
    )
    search_fields = ("stock__symbol", "stock__name", "strategy_used")
    list_filter = ("action", "status", "prediction_date")
    date_hierarchy = "prediction_date"


@admin.register(PredictionAudit)
class PredictionAuditAdmin(admin.ModelAdmin):
    list_display = ("prediction", "is_successful", "pnl_percentage", "resolved_date", "root_cause_category", "duration_days")
    search_fields = ("prediction__stock__symbol", "root_cause_category", "ai_lesson_learned")
    list_filter = ("is_successful", "root_cause_category")


@admin.register(DailyVerificationLog)
class DailyVerificationLogAdmin(admin.ModelAdmin):
    list_display = ("audit_date", "active_predictions_count", "targets_hit_today", "stop_losses_hit_today", "cumulative_win_rate_pct", "total_completed_trades")
    list_filter = ("audit_date",)
