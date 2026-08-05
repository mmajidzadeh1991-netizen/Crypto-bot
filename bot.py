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
        "حد ضرر باید همواره بر اساس ساختار تکنیکال و پشت اوردر بلاک‌ها یا نقدینگی معتبر قرار گیرد تا از استاپ‌هانتینگ جلوگیری شود."
    ]
}

# لیست ارزها متصل به موتور استاندارد TradingView
TOP_COINS = [
    {"symbol": "BTCUSDT", "exchange": "BINANCE", "name": "بیت‌کوین (BTC)"},
    {"symbol": "ETHUSDT", "exchange": "BINANCE", "name": "اتریوم (ETH)"},
    {"symbol": "SOLUSDT", "exchange": "BINANCE", "name": "سولانا (SOL)"},
    {"symbol": "XRPUSDT", "exchange": "BINANCE", "name": "ریپل (XRP)"},
    {"symbol": "BNBUSDT", "exchange": "BINANCE", "name": "بایننس کوین (BNB)"},
    {"symbol": "ADAUSDT", "exchange": "BINANCE", "name": "کاردانو (ADA)"},
    {"symbol": "AVAXUSDT", "exchange": "BINANCE", "name": "اولانچ (AVAX)"},
    {"symbol": "LINKUSDT", "exchange": "BINANCE", "name": "چین‌لینک (LINK)"}
]

# دیکشنری برای ثبت آخرین زمان ارسال سیگنال به تفکیک هر ارز
LAST_SIGNAL_TIME = {}

# تابع ارسال پیام به تلگرام
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

# ارتباط با هوش مصنوعی Groq با پرامپت بالانس‌شده و دقیق SMC/ICT
def ask_groq_ai_institutional(prompt_text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    lessons_str = "\n".join([f"- {lesson}" for lesson in TRADING_JOURNAL["lessons_learned"]])
    
    system_prompt = (
        "تو یک الگوریتم تریدینگ نهادی حرفه‌ای و تحلیلگر ارشد بازارهای مالی هستی. "
        "تخصص مطلق و اصلی تو سبک‌های **ICT (اسمارت مانی)، SMC، پرایس اکشن ال بروکس و اوردر فلو** است. "
        "تحلیل حجم معاملات و والیوم پروفایل تنها به عنوان یک «فیلتر تکمیلی و تاییدکننده» در کنار ساختار تکنیکال استفاده می‌شود، نه تمرکز اصلی. "
        "قوانین حیاتی برای تعیین نقاط:\n"
        "- نقاط ورود (Entry) باید بسیار دقیق، تمیز و بر اساس پولبک به نواحی معتبر (مثل اوردر بلاک، FVG یا بریک‌کراکر) باشند.\n"
        "- حد ضرر (Stop Loss) باید حتماً پشت ساختار معتبر تکنیکال (پشت اوردر بلاک یا سقف/کف حمایتی/مقاومتی) با فاصله ایمن قرار گیرد تا از استاپ‌هانت جلوگیری شود.\n\n"
        f"📚 **حافظه یادگیری و تجربیات قبلی ربات:**\n{lessons_str}\n\n"
        "اگر شرایط بازار ایده‌آل و موقعیت ورود مناسبی وجود دارد، خروجی باید یک سیگنال دقیق با این ساختار باشد:\n"
        "1. جهت پوزیشن (Long یا Short)\n"
        "2. درصد تاییدیه یا موفقیت (مثلا 88%)\n"
        "3. نقطه ورود اول (Entry 1) و نقطه ورود دوم (در صورت نیاز پله‌ای)\n"
        "4. حد ضرر (Stop Loss) کاملاً منطقی و ساختاریافته\n"
        "5. سه سطح حد سود (TP1, TP2, TP3)\n"
        "6. مدیریت معامله: نقطه ریسک‌فری (Risk-Free) و تریلینگ استاپ\n"
        "7. تحلیل فنی ساختاری (بررسی روند 4H، ساختار 1H، تاییدیه 15M، اوردر بلاک، FVG و وضعیت حجم به عنوان تاییدیه)."
    )

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.2,
        "max_tokens": 1200
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=25)
        res_data = response.json()
        if "choices" in res_data:
            return res_data["choices"][0]["message"]["content"]
        else:
            return None
    except Exception as e:
        print(f"Groq API Exception: {e}")
        return None

# تحلیل چندتایم‌فریمه بازار
def analyze_institutional_market(coin):
    try:
        h_4h = TA_Handler(symbol=coin["symbol"], exchange=coin["exchange"], screener="crypto", interval=Interval.INTERVAL_4_HOURS)
        rec_4h = h_4h.get_analysis().summary.get("RECOMMENDATION", "NEUTRAL")
        
        h_1h = TA_Handler(symbol=coin["symbol"], exchange=coin["exchange"], screener="crypto", interval=Interval.INTERVAL_1_HOUR)
        ind_1h = h_1h.get_analysis().indicators
        rec_1h = h_1h.get_analysis().summary.get("RECOMMENDATION", "NEUTRAL")
        
        h_15m = TA_Handler(symbol=coin["symbol"], exchange=coin["exchange"], screener="crypto", interval=Interval.INTERVAL_15_MINUTES)
        ind_15m = h_15m.get_analysis().indicators
        rec_15m = h_15m.get_analysis().summary.get("RECOMMENDATION", "NEUTRAL")

        close_price = ind_1h.get("close", 0)
        rsi_15m = ind_15m.get("RSI", 0)
        volume_1h = ind_1h.get("volume", 0)
        
        prompt = (
            f"ارز {coin['name']} ({coin['symbol']}) داده‌های بازار (TradingView):\n"
            f"- ساختار ۴ ساعته: {rec_4h}\n"
            f"- مومنتوم ۱ ساعته (قیمت بسته شدن: {close_price} | حجم: {volume_1h}): {rec_1h}\n"
            f"- تاییدیه ۱۵ دقیقه (RSI: {rsi_15m}): {rec_15m}\n\n"
            f"لطفاً بر اساس سبک قدرتمند SMC و ICT (با نگاهی به حجم به عنوان تاییدیه)، بررسی کن که آیا موقعیت ورود تمیز و استانداردی وجود دارد؟ در صورت تایید، سیگنال کامل را صادر کن."
        )
        
        signal_output = ask_groq_ai_institutional(prompt)
        return signal_output
        
    except Exception as e:
        print(f"Technical Analysis Error for {coin['symbol']}: {e}")
        return None

