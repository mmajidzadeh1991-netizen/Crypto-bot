import time
import requests
from flask import Flask
import threading

# --- تنظیمات وب‌سرور برای سازگاری با Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Trading Bot is running 24/7!"

def run_web():
    app.run(host="0.0.0.0", port=10000)


# --- تنظیمات ربات تلگرام ---
TOKEN = "8905848713:AAGrGzm8vqX1_ZGh9C7mmIPO0dRM430x1bA"
CHAT_ID = "927615637"

TOP_6_COINS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT"]

PRICE_ALERTS = {}
LAST_SIGNAL_TIME = {}
ACTIVE_TRADE = None

def send_telegram_message(message, chat_id=CHAT_ID):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
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

def check_candle_confirmation(candles):
    """بررسی تاییدیه کندلی (کندل صعودی قوی یا اینگالف)"""
    if not candles or len(candles) < 2:
        return False
        
    prev_candle = candles[-2]
    last_candle = candles[-1]
    
    is_green = last_candle['close'] > last_candle['open']
    body_size = abs(last_candle['close'] - last_candle['open'])
    total_size = last_candle['high'] - last_candle['low']
    
    if total_size == 0:
        return False
        
    is_strong_body = (body_size / total_size) >= 0.40
    is_engulfing = last_candle['close'] > prev_candle['high']
    
    return is_green and (is_strong_body or is_engulfing)

def analyze_market_multi_timeframe(symbol):
    """
    تحلیل چندتایم‌فریمه:
    1. بررسی روند 4 ساعته و ناحیه کلیدی در 15 دقیقه
    2. بررسی تاییدیه سریع‌تر در تایم‌فریم پایین‌تر (مثلا 5 دقیقه) برای ورود بهینه
    """
    candles_4h = get_binance_candles(symbol, interval="4h", limit=5)
    if not candles_4h:
        return None, None
    trend_4h = "BULLISH" if candles_4h[-1]['close'] > candles_4h[-3]['open'] else "BEARISH"
    if trend_4h != "BULLISH":
        return None, None
        
    candles_15m = get_binance_candles(symbol, interval="15m", limit=15)
    if not candles_15m or len(candles_15m) < 10:
        return None, None
        
    current_price = candles_15m[-1]['close']
    c1 = candles_15m[-3]
    c3 = candles_15m[-1]
    has_fvg = c3['low'] > c1['high']
    fvg_level = (c1['high'] + c3['low']) / 2 if has_fvg else 0
    
    if has_fvg or (current_price <= fvg_level * 1.015):
        candles_5m = get_binance_candles(symbol, interval="5m", limit=10)
        has_5m_confirmation = check_candle_confirmation(candles_5m)
        
        if has_5m_confirmation:
            entry_1 = current_price
            entry_2 = entry_1 * 0.994
            stop_loss = min(candles_5m[-1]['low'], c1['low']) * 0.995
            risk = entry_1 - stop_loss
            
            if risk <= 0:
                return None, None
                
            tp1 = entry_1 + (risk * 1.5)
            tp2 = entry_1 + (risk * 2.5)
            tp3 = entry_1 + (risk * 4.0)
            
            trade_data = {
                "symbol": symbol,
                "entry_1": entry_1,
                "entry_2": entry_2,
                "stop_loss": stop_loss,
                "tp1": tp1,
                "tp2": tp2,
                "tp3": tp3,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False
            }
            
            signal_text = (
                f"🚀 **سیگنالِ تاییدشده (مایکرواسکوپیک - تایم 5م دقیقه)** 🚀\n\n"
                f"🟢 **رمز ارز:** `{symbol}`\n"
                f"📈 روند 4H صعودی | ⚡ **تاییدیه سریع در تایم پایین‌تر صادر شد!**\n\n"
                f"📌 **نقطه ورود اول (Entry 1):** `{entry_1:.4f}`\n"
                f"📉 **نقطه ورود دوم پله‌ای (Entry 2):** `{entry_2:.4f}`\n"
                f"🛑 **حد ضرر (Stop Loss):** `{stop_loss:.4f}` (بهینه شده)\n\n"
                f"🎯 **تارگت اول (TP1):** `{tp1:.4f}`\n"
                f"🎯 **تارگت دوم (TP2):** `{tp2:.4f}`\n"
                f"🎯 **تارگت سوم (TP3):** `{tp3:.4f}`\n\n"
                f"🤖 *مدیریت زنده معامله از این لحظه آغاز شد.*"
            )
            return trade_data, signal_text
            
    return None, None

