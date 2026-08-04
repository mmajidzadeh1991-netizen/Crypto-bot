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
    return "Advanced TradingView & CoinGecko Bot is running 24/7!"

def run_web():
    app.run(host="0.0.0.0", port=10000)

# --- تنظیمات ربات تلگرام ---
TOKEN = "8905848713:AAGrGzm8vqX1_ZGh9C7mmIPO0dRM430x1bA"
CHAT_ID = "927615637"

# نمادها برای تریدینگ‌ویو (بازار کریپتو در صرافی بایننس یا صرافی‌های عمومی)
TOP_COINS_TV = [
    {"symbol": "BTCUSDT", "exchange": "BINANCE", "coingecko_id": "bitcoin"},
    {"symbol": "ETHUSDT", "exchange": "BINANCE", "coingecko_id": "ethereum"},
    {"symbol": "BNBUSDT", "exchange": "BINANCE", "coingecko_id": "binancecoin"},
    {"symbol": "SOLUSDT", "exchange": "BINANCE", "coingecko_id": "solana"},
    {"symbol": "XRPUSDT", "exchange": "BINANCE", "coingecko_id": "ripple"},
    {"symbol": "ADAUSDT", "exchange": "BINANCE", "coingecko_id": "cardano"}
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
    """دریافت قیمت لحظه‌ای و اطلاعات از کوین‌گکو"""
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
        print(f"خطا در دریافت قیمت از کوین‌گکو برای {coin_id}: ${e}")
    return None

def get_tradingview_analysis(symbol, exchange="BINANCE"):
    """دریافت تحلیل تکنیکال و پیشنهاد خرید/فروش از تریدینگ‌ویو"""
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
            "neutral": analysis.summary.get("NEUTRAL", 0),
            "indicators": analysis.indicators
        }
    except Exception as e:
        print(f"خطا در دریافت تحلیل تریدینگ‌ویو برای {symbol}: {e}")
        return None

def analyze_any_coin(coin_input):
    clean = coin_input.upper().replace("USDT", "").replace("USD", "").replace("/", "").strip()
    if not clean:
        return "❌ لطفاً نام ارز را به درستی وارد کنید (مثلا: BTC یا ETH)"
        
    symbol_tv = f"{clean}USDT"
    
    # پیدا کردن شناسه کوین‌گکو به صورت پویا یا تطبیق ساده
    coingecko_id = clean.lower()
    if coingecko_id == "btc": coingecko_id = "bitcoin"
    elif coingecko_id == "eth": coingecko_id = "ethereum"
    elif coingecko_id == "sol": coingecko_id = "solana"
    elif coingecko_id == "bnb": coingecko_id = "binancecoin"
    elif coingecko_id == "xrp": coingecko_id = "ripple"
    
    cg_data = get_coingecko_price(coingecko_id)
    tv_data = get_tradingview_analysis(symbol_tv)
    
    if not cg_data or not tv_data:
        return f"❌ اطلاعات کافی برای رمز ارز `{clean}` از تریدینگ‌ویو یا کوین‌گکو یافت نشد."
        
    current_price = cg_data["price"]
    change_24h = cg_data["change_24h"]
    rec = tv_data["recommendation"]
    
    # ترجمه وضعیت تریدینگ‌ویو به فارسی
    rec_fa = "خرید قوی 🟢" if "STRONG_BUY" in rec else ("فروش قوی 🔴" if "STRONG_SELL" in rec else ("خرید 🟢" if "BUY" in rec else ("فروش 🔴" if "SELL" in rec else "خنثی ⚪")))
    
    analysis_text = (
        f"📊 **گزارش تحلیل پیشرفته (TradingView & CoinGecko): `{clean}`**\n\n"
        f"💵 **قیمت لحظه‌ای:** `${current_price:,.2f}`\n"
        f"📉 **تغییرات ۲۴ ساعته:** `{change_24h:+.2f}%`\n"
        f"🎯 **سیگنال نهایی تریدینگ‌ویو:** `{rec_fa}`\n"
        f"📈 پیشنهادهای خرید اندیکاتورها: `{tv_data['buy']}` | فروش: `{tv_data['sell']}`\n\n"
    )
    
    if "BUY" in rec:
        entry = current_price
        sl = current_price * 0.98
        tp = current_price * 1.04
        analysis_text += (
            f"🟢 **پیشنهاد پوزیشن LONG (بر اساس تریدینگ‌ویو):**\n"
            f"📌 **ورود:** `{entry:,.2f}`\n"
            f"🛑 **حد ضرر:** `{sl:,.2f}`\n"
            f"🎯 **تارگت:** `{tp:,.2f}`\n"
        )
    elif "SELL" in rec:
        entry = current_price
        sl = current_price * 1.02
        tp = current_price * 0.96
        analysis_text += (
            f"🔴 **پیشنهاد پوزیشن SHORT (بر اساس تریدینگ‌ویو):**\n"
            f"📌 **ورود:** `{entry:,.2f}`\n"
            f"🛑 **حد ضرر:** `{sl:,.2f}`\n"
            f"🎯 **تارگت:** `{tp:,.2f}`\n"
        )
    else:
        analysis_text += "⚪ بازار در وضعیت تعادل و خنثی است؛ پیشنهاد می‌شود منتظر تاییدیه بمانید.\n"
        
    return analysis_text

