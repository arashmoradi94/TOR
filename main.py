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

# بارگذاری متغیرهای محیطی
load_dotenv()

# تنظیمات اساسی
TOKEN = os.environ.get('TOKEN')
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID')

if not TOKEN:
    raise ValueError("توکن تلگرام تنظیم نشده است")

# ساخت اپلیکیشن فلسک
app = Flask(__name__)

# ساخت ربات تلگرام
bot = TeleBot(TOKEN)

DB_PATH = '/tmp/bot_database.db'

# تابع پیشرفته برای تست و اتصال به API
def test_woocommerce_api(api_url, consumer_key, consumer_secret):
    """
    تست اتصال به API ووکامرس با بررسی‌های دقیق
    """
    try:
        # ساخت پارامترهای احراز هویت
        params = {
            'consumer_key': consumer_key,
            'consumer_secret': consumer_secret
        }
        
        # کدگذاری پارامترها برای URL
        query_string = urllib.parse.urlencode(params)
        full_url = f"{api_url}/wp-json/wc/v3/products?{query_string}"
        
        # درخواست با اطلاعات کامل
        response = requests.get(
            full_url,
            timeout=10
        )
        
        # بررسی وضعیت درخواست
        if response.status_code == 200:
            products = response.json()
            return {
                'status': True, 
                'message': f'اتصال موفق. تعداد محصولات: {len(products)}',
                'products_count': len(products)
            }
        else:
            return {
                'status': False, 
                'message': f'خطا در اتصال. کد وضعیت: {response.status_code}',
                'error_details': response.text
            }
    
    except requests.exceptions.RequestException as e:
        return {
            'status': False, 
            'message': f'خطای اتصال: {str(e)}'
        }

# تنظیمات پایگاه داده
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

    # اتصال به پایگاه داده
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ذخیره یا بروزرسانی آدرس سایت
    cursor.execute('''
        INSERT OR REPLACE INTO users (chat_id, site_url) VALUES (?, ?)
    ''', (chat_id, api_url))
    conn.commit()
    conn.close()

    bot.reply_to(message, "آدرس سایت ذخیره شد. لطفاً Consumer Key را وارد کنید.")
    bot.register_next_step_handler(message, save_consumer_key)

def save_consumer_key(message):
    chat_id = message.chat.id
    consumer_key = message.text.strip()

    # اتصال به پایگاه داده
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ذخیره یا بروزرسانی Consumer Key
    cursor.execute('''
        INSERT OR REPLACE INTO users (chat_id, consumer_key) VALUES (?, ?)
    ''', (chat_id, consumer_key))
    conn.commit()
    conn.close()

    bot.reply_to(message, "Consumer Key ذخیره شد. لطفاً Consumer Secret را وارد کنید.")
    bot.register_next_step_handler(message, save_consumer_secret)

def save_consumer_secret(message):
    chat_id = message.chat.id
    consumer_secret = message.text.strip()

    # اتصال به پایگاه داده
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ذخیره یا بروزرسانی Consumer Secret
    cursor.execute('''
        INSERT OR REPLACE INTO users (chat_id, consumer_secret) VALUES (?, ?)
    ''', (chat_id, consumer_secret))
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
        products = []  # لیست محصولات
        page = 1  # شماره صفحه شروع

        while True:
            # پارامترهای درخواست
            params = {
                'consumer_key': consumer_key,
                'consumer_secret': consumer_secret,
                'per_page': 100,  # تعداد محصولات در هر صفحه
                'page': page      # شماره صفحه
            }
            
            # کدگذاری پارامترها
            query_string = urllib.parse.urlencode(params)
            full_url = f"{site_url}/wp-json/wc/v3/products?{query_string}"
            
            # درخواست محصولات
            response = requests.get(full_url)
            
            if response.status_code == 200:
                page_products = response.json()
                
                # اگر هیچ محصولی در صفحه نیست، حلقه را تمام می‌کنیم
                if not page_products:
                    break
                
                # افزودن محصولات صفحه به لیست
                products.extend(page_products)
                
                # اگر تعداد محصولات کمتر از `per_page` باشد، به این معنی است که دیگر صفحه‌ای برای بارگذاری وجود ندارد
                if len(page_products) < 100:
                    break

                page += 1
            else:
                bot.send_message(chat_id, f"خطا در دریافت صفحه {page}: {response.status_code}")
                break
        
        # تبدیل محصولات به دیتافریم
        df = pd.DataFrame([ 
            {
                "شناسه": p['id'],
                "نام محصول": p['name'],
                "قیمت": p['price'],
                "موجودی": p.get('stock_quantity', 'نامشخص')
            } for p in products
        ])
        
        # ذخیره در اکسل
        excel_path = f"/tmp/products_{chat_id}.xlsx"
        df.to_excel(excel_path, index=False, encoding='utf-8')
        
        # ارسال فایل
        with open(excel_path, 'rb') as file:
            bot.send_document(chat_id, file, caption="لیست محصولات")
    
    except Exception as e:
        bot.send_message(chat_id, f"خطای سیستمی: {str(e)}")


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
