import os
import hashlib
from dotenv import load_dotenv
from flask import Flask, request
import telebot  # اضافه کردن این خط
from telebot import TeleBot  # وارد کردن TeleBot از telebot
import sqlite3
from datetime import datetime
import requests
import pandas as pd
import json
from requests.auth import HTTPBasicAuth  # برای استفاده از احراز هویت پایه

load_dotenv()

# تنظیمات اساسی
TOKEN = os.environ.get('TOKEN')  # توکن ربات تلگرام
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID')

if not TOKEN:
    raise ValueError("TOKEN is not set correctly")

# ساخت اپلیکیشن فلسک
app = Flask(__name__)

# ساخت ربات تلگرام
bot = TeleBot(TOKEN)

DB_PATH = '/tmp/bot_database.db'

# تنظیمات پایگاه داده
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # جدول کاربران
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            phone_number TEXT,
            registered_at DATETIME,
            api_url TEXT,
            api_key_public TEXT,
            api_key_secret TEXT
        )
    ''')

    conn.commit()
    conn.close()

# رمزنگاری کلیدها برای امنیت
def encrypt_key(key):
    return hashlib.sha256(key.encode()).hexdigest()

# دستور شروع
@bot.message_handler(commands=['start'])
def start_command(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    contact_button = telebot.types.KeyboardButton('اشتراک‌گذاری شماره تلفن', request_contact=True)
    markup.add(contact_button)

    bot.reply_to(message, 
        f"سلام {message.from_user.first_name}! به ربات ما خوش آمدید.\n"
        "لطفاً شماره تماس خود را با زدن دکمه اشتراک‌گذاری شماره ارسال کنید.", 
        reply_markup=markup
    )

# هندل کردن دریافت شماره تماس
@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    contact = message.contact
    chat_id = message.chat.id

    # ذخیره اطلاعات کاربر در پایگاه داده
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(''' 
        INSERT OR REPLACE INTO users 
        (chat_id, first_name, last_name, phone_number, registered_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (chat_id, contact.first_name, contact.last_name, contact.phone_number, datetime.now()))
    conn.commit()
    conn.close()

    # منوی اصلی
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('اتصال به سایت', 'دریافت لیست محصولات')
    bot.reply_to(message, 'منوی اصلی:', reply_markup=markup)

# ذخیره‌سازی آدرس سایت
@bot.message_handler(func=lambda message: message.text == 'اتصال به سایت')
def handle_connect_to_site(message):
    bot.reply_to(message, "لطفاً آدرس سایت خود را وارد کنید (مثلاً: https://yoursite.com):")
    bot.register_next_step_handler(message, save_site_url)

def save_site_url(message):
    chat_id = message.chat.id
    api_url = message.text.strip()

    if not api_url.startswith("http"):
        bot.reply_to(message, "آدرس سایت معتبر نیست. لطفاً دوباره وارد کنید.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(''' 
        UPDATE users SET api_url = ? WHERE chat_id = ? 
    ''', (api_url, chat_id))
    conn.commit()
    conn.close()

    bot.reply_to(message, "آدرس سایت ذخیره شد. لطفاً Customer Key را وارد کنید.")
    bot.register_next_step_handler(message, save_customer_key)

def save_customer_key(message):
    chat_id = message.chat.id
    customer_key = message.text.strip()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(''' 
        UPDATE users SET api_key_public = ? WHERE chat_id = ? 
    ''', (encrypt_key(customer_key), chat_id))
    conn.commit()
    conn.close()

    bot.reply_to(message, "Customer Key ذخیره شد. لطفاً Secret Key را وارد کنید.")
    bot.register_next_step_handler(message, save_secret_key)

def save_secret_key(message):
    chat_id = message.chat.id
    secret_key = message.text.strip()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(''' 
        UPDATE users SET api_key_secret = ? WHERE chat_id = ? 
    ''', (encrypt_key(secret_key), chat_id))
    conn.commit()
    conn.close()

    bot.reply_to(message, "Secret Key ذخیره شد. حالا در حال بررسی اتصال به سایت هستیم...")
    test_api_connection(chat_id)

def test_api_connection(chat_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT api_url, api_key_public, api_key_secret FROM users WHERE chat_id = ?', (chat_id,))
    user = cursor.fetchone()
    conn.close()

    if not user or not user[0] or not user[1] or not user[2]:
        bot.send_message(chat_id, "اطلاعات ناقص است. لطفاً دوباره تلاش کنید.")
        return

    api_url, customer_key, secret_key = user

    try:
        # استفاده از احراز هویت به شکل صحیح
        response = requests.get(f"{api_url}/wp-json/wc/v3/products", auth=HTTPBasicAuth(customer_key, secret_key), timeout=500)
        if response.status_code == 200:
            bot.send_message(chat_id, "اتصال به سایت با موفقیت برقرار شد.")
        else:
            bot.send_message(chat_id, "اتصال برقرار نشد. کد خطا: " + str(response.status_code))
    except Exception as e:
        bot.send_message(chat_id, f"خطا در اتصال: {str(e)}")

# دریافت لیست محصولات و ارسال به اکسل
@bot.message_handler(func=lambda message: message.text == 'دریافت لیست محصولات')
def handle_get_products(message):
    chat_id = message.chat.id

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT api_url, api_key_public, api_key_secret FROM users WHERE chat_id = ?', (chat_id,))
    user = cursor.fetchone()
    conn.close()

    if not user or not user[0] or not user[1] or not user[2]:
        bot.reply_to(message, "ابتدا باید اطلاعات اتصال به سایت را وارد کنید.")
        return

    api_url, customer_key, secret_key = user
    products = []

    try:
        page = 1
        while True:
            # درخواست برای دریافت محصولات
            response = requests.get(f"{api_url}/wp-json/wc/v3/products?page={page}&per_page=50", auth=HTTPBasicAuth(customer_key, secret_key))
            if response.status_code != 200:
                raise Exception("خطا در دریافت محصولات.")

            page_products = response.json()
            if not page_products:
                break

            products.extend(page_products)
            page += 1

        product_list = [
            {
                "ID": product['id'],
                "Name": product['name'],
                "Stock": product.get('stock_quantity', 'نامشخص'),
                "Price": product['price']
            } for product in products
        ]

        df = pd.DataFrame(product_list)
        excel_file_path = "/tmp/products.xlsx"
        df.to_excel(excel_file_path, index=False)

        with open(excel_file_path, 'rb') as file:
            bot.send_document(chat_id, file, caption="لیست محصولات سایت شما")

    except Exception as e:
        bot.reply_to(message, f"خطا: {e}")

# روت برای نگه داشتن ربات آنلاین
@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def home():
    return "ربات تلگرام آنلاین است", 200

if __name__ == "__main__":
    init_db()
    bot.remove_webhook()
    bot.set_webhook(url='tor-production.up.railway.app/' + TOKEN)
    app.run(host="0.0.0.0", port=8080)
