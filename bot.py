import os
import requests
import time
import threading
from datetime import datetime
from flask import Flask, request
from tradingview_ta import TA_Handler, Interval

# تنظیمات اصلی ربات
TELEGRAM_BOT_TOKEN = "8905848713:AAGrGzm8vqX1_ZGh9C7mmIPO0dRM430x1bA"
DEFAULT_CHAT_ID = "927615637"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

app = Flask(__name__)

# ژورنال هوشمند پیشرفته با قابلیت یادگیری و بازبینی خودکار معاملات
TRADING_JOURNAL = {
    "past_signals": [],
    "lessons_learned": [
        "در سشن‌های کم‌حجم آسیایی، احتمال فیک‌بریک‌اوت در نواحی FVG بالاست؛ تمرکز باید روی سشن لندن و نیویورک باشد.",
        "حد ضرر باید همواره بر اساس ساختار تکنیکال و پشت اوردر بلاک‌ها یا نقدینگی معتبر قرار گیرد تا از استاپ‌هانتینگ جلوگیری شود.",
        "به هنگام انتشار اخبار مهم فاندامنتال، ربات باید فوراً هشدار دهد و تا تخلیه هیجان خبر از ورود مستقیم جلوگیری کند."
    ]
}

# لیست ارزهای پیش‌فرض منو (متصل به موتور TradingView)
TOP_COINS = [
    {"symbol": "BTCUSDT", "exchange": "BINANCE", "name": "بیت‌کوین (BTC - TradingView)", "cg_id": "bitcoin"},
    {"symbol": "ETHUSDT", "exchange": "BINANCE", "name": "اتریوم (ETH - TradingView)", "cg_id": "ethereum"},
    {"symbol": "SOLUSDT", "exchange": "BINANCE", "name": "سولانا (SOL - TradingView)", "cg_id": "solana"},
    {"symbol": "XRPUSDT", "exchange": "BINANCE", "name": "ریپل (XRP - TradingView)", "cg_id": "ripple"},
    {"symbol": "BNBUSDT", "exchange": "BINANCE", "name": "بایننس کوین (BNB - TradingView)", "cg_id": "binancecoin"},
    {"symbol": "ADAUSDT", "exchange": "BINANCE", "name": "کاردانو (ADA - TradingView)", "cg_id": "cardano"},
    {"symbol": "AVAXUSDT", "exchange": "BINANCE", "name": "اولانچ (AVAX - TradingView)", "cg_id": "avalanche-2"},
    {"symbol": "LINKUSDT", "exchange": "BINANCE", "name": "چین‌لینک (LINK - TradingView)", "cg_id": "chainlink"}
]

# دیکشنری برای ثبت آخرین زمان ارسال سیگنال به تفکیک هر ارز (تنظیم شده روی ۲ ساعت = ۷۲۰۰ ثانیه)
LAST_SIGNAL_TIME = {}

# تابع ارسال پیام به تلگرام با مدیریت خطا
def send_telegram_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
        
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Error sending message: {e}")
        return None

# بررسی سشن‌های معاملاتی (Killzones)
def is_optimal_trading_session():
    current_hour = datetime.utcnow().hour
    if 7 <= current_hour <= 21:
        return True
    return False

# دریافت داده‌های فاندامنتال از CoinGecko
def fetch_coingecko_data(symbol_clean):
    try:
        mapping = {
            "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "XRP": "ripple",
            "BNB": "binancecoin", "ADA": "cardano", "AVAX": "avalanche-2", "LINK": "chainlink",
            "DOGE": "dogecoin", "PEPE": "pepe", "NEAR": "near", "SHIB": "shiba-inu"
        }
        coin_id = mapping.get(symbol_clean.upper(), symbol_clean.lower())
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json().get("market_data", {})
            mcap = data.get("market_cap", {}).get("usd", 0)
            change_24h = data.get("price_change_percentage_24h", 0)
            ath = data.get("ath", {}).get("usd", 0)
            return f"مایکت کپ: ${mcap:,.0f} | تغییر ۲۴ ساعته: {change_24h:.2f}% | ATH: ${ath:,.2f}"
    except Exception as e:
        print(f"CoinGecko Error: {e}")
    return "اطلاعات فاندامنتال موقتاً در دسترس نیست."

