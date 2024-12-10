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

    # جدول کاربران
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            phone_number TEXT,
            registered_at DATETIME
        )
    ''')

    # جدول اشتراک‌ها
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER,
            subscription_type TEXT,
            start_date DATETIME,
            end_date DATETIME
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

# هندل کردن دریافت شماره تماس
@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    contact = message.contact
    chat_id = message.chat.id

    # ذخیره اطلاعات کاربر در پایگاه داده
    conn = sqlite3.connect('bot_database.db')
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
    markup.row('تست پنج روزه رایگان')
    markup.row('خرید اشتراک')
    markup.row('سوالات متداول', 'ارتباط با پشتیبانی')

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
    bot.set_webhook(url='telebot-production-526c.up.railway.app/' + TOKEN)

    # اجرای سرور فلسک
    app.run(host='0.0.0.0', port=8080)
