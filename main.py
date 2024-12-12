import os
import hashlib
from dotenv import load_dotenv
from flask import Flask, request
import telebot
from telebot import TeleBot
import sqlite3
from datetime import datetime
import requests
import pandas as pd
import json
import urllib.parse
from telebot import types
from datetime import datetime

# بارگذاری متغیرهای محیطی
load_dotenv()

# تنظیمات
TOKEN = os.getenv('TOKEN')
if not TOKEN:
    raise ValueError("توکن تلگرام تنظیم نشده است")

DB_PATH = '/tmp/bot_database.db'

app = Flask(__name__)
bot = TeleBot(TOKEN)

# تابع ایجاد پایگاه داده
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            phone_number TEXT,
            registered_at DATETIME,
            site_url TEXT,
            consumer_key TEXT,
            consumer_secret TEXT
        )
    ''')
    conn.commit()
    conn.close()

# دستورات ربات
@bot.message_handler(commands=['start'])
def start_command(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    contact_button = types.KeyboardButton('اشتراک‌گذاری شماره تلفن', request_contact=True)
    markup.add(contact_button)
    bot.reply_to(message, 
                 f"سلام {message.from_user.first_name}، خوش آمدید! لطفاً شماره تماس خود را ارسال کنید.", 
                 reply_markup=markup)

@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    contact = message.contact
    chat_id = message.chat.id

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users 
        (chat_id, first_name, last_name, phone_number, registered_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (chat_id, contact.first_name, contact.last_name, contact.phone_number, datetime.now()))
    conn.commit()
    conn.close()

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('اتصال به سایت', 'دریافت محصولات به اکسل')
    bot.reply_to(message, 'منوی اصلی:', reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == 'اتصال به سایت')
def connect_to_site(message):
    bot.reply_to(message, "لطفاً آدرس سایت خود را وارد کنید:")
    bot.register_next_step_handler(message, save_site_url)

def save_site_url(message):
    chat_id = message.chat.id
    site_url = message.text.strip()

    if not site_url.startswith("http"):
        bot.reply_to(message, "آدرس سایت معتبر نیست. دوباره تلاش کنید.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET site_url = ? WHERE chat_id = ?", (site_url, chat_id))
    conn.commit()
    conn.close()

    bot.reply_to(message, "آدرس سایت ذخیره شد. لطفاً Consumer Key را وارد کنید.")
    bot.register_next_step_handler(message, save_consumer_key)

def save_consumer_key(message):
    chat_id = message.chat.id
    consumer_key = message.text.strip()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET consumer_key = ? WHERE chat_id = ?", (consumer_key, chat_id))
    conn.commit()
    conn.close()

    bot.reply_to(message, "Consumer Key ذخیره شد. لطفاً Consumer Secret را وارد کنید.")
    bot.register_next_step_handler(message, save_consumer_secret)

def save_consumer_secret(message):
    chat_id = message.chat.id
    consumer_secret = message.text.strip()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET consumer_secret = ? WHERE chat_id = ?", (consumer_secret, chat_id))
    conn.commit()
    conn.close()

    bot.reply_to(message, "Consumer Secret ذخیره شد. اطلاعات اتصال کامل شد.")

@bot.message_handler(func=lambda message: message.text == 'دریافت محصولات به اکسل')
def export_products_to_excel(message):
    chat_id = message.chat.id

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT site_url, consumer_key, consumer_secret FROM users WHERE chat_id = ?", (chat_id,))
    user = cursor.fetchone()
    conn.close()

    if not user or not all(user):
        bot.reply_to(message, "ابتدا اطلاعات اتصال به سایت را وارد کنید.")
        return

    site_url, consumer_key, consumer_secret = user
    try:
        params = {'consumer_key': consumer_key, 'consumer_secret': consumer_secret}
        query_string = urllib.parse.urlencode(params)
        full_url = f"{site_url}/wp-json/wc/v3/products?{query_string}"
        response = requests.get(full_url)

        if response.status_code == 200:
            products = response.json()

            data = [{
                'ID': product['id'],
                'Name': product['name'],
                'Price': product['price'],
                'Stock': product.get('stock_quantity', 'N/A')
            } for product in products]
            df = pd.DataFrame(data)

            file_path = '/tmp/products.xlsx'
            df.to_excel(file_path, index=False)

            with open(file_path, 'rb') as file:
                bot.send_document(chat_id, file)
        else:
            bot.reply_to(message, f"خطا در دریافت محصولات. کد وضعیت: {response.status_code}")

    except Exception as e:
        bot.reply_to(message, f"خطای سیستمی: {str(e)}")

# وب‌هوک
@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def home():
    return "ربات فعال است!", 200

import sqlite3
from flask import Flask

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('database.db')  # اتصال به دیتابیس
    cur = conn.cursor()
    # ایجاد جدول در دیتابیس
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            phone_number TEXT,
            registered_at DATETIME,
            site_url TEXT,
            consumer_key TEXT,
            consumer_secret TEXT
        )
    ''')
    conn.commit()
    conn.close()

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

# دریافت شماره تماس
@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    contact = message.contact
    chat_id = message.chat.id

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(''' 
        INSERT OR REPLACE INTO users 
        (chat_id, first_name, last_name, phone_number, registered_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (chat_id, contact.first_name, contact.last_name, contact.phone_number, datetime.now()))
    conn.commit()
    conn.close()

    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('اتصال به سایت', 'دریافت لیست محصولات')
    bot.reply_to(message, 'منوی اصلی:', reply_markup=markup)

# اتصال به سایت
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
        UPDATE users SET site_url = ? WHERE chat_id = ? 
    ''', (api_url, chat_id))
    conn.commit()
    conn.close()

    bot.reply_to(message, "آدرس سایت ذخیره شد. لطفاً Consumer Key را وارد کنید.")
    bot.register_next_step_handler(message, save_consumer_key)

