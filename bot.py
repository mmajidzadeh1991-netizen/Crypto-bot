import time
import requests
from flask import Flask
import threading
import json
from datetime import datetime
from tradingview_ta import TA_Handler, Interval

# --- تنظیمات وب‌سرور ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Gemini-Powered ICT & SMC Trading Bot is running 24/7!"

def run_web():
    app.run(host="0.0.0.0", port=10000)

# --- تنظیمات ربات تلگرام و گوگل جمنای ---
TOKEN = "8905848713:AAGrGzm8vqX1_ZGh9C7mmIPO0dRM430x1bA"
CHAT_ID = "927615637"

# جدیدترین کلید API شما
GEMINI_API_KEY = "AQ.Ab8RN6Kzpb3DfA25-nulJAcs-FcY0R0pB7V-kj15r6UOTN1wOQ"

# نمادها برای تریدینگ‌ویو و کوین‌گکو
TOP_COINS_TV = [
    {"symbol": "BTCUSDT", "exchange": "BINANCE", "coingecko_id": "bitcoin"},
    {"symbol": "ETHUSDT", "exchange": "BINANCE", "coingecko_id": "ethereum"},
    {"symbol": "SOLUSDT", "exchange": "BINANCE", "coingecko_id": "solana"}
]

LAST_HEARTBEAT_TIME = time.time()
ACTIVE_TRADE = None
USER_STATES = {}

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

def get_coingecko_price(coin_id):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        if coin_id in data:
            return {
                "price": data[coin_id]["usd"],
                "change_24h": data[coin_id].get("usd_24h_change", 0.0)
            }
    except Exception as e:
        print(f"خطا در دریافت قیمت از کوین‌گکو برای {coin_id}: {e}")
    return None

def get_tradingview_analysis(symbol, exchange="BINANCE"):
    try:
        handler = TA_Handler(
            symbol=symbol,
            exchange=exchange,
            screener="crypto",
            interval=Interval.INTERVAL_1_HOUR
        )
        analysis = handler.get_analysis()
        return {
            "recommendation": analysis.summary.get("RECOMMENDATION", "NEUTRAL"),
            "buy": analysis.summary.get("BUY", 0),
            "sell": analysis.summary.get("SELL", 0),
            "indicators": analysis.indicators
        }
    except Exception as e:
        print(f"خطا در دریافت تحلیل تریدینگ‌ویو برای {symbol}: {e}")
        return None