# دریافت اطلاعات مشتقات، Open Interest و Funding Rate از Coinglass عمومی
def fetch_coinglass_data(symbol_clean):
    try:
        url = f"https://open-api-v4.coinglass.com/api/futures/coins-markets"
        headers = {"accept": "application/json"}
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            result = res.json()
            if result.get("code") == "0":
                coins_list = result.get("data", [])
                for item in coins_list:
                    if item.get("symbol", "").upper() == symbol_clean.upper():
                        oi_usd = item.get("open_interest_usd", 0)
                        funding = item.get("avg_funding_rate_by_oi", 0) * 100
                        oi_change_24h = item.get("open_interest_change_percent_24h", 0)
                        return f"OI: ${oi_usd:,.0f} (تغییر ۲۴ ساعته: {oi_change_24h:.2f}%) | Funding: {funding:.4f}%"
    except Exception as e:
        print(f"Coinglass Error: {e}")
    return "داده‌های فیوچرز در حال به‌روزرسانی است."

# ارتباط با هوش مصنوعی Groq با قوانین سخت‌گیرانه برای اعلان دقیق نوع پیام و خلاصه بودن تحلیل‌ها
def ask_groq_ai_institutional(prompt_text, image_url=None):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    lessons_str = "\n".join([f"- {lesson}" for lesson in TRADING_JOURNAL["lessons_learned"]])
    
    system_prompt = (
        "تو یک الگوریتم تریدینگ نهادی پیشرفته و تحلیلگر ارشد با قابلیت بینایی (Vision) هستی. "
        "استراتژی اصلی تو مبتنی بر ICT، SMC (اوردر بلاک، لیکوییدیتی سویپ و FVG)، اوردر فلو و پرایس اکشن ال بروکس است. "
        "📌 **قوانین حیاتی و ساختار خروجی:**\n"
        "1. در بالاترین خط پیام حتماً به صراحت و با یکی از این دو برچسب نوع پیام را مشخص کن:\n"
        "   - **[🚨 اعلامیه سیگنال معاملاتی جدید]** (اگر شرایط ورود به معامله وجود دارد)\n"
        "   - **[🎯 اعلامیه تعیین تارگت‌ها و حد سود]** (اگر صرفاً به روزرسانی و مشخص کردن اهداف قیمتی است)\n"
        "2. بخش **توضیحات و تحلیل تکنیکال باید بسیار کوتاه، خطی، چکیده و کلیدی** باشد (حداکثر یک الی دو خط اشاره به اوردر بلاک یا ناحیه سویپ).\n"
        "3. مدیریت ریسک به ریوارد پویا (۱ به ۲، ۱ به ۳ یا بیشتر) بر اساس ساختار چارت.\n\n"
        f"📚 **حافظه یادگیری ربات:**\n{lessons_str}\n\n"
        "فرمت دقیق خروجی:\n"
        "[🚨 اعلامیه سیگنال معاملاتی جدید] یا [🎯 اعلامیه تعیین تارگت‌ها و حد سود]\n"
        "- جهت پوزیشن (Long / Short)\n"
        "- نقطه ورود (Entry)\n"
        "- حد ضرر (Stop Loss)\n"
        "- سطوح تارگت (TP1, TP2, TP3) با ذکر نسبت ریسک به ریوارد\n"
        "- تحلیل بسیار کوتاه و چکیده"
    )

    if image_url:
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ]
        model_name = "llama-3.2-11b-vision-preview"
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text}
        ]
        model_name = "llama-3.3-70b-versatile"

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 1000
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        res_data = response.json()
        if "choices" in res_data:
            return res_data["choices"][0]["message"]["content"]
        else:
            return None
    except Exception as e:
        print(f"Groq API Exception: {e}")
        return None

