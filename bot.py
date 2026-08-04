import time
import requests
from flask import Flask
import threading
import json
from datetime import datetime

# --- تنظیمات وب‌سرور ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Advanced Multi-Directional Whale & Yahoo Finance Bot is running 24/7!"

def run_web():
    app.run(host="0.0.0.0", port=10000)

# --- تنظیمات ربات تلگرام ---
TOKEN = "8905848713:AAGrGzm8vqX1_ZGh9C7mmIPO0dRM430x1bA"
CHAT_ID = "927615637"

TOP_6_COINS = ["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD", "ADA-USD"]

LAST_SIGNAL_TIME = {}
LAST_HEARTBEAT_TIME = time.time()
ACTIVE_TRADE = None
USER_STATES = {} # برای ذخیره وضعیت حالت انتظار دریافت نام ارز از کاربر

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
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"خطا در ارسال پیام: {e}")

def get_yahoo_candles(symbol, interval="1h", range_period="5d"):
    # دریافت داده‌ها از یاهو فایننس (بدون نیاز به فیلترشکن و کاملاً رایگان)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range={range_period}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
            
        data = response.json()
        result = data.get('chart', {}).get('result')
        if not result:
            return None
            
        res = result[0]
        timestamps = res.get('timestamp', [])
        quote = res.get('indicators', {}).get('quote', [{}])[0]
        
        opens = quote.get('open', [])
        highs = quote.get('high', [])
        lows = quote.get('low', [])
        closes = quote.get('close', [])
        volumes = quote.get('volume', [])
        
        candles = []
        for i in range(len(timestamps)):
            if closes[i] is not None and opens[i] is not None:
                candles.append({
                    "open": float(opens[i]),
                    "high": float(highs[i]),
                    "low": float(lows[i]),
                    "close": float(closes[i]),
                    "volume": float(volumes[i]) if volumes[i] is not None else 0.0
                })
        return candles
    except Exception as e:
        print(f"خطا در دریافت اطلاعات یاهو برای {symbol}: {e}")
        return None

def analyze_any_coin(coin_input):
    # پاک‌سازی و تبدیل ورودی کاربر به فرمت یاهو فایننس
    clean = coin_input.upper().replace("USDT", "").replace("USD", "").replace("/", "").strip()
    if not clean:
        return "❌ لطفاً نام ارز را به درستی وارد کنید (مثلا: BTC یا ETH)"
        
    symbol = f"{clean}-USD"
    candles = get_yahoo_candles(symbol, interval="1h", range_period="7d")
    
    if not candles or len(candles) < 5:
        return f"❌ متأسفانه اطلاعاتی برای رمز ارز `{clean}` یافت نشد یا نماد اشتباه است."
        
    current_price = candles[-1]['close']
    prev_price = candles[-2]['close']
    price_change = ((current_price - prev_price) / prev_price) * 100
    
    high_5d = max([c['high'] for c in candles[-5:]])
    low_5d = min([c['low'] for c in candles[-5:]])
    
    # تحلیل تکنیکال ساده و جامع
    trend = "صعودی 📈" if current_price > candles[-3]['open'] else "نزولی 📉"
    
    analysis_text = (
        f"📊 **گزارش تحلیل جامع ارز: `{clean}`**\n\n"
        f"💵 **قیمت لحظه‌ای:** `${current_price:,.2f}`\n"
        f"📉 **تغییرات کندل آخر:** `{price_change:+.2f}%`\n"
        f"🔄 **روند کلی (کوتاه‌مدت):** `{trend}`\n"
        f"🔺 **بالاترین قیمت ۵ دوره اخیر:** `${high_5d:,.2f}`\n"
        f"🔻 **پایین‌ترین قیمت ۵ دوره اخیر:** `${low_5d:,.2f}`\n\n"
    )
    
    # پیشنهاد پوزیشن هوشمندانه (حتی اگر بازار خنثی باشد، نقاط کلیدی را اعلام می‌کند)
    if price_change > 0:
        entry = current_price
        sl = low_5d * 0.99
        tp = current_price + (current_price - sl) * 2
        analysis_text += (
            f"🟢 **ارزیابی موقعیت (پیشنهاد پوزیشن LONG):**\n"
            f"با توجه به روند مثبت اخیر:\n"
            f"📌 **نقطه ورود پیشنهادی:** `{entry:,.2f}`\n"
            f"🛑 **حد ضرر (Stop Loss):** `{sl:,.2f}`\n"
            f"🎯 **تارگت سود (Take Profit):** `{tp:,.2f}`\n"
        )
    else:
        entry = current_price
        sl = high_5d * 1.01
        tp = current_price - (sl - current_price) * 2
        analysis_text += (
            f"🔴 **ارزیابی موقعیت (پیشنهاد پوزیشن SHORT):**\n"
            f"با توجه به اصلاح قیمت:\n"
            f"📌 **نقطه ورود پیشنهادی:** `{entry:,.2f}`\n"
            f"🛑 **حد ضرر (Stop Loss):** `{sl:,.2f}`\n"
            f"🎯 **تارگت سود (Take Profit):** `{tp:,.2f}`\n"
        )
        
    return analysis_text

