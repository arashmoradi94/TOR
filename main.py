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

# [Previous helper functions remain the same: test_woocommerce_api, init_db]

# متغیرهای جهانی برای نگهداری اطلاعات موقت
user_product_cache = {}

def test_woocommerce_api(api_url, consumer_key, consumer_secret):
    # [Previous implementation remains the same]
    pass

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

# دستورات قبلی مثل start_command و handle_contact و غیره

# تابع نمایش محصولات به صورت دکمه
def show_products_as_buttons(chat_id, products):
    # محدود کردن تعداد محصولات به 20 عدد برای جلوگیری از محدودیت تلگرام
    products = products[:20]
    
    # ایجاد صفحه‌بندی برای محصولات
    markup = telebot.types.InlineKeyboardMarkup()
    
    for product in products:
        # ایجاد دکمه برای هر محصول با نام و شناسه
        button = telebot.types.InlineKeyboardButton(
            text=f"{product['name']} (قیمت: {product['price']} تومان)", 
            callback_data=f"product_{product['id']}"
        )
        markup.add(button)
    
    bot.send_message(chat_id, "لیست محصولات:", reply_markup=markup)

# هندلر دریافت محصولات با نمایش دکمه‌ای
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
            
            # کش کردن محصولات برای استفاده بعدی
            user_product_cache[chat_id] = {
                p['id']: p for p in products
            }
            
            # نمایش محصولات به صورت دکمه
            show_products_as_buttons(chat_id, products)
        
        else:
            bot.send_message(chat_id, f"خطا در دریافت محصولات. کد وضعیت: {response.status_code}")
    
    except Exception as e:
        bot.send_message(chat_id, f"خطای سیستمی: {str(e)}")

# هندلر انتخاب محصول و دریافت قیمت جدید
@bot.callback_query_handler(func=lambda call: call.data.startswith('product_'))
def product_selected(call):
    chat_id = call.message.chat.id
    product_id = int(call.data.split('_')[1])
    
    # بررسی وجود محصول در کش
    if chat_id not in user_product_cache or product_id not in user_product_cache[chat_id]:
        bot.answer_callback_query(call.id, "محصول مورد نظر یافت نشد.")
        return
    
    product = user_product_cache[chat_id][product_id]
    
    # ارسال اطلاعات محصول
    message = (f"محصول انتخابی: {product['name']}\n"
               f"قیمت فعلی: {product['price']} تومان\n"
               "لطفاً قیمت جدید را وارد کنید:")
    
    # ذخیره اطلاعات محصول در حافظه موقت برای مرحله بعدی
    user_product_cache[chat_id]['selected_product'] = product_id
    
    bot.send_message(chat_id, message)

# هندلر دریافت قیمت جدید و تأیید
@bot.message_handler(func=lambda message: True)
def handle_new_price(message):
    chat_id = message.chat.id
    
    # بررسی اینکه آیا کاربر قبلاً محصولی را انتخاب کرده است
    if (chat_id in user_product_cache and 
        'selected_product' in user_product_cache[chat_id]):
        
        try:
            new_price = float(message.text.replace(',', ''))
            product_id = user_product_cache[chat_id]['selected_product']
            
            # ایجاد markup برای تأیید
            markup = telebot.types.InlineKeyboardMarkup()
            confirm_button = telebot.types.InlineKeyboardButton(
                "تأیید", callback_data=f"confirm_{product_id}_{new_price}"
            )
            cancel_button = telebot.types.InlineKeyboardButton(
                "انصراف", callback_data="cancel_update"
            )
            markup.row(confirm_button, cancel_button)
            
            bot.send_message(
                chat_id, 
                f"آیا مطمئن هستید قیمت به {new_price} تومان تغییر کند؟",
                reply_markup=markup
            )
        
        except ValueError:
            bot.reply_to(message, "لطفاً یک عدد معتبر وارد کنید.")

# هندلر تأیید یا لغو آپدیت قیمت
@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_') or call.data == 'cancel_update')
def confirm_price_update(call):
    chat_id = call.message.chat.id
    
    if call.data == 'cancel_update':
        bot.answer_callback_query(call.id, "عملیات لغو شد.")
        bot.delete_message(chat_id, call.message.message_id)
        return
    
    # استخراج اطلاعات از callback_data
    _, product_id, new_price = call.data.split('_')
    
    # بازیابی اطلاعات اتصال به WooCommerce
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT site_url, consumer_key, consumer_secret FROM users WHERE chat_id = ?', (chat_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user or not all(user):
        bot.answer_callback_query(call.id, "اطلاعات اتصال یافت نشد.")
        return
    
    site_url, consumer_key, consumer_secret = user
    
    try:
        # آپدیت قیمت محصول
        params = {
            'consumer_key': consumer_key,
            'consumer_secret': consumer_secret
        }
        
        # درخواست آپدیت محصول
        update_url = f"{site_url}/wp-json/wc/v3/products/{product_id}"
        update_data = {
            "price": str(new_price)
        }
        
        response = requests.put(
            update_url, 
            params=params, 
            json=update_data
        )
        
        if response.status_code in [200, 201]:
            bot.answer_callback_query(call.id, "قیمت با موفقیت به‌روز شد.")
            bot.delete_message(chat_id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, f"خطا در به‌روزرسانی. کد وضعیت: {response.status_code}")
    
    except Exception as e:
        bot.answer_callback_query(call.id, f"خطای سیستمی: {str(e)}")

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
