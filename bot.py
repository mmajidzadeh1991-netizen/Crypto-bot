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

# ارتباط با هوش مصنوعی Groq با تمرکز اصلی تکنیکال و رصد هوشمند اخبار مهم
def ask_groq_ai_institutional(prompt_text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    lessons_str = "\n".join([f"- {lesson}" for lesson in TRADING_JOURNAL["lessons_learned"]])
    
    system_prompt = (
        "تو یک الگوریتم تریدینگ نهادی پیشرفته و تحلیلگر ارشد بازارهای مالی هستی. "
        "تمرکز اصلی و ۹۰ درصدی تو بر روی **تحلیل تکنیکال عمیق، سبک‌های ICT (اسمارت مانی)، SMC، اوردر فلو و پرایس اکشن ال بروکس** است. "
        "اما قانون فاندامنتال این است: ربات فقط در زمان‌هایی که **خبر مهمی در بازار منتشر شده یا تاثیرگذار است**، آن را به عنوان یک هشدار ویژه در نظر می‌گیرد تا از تله‌های بازار جلوگیری کند. در حالت عادی تمام تمرکز روی چارت است. "
        "نکته حیاتی: حد ضرر (Stop Loss) باید با دقت بالا و پشت اوردر بلاک‌های معتبر تعیین شود تا از استاپ‌هانتینگ جلوگیری گردد.\n\n"
        f"📚 **حافظه یادگیری و تجربیات قبلی ربات:**\n{lessons_str}\n\n"
        "اگر شرایط بازار ایده‌آل و موقعیت ورود مناسبی وجود دارد، خروجی باید یک سیگنال دقیق و ساختاریافته با این جزئیات باشد:\n"
        "1. جهت پوزیشن (Long یا Short)\n"
        "2. **درصد تاییدیه یا موفقیت (مثلا 89%)**\n"
        "3. نقطه ورود اول (Entry 1) و نقطه ورود دوم (پله‌ای/DCA)\n"
        "4. حد ضرر (Stop Loss) کاملاً دقیق و مهندسی‌شده\n"
        "5. سه سطح حد سود (TP1, TP2, TP3)\n"
        "6. مدیریت معامله: نقطه ریسک‌فری (Risk-Free) و تریلینگ استاپ (Trailing Stop)\n"
        "7. تحلیل فنی نهادی و در صورت وجود خبر مهم، هشدار فاندامنتال کوتاه."
    )

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.2,
        "max_tokens": 1300
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

# تحلیل چندتایم‌فریمه بازار با تمرکز اصلی چارت و رصد اخبار مهم
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
            f"ارز {coin['name']} ({coin['symbol']}) داده‌های معاملاتی (TradingView):\n"
            f"- ساختار ۴ ساعته: {rec_4h}\n"
            f"- مومنتوم ۱ ساعته (قیمت: {close_price} | حجم: {volume_1h}): {rec_1h}\n"
            f"- تاییدیه ۱۵ دقیقه (RSI: {rsi_15m}): {rec_15m}\n\n"
            f"لطفاً با تمرکز اصلی و کامل روی چارت، SMC، ICT و پرایس اکشن بررسی کن آیا موقعیت ورودی وجود دارد؟ (فقط اگر خبر مهم تاثیرگذاری در جریان است به آن اشاره کن). در صورت تایید، سیگنال کامل همراه با درصد موفقیت را صادر کن."
        )
        
        signal_output = ask_groq_ai_institutional(prompt)
        return signal_output
        
    except Exception as e:
        print(f"Technical Analysis Error for {coin['symbol']}: {e}")
        return None

# اسکنر خودکار هوشمند (رصد بازار هر ۳۰ دقیقه)
def institutional_trader_scanner():
    print("🏛️ اسکنر لحظه‌ای نهادی (تمرکز روی چارت + رصد اخبار مهم) فعال شد...")
    while True:
        try:
            if is_optimal_trading_session():
                for coin in TOP_COINS:
                    symbol = coin["symbol"]
                    current_time = time.time()
                    
                    if symbol in LAST_SIGNAL_TIME and (current_time - LAST_SIGNAL_TIME[symbol] < 1800):
                        continue 
                    
                    print(f"🔍 در حال ارزیابی چارت و رویدادهای {symbol}...")
                    signal = analyze_institutional_market(coin)
                    
                    if signal and ("جهت پوزیشن" in signal or "Long" in signal or "Short" in signal) and "ندارد" not in signal:
                        LAST_SIGNAL_TIME[symbol] = current_time
                        
                        TRADING_JOURNAL["past_signals"].append({
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "symbol": symbol,
                            "details": signal[:120]
                        })
                        
                        full_msg = f"📊📈 **سیگنال نهادی (چارت + رصد اخبار مهم)** 📈📊\n\n{signal}"
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

            send_telegram_message(chat_id, f"⏳ در حال تحلیل تخصصی چارت برای {data}...")
            ai_response = ask_groq_ai_institutional(f"لطفاً تحلیل کامل تکنیکال، درصد موفقیت، نقاط ورود، استاپ لاس ساختاری، ریسک‌فری و تریلینگ استاپ را به همراه بررسی خبر مهم (در صورت وجود) برای ارز {data} ارائه بده.")
            
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
                    "🤖 **سیستم تریدر نهادی هوشمند (تمرکز چارت + رصد اخبار مهم)**\n\n"
                    "سلام! ربات شما آماده است. تمرکز اصلی روی چارت و SMC است و فقط هنگام انتشار اخبار مهم به شما هشدار می‌دهد.\n"
                    "از منوی زیر برای بررسی ارزها استفاده کنید:"
                )
                send_telegram_message(chat_id, welcome_msg, reply_markup=keyboard)
            else:
                send_telegram_message(chat_id, "⏳ در حال بررسی چارت و تحلیل درخواست شما...")
                ai_response = ask_groq_ai_institutional(f"کاربر این درخواست را مطرح کرده است: '{text}'. لطفاً با تمرکز بر چارت و تکنیکال پاسخ کامل بده.")
                
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
    return "Institutional Trading Bot with Chart Focus & News Alert is running!", 200

if __name__ == "__main__":
    scanner_thread = threading.Thread(target=institutional_trader_scanner, daemon=True)
    scanner_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