def analyze_market_auto(symbol):
    candles = get_yahoo_candles(symbol, interval="1h", range_period="5d")
    if not candles or len(candles) < 5:
        return None, None, None
        
    current_price = candles[-1]['close']
    last_c = candles[-1]
    prev_c = candles[-2]
    
    is_green = last_c['close'] > last_c['open']
    body = abs(last_c['close'] - last_c['open'])
    total = last_c['high'] - last_c['low']
    
    if total > 0 and (body / total) >= 0.40:
        if is_green:
            entry = current_price
            sl = min(last_c['low'], prev_c['low']) * 0.995
            risk = entry - sl
            if risk <= 0: return None, None, None
            tp1 = entry + (risk * 1.5)
            tp2 = entry + (risk * 2.5)
            
            trade_data = {"symbol": symbol, "type": "LONG", "entry": entry, "sl": sl, "tp1": tp1}
            msg = f"🚀 **سیگنالِ خودکار خرید (LONG)**\n🟢 نماد: `{symbol}`\n📌 ورود: `{entry:,.2f}`\n🛑 حد ضرر: `{sl:,.2f}`\n🎯 تارگت: `{tp1:,.2f}`"
            return trade_data, msg, {"inline_keyboard": [[{"text": "❌ بستن", "callback_data": "CLOSE_TRADE"}]]}
        else:
            entry = current_price
            sl = max(last_c['high'], prev_c['high']) * 1.005
            risk = sl - entry
            if risk <= 0: return None, None, None
            tp1 = entry - (risk * 1.5)
            
            trade_data = {"symbol": symbol, "type": "SHORT", "entry": entry, "sl": sl, "tp1": tp1}
            msg = f"📉 **سیگنالِ خودکار فروش (SHORT)**\n🔴 نماد: `{symbol}`\n📌 ورود: `{entry:,.2f}`\n🛑 حد ضرر: `{sl:,.2f}`\n🎯 تارگت: `{tp1:,.2f}`"
            return trade_data, msg, {"inline_keyboard": [[{"text": "❌ بستن", "callback_data": "CLOSE_TRADE"}]]}
            
    return None, None, None

