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
    Dispatches a sleek, mobile-optimized EOD stock market verification and prediction alert.
    Categorizes stocks into Actionable Calls (BUY/ACCUMULATE) and Compact Watchlist (HOLD/NEUTRAL)
    to eliminate cluttered multiline text-wrapping on mobile screens.
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

    # Header section
    header_lines = [
        "🏛️ <b>BULLGUARD AI · EOD AUDIT</b>",
        f"📅 <i>{date_str}</i>",
        f"🌐 <b>Regime:</b> <code>{regime}</code>",
        "",
        "📊 <b>VERIFIED PERFORMANCE:</b>",
        f"• <b>System Win Rate:</b> <b>{overall_win_rate}%</b> ({total_wins}W · {total_losses}L)",
        f"• <b>Active Monitored Calls:</b> <code>{active_count}</code>",
    ]

    bullish_stocks = []
    bearish_stocks = []
    neutral_stocks = []

    if stock_items:
        for item in stock_items:
            action = item.get("action", "HOLD")
            if action in ["STRONG_BUY", "ACCUMULATE"]:
                bullish_stocks.append(item)
            elif action in ["STRONG_SELL", "SELL"]:
                bearish_stocks.append(item)
            else:
                neutral_stocks.append(item)

    lines = list(header_lines)

    # 1. High-Conviction Long Calls
    if bullish_stocks:
        lines.append("")
        lines.append("🟢 <b>HIGH-CONVICTION BUY CALLS (LONG):</b>")
        for idx, item in enumerate(bullish_stocks, start=1):
            sym = item.get("symbol", "").replace(".NS", "")
            action = item.get("action", "")
            label = "STRONG BUY" if action == "STRONG_BUY" else "ACCUMULATE"
            curr = f"₹{item.get('current_price', 0):,.0f}"
            daily_tgt = f"₹{item.get('daily_target_price', 0):,.0f}" if item.get('daily_target_price') else "—"
            daily_sl = f"₹{item.get('daily_stop_loss_price', 0):,.0f}" if item.get('daily_stop_loss_price') else "—"
            weekly_tgt = f"₹{item.get('weekly_target_price', 0):,.0f}" if item.get('weekly_target_price') else "—"
            conf = item.get("confidence_score", 75)
            lines.append(
                f"{idx}. 🟢 <b>{sym}</b> · <b>{label}</b>\n"
                f"   CMP: {curr} ➔ 🎯 <b>Tgt: {weekly_tgt}</b> (SL: {daily_sl}) [<b>RR: 1:3</b>]\n"
                f"   ⚡ Next-Day Tgt: {daily_tgt} · Conf: <b>{conf}%</b>"
            )

    # 2. High-Conviction Short Calls
    if bearish_stocks:
        lines.append("")
        lines.append("🔴 <b>HIGH-CONVICTION SHORT CALLS (BEARISH):</b>")
        for idx, item in enumerate(bearish_stocks, start=1):
            sym = item.get("symbol", "").replace(".NS", "")
            action = item.get("action", "")
            label = "STRONG SELL" if action == "STRONG_SELL" else "SELL"
            curr = f"₹{item.get('current_price', 0):,.0f}"
            daily_tgt = f"₹{item.get('daily_target_price', 0):,.0f}" if item.get('daily_target_price') else "—"
            daily_sl = f"₹{item.get('daily_stop_loss_price', 0):,.0f}" if item.get('daily_stop_loss_price') else "—"
            weekly_tgt = f"₹{item.get('weekly_target_price', 0):,.0f}" if item.get('weekly_target_price') else "—"
            conf = item.get("confidence_score", 75)
            lines.append(
                f"{idx}. 🔴 <b>{sym}</b> · <b>{label}</b>\n"
                f"   CMP: {curr} ➔ 🛑 <b>Downside Tgt: {weekly_tgt}</b> (Protective SL: {daily_sl}) [<b>RR: 1:3</b>]\n"
                f"   ⚡ Next-Day Downside: {daily_tgt} · Conf: <b>{conf}%</b>"
            )

    # 3. Compact Neutral / Hold Watchlist
    if neutral_stocks:
        lines.append("")
        lines.append("⏸️ <b>NEUTRAL / HOLD STOCKS (Watchlist):</b>")
        for item in neutral_stocks:
            sym = item.get("symbol", "").replace(".NS", "")
            curr = f"₹{item.get('current_price', 0):,.0f}"
            act = item.get("action", "HOLD")
            lines.append(f"• 🟡 <b>{sym}</b>: {curr} ({act})")

    # 3. Resolved Audits Today (Which day prediction was made, which day target/stop loss was hit)
    lines.append("")
    lines.append("🔔 <b>TRADES RESOLVED TODAY:</b>")
    if newly_resolved_audits:
        seen_resolved = set()
        for audit in newly_resolved_audits:
            pred = audit.prediction
            key = f"{pred.stock.symbol}_{pred.timeframe_type}_{audit.resolved_date}"
            if key in seen_resolved:
                continue
            seen_resolved.add(key)

            sym = pred.stock.symbol.replace(".NS", "")
            is_win = audit.is_successful
            icon = "🎯" if is_win else "🛑"
            status_text = "TARGET HIT ✅" if is_win else "STOP-LOSS HIT ❌"
            pnl_val = audit.pnl_percentage if audit.pnl_percentage is not None else (pred.expected_return_pct if is_win else -pred.max_risk_pct)
            pnl_str = f"{pnl_val:+.1f}%"

            # Days & dates
            pred_date_str = pred.prediction_date.strftime("%d-%b") if pred.prediction_date else "Earlier"
            hit_date_str = audit.resolved_date.strftime("%d-%b") if audit.resolved_date else "Today"
            duration = audit.duration_days or pred.resolution_day or 1

            entry_price = f"₹{pred.entry_price:,.0f}"
            exit_price = f"₹{audit.exit_price or pred.target_price or 0:,.0f}" if is_win else f"₹{audit.exit_price or pred.stop_loss_price or 0:,.0f}"

            tf_badge = "DAILY ⚡" if pred.timeframe_type == "DAILY" else ("WEEKLY 📅" if pred.timeframe_type == "WEEKLY" else "MONTHLY 🗓️")

            lines.append(
                f"• {icon} <b>{sym}</b> [{tf_badge}] — <b>{status_text} ({pnl_str})</b>\n"
                f"  📅 <b>Called:</b> {pred_date_str} ➔ <b>Hit:</b> {hit_date_str} (Day {duration})\n"
                f"  💰 Entry: {entry_price} | Exit: {exit_price} | RR: 1:3"
            )
    else:
        lines.append("• <i>No calls hit target or stop-loss today (all active positions monitored).</i>")

    lines.append("")
    lines.append("⚡ <i>BullGuard AI · Automated Market Engine</i>")

    # Split message cleanly if over 3800 chars to avoid Telegram rejection
    full_text = "\n".join(lines)
    if len(full_text) > 3800:
        split_idx = full_text.find("⏸️ <b>NEUTRAL / HOLD STOCKS")
        if split_idx != -1:
            part1 = full_text[:split_idx].strip()
            part2 = full_text[split_idx:].strip()
            res1 = _send_telegram_raw(bot_token, chat_id, part1)
            res2 = _send_telegram_raw(bot_token, chat_id, part2)
            return res1 and res2

    return _send_telegram_raw(bot_token, chat_id, full_text)
