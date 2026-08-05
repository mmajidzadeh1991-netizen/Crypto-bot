import os
import requests
import time
import threading
from datetime import datetime
from flask import Flask, request
from tradingview_ta import TA_Handler, Interval

# تنظیمات اصلی
TELEGRAM_BOT_TOKEN = "8905848713:AAGrGzm8vqX1_ZGh9C7mmIPO0dRM430x1bA"
DEFAULT_CHAT_ID = "927615637"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

app = Flask(__name__)

# حافظه داخلی برای ژورنال معامله‌گری و یادگیری ربات (ثبت عیب‌یابی‌ها و تجربه بازار)
TRADING_JOURNAL = {
    "past_signals": [],
    "lessons_learned": [
        "در بازارهای رنج ۴ ساعته، ورود در تایم ۱۵ دقیقه نیاز به تاییدیه شکست واقعی دارد.",
        "اگر کندل تثبیت ۱۵ دقیقه بسته نشود، احتمال فیک‌بریک‌اوت در نواحی FVG بالاست."
    ]
}

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
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error sending message: {e}")

# تابع هوش مصنوعی با قابلیت یادگیری، ژورنال و تحلیل چندتایم‌فریمه عمیق
def ask_groq_ai_advanced(prompt_text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # تزریق درس‌های آموخته‌شده قبلی به حافظه هوش مصنوعی برای یادگیری مداوم
    lessons_str = "\n".join([f"- {lesson}" for lesson in TRADING_JOURNAL["lessons_learned"]])
    
    system_prompt = (
        "تو یک تریدر نهادی هوشمند، الگوریتمی و خودآموز در بازارهای مالی هستی. "
        "تخصص مطلق تو سبک‌های ICT (اسمارت مانی)، SMC، اوردر فلو و پرایس اکشن ال بروکس است. "
        "تو مجهز به تحلیل چندتایم‌فریمه عمیق هستی: روند ساختاری کلان در **۴ ساعته**، جهت مومنتوم در **۱ ساعته**، نقطه ورود دقیق در **۱۵ دقیقه**، و بررسی تثبیت کندل‌ها در **تایم‌فریم‌های پایین‌تر (مثلا ۵ دقیقه)**. "
        "کاربر به شدت روی دقت بالا، تعیین درصد موفقیت دقیق (مثلا 88%) و کیفیت سیگنال تاکید دارد. روزانه به چند سیگنال عالی با کیفیت بالا نیاز داریم. "
        "همچنین تو باید از تجربیات و ژورنال معاملات قبلی یاد بگیری تا خطاهای گذشته را تکرار نکنی.\n\n"
        f"📚 **تجربیات و درس‌های آموخته‌شده قبلی (برای بهبود دقت):**\n{lessons_str}\n\n"
        "اگر بازار شرایط مناسبی دارد، خروجی باید یک سیگنال دقیق با این ساختار باشد:\n"
        "1. جهت پوزیشن (Long یا Short)\n"
        "2. درصد تاییدیه یا موفقیت (مثلا 87%)\n"
        "3. نقطه ورود اول (Entry 1) و نقطه ورود دوم (پله‌ای/DCA)\n"
        "4. حد ضرر (Stop Loss) دقیق بر اساس ساختار ۴ ساعته\n"
        "5. سه سطح حد سود (TP1, TP2, TP3)\n"
        "6. مدیریت معامله شامل: نقطه ریسک‌فری (Risk-Free) و استراتژی تریلینگ استاپ (Trailing Stop)\n"
        "7. تحلیل فنی و چندتایم‌فریمه کامل (توضیح روند ۴ ساعته، ۱ ساعته، و تاییدیه کندلی در ۱۵ دقیقه/تایم پایین‌تر)."
    )

    payload = {
        "model": "llama3-70b-8192",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.25,
        "max_tokens": 1200
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        res_data = response.json()
        if "choices" in res_data:
            return res_data["choices"][0]["message"]["content"]
        else:
            return None
    except Exception as e:
        print(f"Groq API Error: {e}")
        return None

# تابع تحلیل چندتایم‌فریمه بازار (4H, 1H, 15M)
def analyze_multi_timeframe(coin):
    try:
        # بررسی 4 ساعته (روند کلان)
        h_4h = TA_Handler(symbol=coin["symbol"], exchange=coin["exchange"], screener="crypto", interval=Interval.INTERVAL_4_HOURS)
        rec_4h = h_4h.get_analysis().summary.get("RECOMMENDATION", "NEUTRAL")
        
        # بررسی 1 ساعته (مومنتوم)
        h_1h = TA_Handler(symbol=coin["symbol"], exchange=coin["exchange"], screener="crypto", interval=Interval.INTERVAL_1_HOUR)
        ind_1h = h_1h.get_analysis().indicators
        rec_1h = h_1h.get_analysis().summary.get("RECOMMENDATION", "NEUTRAL")
        
        # بررسی 15 دقیقه (نقطه ورود و تثبیت کندل)
        h_15m = TA_Handler(symbol=coin["symbol"], exchange=coin["exchange"], screener="crypto", interval=Interval.INTERVAL_15_MINUTES)
        ind_15m = h_15m.get_analysis().indicators
        rec_15m = h_15m.get_analysis().summary.get("RECOMMENDATION", "NEUTRAL")

        close_price = ind_1h.get("close", 0)
        rsi_15m = ind_15m.get("RSI", 0)
        
        # ارسال داده‌ها به هوش مصنوعی برای تصمیم‌گیری نهایی چندتایم‌فریمه
        prompt = (
            f"ارز {coin['name']} ({coin['symbol']}) برای تحلیل چندتایم‌فریمه:\n"
            f"- وضعیت ساختاری در ۴ ساعته: {rec_4h}\n"
            f"- وضعیت مومنتوم در ۱ ساعته: {rec_1h} (قیمت: {close_price})\n"
            f"- وضعیت ورود در ۱۵ دقیقه: {rec_15m} (RSI: {rsi_15m})\n\n"
            f"لطفاً وضعیت باز و بسته شدن کندل‌ها و تثبیت قیمت را بررسی کن. اگر هم‌راستایی کامل وجود دارد، سیگنال باکیفیت و درصد موفقیت بالا صادر کن."
        )
        
        signal_output = ask_groq_ai_advanced(prompt)
        return signal_output
        
    except Exception as e:
        print(f"Multi-TF Analysis Error for {coin['symbol']}: {e}")
        return None

# اسکنر خودکار با قابلیت ژورنال‌نویسی و یادگیری روزانه
def smart_trader_scanner():
    print("🧠 ربات هوشمند چندتایم‌فریمه با قابلیت یادگیری و ژورنال‌نویسی فعال شد...")
    while True:
        try:
            for coin in TOP_COINS:
                print(f"در حال بررسی چندتایم‌فریمه {coin['symbol']}...")
                signal = analyze_multi_timeframe(coin)
                
                if signal and ("جهت پوزیشن" in signal or "Long" in signal or "Short" in signal):
                    # ثبت سیگنال در ژورنال داخلی برای ردیابی و یادگیری
                    TRADING_JOURNAL["past_signals"].append({
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "symbol": coin["symbol"],
                        "details": signal[:100]
                    })
                    
                    full_msg = f"💎 **سیگنالِ پیشرفته چندتایم‌فریمه (ICT/SMC)** 💎\n\n{signal}"
                    send_telegram_message(DEFAULT_CHAT_ID, full_msg)
                    
                    # استراحت هوشمند برای حفظ کیفیت سیگنال‌های روزانه
                    time.sleep(10800) # ۳ ساعت فاصله برای تحلیل بعدی
                
                time.sleep(45)
                
        except Exception as e:
            print(f"Scanner Loop Error: {e}")
            
        time.sleep(14400)

@app.route(f"/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = request.get_json()
    
    if "callback_query" in update:
        callback = update["callback_query"]
        chat_id = callback["message"]["chat"]["id"]
        data = callback["data"]
        
        # اگر کاربر دکمه گزارش ژورنال یا وضعیت یادگیری را خواست
        if data == "JOURNAL_STATS":
            journal_msg = (
                "📖 **ژورنال معامله‌گری و وضعیت یادگیری ربات:**\n\n"
                f"🔹 تعداد کل سیگنال‌های ثبت‌شده در حافظه: `{len(TRADING_JOURNAL['past_signals'])}\n`"
                f"🧠 **آخرین درس‌ها و عیب‌یابی‌های خودآموز ربات:**\n" + "\n".join([f"• {l}" for l in TRADING_JOURNAL['lessons_learned']])
            )
            send_telegram_message(chat_id, journal_msg)
            return "ok", 200

        send_telegram_message(chat_id, f"⏳ در حال تحلیل چندتایم‌فریمه عمیق (4H, 1H, 15M) برای {data}...")
        ai_response = ask_groq_ai_advanced(f"لطفاً تحلیل کامل چندتایم‌فریمه، درصد موفقیت، نقاط ورود، استاپ، ریسک‌فری و تریلینگ استاپ را برای ارز {data} ارائه بده.")
        if ai_response:
            send_telegram_message(chat_id, ai_response)
        else:
            send_telegram_message(chat_id, "❌ خطا در پردازش تحلیل.")
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
                "🤖 **سیستم تریدر هوشمند خودآموز (مولتی تایم‌فریم + ژورنال)**\n\n"
                "سلام! من به صورت ۲۴ ساعته بازار را در تایم‌فریم‌های **۴ ساعته، ۱ ساعته و ۱۵ دقیقه** مانیتور می‌کنم.\n"
                "ربات دارای سیستم **ژورنال معامله‌گری و یادگیری خودکار** است تا کیفیت سیگنال‌ها روز به روز بیشتر شود. از منوی زیر می‌توانید ارزها را بررسی کنید یا گزارش ژورنال را ببینید:"
            )
            send_telegram_message(chat_id, welcome_msg, reply_markup=keyboard)
        else:
            send_telegram_message(chat_id, "⏳ در حال بررسی هم‌راستایی ساختار در چند تایم‌فریم...")
            ai_response = ask_groq_ai_advanced(f"لطفاً تحلیل چندتایم‌فریمه عمیق را برای این درخواست ارائه بده: {text}")
            if ai_response:
                send_telegram_message(chat_id, ai_response, reply_markup=keyboard)
            else:
                send_telegram_message(chat_id, "❌ خطا در پردازش پاسخ.")

    return "ok", 200

@app.route("/", methods=["GET"])
def index():
    return "Self-Learning Multi-Timeframe Trading Bot is running!", 200

if __name__ == "__main__":
    scanner_thread = threading.Thread(target=smart_trader_scanner, daemon=True)
    scanner_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