def handle_callback_queries(last_update_id):
    global ACTIVE_TRADE, USER_STATES
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last_update_id}&timeout=3"
    try:
        response = requests.get(url, timeout=5)
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
                        USER_STATES.pop(sender_chat_id, None)
                        send_telegram_message("❌ پوزیشن فعال بسته شد.", sender_chat_id)
                    elif data_action == "STATUS":
                        if ACTIVE_TRADE:
                            send_telegram_message(f"📊 **پوزیشن فعال:**\nنوع: `{ACTIVE_TRADE['type']}`\nارز: `{ACTIVE_TRADE['symbol']}`\nورود: `{ACTIVE_TRADE['entry']}`", sender_chat_id)
                        else:
                            send_telegram_message("⚪ هیچ پوزیشن فعالی باز نیست.", sender_chat_id)
                    elif data_action == "ANALYZE_CUSTOM":
                        USER_STATES[sender_chat_id] = "WAITING_FOR_COIN"
                        send_telegram_message("🔍 لطفاً **نام یا نماد ارز موردنظر** خود را بفرستید (مثلاً: `BTC` یا `SOL` یا `Ethereum`):", sender_chat_id)
                    elif data_action == "SCAN_NOW":
                        send_telegram_message("🔍 در حال اسکن بازار...", sender_chat_id)
                        for coin in TOP_6_COINS:
                            td, msg, kb = analyze_market_auto(coin)
                            if td:
                                ACTIVE_TRADE = td
                                send_telegram_message(msg, sender_chat_id, kb)
                                break
                        else:
                            send_telegram_message("⚪ اسکن انجام شد. فعلاً موقعیت خودکار خاصی شناسایی نشد.", sender_chat_id)

                elif "message" in update and "text" in update["message"]:
                    raw_text = update["message"]["text"]
                    sender_chat_id = update["message"]["chat"]["id"]
                    text_clean = raw_text.strip()
                    text_upper = text_clean.upper()
                    
                    if text_upper in ["/START", "/MENU", "START", "MENU"]:
                        USER_STATES.pop(sender_chat_id, None)
                        menu_keyboard = {
                            "inline_keyboard": [
                                [{"text": "📊 وضعیت پوزیشن", "callback_data": "STATUS"}, {"text": "🔍 اسکن خودکار بازار", "callback_data": "SCAN_NOW"}],
                                [{"text": "📈 تحلیل دلخواه ارز (نام ارز)", "callback_data": "ANALYZE_CUSTOM"}],
                                [{"text": "❌ بستن پوزیشن", "callback_data": "CLOSE_TRADE"}]
                            ]
                        }
                        send_telegram_message("🤖 **منوی ربات تحلیلگر (بدون نیاز به فیلترشکن):**\nلطفاً یکی از گزینه‌ها را انتخاب کنید:", sender_chat_id, menu_keyboard)
                    
                    elif USER_STATES.get(sender_chat_id) == "WAITING_FOR_COIN":
                        USER_STATES.pop(sender_chat_id, None)
                        result_analysis = analyze_any_coin(text_clean)
                        send_telegram_message(result_analysis, sender_chat_id)
                    else:
                        # اگر کاربر مستقیم نام ارز را بدون زدن دکمه فرستاد، مستقیم تحلیلش کن
                        result_analysis = analyze_any_coin(text_clean)
                        send_telegram_message(result_analysis, sender_chat_id)
                            
    except Exception as e:
        print(f"خطا در پردازش تلگرام: {e}")
        
    return last_update_id

def run_bot_loop():
    global ACTIVE_TRADE, LAST_HEARTBEAT_TIME
    print("ربات تحلیلگر یاهو فایننس روشن شد...")
    send_telegram_message("🤖 **ربات هوشمند تحلیل و سیگنال‌دهی بازار فعال شد.** از موتور Yahoo Finance استفاده می‌کند و نیاز به فیلترشکن ندارد.")
    
    last_update_id = 0
    counter = 0
    
    while True:
        last_update_id = handle_callback_queries(last_update_id)
        current_time = time.time()
        
        if current_time - LAST_HEARTBEAT_TIME >= 14400:
            send_telegram_message("💓 **سلامت سیستم:** ربات فعال و متصل به موتور قدرتمند داده‌های جهانی است.")
            LAST_HEARTBEAT_TIME = current_time
        
        counter += 1
        if counter >= 10 and not ACTIVE_TRADE:
            counter = 0
            for coin in TOP_6_COINS:
                td, message_result, keyboard = analyze_market_auto(coin)
                if td:
                    ACTIVE_TRADE = td
                    send_telegram_message(message_result, reply_markup=keyboard)
                    break
                time.sleep(1)
                
        time.sleep(5)

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot_loop)
    bot_thread.daemon = True
    bot_thread.start()
    
    run_web()
