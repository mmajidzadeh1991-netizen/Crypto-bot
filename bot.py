import os
import requests
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = "8905848713:AAGrGzm8vqX1_ZGh9C7mmIPO0dRM430x1bA"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")


def ask_groq(prompt):
  if not GROQ_API_KEY:
    return "خطا: کلید هوش مصنوعی GROQ_API_KEY در متغیرهای محیطی هاست تنظیم نشده است!"

  url = "https://api.groq.com/openai/v1/chat/completions"
  headers = {
      "Authorization": f"Bearer {GROQ_API_KEY}",
      "Content-Type": "application/json",
  }
  payload = {
      "model": "llama-3.3-70b-versatile",
      "messages": [{"role": "user", "content": prompt}],
      "temperature": 0.7,
  }

  try:
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    if response.status_code == 200:
      res_json = response.json()
      content = res_json["choices"][0]["message"]["content"]
      return content
    else:
      return (
          f"خطای سرور گروق (کد {response.status_code}): {response.text}"
      )
  except Exception as e:
    return f"خطای ارتباط با هوش مصنوعی: {str(e)}"


@app.route(f"/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
  data = request.get_json()
  if data and "message" in data:
    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "")

    if text.startswith("/start"):
      reply_text = (
          "سلام! ربات تحلیلگر بازار با موفقیت فعال شد. پیام خود را بفرستید:"
      )
    else:
      # ارسال پیام کاربر به هوش مصنوعی گروق
      reply_text = ask_groq(text)

    # ارسال پاسخ به تلگرام
    send_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(
        send_url, json={"chat_id": chat_id, "text": reply_text}, timeout=10
    )

  return "OK", 200


@app.route("/")
def index():
  return "Bot is running successfully!", 200


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port)