def manage_active_trade():
    global ACTIVE_TRADE
    if not ACTIVE_TRADE:
        return
        
    symbol = ACTIVE_TRADE["symbol"]
    candles = get_binance_candles(symbol, interval="1m", limit=1)
    if not candles:
        return
        
    current_price = candles[-1]['close']
    sl = ACTIVE_TRADE["stop_loss"]
    tp1 = ACTIVE_TRADE["tp1"]
    tp2 = ACTIVE_TRADE["tp2"]
    tp3 = ACTIVE_TRADE["tp3"]
    
    if current_price <= sl:
        send_telegram_message(f"🛑 **حد ضرر پوزیشن `{symbol}` لمس شد.** معامله با ضرر بسته شد.")
        ACTIVE_TRADE = None
        return
        
    if not ACTIVE_TRADE.get("tp1_hit") and current_price >= tp1:
        ACTIVE_TRADE["tp1_hit"] = True
        send_telegram_message(
            f"🎯 **تارگت اول (TP1) ارز `{symbol}` تاچ شد!** ✅\n\n"
            f"💡 **مدیریت سرمایه:** حد ضرر خود را به نقطه ورود انتقال دهید (**Risk-Free**)."
        )
        
    if ACTIVE_TRADE.get("tp1_hit") and not ACTIVE_TRADE.get("tp2_hit") and current_price >= tp2:
        ACTIVE_TRADE["tp2_hit"] = True
        send_telegram_message(
            f"🎯🎯 **تارگت دوم (TP2) ارز `{symbol}` فتح شد!** 🚀\n\n"
            f"💡 **تریلینگ استاپ:** استاپ‌لاس را پشت تارگت اول قفل کنید."
        )
        
    if ACTIVE_TRADE.get("tp2_hit") and not ACTIVE_TRADE.get("tp3_hit") and current_price >= tp3:
        send_telegram_message(f"🏆🏆🏆 **تارگت نهایی (TP3) ارز `{symbol}` با موفقیت تاچ شد!** کل سود کسب شد.")
        ACTIVE_TRADE = None

def check_telegram_updates(last_update_id):
    global ACTIVE_TRADE
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last_update_id}&timeout=3"
    try:
        response = requests.get(url)
        data = response.json()
        
        if data.get("ok") and data.get("result"):
            for update in data["result"]:
                last_update_id = update["update_id"] + 1
                
                if "message" in update and "text" in update["message"]:
                    raw_text = update["message"]["text"]
                    sender_chat_id = update["message"]["chat"]["id"]
                    text_upper = raw_text.upper().strip()
                    
                    if text_upper in ["/START", "START"]:
                        reply_msg = "🤖 **دستیار چندتایم‌فریمه فعال است.** ربات همزمان نواحی مهم را در 15م و تاییدیه را در 5م دقیقه چک می‌کند."
                    elif text_upper == "CLOSE":
                        ACTIVE_TRADE = None
                        reply_msg = "❌ پوزیشن فعال بسته شد."
                    else:
                        clean_coin = text_upper.replace("(", "").replace(")", "").strip()
                        if clean_coin in ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA"]:
                            clean_coin += "USDT"
                            
                        trade_data, msg_res = analyze_market_multi_timeframe(clean_coin)
                        if trade_data:
                            ACTIVE_TRADE = trade_data
                            reply_msg = msg_res
                        else:
                            reply_msg = f"⚪ ارز `{clean_coin}` بررسی شد. هنوز تاییدیه مناسب در تایم پایین‌تر صادر نشده است."
                            
                    send_telegram_message(reply_msg, sender_chat_id)
                    
    except Exception as e:
        print(f"خطا در خواندن پیام: {e}")
        
    return last_update_id

def run_bot_loop():
    print("دستیار هوشمند چندتایم‌فریمه روی وب‌سرور روشن شد...")
    send_telegram_message("🤖 **سیستم ترید چندتایم‌فریمه (15m + 5m) روی سرور ابری استارت خورد.**")
    
    last_update_id = 0
    counter = 0
    
    while True:
        last_update_id = check_telegram_updates(last_update_id)
        
        if ACTIVE_TRADE:
            manage_active_trade()
        else:
            counter += 1
            if counter >= 5:
                counter = 0
                for coin in TOP_6_COINS:
                    trade_data, message_result = analyze_market_multi_timeframe(coin)
                    current_time = time.time()
                    
                    if trade_data:
                        if coin not in LAST_SIGNAL_TIME or (current_time - LAST_SIGNAL_TIME[coin]) > 7200:
                            ACTIVE_TRADE = trade_data
                            send_telegram_message(message_result)
                            LAST_SIGNAL_TIME[coin] = current_time
                            break
                    time.sleep(1)
                    
        time.sleep(5)

if __name__ == "__main__":
    # اجرای ربات در یک Thread جداگانه برای فعالیت همزمان با وب‌سرور
    bot_thread = threading.Thread(target=run_bot_loop)
    bot_thread.daemon = True
    bot_thread.start()
    
    # اجرای وب‌سرور Flask برای راضی نگه داشتن سایت Render
    run_web()
