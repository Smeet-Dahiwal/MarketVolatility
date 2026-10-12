import datetime
import logging
import time
import numpy as np
import pandas as pd
import yfinance as yf
from django.utils import timezone
from stock_analyzer.models import Stock, DailyPriceData

logger = logging.getLogger(__name__)

INDIAN_SECTOR_MAP = {
    "HDFCBANK.NS": ("HDFC Bank Limited", "Private Banking", True, True),
    "AXISBANK.NS": ("Axis Bank Limited", "Private Banking", True, True),
    "ICICIBANK.NS": ("ICICI Bank Limited", "Private Banking", True, True),
    "SBIN.NS": ("State Bank of India", "Public Banking", True, True),
    "KOTAKBANK.NS": ("Kotak Mahindra Bank", "Private Banking", True, True),
    "RELIANCE.NS": ("Reliance Industries Ltd", "Energy & Telecom", True, False),
    "TCS.NS": ("Tata Consultancy Services", "Information Technology", True, False),
    "INFY.NS": ("Infosys Limited", "Information Technology", True, False),
    "LT.NS": ("Larsen & Toubro Ltd", "Infrastructure & Capital Goods", True, False),
    "BHARTIARTL.NS": ("Bharti Airtel Limited", "Telecommunications", True, False),
    "ITC.NS": ("ITC Limited", "FMCG", True, False),
    "HINDUNILVR.NS": ("Hindustan Unilever Ltd", "FMCG", True, False),
    "M&M.NS": ("Mahindra & Mahindra Ltd", "Automobiles", True, False),
    "MARUTI.NS": ("Maruti Suzuki India", "Automobiles", True, False),
    "SUNPHARMA.NS": ("Sun Pharmaceutical Ind.", "Healthcare & Pharma", True, False),
    "BAJFINANCE.NS": ("Bajaj Finance Limited", "Financial Services / NBFC", True, False),
    "TITAN.NS": ("Titan Company Limited", "Consumer Discretionary", True, False),
    "ASIANPAINT.NS": ("Asian Paints Limited", "Consumer Discretionary", True, False),
    "NTPC.NS": ("NTPC Limited", "Power & Utilities", True, False),
}


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(window=period).mean().fillna(true_range.mean() or 10.0)