# اسکنر خودکار هوشمند (هر ۳۰ دقیقه)
def institutional_trader_scanner():
    print("🏛️ اسکنر لحظه‌ای نهادی (با پرامپت بالانس‌شده SMC/ICT) فعال شد...")
    while True:
        try:
            if is_optimal_trading_session():
                for coin in TOP_COINS:
                    symbol = coin["symbol"]
                    current_time = time.time()
                    
                    if symbol in LAST_SIGNAL_TIME and (current_time - LAST_SIGNAL_TIME[symbol] < 1800):
                        continue 
                    
                    print(f"🔍 در حال ارزیابی ساختاری {symbol}...")
                    signal = analyze_institutional_market(coin)
                    
                    if signal and ("جهت پوزیشن" in signal or "Long" in signal or "Short" in signal) and "ندارد" not in signal:
                        LAST_SIGNAL_TIME[symbol] = current_time
                        
                        TRADING_JOURNAL["past_signals"].append({
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "symbol": symbol,
                            "details": signal[:120]
                        })
                        
                        full_msg = f"🏛️🚨 **سیگنال نهادی (ساختار SMC / ICT)** 🚨🏛️\n\n{signal}"
                        send_telegram_message(DEFAULT_CHAT_ID, full_msg)
                    
                    time.sleep(15)
                    
            else:
                print("⏳ خارج از سشن‌های اصلی؛ رصد ملایم بازار...")
                
        except Exception as e:
            print(f"Scanner Loop Error: {e}")
            
        time.sleep(1800)

# مدیریت وب‌هوک و دریافت پیام‌ها از تلگرام
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

            send_telegram_message(chat_id, f"⏳ در حال تحلیل ساختاری SMC/ICT برای {data}...")
            ai_response = ask_groq_ai_institutional(f"لطفاً تحلیل کامل نهادی بر پایه SMC، ICT و پرایس اکشن را به همراه نقاط ورود و استاپ لاس دقیق برای ارز {data} ارائه بده.")
            
            if ai_response:
                send_telegram_message(chat_id, ai_response)
            else:
                send_telegram_message(chat_id, "⚪ پاسخ خالی از هوش مصنوعی دریافت شد.")
            return "ok", 200

        if "message" in update:
            chat_id = update["message"]["chat"]["id"]
            text = update["message"].get("text", "")

            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "🪙 بیت‌کوین (BTC)", "callback_data": "BTCUSDT"},
                        {"text": "Ξ اتریوم (ETH)", "callback_data": "ETHUSDT"}
                    ],
                    [
                        {"text": "⚡ سولانا (SOL)", "callback_data": "SOLUSDT"},
                        {"text": "💎 ریپل (XRP)", "callback_data": "XRPUSDT"}
                    ],
                    [
                        {"text": "🟢 بایننس کوین (BNB)", "callback_data": "BNBUSDT"},
                        {"text": "🟣 کاردانو (ADA)", "callback_data": "ADAUSDT"}
                    ],
                    [
                        {"text": "🔺 اولانچ (AVAX)", "callback_data": "AVAXUSDT"},
                        {"text": "🔗 چین‌لینک (LINK)", "callback_data": "LINKUSDT"}
                    ],
                    [
                        {"text": "📖 ژورنال و وضعیت یادگیری هوش مصنوعی", "callback_data": "JOURNAL_STATS"}
                    ]
                ]
            }

            if text.startswith("/start") or text.startswith("/help"):
                welcome_msg = (
                    "🤖 **سیستم تریدر نهادی هوشمند (تمرکز اصلی روی SMC / ICT)**\n\n"
                    "سلام! پرامپت ربات اصلاح و بالانس شد تا تحلیل‌ها کاملاً روی ساختار پرایس اکشن، نواحی اوردر بلاک و استاپ‌لاس‌های منطقی متمرکز باشند.\n"
                    "از منوی زیر برای بررسی دستی ارزها استفاده کنید:"
                )
                send_telegram_message(chat_id, welcome_msg, reply_markup=keyboard)
            else:
                send_telegram_message(chat_id, "⏳ در حال بررسی عمیق ساختاری درخواست شما...")
                ai_response = ask_groq_ai_institutional(f"لطفاً تحلیل کامل نهادی را برای این درخواست ارائه بده: {text}")
                
                if ai_response:
                    send_telegram_message(chat_id, ai_response, reply_markup=keyboard)
                else:
                    send_telegram_message(chat_id, "⚪ پاسخ خالی از هوش مصنوعی دریافت شد.")

    except Exception as e:
        error_msg = f"❌ خطای سیستمی در پردازش: {str(e)}"
        print(error_msg)

    return "ok", 200

@app.route("/", methods=["GET"])
def index():
    return "Institutional Trading Bot with Balanced SMC/ICT Prompt is running!", 200

if __name__ == "__main__":
    scanner_thread = threading.Thread(target=institutional_trader_scanner, daemon=True)
    scanner_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
