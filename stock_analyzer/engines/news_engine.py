import logging
import re
import xml.etree.ElementTree as ET
import requests
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Curated Indian Financial Market Sentiment Dictionaries
BULLISH_KEYWORDS = [
    (r"\b(profit jumps?|profit surges?|surged|jumped|profit up|net up)\b", 3),
    (r"\b(beats? estimates?|outperforms?|strong results?|record revenue|record profit)\b", 3),
    (r"\b(order win|bagged order|wins contract|secures deal|mega order)\b", 3),
    (r"\b(upgrade|upgraded|target raised|buy rating|overweight)\b", 2),
    (r"\b(expansion|expands|new plant|capacity addition|acquisition)\b", 2),
    (r"\b(dividend hike|bonus issue|buyback|special dividend)\b", 2),
    (r"\b(all-time high|52-week high|multi-year high|rallies|breakout)\b", 2),
    (r"\b(strong demand|positive outlook|growth momentum|inflows|bullish)\b", 1),
]

BEARISH_KEYWORDS = [
    (r"\b(sebi notice|sebi probe|cbi probe|ed raid|tax raid|fraud|scam)\b", -4),
    (r"\b(penalty|fined|litigation|court order|arrest|defaulted|defaults)\b", -3),
    (r"\b(profit plunges?|profit drops?|net loss|loss widens|plunged|slumped)\b", -3),
    (r"\b(misses? estimates?|downgrade|downgraded|sell rating|underweight)\b", -2),
    (r"\b(target cut|slashes target|cuts price target)\b", -2),
    (r"\b(resignation|resigns|cfo quits|ceo exits|management churn)\b", -2),
    (r"\b(promoter pledge|pledged shares|debt concerns|margin compression)\b", -2),
    (r"\b(declines?|slumps?|tumbles?|weak quarter|revenue decline|headwinds)\b", -1),
]


def fetch_and_analyze_stock_news(symbol: str, company_name: str = "") -> Dict[str, Any]:
    """
    Fetches real-time financial headlines for an Indian stock via Google News RSS
    and evaluates news sentiment polarity (-1.0 to +1.0) and news score (0 to 100).
    """
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").strip()
    search_query = f"{company_name or clean_sym} stock news NSE India"
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(search_query)}&hl=en-IN&gl=IN&ceid=IN:en"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    raw_items = []
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            for item in root.findall(".//item")[:10]:
                title_elem = item.find("title")
                pub_elem = item.find("pubDate")
                if title_elem is not None and title_elem.text:
                    raw_items.append({
                        "title": title_elem.text.strip(),
                        "pubDate": pub_elem.text.strip() if pub_elem is not None else ""
                    })
    except Exception as e:
        logger.warning(f"Could not fetch news RSS for {symbol}: {e}")

    if not raw_items:
        return {
            "sentiment_score": 0.0,
            "sentiment_label": "NEUTRAL 🟡",
            "news_score": 50,
            "latest_headline": f"No recent breaking news headlines found for {clean_sym}.",
            "summary": "Neutral news backdrop; technical indicators and fundamentals remain primary drivers.",
            "headline_count": 0
        }

    total_weight = 0
    bullish_hits = 0
    bearish_hits = 0
    notable_headline = raw_items[0]["title"]

    for item in raw_items:
        title = item["title"].lower()
        
        # Check bullish matches
        for pattern, weight in BULLISH_KEYWORDS:
            if re.search(pattern, title, re.IGNORECASE):
                total_weight += weight
                bullish_hits += 1

        # Check bearish matches
        for pattern, weight in BEARISH_KEYWORDS:
            if re.search(pattern, title, re.IGNORECASE):
                total_weight += weight  # weight is negative
                bearish_hits += 1

    # Normalize polarity between -1.0 and +1.0
    total_hits = bullish_hits + bearish_hits
    if total_hits > 0:
        polarity = max(min(total_weight / (total_hits * 2.5), 1.0), -1.0)
    else:
        polarity = 0.0

    # News score on a 0 to 100 scale (50 is neutral)
    news_score = int(50 + (polarity * 40))
    news_score = max(min(news_score, 95), 10)

    # Classify Label
    if polarity >= 0.25:
        sentiment_label = "BULLISH 🟢"
        summary = (
            f"Positive news catalyst: Favorable operational updates & expansion reports detected ({bullish_hits} positive cues). "
            f"Institutional sentiment tailwind supports upward price trajectory."
        )
    elif polarity <= -0.25:
        sentiment_label = "BEARISH 🔴"
        summary = (
            f"Negative news overhang: Media reports signal cautionary regulatory, margin, or operational headwinds ({bearish_hits} negative cues). "
            f"Increased volatility risk; defensive posturing required."
        )
    else:
        sentiment_label = "NEUTRAL 🟡"
        summary = "Balanced media sentiment with routine operational coverage. Market price action guided primarily by trend templates and smart money."

    return {
        "sentiment_score": round(polarity, 2),
        "sentiment_label": sentiment_label,
        "news_score": news_score,
        "latest_headline": notable_headline,
        "summary": summary,
        "headline_count": len(raw_items)
    }