# تحلیل جامع و چندمنظوره بازار
def analyze_custom_market(raw_symbol, image_url=None):
    try:
        symbol = raw_symbol.upper().strip()
        if not symbol.endswith("USDT") and not symbol.endswith("USD"):
            symbol += "USDT"
            
        symbol_clean = symbol.replace("USDT", "").replace("USD", "")
            
        h_4h = TA_Handler(symbol=symbol, exchange="BINANCE", screener="crypto", interval=Interval.INTERVAL_4_HOURS)
        rec_4h = h_4h.get_analysis().summary.get("RECOMMENDATION", "NEUTRAL")
        
        h_1h = TA_Handler(symbol=symbol, exchange="BINANCE", screener="crypto", interval=Interval.INTERVAL_1_HOUR)
        ind_1h = h_1h.get_analysis().indicators
        rec_1h = h_1h.get_analysis().summary.get("RECOMMENDATION", "NEUTRAL")
        
        h_15m = TA_Handler(symbol=symbol, exchange="BINANCE", screener="crypto", interval=Interval.INTERVAL_15_MINUTES)
        ind_15m = h_15m.get_analysis().indicators
        rec_15m = h_15m.get_analysis().summary.get("RECOMMENDATION", "NEUTRAL")

        close_price = ind_1h.get("close", 0)
        rsi_15m = ind_15m.get("RSI", 0)

        cg_info = fetch_coingecko_data(symbol_clean)
        cg_glass = fetch_coinglass_data(symbol_clean)
        
        prompt = (
            f"ارز مورد نظر ({symbol}) قیمت لایو: {close_price}\n"
            f"- ۴ساعته: {rec_4h} | ۱ساعته: {rec_1h} | RSI: {rsi_15m}\n"
            f"- فاندامنتال: {cg_info} | مشتقات: {cg_glass}\n\n"
            "لطفاً بر اساس وضعیت بازار تعیین کن که آیا این یک 'سیگنال معاملاتی' است یا 'اعلامیه تعیین تارگت'؛ سپس پاسخ را با برچسب مربوطه شروع کرده و تمام توضیحات تحلیلی را تا حد امکان بسیار مختصر بنویس."
        )
        
        signal_output = ask_groq_ai_institutional(prompt, image_url=image_url)
        return signal_output, symbol, close_price
        
    except Exception as e:
        print(f"Technical Analysis Error for {raw_symbol}: {e}")
        return None, None, 0

# اسکنر خودکار هوشمند
def institutional_trader_scanner():
    print("🏛️ اسکنر لحظه‌ای نهادی فعال شد...")
    while True:
        try:
            if is_optimal_trading_session():
                for coin in TOP_COINS:
                    symbol = coin["symbol"]
                    current_time = time.time()
                    
                    if symbol in LAST_SIGNAL_TIME and (current_time - LAST_SIGNAL_TIME[symbol] < 7200):
                        continue 
                    
                    signal, _, current_p = analyze_custom_market(symbol)
                    
                    if signal and ("جهت پوزیشن" in signal or "Long" in signal or "Short" in signal) and "ندارد" not in signal:
                        LAST_SIGNAL_TIME[symbol] = current_time
                        
                        TRADING_JOURNAL["past_signals"].append({
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "symbol": symbol,
                            "details": signal[:120],
                            "entry_price": current_p
                        })
                        
                        vision_request_note = (
                            "\n\n💬 **بازبینی بصری:**\n"
                            f"اگر مایل هستید، اسکرین‌شات چارت `{symbol}` را بفرستید تا ربات آن را بررسی کند."
                        )
                        
                        full_msg = f"📊📈 **اسکنر خودکار - {symbol}** 📈📊\n\n{signal}{vision_request_note}"
                        send_telegram_message(DEFAULT_CHAT_ID, full_msg)
                    
                    time.sleep(15)
            else:
                print("⏳ خارج از سشن‌های اصلی؛ رصد ملایم بازار...")
        except Exception as e:
            print(f"Scanner Loop Error: {e}")
            
        time.sleep(1800)

