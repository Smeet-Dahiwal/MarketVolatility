import os
from twilio.rest import Client
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_ID")

def send_telegram_alert(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": GROUP_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"   # allows bold, italics, links
    }
    r = requests.post(url, data=payload)
    if r.status_code != 200:
        print("❌ Telegram alert failed:", r.text)
    else:
        print("✅ Telegram alert sent")


def send_whatsapp_alert(message: str):
    try:
        account_sid = os.getenv("TWILIO_SID")
        auth_token = os.getenv("TWILIO_TOKEN")
        from_whatsapp = os.getenv("TWILIO_WHATSAPP_FROM")
        to_whatsapp = os.getenv("TO_WHATSAPP_NUMBER")

        if not all([account_sid, auth_token, from_whatsapp, to_whatsapp]):
            print("⚠️ Twilio environment variables not set")
            return

        client = Client(account_sid, auth_token)

        msg = client.messages.create(
            body=message,
            from_=from_whatsapp,
            to=to_whatsapp
        )

        print(f"✅ WhatsApp alert sent | SID: {msg.sid}")

    except Exception as e:
        print("❌ WhatsApp alert failed:", e)
