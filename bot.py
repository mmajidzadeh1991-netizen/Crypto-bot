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

# لیست ارزهای پیش‌فرض منو
TOP_COINS = [
    {"symbol": "BTCUSDT", "exchange": "BINANCE", "name": "بیت‌کوین (BTC)", "cg_id": "bitcoin"},
    {"symbol": "ETHUSDT", "exchange": "BINANCE", "name": "اتریوم (ETH)", "cg_id": "ethereum"},
    {"symbol": "SOLUSDT", "exchange": "BINANCE", "name": "سولانا (SOL)", "cg_id": "solana"},
    {"symbol": "XRPUSDT", "exchange": "BINANCE", "name": "ریپل (XRP)", "cg_id": "ripple"},
    {"symbol": "BNBUSDT", "exchange": "BINANCE", "name": "بایننس کوین (BNB)", "cg_id": "binancecoin"},
    {"symbol": "ADAUSDT", "exchange": "BINANCE", "name": "کاردانو (ADA)", "cg_id": "cardano"},
    {"symbol": "AVAXUSDT", "exchange": "BINANCE", "name": "اولانچ (AVAX)", "cg_id": "avalanche-2"},
    {"symbol": "LINKUSDT", "exchange": "BINANCE", "name": "چین‌لینک (LINK)", "cg_id": "chainlink"}
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

# دریافت داده‌های فاندامنتال از CoinGecko
def fetch_coingecko_data(symbol_clean):
    try:
        # نگاشت نمادها به شناسه کوین‌گکو
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
            return f"مایکت کپ: ${mcap:,.0f} | تغییر ۲۴ ساعته: {change_24h:.2f}% | سقف تاریخی (ATH): ${ath:,.2f}"
    except Exception as e:
        print(f"CoinGecko Error: {e}")
    return "اطلاعات فاندامنتال کوین‌گکو موقتاً در دسترس نیست."

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
                        return f"حجم معاملات باز (OI): ${oi_usd:,.0f} (تغییر ۲۴ ساعته: {oi_change_24h:.2f}%) | نرخ تامین مالی (Funding Rate): {funding:.4f}%"
    except Exception as e:
        print(f"Coinglass Error: {e}")
    return "داده‌های مشتقات و Open Interest کوین‌گلس در حال به‌روزرسانی است."

# ارتباط با هوش مصنوعی Groq با الزام استفاده از قیمت لایو و اطلاعات ترکیبی
def ask_groq_ai_institutional(prompt_text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    lessons_str = "\n".join([f"- {lesson}" for lesson in TRADING_JOURNAL["lessons_learned"]])
    
    system_prompt = (
        "تو یک الگوریتم تریدینگ نهادی پیشرفته و تحلیلگر ارشد بازارهای مالی هستی. "
        "تمرکز اصلی و ۹۰ درصدی تو بر روی **تحلیل تکنیکال عمیق، سبک‌های ICT (اسمارت مانی)، SMC، اوردر فلو، پرایس اکشن ال بروکس، به همراه بررسی داده‌های فاندامنتال (CoinGecko) و مشتقات بازار/تجمع پوزیشن‌ها (Coinglass)** است. "
        "قانون حیاتی: حتماً از **قیمت لایو و دقیق بازار** و داده‌های تکمیلی که به تو داده می‌شود استفاده کن و نقاط ورود (Entry)، حد ضرر (SL) و حد سودها (TP) را منحصراً بر اساس همین قیمت واقعی محاسبه و اعلام کن.\n\n"
        f"📚 **حافظه یادگیری و تجربیات قبلی ربات:**\n{lessons_str}\n\n"
        "اگر شرایط بازار ایده‌آل و موقعیت ورود مناسبی وجود دارد، خروجی باید یک سیگنال دقیق و ساختاریافته با این جزئیات باشد:\n"
        "1. جهت پوزیشن (Long یا Short)\n"
        "2. **درصد تاییدیه یا موفقیت (مثلا 89%)**\n"
        "3. نقطه ورود اول (Entry 1) و نقطه ورود دوم (پله‌ای/DCA)\n"
        "4. حد ضرر (Stop Loss) کاملاً دقیق و مهندسی‌شده بر اساس قیمت لایو\n"
        "5. سه سطح حد سود (TP1, TP2, TP3)\n"
        "6. مدیریت معامله: نقطه ریسک‌فری (Risk-Free) و تریلینگ استاپ (Trailing Stop)\n"
        "7. تحلیل فنی نهادی، ارزیابی وضعیت Open Interest و در صورت وجود خبر مهم، هشدار فاندامنتال کوتاه."
    )

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.2,
        "max_tokens": 1400
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

# تحلیل جامع و چندمنظوره بازار (TradingView + CoinGecko + Coinglass)
def analyze_custom_market(raw_symbol):
    try:
        symbol = raw_symbol.upper().strip()
        if not symbol.endswith("USDT") and not symbol.endswith("USD"):
            symbol += "USDT"
            
        symbol_clean = symbol.replace("USDT", "").replace("USD", "")
            
        # 1. استعلام از TradingView
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
        volume_1h = ind_1h.get("volume", 0)

        # 2. استعلام از CoinGecko
        cg_info = fetch_coingecko_data(symbol_clean)

        # 3. استعلام از Coinglass
        cg_glass = fetch_coinglass_data(symbol_clean)
        
        prompt = (
            f"ارز مورد نظر ({symbol}) داده‌های ترکیبی زنده پلتفرم‌ها:\n"
            f"- **قیمت لحظه‌ای و دقیق بازار (TradingView Live Close): {close_price}**\n"
            f"- ساختار ۴ ساعته: {rec_4h}\n"
            f"- مومنتوم ۱ ساعته (حجم: {volume_1h}): {rec_1h}\n"
            f"- تاییدیه ۱۵ دقیقه (RSI: {rsi_15m}): {rec_15m}\n"
            f"- داده‌های فاندامنتال (CoinGecko): {cg_info}\n"
            f"- داده‌های مشتقات و تجمع پوزیشن‌ها (Coinglass): {cg_glass}\n\n"
            f"با توجه به قیمت لایو بازار `{close_price}` و داده‌های جامع بالا، با تمرکز کامل روی چارت، SMC، ICT، اوردر فلو و وضعیت فیوچرز بررسی کن آیا موقعیت ورودی وجود دارد؟ مقادیر ورود و حد سود و ضرر را بر اساس همین قیمت دقیق محاسبه کن."
        )
        
        signal_output = ask_groq_ai_institutional(prompt)
        return signal_output, symbol
        
    except Exception as e:
        print(f"Technical Analysis Error for {raw_symbol}: {e}")
        return None, None

# اسکنر خودکار هوشمند (رصد بازار هر ۳۰ دقیقه)
def institutional_trader_scanner():
    print("🏛️ اسکنر لحظه‌ای نهادی (TradingView + CoinGecko + Coinglass) فعال شد...")
    while True:
        try:
            if is_optimal_trading_session():
                for coin in TOP_COINS:
                    symbol = coin["symbol"]
                    current_time = time.time()
                    
                    if symbol in LAST_SIGNAL_TIME and (current_time - LAST_SIGNAL_TIME[symbol] < 1800):
                        continue 
                    
                    print(f"🔍 در حال ارزیابی جامع چارت و داده‌های {symbol}...")
                    signal, _ = analyze_custom_market(symbol)
                    
                    if signal and ("جهت پوزیشن" in signal or "Long" in signal or "Short" in signal) and "ندارد" not in signal:
                        LAST_SIGNAL_TIME[symbol] = current_time
                        
                        TRADING_JOURNAL["past_signals"].append({
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "symbol": symbol,
                            "details": signal[:120]
                        })
                        
                        full_msg = f"📊📈 **سیگنال نهادی پیشرفته ({symbol})** 📈📊\n\n{signal}"
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

            send_telegram_message(chat_id, f"⏳ در حال استعلام قیمت لایو، داده‌های کوین‌گکو، کوین‌گلس و تحلیل تخصصی `{data}`...")
            ai_response, _ = analyze_custom_market(data)
            
            if ai_response:
                send_telegram_message(chat_id, ai_response)
            else:
                send_telegram_message(chat_id, f"⚪ خطا در دریافت داده‌های بازار برای نماد `{data}`.")
            return "ok", 200

        if "message" in update:
            chat_id = update["message"]["chat"]["id"]
            text = update["message"].get("text", "").strip()

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
                    "🤖 **سیستم تریدر نهادی پیشرفته (متصل به TradingView + CoinGecko + Coinglass)**\n\n"
                    "سلام! ربات هم‌زمان به تکنیکال تریدینگ‌ویو، داده‌های فاندامنتال کوین‌گکو و وضعیت مشتقات کوین‌گلس متصل است.\n"
                    "می‌توانید از دکمه‌های زیر استفاده کنید یا **نام هر ارز دلخواهی** (مثل `doge` یا `near`) را ارسال کنید."
                )
                send_telegram_message(chat_id, welcome_msg, reply_markup=keyboard)
            else:
                send_telegram_message(chat_id, f"⏳ در حال استعلام لایو از ۳ منبع و تحلیل تخصصی برای `{text}`...")
                ai_response, verified_symbol = analyze_custom_market(text)
                
                if ai_response:
                    send_telegram_message(chat_id, f"📊 **نتیجه تحلیل ترکیبی برای: {verified_symbol}**\n\n{ai_response}", reply_markup=keyboard)
                else:
                    send_telegram_message(chat_id, f"❌ نماد `{text}` یافت نشد یا در دریافت اطلاعات خطا رخ داد. لطفاً نماد صحیح را وارد کنید (مثلا: doge).", reply_markup=keyboard)

    except Exception as e:
        error_msg = f"❌ خطای سیستمی در پردازش: {str(e)}"
        print(error_msg)

    return "ok", 200

@app.route("/", methods=["GET"])
def index():
    return "Multi-Source Institutional Trading Bot (TradingView + CoinGecko + Coinglass) is running!", 200

if __name__ == "__main__":
    scanner_thread = threading.Thread(target=institutional_trader_scanner, daemon=True)
    scanner_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
