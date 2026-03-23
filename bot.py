import telebot
import time
import threading
import requests
import re
import os

# =============== CONFIG ===============
BOT_TOKEN = os.getenv("BOT_TOKEN")
INCOMING_CHANNEL_ID = int(os.getenv("INCOMING_CHANNEL_ID"))
OUTGOING_CHANNEL_ID = int(os.getenv("OUTGOING_CHANNEL_ID"))

COOLDOWN_TIME = 0  # 🔥 DISABLED

bot = telebot.TeleBot(BOT_TOKEN)

closed_signals = set()
last_signal_time = 0

# =============== PRICE FETCH ===============
def get_price(symbol):
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        data = requests.get(url, timeout=5).json()
        return float(data['price'])
    except:
        print("❌ PRICE FETCH ERROR")
        return None

# =============== PARSER ===============
def parse_signal(text):
    try:
        original_text = text
        text = text.upper()

        print("\n==============================")
        print("📩 NEW MESSAGE")
        print(original_text)
        print("==============================")

        # ========= SYMBOL =========
        symbol = None

        m = re.search(r"#?([A-Z]{2,15})\s*/\s*USDT", text)
        if m:
            symbol = m.group(1)

        if not symbol:
            m = re.search(r"\b([A-Z]{2,15})USDT\b", text)
            if m:
                symbol = m.group(1)

        if not symbol:
            m = re.search(r"PAIR[: ]+([A-Z]{2,15})/USDT", text)
            if m:
                symbol = m.group(1)

        if not symbol:
            print("❌ FAILED: SYMBOL")
            return None

        print(f"✅ SYMBOL: {symbol}")

        # ========= SIDE =========
        side = "LONG"
        if "SHORT" in text or "SELL" in text:
            side = "SHORT"

        print(f"✅ SIDE: {side}")

        # ========= ENTRY =========
        entry = None

        # RANGE ENTRY
        m = re.search(r"ENTRY[^\d]*(\d+\.\d+)\s*[-–]\s*(\d+\.\d+)", text)
        if m:
            entry = float(m.group(1))

        # NUMBERED ENTRY (FIXED 🔥)
        if not entry:
            nums = re.findall(r"\)\s*(\d+\.\d+)", text)
            if nums:
                entry = float(nums[0])

        # SINGLE ENTRY
        if not entry:
            m = re.search(r"ENTRY[^\d]*(\d+\.\d+)", text)
            if m:
                entry = float(m.group(1))

        if not entry:
            print("❌ FAILED: ENTRY")
            return None

        print(f"✅ ENTRY: {entry}")

        # ========= SL =========
        sl = None

        m = re.search(r"(SL|STOP LOSS|STOP)[^\d]*(\d+\.\d+)", text)
        if m:
            sl = float(m.group(2))

        if not sl:
            print("❌ FAILED: SL")
            return None

        print(f"✅ SL: {sl}")

        # ========= TARGETS =========
        tps = []

        # ONLY TAKE TARGET SECTION 🔥
        target_section = ""
        m = re.search(r"TARGETS?[:\s]*(.*)", text, re.DOTALL)
        if m:
            target_section = m.group(1)

        # numbered TP
        tps += re.findall(r"\)\s*(\d+\.\d+)", target_section)

        # fallback: decimals in target section only
        if len(tps) == 0:
            tps += re.findall(r"\d+\.\d+", target_section)

        # convert
        tps = list(dict.fromkeys([float(x) for x in tps]))

        # filter direction
        if side == "LONG":
            tps = [tp for tp in tps if tp > entry]
        else:
            tps = [tp for tp in tps if tp < entry]

        tps = tps[:6]

        if len(tps) == 0:
            print("❌ FAILED: TP (no valid targets after filtering)")
            return None

        print(f"✅ TPS: {tps}")

        return symbol, entry, sl, tps, side

    except Exception as e:
        print(f"❌ PARSE ERROR: {str(e)}")
        return None

# =============== VALIDATION ===============
def is_valid(symbol, entry, tps, sl, side):
    price = get_price(symbol + "USDT")

    if price is None:
        return False

    print(f"📊 LIVE PRICE: {price}")

    if side == "LONG" and price <= sl:
        print("❌ SL HIT ALREADY (LONG)")
        return False

    if side == "SHORT" and price >= sl:
        print("❌ SL HIT ALREADY (SHORT)")
        return False

    return True

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

# =============== TP MESSAGE ===============
def send_tp(symbol, hit, profit, msg_id):
    msg = f"""🚀 MASSIVE PROFITS 🚀  

#{symbol} Running 🔥  

{round(profit,2)}%+ Profit 📈  

💰 TP{hit} HIT ✅"""

    bot.send_message(OUTGOING_CHANNEL_ID, msg, reply_to_message_id=msg_id)

# =============== SL MESSAGE ===============
def send_sl(symbol, msg_id):
    msg = f"""⚠️ TRADE CLOSED ⚠️  

#{symbol}  

🛑 SL HIT"""

    bot.send_message(OUTGOING_CHANNEL_ID, msg, reply_to_message_id=msg_id)

# =============== TRACK ===============
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

# =============== CLOSE ===============
@bot.channel_post_handler(func=lambda m: m.text and "/close" in m.text.lower())
def close_signal(message):
    if message.chat.id != INCOMING_CHANNEL_ID:
        return

    if message.reply_to_message:
        closed_signals.add(message.reply_to_message.message_id)

# =============== MAIN ===============
@bot.channel_post_handler(func=lambda m: True)
def handle_signal(message):

    global last_signal_time

    if message.chat.id != INCOMING_CHANNEL_ID:
        return

    if message.message_id in closed_signals:
        return

    parsed = parse_signal(message.text)

    if not parsed:
        print("❌ FINAL RESULT: PARSE FAILED")
        return

    symbol, entry, sl, tps, side = parsed

    if not is_valid(symbol, entry, tps, sl, side):
        print("❌ FINAL RESULT: INVALID SIGNAL")
        return

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