def save_consumer_key(message):
    chat_id = message.chat.id
    consumer_key = message.text.strip()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(''' 
        UPDATE users SET consumer_key = ? WHERE chat_id = ? 
    ''', (consumer_key, chat_id))
    conn.commit()
    conn.close()

    bot.reply_to(message, "Consumer Key ذخیره شد. لطفاً Consumer Secret را وارد کنید.")
    bot.register_next_step_handler(message, save_consumer_secret)

def save_consumer_secret(message):
    chat_id = message.chat.id
    consumer_secret = message.text.strip()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(''' 
        UPDATE users SET consumer_secret = ? WHERE chat_id = ? 
    ''', (consumer_secret, chat_id))
    conn.commit()
    conn.close()

    bot.reply_to(message, "Consumer Secret ذخیره شد. در حال بررسی اتصال...")
    test_connection(chat_id)

def test_connection(chat_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT site_url, consumer_key, consumer_secret FROM users WHERE chat_id = ?', (chat_id,))
    user = cursor.fetchone()
    conn.close()

    if not user or not all(user):
        bot.send_message(chat_id, "اطلاعات ناقص است. لطفاً مجدداً تلاش کنید.")
        return

    site_url, consumer_key, consumer_secret = user
    
    # تست اتصال با تابع اختصاصی
    result = test_woocommerce_api(site_url, consumer_key, consumer_secret)
    
    if result['status']:
        bot.send_message(chat_id, result['message'])
    else:
        bot.send_message(chat_id, f"خطا در اتصال: {result['message']}")

# دریافت محصولات
@bot.message_handler(func=lambda message: message.text == 'دریافت لیست محصولات')
def handle_get_products(message):
    chat_id = message.chat.id

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT site_url, consumer_key, consumer_secret FROM users WHERE chat_id = ?', (chat_id,))
    user = cursor.fetchone()
    conn.close()

    if not user or not all(user):
        bot.reply_to(message, "ابتدا باید اطلاعات اتصال به سایت را وارد کنید.")
        return

    site_url, consumer_key, consumer_secret = user
    
    try:
        # پارامترهای درخواست
        params = {
            'consumer_key': consumer_key,
            'consumer_secret': consumer_secret
        }
        
        # کدگذاری پارامترها
        query_string = urllib.parse.urlencode(params)
        full_url = f"{site_url}/wp-json/wc/v3/products?{query_string}"
        
        # درخواست محصولات
        response = requests.get(full_url)
        
        if response.status_code == 200:
            products = response.json()
            
            # نمایش محصولات به صورت دکمه‌ها
            markup = telebot.types.InlineKeyboardMarkup()
            for product in products:
                button = telebot.types.InlineKeyboardButton(f"{product['name']} - {product['price']} USD", callback_data=f"edit_{product['id']}")
                markup.add(button)

            bot.send_message(chat_id, "لیست محصولات:", reply_markup=markup)
        
        else:
            bot.send_message(chat_id, f"خطا در دریافت محصولات. کد وضعیت: {response.status_code}")
    
    except Exception as e:
        bot.send_message(chat_id, f"خطای سیستمی: {str(e)}")

# هنگامی که کاربر روی یک محصول کلیک می‌کند
@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def handle_edit_product(call):
    chat_id = call.message.chat.id
    product_id = int(call.data.split('_')[1])

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT site_url, consumer_key, consumer_secret FROM users WHERE chat_id = ?', (chat_id,))
    user = cursor.fetchone()
    conn.close()

    if not user or not all(user):
        bot.send_message(chat_id, "اطلاعات اتصال به سایت ناقص است.")
        return

    site_url, consumer_key, consumer_secret = user
    
    # دریافت اطلاعات محصول
    full_url = f"{site_url}/wp-json/wc/v3/products/{product_id}?consumer_key={consumer_key}&consumer_secret={consumer_secret}"
    response = requests.get(full_url)

    if response.status_code == 200:
        product = response.json()
        bot.send_message(chat_id, f"قیمت فعلی محصول '{product['name']}' برابر است با: {product['price']}\nلطفاً قیمت جدید را وارد کنید:")
        bot.register_next_step_handler(call.message, handle_new_price, product)
    else:
        bot.send_message(chat_id, "خطا در دریافت اطلاعات محصول.")

# دریافت قیمت جدید و بروزرسانی آن
def handle_new_price(message, product):
    chat_id = message.chat.id
    new_price = message.text.strip()

    site_url, consumer_key, consumer_secret = get_user_site_info(chat_id)

    if not site_url or not consumer_key or not consumer_secret:
        bot.send_message(chat_id, "اطلاعات اتصال به سایت ناقص است.")
        return

    # بروزرسانی قیمت محصول از طریق API
    product_data = {
        'regular_price': new_price
    }

    product_url = f"{site_url}/wp-json/wc/v3/products/{product['id']}?consumer_key={consumer_key}&consumer_secret={consumer_secret}"
    response = requests.put(product_url, json=product_data)

    if response.status_code == 200:
        bot.send_message(chat_id, f"قیمت محصول '{product['name']}' به {new_price} تغییر کرد.")
    else:
        bot.send_message(chat_id, f"خطا در به‌روزرسانی قیمت: {response.status_code} - {response.text}")

# روت‌های وب
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
