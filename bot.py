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
        "ورود به معامله بدون تاییدیه حجمی (Volume Confirmation) و بررسی گره‌های نقدینگی معتبر ممنوع است."
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

# ارتباط با هوش مصنوعی Groq با پرامپت پیشرفته ICT/SMC و Volume Profile
def ask_groq_ai_institutional(prompt_text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    lessons_str = "\n".join([f"- {lesson}" for lesson in TRADING_JOURNAL["lessons_learned"]])
    
    system_prompt = (
        "تو یک الگوریتم تریدینگ نهادی پیشرفته (Institutional Trading & Volume Profile Bot) و تحلیلگر ارشد بازارهای مالی هستی. "
        "تخصص مطلق تو ترکیب سبک‌های ICT (اسمارت مانی)، SMC، اوردر فلو، پرایس اکشن ال بروکس و تحلیل پیشرفته **والیوم پروفایل و گره‌های حجمی (Volume Profile & POC)** است. "
        "تو باید هر سناریو را از دیدگاه حجم معاملات واقعی، انباشت سفارشات موسسات، نواحی POC و نقدینگی تایید کنی تا جلوی بریک‌اوت‌های فیک گرفته شود. "
        "نکته بسیار مهم: حد ضرر (Stop Loss) باید با دقت بالا و بر اساس ساختار تکنیکال و پشت گره‌های حجمی معتبر تعیین شود تا به طور طبیعی از استاپ‌هانتینگ جلوگیری کند.\n\n"
        f"📚 **حافظه یادگیری و تجربیات قبلی ربات:**\n{lessons_str}\n\n"
        "اگر شرایط بازار ایده‌آل و موقعیت ورود با تاییدیه حجمی مناسبی وجود دارد، خروجی باید یک سیگنال دقیق با این ساختار باشد:\n"
        "1. جهت پوزیشن (Long یا Short)\n"
        "2. درصد تاییدیه یا موفقیت (مثلا 89%)\n"
        "3. نقطه ورود اول (Entry 1) و نقطه ورود دوم (پله‌ای/DCA)\n"
        "4. حد ضرر (Stop Loss) کاملاً دقیق بر اساس ساختار و گره‌های حجمی\n"
        "5. سه سطح حد سود (TP1, TP2, TP3)\n"
        "6. مدیریت معامله: نقطه ریسک‌فری (Risk-Free) و تریلینگ استاپ (Trailing Stop)\n"
        "7. تحلیل فنی نهادی و حجمی (بررسی وضعیت والیوم پروفایل، POC، اوردر بلاک، FVG و فیلتر سشن)."
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

# تحلیل چندتایم‌فریمه بازار به همراه حجم و والیوم پروفایل
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
            f"ارز {coin['name']} ({coin['symbol']}) داده‌های معاملاتی و حجمی (TradingView):\n"
            f"- ساختار ۴ ساعته: {rec_4h}\n"
            f"- مومنتوم ۱ ساعته (قیمت بسته شدن: {close_price} | حجم معاملات: {volume_1h}): {rec_1h}\n"
            f"- نقطه ورود ۱۵ دقیقه (RSI: {rsi_15m}): {rec_15m}\n\n"
            f"لطفاً با تحلیل والیوم پروفایل، گره‌های حجمی و نواحی POC، بررسی کن که آیا یک موقعیت ورود استاندارد با تاییدیه حجمی وجود دارد یا خیر؟ در صورت تایید، سیگنال کامل را صادر کن."
        )
        
        signal_output = ask_groq_ai_institutional(prompt)
        return signal_output
        
    except Exception as e:
        print(f"Technical Analysis Error for {coin['symbol']}: {e}")
        return None

# اسکنر خودکار هوشمند با قابلیت رصد حجم و گره‌های بازار (هر ۳۰ دقیقه)
def institutional_trader_scanner():
    print("🏛️ اسکنر لحظه‌ای نهادی (مجهز به تحلیل حجمی و والیوم پروفایل) فعال شد...")
    while True:
        try:
            if is_optimal_trading_session():
                for coin in TOP_COINS:
                    symbol = coin["symbol"]
                    current_time = time.time()
                    
                    if symbol in LAST_SIGNAL_TIME and (current_time - LAST_SIGNAL_TIME[symbol] < 1800):
                        continue 
                    
                    print(f"🔍 در حال ارزیابی حجمی و ساختاری {symbol}...")
                    signal = analyze_institutional_market(coin)
                    
                    if signal and ("جهت پوزیشن" in signal or "Long" in signal or "Short" in signal) and "ندارد" not in signal:
                        LAST_SIGNAL_TIME[symbol] = current_time
                        
                        TRADING_JOURNAL["past_signals"].append({
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "symbol": symbol,
                            "details": signal[:120]
                        })
                        
                        full_msg = f"📊🚨 **سیگنال پیشرفته نهادی (مجهز به والیوم پروفایل و حجم واقعی)** 🚨📊\n\n{signal}"
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

            send_telegram_message(chat_id, f"⏳ در حال تحلیل حجمی و والیوم پروفایل برای {data}...")
            ai_response = ask_groq_ai_institutional(f"لطفاً تحلیل کامل نهادی شامل بررسی والیوم پروفایل، گره‌های حجمی POC، نقاط ورود و استاپ لاس ساختاری را برای ارز {data} ارائه بده.")
            
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
                    "🤖 **سیستم تریدر نهادی هوشمند (مجهز به والیوم پروفایل و حجم)**\n\n"
                    "سلام! ربات شما اکنون علاوه بر SMC و ICT، مجهز به **تحلیل والیوم پروفایل و گره‌های حجمی** است و بازار را به صورت خودکار پایش می‌کند.\n"
                    "از منوی زیر برای بررسی دستی استفاده کنید:"
                )
                send_telegram_message(chat_id, welcome_msg, reply_markup=keyboard)
            else:
                send_telegram_message(chat_id, "⏳ در حال بررسی عمیق حجمی درخواست شما...")
                ai_response = ask_groq_ai_institutional(f"لطفاً تحلیل کامل نهادی با رویکرد والیوم پروفایل را برای این درخواست ارائه بده: {text}")
                
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
    return "Institutional Trading Bot with Volume Profile is running!", 200

if __name__ == "__main__":
    scanner_thread = threading.Thread(target=institutional_trader_scanner, daemon=True)
    scanner_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