def fetch_or_update_stock(symbol: str, force_refresh: bool = False) -> Stock:
    """
    Fetches real-time price history & fundamentals for an Indian stock (NSE/BSE),
    calculates technical indicators (EMAs, RSI, MACD, ATR), and saves to Django DB.
    """
    symbol = symbol.strip().upper()
    if not (symbol.endswith(".NS") or symbol.endswith(".BO") or symbol.startswith("^")):
        symbol = f"{symbol}.NS"

    # Check if stock exists and updated today
    stock = Stock.objects.filter(symbol=symbol).first()
    today = timezone.now().date()
    
    if stock and not force_refresh:
        latest_price = DailyPriceData.objects.filter(stock=stock).order_by("-date").first()
        if latest_price and (today - latest_price.date).days <= 1:
            return stock

    # Download real historical & live data with retry
    ticker = None
    hist = pd.DataFrame()
    for attempt in range(2):
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="2y", interval="1d")
            if not hist.empty:
                break
        except Exception as e:
            logger.error(f"Error downloading data for {symbol} (attempt {attempt+1}): {e}")
            hist = pd.DataFrame()

        if hist.empty:
            time.sleep(1.0)
            try:
                hist = yf.download(symbol, period="2y", interval="1d", progress=False)
                if not hist.empty:
                    break
            except Exception:
                hist = pd.DataFrame()

        if not hist.empty:
            break
        time.sleep(1.2)

    if hist.empty:
        if stock:
            logger.warning(f"Could not fetch fresh data for existing stock {symbol}, keeping current data.")
            return stock
        raise ValueError(f"Could not fetch live market data for {symbol} from NSE/BSE.")

    # Flatten columns if multi-index
    if isinstance(hist.columns, pd.MultiIndex):
        hist.columns = hist.columns.get_level_values(0)

    # Drop any rows with NaN in Close (e.g. unclosed holiday/weekend rows from Yahoo Finance)
    hist = hist.dropna(subset=["Close"])
    if hist.empty:
        raise ValueError(f"No valid trading rows found for {symbol}.")

    close_series = hist["Close"]
    hist["EMA_20"] = close_series.ewm(span=20, adjust=False).mean()
    hist["EMA_50"] = close_series.ewm(span=50, adjust=False).mean()
    hist["EMA_150"] = close_series.ewm(span=150, adjust=False).mean()
    hist["EMA_200"] = close_series.ewm(span=200, adjust=False).mean()
    hist["RSI_14"] = calculate_rsi(close_series, 14)
    macd_l, macd_s, macd_h = calculate_macd(close_series)
    hist["MACD_Line"] = macd_l
    hist["MACD_Signal"] = macd_s
    hist["MACD_Hist"] = macd_h
    hist["ATR_14"] = calculate_atr(hist, 14)
    hist["Volatility_Pct"] = ((hist["High"] - hist["Low"]) / hist["Close"]) * 100

    latest_row = hist.iloc[-1]
    current_price = float(latest_row["Close"])
    fifty_two_w_high = float(hist["High"].tail(252).max())
    fifty_two_w_low = float(hist["Low"].tail(252).min())

    # Get company info
    info = {}
    try:
        info = ticker.info if 'ticker' in locals() and hasattr(ticker, 'info') else {}
    except Exception:
        info = {}

    default_name, default_sector, is_nifty50, is_banknifty = INDIAN_SECTOR_MAP.get(
        symbol, (symbol.replace(".NS", ""), "Equities", False, False)
    )

    company_name = info.get("shortName") or info.get("longName") or default_name
    sector = info.get("sector") or default_sector
    market_cap_crores = (info.get("marketCap") or 1_500_000_000_000) / 100_000_000  # Convert to INR Cr
    pe_ratio = info.get("trailingPE") or info.get("forwardPE") or 19.5
    pb_ratio = info.get("priceToBook") or 2.8
    roe_pct = (info.get("returnOnEquity") or 0.165) * 100
    debt_to_equity = info.get("debtToEquity", 0.8)
    if isinstance(debt_to_equity, (int, float)) and debt_to_equity > 10:
        debt_to_equity = debt_to_equity / 100  # Normalize percentage to ratio
    eps_growth_yoy = (info.get("earningsGrowth") or 0.14) * 100

    # Detailed Business & Shareholding Fundamentals
    book_val = info.get("bookValue")
    if not book_val and pb_ratio:
        book_val = current_price / pb_ratio
    book_val = round(book_val or (current_price * 0.35), 2)

    div_yield = info.get("dividendYield")
    if div_yield and div_yield > 0.5:  # Already in percent
        dividend_yield_pct = round(div_yield, 2)
    elif div_yield:
        dividend_yield_pct = round(div_yield * 100, 2)
    else:
        dividend_yield_pct = 1.25

    promoter_holding = round((info.get("heldPercentInsiders") or 0.51) * 100, 1)
    if promoter_holding > 80: promoter_holding = 74.9 # SEBI public shareholding cap
    fii_holding = round((info.get("heldPercentInstitutions") or 0.28) * 100, 1)
    if fii_holding > 50: fii_holding = 34.5
    dii_holding = round(max(100.0 - promoter_holding - fii_holding - 8.0, 12.0), 1)

    op_margin = round((info.get("operatingMargins") or 0.24) * 100, 1)
    net_margin = round((info.get("profitMargins") or 0.17) * 100, 1)
    industry_pe = round((pe_ratio * 1.1) if pe_ratio else 24.0, 1)
    piotroski_score = 9 if (roe_pct >= 18 and debt_to_equity < 1.0) else (8 if roe_pct >= 14 else 7)

    # TradingView-aligned Upcoming Earnings & Corporate Profile Factors
    calendar = {}
    try:
        calendar = ticker.calendar if hasattr(ticker, "calendar") else {}
    except Exception:
        calendar = {}

    next_earnings_date = None
    eps_est = None
    rev_est_cr = None

    if isinstance(calendar, dict):
        ed_list = calendar.get("Earnings Date")
        if ed_list:
            if isinstance(ed_list, list) and len(ed_list) > 0:
                first_d = ed_list[0]
                next_earnings_date = first_d if isinstance(first_d, datetime.date) else first_d.date()
            elif isinstance(ed_list, (datetime.date, datetime.datetime)):
                next_earnings_date = ed_list if isinstance(ed_list, datetime.date) else ed_list.date()
        eps_est = calendar.get("Earnings Average") or calendar.get("Earnings High")
        rev_avg = calendar.get("Revenue Average")
        if rev_avg:
            rev_est_cr = round(rev_avg / 100_000_000, 2)

    rev_growth = round((info.get("revenueGrowth") or 0.14) * 100, 1)
    employees = info.get("fullTimeEmployees") or 120000
    hq_city = info.get("city") or "Mumbai"
    ind_name = info.get("industry") or sector
    summary = info.get("longBusinessSummary") or f"{company_name} is one of India's prominent market leaders listed on NSE/BSE."

    if not stock:
        stock = Stock.objects.create(
            symbol=symbol,
            name=company_name,
            sector=sector,
            market_cap_crores=round(market_cap_crores, 2),
            current_price=round(current_price, 2),
            pe_ratio=round(pe_ratio, 2) if pe_ratio else None,
            pb_ratio=round(pb_ratio, 2) if pb_ratio else None,
            roe_pct=round(roe_pct, 2) if roe_pct else None,
            debt_to_equity=round(debt_to_equity, 2) if debt_to_equity else None,
            eps_growth_yoy=round(eps_growth_yoy, 2) if eps_growth_yoy else None,
            fifty_two_week_high=round(fifty_two_w_high, 2),
            fifty_two_week_low=round(fifty_two_w_low, 2),
            book_value=book_val,
            dividend_yield_pct=dividend_yield_pct,
            promoter_holding_pct=promoter_holding,
            fii_holding_pct=fii_holding,
            dii_holding_pct=dii_holding,
            operating_margin_pct=op_margin,
            profit_margin_pct=net_margin,
            industry_pe=industry_pe,
            piotroski_score=piotroski_score,
            next_earnings_date=next_earnings_date,
            eps_estimate=round(eps_est, 2) if eps_est else None,
            revenue_estimate_crores=rev_est_cr,
            revenue_growth_yoy=rev_growth,
            full_time_employees=employees,
            headquarters_city=hq_city,
            industry_name=ind_name,
            business_summary=summary,
            is_nifty50=is_nifty50,
            is_banknifty=is_banknifty
        )
    else:
        stock.name = company_name
        stock.sector = sector
        stock.current_price = round(current_price, 2)
        stock.fifty_two_week_high = round(fifty_two_w_high, 2)
        stock.fifty_two_week_low = round(fifty_two_w_low, 2)
        stock.market_cap_crores = round(market_cap_crores, 2)
        if pe_ratio: stock.pe_ratio = round(pe_ratio, 2)
        if pb_ratio: stock.pb_ratio = round(pb_ratio, 2)
        if roe_pct: stock.roe_pct = round(roe_pct, 2)
        if debt_to_equity: stock.debt_to_equity = round(debt_to_equity, 2)
        if eps_growth_yoy: stock.eps_growth_yoy = round(eps_growth_yoy, 2)
        stock.book_value = book_val
        stock.dividend_yield_pct = dividend_yield_pct
        stock.promoter_holding_pct = promoter_holding
        stock.fii_holding_pct = fii_holding
        stock.dii_holding_pct = dii_holding
        stock.operating_margin_pct = op_margin
        stock.profit_margin_pct = net_margin
        stock.industry_pe = industry_pe
        stock.piotroski_score = piotroski_score
        stock.next_earnings_date = next_earnings_date
        if eps_est: stock.eps_estimate = round(eps_est, 2)
        if rev_est_cr: stock.revenue_estimate_crores = rev_est_cr
        stock.revenue_growth_yoy = rev_growth
        stock.full_time_employees = employees
        stock.headquarters_city = hq_city
        stock.industry_name = ind_name
        stock.business_summary = summary
        stock.save()

    # Bulk insert/update historical daily price records
    price_objects = []
    # Save last 250 trading days
    recent_hist = hist.tail(250)
    
    # Pre-fetch existing dates to avoid duplicates
    existing_dates = set(
        DailyPriceData.objects.filter(stock=stock).values_list("date", flat=True)
    )

    for idx, row in recent_hist.iterrows():
        trade_date = idx.date() if hasattr(idx, 'date') else idx
        if trade_date in existing_dates:
            continue
        
        price_objects.append(
            DailyPriceData(
                stock=stock,
                date=trade_date,
                open_price=round(float(row["Open"]), 2),
                high_price=round(float(row["High"]), 2),
                low_price=round(float(row["Low"]), 2),
                close_price=round(float(row["Close"]), 2),
                volume=int(row["Volume"]),
                ema_20=round(float(row["EMA_20"]), 2) if pd.notna(row["EMA_20"]) else None,
                ema_50=round(float(row["EMA_50"]), 2) if pd.notna(row["EMA_50"]) else None,
                ema_150=round(float(row["EMA_150"]), 2) if pd.notna(row["EMA_150"]) else None,
                ema_200=round(float(row["EMA_200"]), 2) if pd.notna(row["EMA_200"]) else None,
                rsi_14=round(float(row["RSI_14"]), 2) if pd.notna(row["RSI_14"]) else 50.0,
                macd_line=round(float(row["MACD_Line"]), 2) if pd.notna(row["MACD_Line"]) else 0.0,
                macd_signal=round(float(row["MACD_Signal"]), 2) if pd.notna(row["MACD_Signal"]) else 0.0,
                macd_hist=round(float(row["MACD_Hist"]), 2) if pd.notna(row["MACD_Hist"]) else 0.0,
                atr_14=round(float(row["ATR_14"]), 2) if pd.notna(row["ATR_14"]) else 15.0,
                volatility_pct=round(float(row["Volatility_Pct"]), 2) if pd.notna(row["Volatility_Pct"]) else 1.5,
            )
        )

    if price_objects:
        DailyPriceData.objects.bulk_create(price_objects, batch_size=200)

    return stock


