import os
import sys

# Force UTF-8 encoding for Windows terminal compatibility
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import django

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "market_intelligence.settings")
django.setup()

from stock_analyzer.models import (
    Stock,
    DailyPriceData,
    MutualFund,
    MutualFundHolding,
    TradingBookRule,
    AIPrediction,
    PredictionAudit,
    DailyVerificationLog
)


def inspect_database(symbol=None):
    print("=" * 80)
    print("  BULLGUARD.AI - DATABASE INSPECTION REPORT (SQLite / Django ORM)")
    print("=" * 80)

    # 1. Summary of All Tables & Row Counts
    print("\n📊 1. DATABASE TABLES & RECORD COUNTS:")
    tables = [
        ("Stock (Indian Equities)", Stock.objects.count()),
        ("DailyPriceData (Historical OHLCV + Indicators)", DailyPriceData.objects.count()),
        ("MutualFund (Top AMCs Tracked)", MutualFund.objects.count()),
        ("MutualFundHolding (Smart Money Portfolio Allocations)", MutualFundHolding.objects.count()),
        ("TradingBookRule (6 Trading Masters Strategy Catalog)", TradingBookRule.objects.count()),
        ("AIPrediction (Active & Resolved Trade Calls)", AIPrediction.objects.count()),
        ("PredictionAudit (Post-Mortem Lessons & Verifications)", PredictionAudit.objects.count()),
        ("DailyVerificationLog (4:00 PM Audit Daily Logs)", DailyVerificationLog.objects.count()),
    ]
    for name, count in tables:
        print(f"  • {name:<55}: {count} records")

    # 2. Inspect Fields for Stock Model
    print("\n" + "=" * 80)
    target_symbol = symbol.strip().upper() if symbol else "HDFCBANK.NS"
    if not (target_symbol.endswith(".NS") or target_symbol.endswith(".BO")):
        target_symbol = f"{target_symbol}.NS"

    stock = Stock.objects.filter(symbol=target_symbol).first()
    if not stock:
        stock = Stock.objects.first()

    if stock:
        print(f"🏛️ 2. DETAILED FIELDS & VALUES STORED FOR [{stock.symbol}] ({stock.name}):\n")
        fields = [f.name for f in Stock._meta.fields]
        print(f"  Total Fields Stored on 'Stock': {len(fields)}\n")
        print(f"  {'FIELD NAME':<26} | {'STORED VALUE'}")
        print("  " + "-" * 70)
        for field_name in fields:
            val = getattr(stock, field_name)
            if isinstance(val, float):
                formatted_val = f"{val:,.2f}"
            else:
                formatted_val = str(val)
            # Truncate very long text
            if len(formatted_val) > 65:
                formatted_val = formatted_val[:62] + "..."
            print(f"  {field_name:<26} | {formatted_val}")

    # 3. Active AI Prediction Fields
    print("\n" + "=" * 80)
    pred = AIPrediction.objects.filter(stock=stock).order_by("-id").first()
    if pred:
        print(f"🤖 3. AI PREDICTION RECORD STORED FOR [{stock.symbol}]:\n")
        pred_fields = [f.name for f in AIPrediction._meta.fields]
        print(f"  {'FIELD NAME':<26} | {'STORED VALUE'}")
        print("  " + "-" * 70)
        for field_name in pred_fields:
            val = getattr(pred, field_name)
            if isinstance(val, float):
                formatted_val = f"{val:,.2f}"
            else:
                formatted_val = str(val)
            if len(formatted_val) > 65:
                formatted_val = formatted_val[:62] + "..."
            print(f"  {field_name:<26} | {formatted_val}")

    print("\n" + "=" * 80)
    print("💡 TIP: You can also inspect & edit all fields visually via the Django Admin Panel:")
    print("   👉 Open in browser: http://127.0.0.1:8000/admin/")
    print("   👉 Login: admin  |  Password: admin123")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "HDFCBANK.NS"
    inspect_database(sym)
