import telebot
import time
import threading
import requests
import re

# =============== CONFIG ===============
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
INCOMING_CHANNEL_ID = int(os.getenv("INCOMING_CHANNEL_ID"))
OUTGOING_CHANNEL_ID = int(os.getenv("OUTGOING_CHANNEL_ID"))

COOLDOWN_TIME = 1800  # 30 minutes

bot = telebot.TeleBot(BOT_TOKEN)

# =============== GLOBAL STORAGE ===============
closed_signals = set()
last_signal_time = 0

# =============== BINANCE PRICE ===============
def get_price(symbol):
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        data = requests.get(url, timeout=5).json()
        return float(data['price'])
    except:
        return None

# =============== UNIVERSAL PARSER ===============
def parse_signal(text):
    try:
        text = text.upper()

        # SYMBOL
        symbol = None
        m = re.search(r"#?([A-Z]{2,10})[/ ]?USDT", text)
        if m:
            symbol = m.group(1)

        if not symbol:
            m = re.search(r"\b(XAUUSD|BTCUSD|ETHUSD)\b", text)
            if m:
                symbol = m.group(1)

        if not symbol:
            return None

        # SIDE
        side = "LONG"
        if "SHORT" in text or "SELL" in text:
            side = "SHORT"

        # ENTRY
        entry = None

        m = re.search(r"(ENTRY|ENTRY ZONE|ENTRY TARGET)[^\d]*(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)", text)
        if m:
            entry = float(m.group(2))

        if not entry:
            m = re.search(r"(ENTRY|BUY ABOVE|SHORT BELOW)[^\d]*(\d+\.?\d*)", text)
            if m:
                entry = float(m.group(2))

        if not entry:
            nums = re.findall(r"\)\s*(\d+\.?\d*)", text)
            if nums:
                entry = float(nums[0])

        if not entry:
            return None

        # SL
        sl = None
        m = re.search(r"(SL|STOP ?LOSS)[^\d]*(\d+\.?\d*)", text)
        if m:
            sl = float(m.group(2))

        if not sl:
            return None

        # TARGETS
        tps = []

        tps += re.findall(r"TP\d[: ]*(\d+\.?\d*)", text)
        tps += re.findall(r"\d+\)\s*(\d+\.?\d*)", text)
        tps += re.findall(r"(\d+\.?\d*)\s*-\s*(\d+\.?\d*)", text)

        if len(tps) < 2:
            nums = re.findall(r"\d+\.\d+", text)
            for num in nums:
                if abs(float(num) - entry) < 1e-6:
                    continue
                if abs(float(num) - sl) < 1e-6:
                    continue
                tps.append(num)

        flat = []
        for tp in tps:
            if isinstance(tp, tuple):
                flat.extend(tp)
            else:
                flat.append(tp)

        tps = list(dict.fromkeys([float(x) for x in flat]))
        tps = [tp for tp in tps if tp != entry and tp != sl][:6]

        if len(tps) == 0:
            return None

        return symbol, entry, sl, tps, side

    except:
        return None

# =============== VALIDATION ===============
def is_valid(symbol, entry, tps, sl, side):
    price = get_price(symbol + "USDT")
    if price is None:
        return False

    # 🔥 RELAXED VALIDATION
    # only reject if SL already hit badly

    if side == "LONG":
        if price <= sl:
            return False
    else:
        if price >= sl:
            return False

    return True

# =============== FORMAT SIGNAL ===============
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

# =============== TP MESSAGE ===============
def send_tp(symbol, hit, profit, msg_id):
    msg = f"""🚀 MASSIVE PROFITS 🚀  

#{symbol} Moving As Expected 🔥  

{round(profit,2)}%+ Profit Running 📈  

💰 TP{hit} HIT ✅  

Stay Tuned For More Targets 💎"""

    bot.send_message(OUTGOING_CHANNEL_ID, msg, reply_to_message_id=msg_id)

# =============== SL MESSAGE ===============
def send_sl(symbol, msg_id):
    msg = f"""⚠️ TRADE UPDATE ⚠️  

#{symbol}  

🛑 SL HIT  

Stay Focused — Next Signal Soon 🔥"""

    bot.send_message(OUTGOING_CHANNEL_ID, msg, reply_to_message_id=msg_id)

# =============== TRACK TRADE ===============
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

        if side == "SHORT":
            profit = ((entry - price) / entry) * 100 * leverage

            if price >= sl and hit == 0:
                send_sl(symbol, out_msg_id)
                break

            for i, tp in enumerate(tps):
                if price <= tp and i >= hit:
                    hit = i + 1
                    send_tp(symbol, hit, profit, out_msg_id)

        else:
            profit = ((price - entry) / entry) * 100 * leverage

            if price <= sl and hit == 0:
                send_sl(symbol, out_msg_id)
                break

            for i, tp in enumerate(tps):
                if price >= tp and i >= hit:
                    hit = i + 1
                    send_tp(symbol, hit, profit, out_msg_id)

        time.sleep(5)

# =============== CLOSE COMMAND ===============
@bot.channel_post_handler(func=lambda m: m.text and "/close" in m.text.lower())
def close_signal(message):

    if message.chat.id != INCOMING_CHANNEL_ID:
        return

    if message.reply_to_message:
        closed_signals.add(message.reply_to_message.message_id)

# =============== MAIN HANDLER ===============
@bot.channel_post_handler(func=lambda m: True)
def handle_signal(message):

    global last_signal_time

    if message.chat.id != INCOMING_CHANNEL_ID:
        return

    # 🚫 COOLDOWN CHECK
    current_time = time.time()
    if current_time - last_signal_time < COOLDOWN_TIME:
        print("⏳ Cooldown active - skipped")
        return

    if message.message_id in closed_signals:
        return

    parsed = parse_signal(message.text)
    if not parsed:
        print("❌ Parse failed")
        return

    symbol, entry, sl, tps, side = parsed

    if not is_valid(symbol, entry, tps, sl, side):
        print("❌ Invalid signal")
        return

    sent = bot.send_message(
        OUTGOING_CHANNEL_ID,
        format_signal(symbol, entry, sl, tps, side)
    )

    last_signal_time = time.time()

    threading.Thread(
        target=track_trade,
        args=(symbol, entry, tps, sl, side, sent.message_id, message.message_id)
    ).start()

# =============== START BOT ===============
bot.polling()