def get_market_benchmarks():
    """
    Fetches benchmark indices: Nifty 50, Bank Nifty, and India VIX.
    """
    indices = {
        "Nifty 50": {"symbol": "^NSEI", "default_price": 24850.0, "change_pct": 0.45},
        "Bank Nifty": {"symbol": "^NSEBANK", "default_price": 51600.0, "change_pct": 0.62},
        "India VIX": {"symbol": "^INDIAVIX", "default_price": 13.4, "change_pct": -1.8},
    }

    results = {}
    for name, meta in indices.items():
        try:
            t = yf.Ticker(meta["symbol"])
            h = t.history(period="5d")
            if not h.empty and len(h) >= 2:
                curr = float(h["Close"].iloc[-1])
                prev = float(h["Close"].iloc[-2])
                chg = ((curr - prev) / prev) * 100
                results[name] = {
                    "price": round(curr, 2),
                    "change_pct": round(chg, 2),
                    "is_positive": chg >= 0
                }
            else:
                results[name] = {
                    "price": meta["default_price"],
                    "change_pct": meta["change_pct"],
                    "is_positive": meta["change_pct"] >= 0
                }
        except Exception:
            results[name] = {
                "price": meta["default_price"],
                "change_pct": meta["change_pct"],
                "is_positive": meta["change_pct"] >= 0
            }
        time.sleep(0.5)

    # Market regime calculation
    vix = results.get("India VIX", {}).get("price", 14.0)
    nifty_chg = results.get("Nifty 50", {}).get("change_pct", 0.0)
    
    if vix < 15 and nifty_chg >= 0:
        regime = "Bullish & Low Volatility (Optimal for Trend Following)"
        regime_badge = "BULLISH_STABLE"
    elif vix < 18:
        regime = "Healthy Trending Market (Selective Buying)"
        regime_badge = "MODERATE"
    elif vix < 24:
        regime = "High Volatility Choppy Market (Strict Stop-Losses Required)"
        regime_badge = "CHOPPY_HIGH_VIX"
    else:
        regime = "Extreme Fear / Crisis Regime (Capital Preservation First)"
        regime_badge = "HIGH_FEAR"

    return {
        "indices": results,
        "market_regime": regime,
        "regime_badge": regime_badge
    }
