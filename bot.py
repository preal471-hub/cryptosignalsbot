import asyncio
import time
import random
import requests

# Fix event loop
try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from pyrogram import Client, filters

# 🔑 YOUR DETAILS
API_ID = 31373262
API_HASH = "d677d3aa5b28886108efb00df4d3e52a"
BOT_TOKEN = "8623891050:AAHRtb_j1FlaoYu9z5Ep-YztSwLPFpR-QSM"

# 🤖 ONLY REAL WORKING BOT TOKENS
bot_tokens = [
    "7953263361:AAFILuS9ns8B27Hj8u7VXUpo6bBkGbC5-Og",
    "8711937709:AAEYOyKt5pujHMHVqgjHzmxlQrCI5jOL3J8",
    "8650992486:AAE4ScGnkzilo3b_2AfZheF4O508PrVOjZ0",
    "8642919851:AAEbUdzYdVE9ICV5-4i623J1Lq_o5apmbcM",
]

# ✅ ONLY VALID TELEGRAM REACTIONS
valid_emojis = ["👍", "🔥", "❤️", "👏", "🎉", "💯"]

def send_reactions(chat_id, message_id):
    for token in bot_tokens:
        try:
            emoji = random.choice(valid_emojis)

            url = f"https://api.telegram.org/bot{token}/setMessageReaction"

            data = {
                "chat_id": chat_id,
                "message_id": message_id,
                "reaction": [{"type": "emoji", "emoji": emoji}]
            }

            res = requests.post(url, json=data)

            if res.status_code == 200:
                print(f"✅ {emoji} sent using {token[:12]}")
            else:
                print(f"❌ Failed {token[:12]} → {res.text}")

            time.sleep(1)

        except Exception as e:
            print(f"Error: {e}")


# 🤖 MAIN BOT
app = Client("main_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.channel)
def handle_post(client, message):
    print("📩 New post detected")
    send_reactions(message.chat.id, message.id)


print("🚀 Bot Running...")
app.run()