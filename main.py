import os
from dotenv import load_dotenv
from flask import Flask, request
from telebot import TeleBot
import telebot
import sqlite3
from datetime import datetime
import uuid
import requests
import pandas as pd

load_dotenv()

# تنظیمات اساسی
TOKEN = os.environ.get('TOKEN')  # توکن ربات تلگرام
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID')  # آیدی چت ادمین

if not TOKEN:
    raise ValueError("TOKEN is not set correctly")  # اگر TOKEN خالی است، خطا می‌دهد

print("Token loaded:", TOKEN)  # برای بررسی مقدار TOKEN

# ساخت اپلیکیشن فلسک برای نگه داشتن ربات در حالت آنلاین در ریپلیت
app = Flask(__name__)

# ساخت ربات تلگرام
bot = TeleBot(TOKEN)

# تنظیمات پایگاه داده
def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()

    # جدول اطلاعات سایت وردپرس
    cursor.execute('''CREATE TABLE IF NOT EXISTS wordpress_info (
        id INTEGER PRIMARY KEY,
        url TEXT,
        consumer_key TEXT,
        consumer_secret TEXT
    )''')

    # جدول کاربران
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        phone_number TEXT,
        registered_at DATETIME
    )''')

    conn.commit()
    conn.close()

# دریافت اطلاعات وردپرس از پایگاه داده
def get_wordpress_info():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM wordpress_info LIMIT 1")
    wordpress_info = cursor.fetchone()
    conn.close()
    return wordpress_info

# ذخیره اطلاعات وردپرس در پایگاه داده
def save_wordpress_info(url, consumer_key, consumer_secret):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO wordpress_info (url, consumer_key, consumer_secret) VALUES (?, ?, ?)", (url, consumer_key, consumer_secret))
    conn.commit()
    conn.close()

# دریافت محصولات از API وردپرس
def get_products_from_wordpress():
    wordpress_info = get_wordpress_info()
    if wordpress_info:
        url = wordpress_info[1] + '/wp-json/wc/v3/products'
        auth = (wordpress_info[2], wordpress_info[3])  # استفاده از Consumer Key و Consumer Secret
        
        response = requests.get(url, auth=auth)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    return None

# ساخت فایل اکسل
def create_excel_file(products):
    data = {'Name': [], 'Price': []}
    for product in products:
        data['Name'].append(product['name'])
        data['Price'].append(product['price'])
    
    df = pd.DataFrame(data)
    df.to_excel('products_list.xlsx', index=False)

# ارسال فایل اکسل به کاربر
@bot.message_handler(commands=['get_products'])
def send_products_list(message):
    products = get_products_from_wordpress()
    if products:
        create_excel_file(products)
        with open('products_list.xlsx', 'rb') as file:
            bot.send_document(message.chat.id, file)
    else:
        bot.send_message(message.chat.id, 'متاسفانه نتوانستم محصولات را دریافت کنم.')

# دستور اتصال به سایت
@bot.message_handler(commands=['connect_to_site'])
def connect_to_site(message):
    msg = bot.reply_to(message, "لطفاً آدرس سایت وردپرس خود را وارد کنید:")
    bot.register_next_step_handler(msg, get_url)

# دریافت آدرس سایت وردپرس
def get_url(message):
    url = message.text
    msg = bot.reply_to(message, "لطفاً Consumer Key سایت وردپرس خود را وارد کنید:")
    bot.register_next_step_handler(msg, get_consumer_key, url)

# دریافت Consumer Key
def get_consumer_key(message, url):
    consumer_key = message.text
    msg = bot.reply_to(message, "لطفاً Consumer Secret سایت وردپرس خود را وارد کنید:")
    bot.register_next_step_handler(msg, get_consumer_secret, url, consumer_key)

# دریافت Consumer Secret
def get_consumer_secret(message, url, consumer_key):
    consumer_secret = message.text
    save_wordpress_info(url, consumer_key, consumer_secret)
    
    # ارسال پیام به کاربر برای نشان دادن دکمه "دریافت لیست محصولات"
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('دریافت لیست محصولات')
    markup.row('منوی اصلی')  # دکمه منوی اصلی
    bot.reply_to(message, "اطلاعات سایت شما با موفقیت ذخیره شد. حالا می‌توانید لیست محصولات را دریافت کنید.", reply_markup=markup)

# دستور شروع
@bot.message_handler(commands=['start'])
def start_command(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    contact_button = telebot.types.KeyboardButton('اشتراک‌گذاری شماره تلفن', request_contact=True)
    markup.add(contact_button, connect_button)

    bot.reply_to(message, 
        f"سلام {message.from_user.first_name}! به ربات ما خوش آمدید.\n"
        "لطفاً شماره تماس خود را با زدن دکمه اشتراک‌گذاری شماره ارسال کنید.\n"
        reply_markup=markup
    )

# هندل کردن دریافت شماره تماس
@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    contact = message.contact
    chat_id = message.chat.id

    # ذخیره اطلاعات کاربر در پایگاه داده
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''INSERT OR REPLACE INTO users 
        (chat_id, first_name, last_name, phone_number, registered_at)
        VALUES (?, ?, ?, ?, ?)''', (chat_id, contact.first_name, contact.last_name, contact.phone_number, datetime.now()))
    conn.commit()
    conn.close()

    # منوی اصلی
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('تست پنج روزه رایگان')
    markup.row('خرید اشتراک')
    markup.row('سوالات متداول', 'ارتباط با پشتیبانی')
    markup.row('اتصال به سایت')

    bot.reply_to(message, 'منوی اصلی:', reply_markup=markup)

