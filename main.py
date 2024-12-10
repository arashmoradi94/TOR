import os
from dotenv import load_dotenv
from flask import Flask, request
import telebot
import sqlite3
from datetime import datetime
import uuid
import pandas as pd

load_dotenv()
TOKEN = os.environ.get('TOKEN')  # توکن ربات تلگرام
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID')  # آیدی چت ادمین

if not TOKEN:
    raise ValueError("TOKEN is not set correctly")

print("Token loaded:", TOKEN)

app = Flask(__name__)

bot = telebot.TeleBot(TOKEN)

def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            phone_number TEXT,
            registered_at DATETIME
        )
    ''')

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

@bot.message_handler(commands=['start'])
def start_command(message):
    chat_id = message.chat.id
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,))
    user = cursor.fetchone()
    conn.close()

    if user:
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row('تست پنج روزه رایگان', 'خرید اشتراک')
        markup.row('سوالات متداول', 'ارتباط با پشتیبانی', 'نمایش لیست مشتری‌ها')
        bot.reply_to(message, 'منوی اصلی:', reply_markup=markup)
    else:
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        contact_button = telebot.types.KeyboardButton('اشتراک‌گذاری شماره تلفن', request_contact=True)
        markup.add(contact_button)
        bot.reply_to(message, f"سلام {message.from_user.first_name}! به ربات ما خوش آمدید.\n"
                              "لطفاً شماره تماس خود را با زدن دکمه اشتراک‌گذاری شماره ارسال کنید.",
                      reply_markup=markup)

@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    contact = message.contact
    chat_id = message.chat.id

    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users 
        (chat_id, first_name, last_name, phone_number, registered_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (chat_id, contact.first_name, contact.last_name, contact.phone_number, datetime.now()))
    conn.commit()
    conn.close()

    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('تست پنج روزه رایگان', 'خرید اشتراک')
    markup.row('سوالات متداول', 'ارتباط با پشتیبانی', 'نمایش لیست مشتری‌ها')
    bot.reply_to(message, 'منوی اصلی:', reply_markup=markup)

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
    elif message.text == 'نمایش لیست مشتری‌ها':
        send_users_list(message)

def handle_free_trial(message):
    unique_id = str(uuid.uuid4())
    bot.reply_to(message, f'کد یکتای شما: {unique_id}')
    bot.send_message(chat_id=ADMIN_CHAT_ID, text=f'درخواست تست رایگان از کاربر {message.from_user.id}\nکد یکتا: {unique_id}')

def handle_subscription(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('اشتراک یک ماهه', 'اشتراک دو ماهه')
    markup.row('اشتراک سه ماهه', 'اشتراک شش ماهه')
    bot.reply_to(message, 'لطفاً نوع اشتراک مورد نظر را انتخاب کنید:', reply_markup=markup)

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

def handle_support(message):
    support_text = """
راه‌های ارتباط با پشتیبانی:

ایمیل: support@example.com
تلفن: 02112345678
واتساپ: 09123456789

ساعات پاسخگویی: شنبه تا چهارشنبه 9 صبح تا 5 بعد از ظهر
"""
    bot.reply_to(message, support_text)

def send_users_list(message):
    if message.chat.id != int(ADMIN_CHAT_ID):
        bot.reply_to(message, "این دستور فقط برای ادمین قابل دسترسی است.")
        return

    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT first_name, last_name, phone_number, registered_at FROM users")
    users = cursor.fetchall()
    conn.close()

    # ساخت DataFrame از کاربران
    df = pd.DataFrame(users, columns=["First Name", "Last Name", "Phone Number", "Registered At"])

    # ذخیره فایل اکسل
    file_path = '/tmp/users_list.xlsx'
    df.to_excel(file_path, index=False)

    # ارسال فایل به ادمین
    bot.send_document(ADMIN_CHAT_ID, open(file_path, 'rb'))

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
    bot.set_webhook(url='tor-production.up.railway.app/.com/' + TOKEN)
    app.run(host='0.0.0.0', port=8080)