def ask_ai_expert(user_prompt):
    """ارتباط مستقیم با جمنای به روش HTTP API با کلید جدید"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": GEMINI_API_KEY
    }
    
    system_instruction = (
        "تو یک تریدر ارشد، مشاور و تحلیلگر فوق‌العاده حرفه‌ای بازارهای مالی و ارزهای دیجیتال هستی. "
        "تخصص اصلی تو تسلط کامل و ترکیبی بر سبک‌های زیر است:\n"
        "1. ICT و SMC شامل تشخیص نقدینگی (Liquidity)، بلوک‌های سفارش (Order Blocks)، نواحی FVG (Fair Value Gap)، تغییر ساختار (CHoCH) و ادامه روند (BOS).\n"
        "2. Order Flow (اوردر فلو) و تابلوخوانی.\n"
        "3. پرایس اکشن ال بروکس (Al Brooks) شامل رفتار کندل به کندل، بارهای سیگنال، شکست‌ها و فیک‌بریک‌اوت‌ها (Fakeout).\n"
        "پاسخ‌های تو باید کاملاً تخصصی، دقیق، کاربردی، به زبان فارسی روان و با اصطلاحات درست باشد."
    )
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{system_instruction}\n\nسوال کاربر: {user_prompt}"}
                ]
            }
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        res_data = response.json()
        if "candidates" in res_data:
            return res_data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return f"❌ خطای پاسخ از سرور گوگل: {res_data}"
    except Exception as e:
        return f"❌ خطا در ارتباط با هوش مصنوعی جمنای: {e}"

def analyze_market_auto(coin_info):
    symbol = coin_info["symbol"]
    cg_id = coin_info["coingecko_id"]
    
    cg_data = get_coingecko_price(cg_id)
    tv_data = get_tradingview_analysis(symbol)
    
    if not cg_data or not tv_data:
        return None, None, None
        
    current_price = cg_data["price"]
    rec = tv_data["recommendation"]
    
    if "STRONG_BUY" in rec or "BUY" in rec:
        entry = current_price
        sl = entry * 0.985
        tp1 = entry * 1.025
        tp2 = entry * 1.050
        tp3 = entry * 1.080
        
        trade_data = {"symbol": symbol, "type": "LONG", "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2}
        
        msg = (
            f"🚀 **سیگنالِ پیشرفته (ترکیبی ICT & SMC)**\n"
            f"🟢 نماد: `{symbol}` | پوزیشن: **LONG**\n"
            f"💵 قیمت ورود: `{entry:,.2f}`\n"
            f"🛑 حد ضرر: `{sl:,.2f}`\n"
            f"🎯 تارگت‌ها: TP1: `{tp1:,.2f}` | TP2: `{tp2:,.2f}` | TP3: `{tp3:,.2f}`\n\n"
            f"💡 *تحلیل تکنیکال:* تاییدیه صعود از نواحی نقدینگی صادر شد."
        )
        return trade_data, msg, {"inline_keyboard": [[{"text": "❌ بستن پوزیشن", "callback_data": "CLOSE_TRADE"}]]}
        
    return None, None, None

def handle_callback_queries(last_update_id):
    global ACTIVE_TRADE, USER_STATES
    if last_update_id is None:
        last_update_id = 0
        
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last_update_id}&timeout=3"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if data.get("ok") and data.get("result"):
            for update in data["result"]:
                update_id = update.get("update_id")
                if update_id is not None:
                    last_update_id = update_id + 1
                
                if "callback_query" in update:
                    callback = update["callback_query"]
                    callback_id = callback.get("id")
                    data_action = callback.get("data")
                    message_obj = callback.get("message")
                    
                    if message_obj and "chat" in message_obj:
                        sender_chat_id = message_obj["chat"]["id"]
                        if callback_id:
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
                        elif data_action == "ASK_AI":
                            send_telegram_message("💬 لطفاً سوال تخصصی خود را در سبک‌های **ICT, SMC، اوردر فلو یا پرایس اکشن** بفرستید:", sender_chat_id)
                        elif data_action == "SCAN_NOW":
                            send_telegram_message("🔍 در حال اسکن بازار...", sender_chat_id)
                            for coin in TOP_COINS_TV:
                                td, msg, kb = analyze_market_auto(coin)
                                if td:
                                    ACTIVE_TRADE = td
                                    send_telegram_message(msg, sender_chat_id, kb)
                                    break
                            else:
                                send_telegram_message("⚪ اسکن انجام شد. سیگنال خاصی یافت نشد.", sender_chat_id)

                elif "message" in update and "text" in update["message"]:
                    msg_data = update["message"]
                    raw_text = msg_data["text"]
                    sender_chat_id = msg_data["chat"]["id"]
                    text_clean = raw_text.strip()
                    text_upper = text_clean.upper()
                    
                    if text_upper in ["/START", "/MENU", "START", "MENU"]:
                        USER_STATES.pop(sender_chat_id, None)
                        menu_keyboard = {
                            "inline_keyboard": [
                                [{"text": "📊 وضعیت پوزیشن", "callback_data": "STATUS"}, {"text": "🔍 اسکن بازار", "callback_data": "SCAN_NOW"}],
                                [{"text": "💬 سوال از هوش مصنوعی (ICT/SMC)", "callback_data": "ASK_AI"}],
                                [{"text": "❌ بستن پوزیشن", "callback_data": "CLOSE_TRADE"}]
                            ]
                        }
                        send_telegram_message("🤖 **منوی ربات تریدر هوشمند (Gemini + ICT & SMC):**\nانتخاب کنید:", sender_chat_id, menu_keyboard)
                    else:
                        ai_response = ask_ai_expert(text_clean)
                        send_telegram_message(ai_response, sender_chat_id)
                            
    except Exception as e:
        print(f"خطا در پردازش تلگرام: {e}")
        
    return last_update_id

def run_bot_loop():
    global ACTIVE_TRADE, LAST_HEARTBEAT_TIME
    print("ربات هوشمند جمنای روشن شد...")
    send_telegram_message("🤖 **ربات هوشمند مجهز به جمنای و تخصص ICT/SMC فعال شد.**")
    
    last_update_id = 0
    counter = 0
    
    while True:
        last_update_id = handle_callback_queries(last_update_id)
        current_time = time.time()
        
        if current_time - LAST_HEARTBEAT_TIME >= 14400:
            send_telegram_message("💓 **سلامت سیستم:** هوش مصنوعی فعال است.")
            LAST_HEARTBEAT_TIME = current_time
        
        counter += 1
        if counter >= 12 and not ACTIVE_TRADE:
            counter = 0
            for coin in TOP_COINS_TV:
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
