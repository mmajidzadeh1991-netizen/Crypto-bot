from flask import Flask
import threading
import bot  # فایل اصلی ربات شما

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

if __name__ == "__main__":
    # اجرای ربات در پشت صحنه (Thread جداگانه)
    t = threading.Thread(target=lambda: None) # ربات اصلی خودش حلقه دارد
    # اجرای وب سرور پایتون برای فریب دادن رندر
    app.run(host="0.0.0.0", port=10000)
