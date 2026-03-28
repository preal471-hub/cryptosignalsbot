import telebot
import time
import threading
import requests
import re
import os
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

# =============== CONFIG ===============
BOT_TOKEN = os.getenv("BOT_TOKEN")
INCOMING_CHANNEL_ID = int(os.getenv("INCOMING_CHANNEL_ID"))
OUTGOING_CHANNEL_ID = int(os.getenv("OUTGOING_CHANNEL_ID"))

bot = telebot.TeleBot(BOT_TOKEN)

closed_signals = set()
last_signal_time = 0

# =============== IMAGE GENERATOR ===============
def generate_image(symbol, entry, last, side, leverage, pnl):

    img = Image.open("template.png").convert("RGB")
    draw = ImageDraw.Draw(img)

    now = datetime.now().strftime("%b %d, %Y | %I:%M %p")
    username = "BluepeakCryptoTrading"

    font_username = ImageFont.truetype("Montserrat-Bold.ttf", 40)
    font_date = ImageFont.truetype("Montserrat-Regular.ttf", 24)
    font_symbol = ImageFont.truetype("Montserrat-Bold.ttf", 42)
    font_side = ImageFont.truetype("Montserrat-Bold.ttf", 32)
    font_return = ImageFont.truetype("Montserrat-Bold.ttf", 57)
    font_price = ImageFont.truetype("Montserrat-Bold.ttf", 42)

    white = (255,255,255)
    gray = (150,150,170)
    green = (0,255,170)
    red = (255,70,70)

    pnl_color = green if pnl >= 0 else red

    draw.text((221,130), username, fill=white, font=font_username)
    draw.text((262,182), now, fill=gray, font=font_date)
    draw.text((187,325), f"{symbol}/USDT", fill=white, font=font_symbol)

    draw.text((607,322), f"{leverage}x", fill=white, font=font_side)
    draw.text((718,324), side, fill=red if side=="SHORT" else green, font=font_side)

    txt = f"RETURNS {'+' if pnl>=0 else ''}{pnl:.2f}%"

    for i in range(3):
        draw.text((91-i,424-i), txt, fill=pnl_color, font=font_return)

    draw.text((91,424), txt, fill=pnl_color, font=font_return)

    draw.text((122,571), f"{entry}", fill=white, font=font_price)
    draw.text((497,567), f"{last}", fill=white, font=font_price)

    img.save("final.png")
    return "final.png"

# =============== PRICE FETCH ===============
def get_price(symbol):
    try:
        url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
        data = requests.get(url, timeout=5).json()
        if 'price' in data:
            return float(data['price'])

        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        data = requests.get(url, timeout=5).json()
        if 'price' in data:
            return float(data['price'])

        return None
    except:
        return None

# =============== PARSER (UNCHANGED) ===============
def parse_signal(text):
    try:
        text = text.upper()

        m = re.search(r"#?([A-Z]{2,15})\s*/\s*USDT", text)
        if not m:
            m = re.search(r"\b([A-Z]{2,15})USDT\b", text)
        if not m:
            return None

        symbol = m.group(1)

        side = "SHORT" if "SHORT" in text or "SELL" in text else "LONG"

        nums = re.findall(r"\d+\.\d+", text)
        if len(nums) < 3:
            return None

        entry = float(nums[0])
        sl = float(nums[1])
        tps = [float(x) for x in nums[2:8]]

        if side == "LONG":
            tps = [tp for tp in tps if tp > entry]
        else:
            tps = [tp for tp in tps if tp < entry]

        return symbol, entry, sl, tps, side

    except:
        return None

# =============== FORMAT ===============
def format_signal(symbol, entry, sl, targets, side):
    nums = ['①','②','③','④','⑤','⑥']

    text = f"""🚀 BLUEPEAK FREE TRADE

🌐 ASSET: #{symbol}/USDT  
📊 DIRECTION: {side}  

📍 ENTRY: {entry}  
🛑 SL: {sl}  

🎯 PROFIT TARGETS:
"""
    for i, tp in enumerate(targets):
        text += f"{nums[i]} {tp}\n"

    text += "\n⚡ LEVERAGE: 20X\n🔥 High Probability Setup"
    return text

# =============== NEW TP FUNCTION (IMAGE + TEXT) ===============
def send_tp(symbol, entry, price, side, hit, profit, msg_id):

    leverage = 20

    img = generate_image(symbol, entry, price, side, leverage, profit)

    sent_img = bot.send_photo(
        OUTGOING_CHANNEL_ID,
        open(img, 'rb')
    )

    msg = f"""🚀 MASSIVE PROFITS 🚀  
    ...
    """

    bot.send_message(
        OUTGOING_CHANNEL_ID,
        msg,
        reply_to_message_id=sent_img.message_id   # ❌ THIS LINE CAUSING ISSUE
    )
# =============== SL MESSAGE ===============
def send_sl(symbol, msg_id):
    bot.send_message(
        OUTGOING_CHANNEL_ID,
        f"⚠️ TRADE CLOSED\n#{symbol}\n🛑 SL HIT",
        reply_to_message_id=msg_id
    )

# =============== TRACK (UPDATED ONLY TP CALL) ===============
def track_trade(symbol, entry, tps, sl, side, out_msg_id, incoming_msg_id):

    hit = 0
    leverage = 20

    while True:

        if incoming_msg_id in closed_signals:
            break

        price = get_price(symbol + "USDT")
        if price is None:
            time.sleep(5)
            continue

        # ================= SHORT =================
        if side == "SHORT":

            # SL HIT
            if price >= sl and hit == 0:
                send_sl(symbol, out_msg_id)
                break

            for i, tp in enumerate(tps):

                # ❗ avoid duplicate TP
                if i < hit:
                    continue

                if price <= tp:

                    tp_price = tp  # ✅ FIX: use exact TP price

                    profit = ((entry - tp_price) / entry) * 100 * leverage
                    hit = i + 1

                    send_tp(symbol, entry, tp_price, side, hit, profit, out_msg_id)

        # ================= LONG =================
        else:

            # SL HIT
            if price <= sl and hit == 0:
                send_sl(symbol, out_msg_id)
                break

            for i, tp in enumerate(tps):

                # ❗ avoid duplicate TP
                if i < hit:
                    continue

                if price >= tp:

                    tp_price = tp  # ✅ FIX: use exact TP price

                    profit = ((tp_price - entry) / entry) * 100 * leverage
                    hit = i + 1

                    send_tp(symbol, entry, tp_price, side, hit, profit, out_msg_id)

        time.sleep(5)
# =============== MAIN ===============
@bot.channel_post_handler(content_types=['text', 'photo'])
def handle_signal(message):

    if message.chat.id != INCOMING_CHANNEL_ID:
        return

    text = message.text if message.text else message.caption
    if not text:
        return

    parsed = parse_signal(text)
    if not parsed:
        return

    symbol, entry, sl, tps, side = parsed

    sent = bot.send_message(
        OUTGOING_CHANNEL_ID,
        format_signal(symbol, entry, sl, tps, side)
    )

    threading.Thread(
        target=track_trade,
        args=(symbol, entry, tps, sl, side, sent.message_id, message.message_id)
    ).start()

# =============== START ===============
bot.polling()