# مدیریت وب‌هوک و دریافت پیام‌ها و عکس‌ها از تلگرام
@app.route(f"/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = request.get_json()
    
    try:
        if "callback_query" in update:
            callback = update["callback_query"]
            chat_id = callback["message"]["chat"]["id"]
            data = callback["data"]
            
            if data == "JOURNAL_STATS":
                journal_msg = (
                    "📖 **ژورنال معامله‌گری و سیستم خودآموز نهادی:**\n\n"
                    f"🔹 تعداد سیگنال‌های ثبت‌شده در حافظه: `{len(TRADING_JOURNAL['past_signals'])}\n`"
                    f"🧠 **قوانین و درس‌های آموخته‌شده هوش مصنوعی:**\n" + "\n".join([f"• {l}" for l in TRADING_JOURNAL['lessons_learned']])
                )
                send_telegram_message(chat_id, journal_msg)
                return "ok", 200

            send_telegram_message(chat_id, f"⏳ در حال استعلام قیمت لایو از TradingView و تحلیل تخصصی `{data}`...")
            ai_response, _, _ = analyze_custom_market(data)
            
            if ai_response:
                vision_request_note = (
                    "\n\n💬 **بازبینی بصری:**\n"
                    f"اگر مایل هستید، اسکرین‌شات چارت `{data}` را بفرستید تا ربات تحلیل نهایی را روی عکس اعمال کند."
                )
                send_telegram_message(chat_id, ai_response + vision_request_note)
            else:
                send_telegram_message(chat_id, f"⚪ خطا در دریافت داده‌های بازار برای نماد `{data}`.")
            return "ok", 200

        if "message" in update:
            chat_id = update["message"]["chat"]["id"]
            message = update["message"]
            text = message.get("text", message.get("caption", "")).strip()

            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "🪙 بیت‌کوین (BTC - TradingView)", "callback_data": "BTCUSDT"},
                        {"text": "Ξ اتریوم (ETH - TradingView)", "callback_data": "ETHUSDT"}
                    ],
                    [
                        {"text": "⚡ سولانا (SOL - TradingView)", "callback_data": "SOLUSDT"},
                        {"text": "💎 ریپل (XRP - TradingView)", "callback_data": "XRPUSDT"}
                    ],
                    [
                        {"text": "🟢 بایننس کوین (BNB - TradingView)", "callback_data": "BNBUSDT"},
                        {"text": "🟣 کاردانو (ADA - TradingView)", "callback_data": "ADAUSDT"}
                    ],
                    [
                        {"text": "🔺 اولانچ (AVAX - TradingView)", "callback_data": "AVAXUSDT"},
                        {"text": "🔗 چین‌لینک (LINK - TradingView)", "callback_data": "LINKUSDT"}
                    ],
                    [
                        {"text": "📖 ژورنال و وضعیت یادگیری هوش مصنوعی", "callback_data": "JOURNAL_STATS"}
                    ]
                ]
            }

            if "photo" in message:
                send_telegram_message(chat_id, "👁️ **چشم هوشمند فعال شد!** در حال اسکن تصویر چارت و تعیین دقیق سیگنال یا تارگت‌ها...")
                
                photo_file_id = message["photo"][-1]["file_id"]
                file_info_res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={photo_file_id}")
                file_path = file_info_res.json().get("result", {}).get("file_path")
                
                if file_path:
                    image_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
                    
                    target_symbol = text.upper() if text else "BTCUSDT"
                    if not target_symbol.endswith("USDT") and not target_symbol.endswith("USD"):
                        target_symbol += "USDT"
                        
                    ai_response, verified_symbol, _ = analyze_custom_market(target_symbol, image_url=image_url)
                    
                    if ai_response:
                        send_telegram_message(chat_id, f"📊 **تحلیل بصری برای: {verified_symbol}**\n\n{ai_response}", reply_markup=keyboard)
                    else:
                        send_telegram_message(chat_id, "❌ خطا در تحلیل تصویر چارت.", reply_markup=keyboard)
                else:
                    send_telegram_message(chat_id, "❌ نتوانستم فایل عکس را دریافت کنم.", reply_markup=keyboard)
                
                return "ok", 200

            if text.startswith("/start") or text.startswith("/help"):
                welcome_msg = (
                    "🤖 **سیستم تریدر نهادی پیشرفته**\n\n"
                    "سلام! ربات با قابلیت تفکیک نوع پیام (سیگنال جدید یا اعلامیه تارگت) و تحلیل‌های کاملاً کوتاه و چکیده آماده است.\n"
                    "از منو استفاده کنید، نام ارز را بفرستید یا اسکرین‌شات چارت خود را ارسال کنید."
                )
                send_telegram_message(chat_id, welcome_msg, reply_markup=keyboard)
            else:
                send_telegram_message(chat_id, f"⏳ در حال بررسی لایو برای `{text}`...")
                ai_response, verified_symbol, _ = analyze_custom_market(text)
                
                if ai_response:
                    vision_request_note = (
                        "\n\n💬 **بازبینی بصری:**\n"
                        f"اگر مایل هستید، اسکرین‌شات چارت `{verified_symbol}` را بفرستید تا ربات تحلیل نهایی را روی عکس پیاده کند."
                    )
                    send_telegram_message(chat_id, f"📊 **نتیجه تحلیل برای: {verified_symbol}**\n\n{ai_response}{vision_request_note}", reply_markup=keyboard)
                else:
                    send_telegram_message(chat_id, f"❌ نماد `{text}` یافت نشد یا در دریافت اطلاعات خطا رخ داد.", reply_markup=keyboard)

    except Exception as e:
        print(f"Error: {e}")

    return "ok", 200

@app.route("/", methods=["GET"])
def index():
    return "Institutional Trading Bot with Explicit Message Type & Concise Analysis is running!", 200

if __name__ == "__main__":
    scanner_thread = threading.Thread(target=institutional_trader_scanner, daemon=True)
    scanner_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
