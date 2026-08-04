import time
import requests
from flask import Flask
import threading
import json

# --- تنظیمات وب‌سرور ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Advanced Multi-Directional Whale Bot is running 24/7!"

def run_web():
    app.run(host="0.0.0.0", port=10000)


# --- تنظیمات ربات تلگرام ---
TOKEN = "8905848713:AAGrGzm8vqX1_ZGh9C7mmIPO0dRM430x1bA"
CHAT_ID = "927615637"

TOP_6_COINS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT"]

LAST_SIGNAL_TIME = {}
LAST_HEARTBEAT_TIME = time.time()
ACTIVE_TRADE = None

def send_telegram_message(message, chat_id=CHAT_ID, reply_markup=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
        
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        print(f"خطا در ارسال پیام: {e}")

def get_binance_candles(symbol, interval="15m", limit=20):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        response = requests.get(url)
        data = response.json()
        candles = []
        for c in data:
            candles.append({
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": float(c[5])
            })
        return candles
    except Exception as e:
        print(f"خطا در دریافت کندل‌های {symbol}: {e}")
        return None

def check_whale_and_volume(candles):
    if not candles or len(candles) < 10:
        return False
    volumes = [c['volume'] for c in candles[:-1]]
    avg_volume = sum(volumes) / len(volumes)
    last_volume = candles[-1]['volume']
    return last_volume >= (avg_volume * 2.5)

def analyze_market_multi_timeframe(symbol):
    candles_4h = get_binance_candles(symbol, interval="4h", limit=5)
    if not candles_4h:
        return None, None, None
        
    trend_4h = "BULLISH" if candles_4h[-1]['close'] > candles_4h[-3]['open'] else "BEARISH"
        
    candles_15m = get_binance_candles(symbol, interval="15m", limit=15)
    if not candles_15m or len(candles_15m) < 10:
        return None, None, None
        
    current_price = candles_15m[-1]['close']
    c1 = candles_15m[-3]
    c3 = candles_15m[-1]
    
    candles_5m = get_binance_candles(symbol, interval="5m", limit=10)
    if not candles_5m or len(candles_5m) < 2:
        return None, None, None
        
    last_5m = candles_5m[-1]
    is_whale_activity = check_whale_and_volume(candles_5m)

    if trend_4h == "BULLISH":
        has_fvg = c3['low'] > c1['high']
        fvg_level = (c1['high'] + c3['low']) / 2 if has_fvg else 0
        
        if has_fvg or (current_price <= fvg_level * 1.015):
            is_green = last_5m['close'] > last_5m['open']
            body_size = abs(last_5m['close'] - last_5m['open'])
            total_size = last_5m['high'] - last_5m['low']
            
            if total_size > 0 and (body_size / total_size) >= 0.40 and is_green:
                entry_1 = current_price
                entry_2 = entry_1 * 0.994
                stop_loss = min(last_5m['low'], c1['low']) * 0.995
                risk = entry_1 - stop_loss
                
                if risk <= 0:
                    return None, None, None
                    
                tp1 = entry_1 + (risk * 1.5)
                tp2 = entry_1 + (risk * 2.5)
                tp3 = entry_1 + (risk * 4.0)
                
                trade_data = {
                    "symbol": symbol, "type": "LONG",
                    "entry_1": entry_1, "entry_2": entry_2,
                    "stop_loss": stop_loss, "tp1": tp1, "tp2": tp2, "tp3": tp3,
                    "tp1_hit": False, "tp2_hit": False, "tp3_hit": False
                }
                
                whale_badge = "🐋 **[ورود حجم سنگین نهنگ‌ها!]**\n" if is_whale_activity else ""
                signal_text = (
                    f"🚀 **سیگنالِ خرید (LONG)** 🚀\n\n{whale_badge}"
                    f"🟢 **رمز ارز:** `{symbol}`\n"
                    f"📈 روند 4H صعودی | تاییدیه در تایم 5م صادر شد!\n\n"
                    f"📌 **ورود اول:** `{entry_1:.4f}`\n"
                    f"📉 **ورود پله‌ای:** `{entry_2:.4f}`\n"
                    f"🛑 **حد ضرر:** `{stop_loss:.4f}`\n\n"
                    f"🎯 **تارگت 1:** `{tp1:.4f}`\n🎯 **تارگت 2:** `{tp2:.4f}`\n🎯 **تارگت 3:** `{tp3:.4f}`"
                )
                keyboard = {"inline_keyboard": [[{"text": "❌ بستن معامله", "callback_data": "CLOSE_TRADE"}, {"text": "📊 وضعیت", "callback_data": "STATUS"}]]}
                return trade_data, signal_text, keyboard

    elif trend_4h == "BEARISH":
        has_fvg_short = c3['high'] < c1['low']
        fvg_level_short = (c1['low'] + c3['high']) / 2 if has_fvg_short else 0
        
        if has_fvg_short or (current_price >= fvg_level_short * 0.985):
            is_red = last_5m['close'] < last_5m['open']
            body_size = abs(last_5m['close'] - last_5m['open'])
            total_size = last_5m['high'] - last_5m['low']
            
            if total_size > 0 and (body_size / total_size) >= 0.40 and is_red:
                entry_1 = current_price
                entry_2 = entry_1 * 1.006
                stop_loss = max(last_5m['high'], c1['high']) * 1.005
                risk = stop_loss - entry_1
                
                if risk <= 0:
                    return None, None, None
                    
                tp1 = entry_1 - (risk * 1.5)
                tp2 = entry_1 - (risk * 2.5)
                tp3 = entry_1 - (risk * 4.0)
                
                trade_data = {
                    "symbol": symbol, "type": "SHORT",
                    "entry_1": entry_1, "entry_2": entry_2,
                    "stop_loss": stop_loss, "tp1": tp1, "tp2": tp2, "tp3": tp3,
                    "tp1_hit": False, "tp2_hit": False, "tp3_hit": False
                }
                
                whale_badge = "🐋 **[فشار فروش سنگین نهنگ‌ها!]**\n" if is_whale_activity else ""
                signal_text = (
                    f"📉 **سیگنالِ فروش (SHORT)** 📉\n\n{whale_badge}"
                    f"🔴 **رمز ارز:** `{symbol}`\n"
                    f"📉 روند 4H نزولی | تاییدیه در تایم 5م صادر شد!\n\n"
                    f"📌 **ورود اول:** `{entry_1:.4f}`\n"
                    f"📈 **ورود پله‌ای:** `{entry_2:.4f}`\n"
                    f"🛑 **حد ضرر:** `{stop_loss:.4f}`\n\n"
                    f"🎯 **تارگت 1:** `{tp1:.4f}`\n🎯 **تارگت 2:** `{tp2:.4f}`\n🎯 **تارگت 3:** `{tp3:.4f}`"
                )
                keyboard = {"inline_keyboard": [[{"text": "❌ بستن معامله", "callback_data": "CLOSE_TRADE"}, {"text": "📊 وضعیت", "callback_data": "STATUS"}]]}
                return trade_data, signal_text, keyboard
                
    return None, None, None

def manage_active_trade():
    global ACTIVE_TRADE
    if not ACTIVE_TRADE:
        return
        
    symbol = ACTIVE_TRADE["symbol"]
    trade_type = ACTIVE_TRADE["type"]
    candles = get_binance_candles(symbol, interval="1m", limit=1)
    if not candles:
        return
        
    current_price = candles[-1]['close']
    sl = ACTIVE_TRADE["stop_loss"]
    tp1 = ACTIVE_TRADE["tp1"]
    tp2 = ACTIVE_TRADE["tp2"]
    tp3 = ACTIVE_TRADE["tp3"]
    
    if trade_type == "LONG":
        if current_price <= sl:
            send_telegram_message(f"🛑 **حد ضرر پوزیشن لانگ `{symbol}` لمس شد.** معامله بسته شد.")
            ACTIVE_TRADE = None
            return
        if not ACTIVE_TRADE.get("tp1_hit") and current_price >= tp1:
            ACTIVE_TRADE["tp1_hit"] = True
            send_telegram_message(f"🎯 **تارگت اول (TP1) لانگ `{symbol}` تاچ شد!** ✅ (ریسک‌فری شد)")
        if ACTIVE_TRADE.get("tp1_hit") and not ACTIVE_TRADE.get("tp2_hit") and current_price >= tp2:
            ACTIVE_TRADE["tp2_hit"] = True
            send_telegram_message(f"🎯🎯 **تارگت دوم (TP2) لانگ `{symbol}` فتح شد!** 🚀")
        if ACTIVE_TRADE.get("tp2_hit") and not ACTIVE_TRADE.get("tp3_hit") and current_price >= tp3:
            send_telegram_message(f"🏆🏆🏆 **تارگت نهایی (TP3) لانگ `{symbol}` تاچ شد!**")
            ACTIVE_TRADE = None
            
    elif trade_type == "SHORT":
        if current_price >= sl:
            send_telegram_message(f"🛑 **حد ضرر پوزیشن شورت `{symbol}` لمس شد.** معامله بسته شد.")
            ACTIVE_TRADE = None
            return
        if not ACTIVE_TRADE.get("tp1_hit") and current_price <= tp1:
            ACTIVE_TRADE["tp1_hit"] = True
            send_telegram_message(f"🎯 **تارگت اول (TP1) شورت `{symbol}` تاچ شد!** ✅ (ریسک‌فری شد)")
        if ACTIVE_TRADE.get("tp1_hit") and not ACTIVE_TRADE.get("tp2_hit") and current_price <= tp2:
            ACTIVE_TRADE["tp2_hit"] = True
            send_telegram_message(f"🎯🎯 **تارگت دوم (TP2) شورت `{symbol}` فتح شد!** 🚀")
        if ACTIVE_TRADE.get("tp2_hit") and not ACTIVE_TRADE.get("tp3_hit") and current_price <= tp3:
            send_telegram_message(f"🏆🏆🏆 **تارگت نهایی (TP3) شورت `{symbol}` تاچ شد!**")
            ACTIVE_TRADE = None

def handle_callback_queries(last_update_id):
    global ACTIVE_TRADE
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last_update_id}&timeout=3"
    try:
        response = requests.get(url)
        data = response.json()
        
        if data.get("ok") and data.get("result"):
            for update in data["result"]:
                last_update_id = update["update_id"] + 1
                
                if "callback_query" in update:
                    callback = update["callback_query"]
                    callback_id = callback["id"]
                    data_action = callback["data"]
                    sender_chat_id = callback["message"]["chat"]["id"]
                    
                    requests.post(f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery", json={"callback_query_id": callback_id})
                    
                    if data_action == "CLOSE_TRADE":
                        ACTIVE_TRADE = None
                        send_telegram_message("❌ پوزیشن فعال بسته شد.", sender_chat_id)
                    elif data_action == "STATUS":
                        if ACTIVE_TRADE:
                            send_telegram_message(f"📊 **پوزیشن فعال:**\nنوع: `{ACTIVE_TRADE['type']}`\nارز: `{ACTIVE_TRADE['symbol']}`\nورود: `{ACTIVE_TRADE['entry_1']}`", sender_chat_id)
                        else:
                            send_telegram_message("⚪ هیچ پوزیشن فعالی باز نیست.", sender_chat_id)
                    elif data_action == "SCAN_NOW":
                        send_telegram_message("🔍 در حال اسکن بازار دوطرفه...", sender_chat_id)
                        for coin in TOP_6_COINS:
                            td, msg, kb = analyze_market_multi_timeframe(coin)
                            if td:
                                ACTIVE_TRADE = td
                                send_telegram_message(msg, sender_chat_id, kb)
                                break
                        else:
                            send_telegram_message("⚪ اسکن انجام شد. فعلاً فرصت مناسبی یافت نشد.", sender_chat_id)

                elif "message" in update and "text" in update["message"]:
                    raw_text = update["message"]["text"]
                    sender_chat_id = update["message"]["chat"]["id"]
                    text_upper = raw_text.upper().strip()
                    
                    if text_upper in ["/START", "/MENU", "START", "MENU"]:
                        menu_keyboard = {
                            "inline_keyboard": [
                                [{"text": "📊 وضعیت پوزیشن فعال", "callback_data": "STATUS"}],
                                [{"text": "🔍 اسکن بازار (Long/Short)", "callback_data": "SCAN_NOW"}],
                                [{"text": "❌ بستن پوزیشن", "callback_data": "CLOSE_TRADE"}]
                            ]
                        }
                        send_telegram_message("🤖 **منوی کنترل ربات پیشرفته دوطرفه:**\nلطفاً یکی را انتخاب کنید:", sender_chat_id, menu_keyboard)
                    else:
                        clean_coin = text_upper.replace("(", "").replace(")", "").strip()
                        if clean_coin in ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA"]:
                            clean_coin += "USDT"
                            
                        trade_data, msg_res, kb = analyze_market_multi_timeframe(clean_coin)
                        if trade_data:
                            ACTIVE_TRADE = trade_data
                            send_telegram_message(msg_res, sender_chat_id, kb)
                        else:
                            send_telegram_message(f"⚪ ارز `{clean_coin}` بررسی شد. شرایط معامله در هیچ‌کدام از جهت‌ها برقرار نبود.", sender_chat_id)
                            
    except Exception as e:
        print(f"خطا در پردازش تلگرام: {e}")
        
    return last_update_id

def run_bot_loop():
    global ACTIVE_TRADE, LAST_HEARTBEAT_TIME
    print("ربات دوطرفه (Long & Short) + هوش نهنگ روشن شد...")
    send_telegram_message("🤖 **سیستم معاملاتی دوطرفه (Long/Short) فعال شد.** ربات بازار را از هر دو جهت رصد می‌کند.")
    
    last_update_id = 0
    counter = 0
    
    while True:
        last_update_id = handle_callback_queries(last_update_id)
        
        current_time = time.time()
        if current_time - LAST_HEARTBEAT_TIME >= 14400:
            send_telegram_message("💓 **گزارش سلامت سیستم:** ربات کاملاً بیدار است و به صورت ۲۴ ساعته بازار را رصد می‌کند.")
            LAST_HEARTBEAT_TIME = current_time
        
        if ACTIVE_TRADE:
            manage_active_trade()
        else:
            counter += 1
            if counter >= 5:
                counter = 0
                for coin in TOP_6_COINS:
                    trade_data, message_result, keyboard = analyze_market_multi_timeframe(coin)
                    
                    if trade_data:
                        if coin not in LAST_SIGNAL_TIME or (current_time - LAST_SIGNAL_TIME[coin]) > 7200:
                            ACTIVE_TRADE = trade_data
                            send_telegram_message(message_result, reply_markup=keyboard)
                            LAST_SIGNAL_TIME[coin] = current_time
                            break
                    time.sleep(1)
                    
        time.sleep(5)

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot_loop)
    bot_thread.daemon = True
    bot_thread.start()
    
    run_web()
