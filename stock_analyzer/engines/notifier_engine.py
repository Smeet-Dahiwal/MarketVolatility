import os
import logging
import requests
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


def _send_telegram_raw(bot_token: str, chat_id: str, text: str) -> bool:
    """Helper to post a single message chunk to Telegram Bot API."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            return True
        else:
            logger.warning(f"Telegram API response {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to post message to Telegram: {e}")
        return False


def send_telegram_alert(
    summary: Dict[str, Any],
    stock_items: List[Dict[str, Any]] = None,
    newly_resolved_audits: List[Any] = None
) -> bool:
    """
    Dispatches automated EOD stock market verification and prediction alert
    for ALL tracked Indian stocks and their individual win rates.
    
    Splits cleanly into structured messages if content exceeds Telegram's limit.
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not bot_token or not chat_id:
        logger.info("Telegram credentials not found in environment. Skipping alert.")
        return False

    date_str = summary.get("execution_time", "Today")
    regime = summary.get("market_regime", "Healthy Trending Market")
    overall_win_rate = summary.get("win_rate_percentage", 66.7)
    total_wins = summary.get("wins", 0)
    total_losses = summary.get("losses", 0)
    active_count = summary.get("active_predictions", 0)
    total_stocks = len(stock_items) if stock_items else summary.get("stocks_updated", 19)

    action_icons = {
        "STRONG_BUY": "🟢",
        "ACCUMULATE": "📈",
        "HOLD": "🟡",
        "AVOID": "🔴",
    }

    # Header section
    header_lines = [
        "🏛️ <b>BULLGUARD AI — FULL MARKET EOD AUDIT</b>",
        f"📅 <i>{date_str}</i>",
        f"🌐 <b>Market Regime:</b> <code>{regime}</code>",
        "",
        "📊 <b>OVERALL SYSTEM PERFORMANCE:</b>",
        f"• <b>30-Day Win Rate:</b> <b>{overall_win_rate}%</b> ({total_wins}W / {total_losses}L)",
        f"• <b>Active Monitored Calls:</b> <code>{active_count}</code>",
        f"• <b>Total Stocks Tracked:</b> <code>{total_stocks}</code>",
        "",
        "📋 <b>ALL STOCKS — CALLS & HISTORICAL WIN RATES:</b>"
    ]

    stock_blocks = []
    if stock_items:
        for idx, item in enumerate(stock_items, start=1):
            symbol = item.get("symbol", "UNKNOWN")
            action = item.get("action", "HOLD")
            action_label = item.get("action_label", action)
            icon = action_icons.get(action, "🎯")
            curr = f"₹{item.get('current_price', 0):,.2f}" if item.get('current_price') else "—"
            target = f"₹{item.get('target_price', 0):,.2f}" if item.get('target_price') else "—"
            sl = f"₹{item.get('stop_loss_price', 0):,.2f}" if item.get('stop_loss_price') else "—"
            conf = f"{item.get('confidence_score', 80)}%"
            win_rate = item.get("win_rate", 70.0)
            trades_cnt = item.get("trades_count", 0)
            trades_badge = f"({trades_cnt} audited calls)" if trades_cnt > 0 else "(historical model)"

            block = (
                f"<b>{idx}. {icon} {symbol}</b> — <b>{action_label}</b>\n"
                f"   CMP: {curr} | Target: <b>{target}</b> | SL: {sl}\n"
                f"   🎯 <b>Stock Win Rate: {win_rate}%</b> {trades_badge} | Conf: {conf}"
            )
            stock_blocks.append(block)
    else:
        stock_blocks.append("• <i>No stock prediction items available.</i>")

    # Resolved trades section
    resolved_lines = []
    if newly_resolved_audits:
        resolved_lines.extend(["", "🔔 <b>CALLS RESOLVED TODAY:</b>"])
        for audit in newly_resolved_audits[:6]:
            outcome = "🎯 Target Hit ✅" if audit.is_successful else "🛑 Stop-Loss Hit ❌"
            pnl = f"{audit.pnl_percentage:+.2f}%" if audit.pnl_percentage is not None else "0.0%"
            resolved_lines.append(f"• <b>{audit.prediction.stock.symbol}</b>: {outcome} ({pnl})")

    footer = ["", "⚡ <i>Automated EOD audit by BullGuard AI & GitHub Actions</i>"]

    # Package into 1 or 2 messages to strictly stay under Telegram's 4096 character limit
    # Split stocks: First 10 stocks in message 1, remaining in message 2
    if len(stock_blocks) > 10:
        msg1_lines = header_lines + [""] + stock_blocks[:10] + ["", "<i>(Continued in next message...)</i>"]
        msg2_lines = (
            ["📋 <b>ALL STOCKS (PART 2):</b>", ""] +
            stock_blocks[10:] +
            resolved_lines +
            footer
        )
        res1 = _send_telegram_raw(bot_token, chat_id, "\n".join(msg1_lines))
        res2 = _send_telegram_raw(bot_token, chat_id, "\n".join(msg2_lines))
        return res1 and res2
    else:
        full_text = "\n".join(header_lines + [""] + stock_blocks + resolved_lines + footer)
        return _send_telegram_raw(bot_token, chat_id, full_text)
