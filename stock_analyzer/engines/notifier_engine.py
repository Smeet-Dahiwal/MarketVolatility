import os
import logging
import requests
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


def send_telegram_alert(
    summary: Dict[str, Any],
    top_predictions: List[Any] = None,
    newly_resolved_audits: List[Any] = None
) -> bool:
    """
    Dispatches automated EOD stock market verification and prediction alert
    via Telegram Bot API using HTML formatting.
    
    Expects TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in environment.
    Safely skips if not configured.
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not bot_token or not chat_id:
        logger.info("Telegram credentials not found in environment. Skipping alert.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    # Extract summary metrics
    date_str = summary.get("execution_time", "Today")
    regime = summary.get("market_regime", "Healthy Trending Market")
    win_rate = summary.get("win_rate_percentage", 66.7)
    wins = summary.get("wins", 0)
    losses = summary.get("losses", 0)
    active_count = summary.get("active_predictions", 0)
    stocks_updated = summary.get("stocks_updated", 19)

    lines = [
        "🏛️ <b>BULLGUARD AI — 4:00 PM MARKET AUDIT</b>",
        f"📅 <i>{date_str}</i>",
        f"🌐 <b>Market Regime:</b> <code>{regime}</code>",
        "",
        "📊 <b>VERIFIED PERFORMANCE:</b>",
        f"• <b>30-Day Win Rate:</b> <b>{win_rate}%</b> ({wins}W / {losses}L)",
        f"• <b>Active Monitored Calls:</b> <code>{active_count}</code>",
        f"• <b>Tracked Stocks Updated:</b> <code>{stocks_updated}</code>",
        "",
        "🎯 <b>TOP HIGH-CONVICTION CALLS FOR TOMORROW:</b>"
    ]

    action_icons = {
        "STRONG_BUY": "🟢",
        "ACCUMULATE": "📈",
        "HOLD": "🟡",
        "AVOID": "🔴",
    }

    if top_predictions:
        for pred in top_predictions[:6]:
            icon = action_icons.get(pred.action, "🎯")
            action_label = pred.get_action_display() if hasattr(pred, 'get_action_display') else pred.action
            curr = f"₹{pred.entry_price:,.2f}" if pred.entry_price else "—"
            target = f"₹{pred.target_price:,.2f}" if pred.target_price else "—"
            sl = f"₹{pred.stop_loss_price:,.2f}" if pred.stop_loss_price else "—"
            conf = f"{pred.confidence_score}%" if pred.confidence_score else "N/A"

            lines.append(
                f"{icon} <b>{pred.stock.symbol}</b> — {action_label}\n"
                f"   Entry: {curr} | Target: <b>{target}</b> | SL: {sl} (Conf: {conf})"
            )
    else:
        lines.append("• <i>No active forecasts available.</i>")

    # If any trades were resolved today
    if newly_resolved_audits:
        lines.extend(["", "🔔 <b>CALLS RESOLVED TODAY:</b>"])
        for audit in newly_resolved_audits[:4]:
            outcome = "🎯 Target Hit ✅" if audit.is_successful else "🛑 Stop-Loss Hit ❌"
            pnl = f"{audit.pnl_percentage:+.2f}%" if audit.pnl_percentage is not None else "0.0%"
            lines.append(f"• <b>{audit.prediction.stock.symbol}</b>: {outcome} ({pnl})")

    lines.extend([
        "",
        "⚡ <i>Automated EOD audit by BullGuard AI & GitHub Actions</i>"
    ])

    payload = {
        "chat_id": chat_id,
        "text": "\n".join(lines),
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        resp = requests.post(url, json=payload, timeout=12)
        if resp.status_code == 200:
            logger.info("Telegram notification delivered successfully.")
            return True
        else:
            logger.warning(f"Telegram API response {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to dispatch Telegram message: {e}")
        return False