# هندل کردن پیام‌های متنی
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.text == 'تست پنج روزه رایگان':
        handle_free_trial(message)
    elif message.text == 'خرید اشتراک':
        handle_subscription(message)
    elif message.text == 'سوالات متداول':
        handle_faq(message)
    elif message.text == 'ارتباط با پشتیبانی':
        handle_support(message)
    elif message.text == 'اتصال به سایت':
        connect_to_site(message)
    elif message.text == 'منوی اصلی':
        start_command(message)  # برگشت به منوی اصلی
    elif message.text == 'دریافت لیست محصولات':
        send_products_list(message)

# مدیریت تست رایگان
def handle_free_trial(message):
    unique_id = str(uuid.uuid4())
    bot.reply_to(message, f'کد یکتای شما: {unique_id}')

    # ارسال به ادمین
    bot.send_message(
        chat_id=ADMIN_CHAT_ID, 
        text=f'درخواست تست رایگان از کاربر {message.from_user.id}\nکد یکتا: {unique_id}'
    )

# مدیریت اشتراک‌ها
def handle_subscription(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('اشتراک یک ماهه', 'اشتراک دو ماهه')
    markup.row('اشتراک سه ماهه', 'اشتراک شش ماهه')
    markup.row('منوی اصلی')  # دکمه منوی اصلی

    bot.reply_to(message, 'لطفاً نوع اشتراک مورد نظر را انتخاب کنید:', reply_markup=markup)

# مدیریت سوالات متداول
def handle_faq(message):
    faq_text = """
سوالات متداول:

1. نحوه استفاده از ربات
2. شرایط اشتراک رایگان
3. نحوه خرید اشتراک
4. پشتیبانی و راهنمایی

برای اطلاعات بیشتر با پشتیبانی تماس بگیرید.
"""
    bot.reply_to(message, faq_text)

# مدیریت ارتباط با پشتیبانی
def handle_support(message):
    support_text = """
راه‌های ارتباط با پشتیبانی:

ایمیل: support@example.com
تلفن: 02112345678
واتساپ: 09123456789

ساعات پاسخگویی: شنبه تا چهارشنبه 9 صبح تا 5 بعد از ظهر
"""
    bot.reply_to(message, support_text)

# روت برای نگه داشتن ربات آنلاین در ریپلیت
@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def home():
    return "ربات تلگرام آنلاین است", 200

# اجرای اسکریپت
if __name__ == "__main__":
    # راه‌اندازی پایگاه داده
    init_db()

    # تنظیم وب‌هوک
    bot.remove_webhook()
    bot.set_webhook(url='tor-production.up.railway.app/' + TOKEN)

    # اجرای سرور فلسک
    app.run(host='0.0.0.0', port=8080)
