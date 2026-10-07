from django.urls import path
from stock_analyzer import views

app_name = "stock_analyzer"

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("stock/<str:symbol>/", views.stock_detail_view, name="stock_detail"),
    path("smart-money/", views.smart_money_view, name="smart_money"),
    path("predictions/", views.predictions_ledger_view, name="predictions"),
    path("strategy-library/", views.strategy_library_view, name="strategy_library"),
    path("api/run-audit/", views.run_audit_api, name="run_audit_api"),
    path("api/search/", views.quick_search_api, name="quick_search_api"),
    path("api/live-quote/<str:symbol>/", views.get_live_quote_api, name="live_quote_api"),
]