def analyze_market_auto(coin_info):
    symbol = coin_info["symbol"]
    cg_id = coin_info["coingecko_id"]
    
    cg_data = get_coingecko_price(cg_id)
    tv_data = get_tradingview_analysis(symbol)
    
    if not cg_data or not tv_data:
        return None, None, None
        
    current_price = cg_data["price"]
    rec = tv_data["recommendation"]
    
    if "STRONG_BUY" in rec:
        entry = current_price
        sl = entry * 0.985
        tp1 = entry * 1.03
        trade_data = {"symbol": symbol, "type": "LONG", "entry": entry, "sl": sl, "tp1": tp1}
        msg = f"🚀 **سیگنالِ خودکار خرید قوی (LONG)**\n🟢 نماد: `{symbol}`\n📌 ورود: `{entry:,.2f}`\n🛑 حد ضرر: `{sl:,.2f}`\n🎯 تارگت: `{tp1:,.2f}`"
        return trade_data, msg, {"inline_keyboard": [[{"text": "❌ بستن", "callback_data": "CLOSE_TRADE"}]]}
        
    elif "STRONG_SELL" in rec:
        entry = current_price
        sl = entry * 1.015
        tp1 = entry * 0.97
        trade_data = {"symbol": symbol, "type": "SHORT", "entry": entry, "sl": sl, "tp1": tp1}
        msg = f"📉 **سیگنالِ خودکار فروش قوی (SHORT)**\n🔴 نماد: `{symbol}`\n📌 ورود: `{entry:,.2f}`\n🛑 حد ضرر: `{sl:,.2f}`\n🎯 تارگت: `{tp1:,.2f}`"
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
                        send_telegram_message("🔍 لطفاً **نام یا نماد ارز موردنظر** خود را بفرستید (مثلاً: `BTC` یا `SOL`):", sender_chat_id)
                    elif data_action == "SCAN_NOW":
                        send_telegram_message("🔍 در حال اسکن بازار با تریدینگ‌ویو و کوین‌گکو...", sender_chat_id)
                        for coin in TOP_COINS_TV:
                            td, msg, kb = analyze_market_auto(coin)
                            if td:
                                ACTIVE_TRADE = td
                                send_telegram_message(msg, sender_chat_id, kb)
                                break
                        else:
                            send_telegram_message("⚪ اسکن انجام شد. در حال حاضر سیگنال قوی (Strong Buy/Sell) در بازار پیدا نشد.", sender_chat_id)

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
                                [{"text": "📈 تحلیل دلخواه ارز", "callback_data": "ANALYZE_CUSTOM"}],
                                [{"text": "❌ بستن پوزیشن", "callback_data": "CLOSE_TRADE"}]
                            ]
                        }
                        send_telegram_message("🤖 **منوی ربات (موتور TradingView و CoinGecko):**\nلطفاً یکی از گزینه‌ها را انتخاب کنید:", sender_chat_id, menu_keyboard)
                    
                    elif USER_STATES.get(sender_chat_id) == "WAITING_FOR_COIN":
                        USER_STATES.pop(sender_chat_id, None)
                        result_analysis = analyze_any_coin(text_clean)
                        send_telegram_message(result_analysis, sender_chat_id)
                    else:
                        result_analysis = analyze_any_coin(text_clean)
                        send_telegram_message(result_analysis, sender_chat_id)
                            
    except Exception as e:
        print(f"خطا در پردازش تلگرام: {e}")
        
    return last_update_id

def run_bot_loop():
    global ACTIVE_TRADE, LAST_HEARTBEAT_TIME
    print("ربات با موتور TradingView و CoinGecko روشن شد...")
    send_telegram_message("🤖 **ربات هوشمند تحلیل و سیگنال‌دهی فعال شد.** از موتور تحلیلی تریدینگ‌ویو و داده‌های کوین‌گکو استفاده می‌کند.")
    
    last_update_id = 0
    counter = 0
    
    while True:
        last_update_id = handle_callback_queries(last_update_id)
        current_time = time.time()
        
        if current_time - LAST_HEARTBEAT_TIME >= 14400:
            send_telegram_message("💓 **سلامت سیستم:** ربات فعال و متصل به تحلیلگر تریدینگ‌ویو است.")
            LAST_HEARTBEAT_TIME = current_time
        
        counter += 1
        if counter >= 10 and not ACTIVE_TRADE:
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
