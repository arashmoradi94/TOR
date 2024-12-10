import os
from dotenv import load_dotenv
from flask import Flask, request
import telebot
import sqlite3
from datetime import datetime
import uuid

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
        markup.row('🆓 تست پنج روزه رایگان', '💳 خرید اشتراک')
        markup.row('❓ سوالات متداول', '📞 ارتباط با پشتیبانی')
        bot.reply_to(message, 'منوی اصلی:', reply_markup=markup)
    else:
        bot.reply_to(message, "سلام! لطفاً نام و نام خانوادگی خود را وارد کنید.")
        bot.register_next_step_handler(message, handle_name)

def handle_name(message):
    chat_id = message.chat.id
    user_name = message.text
    bot.reply_to(message, "لطفاً شماره تلفن خود را وارد کنید.")
    bot.register_next_step_handler(message, handle_phone, user_name)

def handle_phone(message, user_name):
    chat_id = message.chat.id
    phone_number = message.text

    first_name, last_name = user_name.split(" ", 1)  # فرض بر این است که نام و نام خانوادگی با یک فاصله وارد شده‌اند
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users 
        (chat_id, first_name, last_name, phone_number, registered_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (chat_id, first_name, last_name, phone_number, datetime.now()))
    conn.commit()
    conn.close()

    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('🆓 تست پنج روزه رایگان', '💳 خرید اشتراک')
    markup.row('❓ سوالات متداول', '📞 ارتباط با پشتیبانی')
    bot.reply_to(message, 'منوی اصلی:', reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.text == '🆓 تست پنج روزه رایگان':
        handle_free_trial(message)
    elif message.text == '💳 خرید اشتراک':
        handle_subscription(message)
    elif message.text == '❓ سوالات متداول':
        handle_faq(message)
    elif message.text == '📞 ارتباط با پشتیبانی':
        handle_support(message)

def handle_free_trial(message):
    unique_id = str(uuid.uuid4())
    bot.reply_to(message, f'کد یکتای شما: {unique_id}')
    bot.send_message(chat_id=ADMIN_CHAT_ID, text=f'درخواست تست رایگان از کاربر {message.from_user.id}\nکد یکتا: {unique_id}')

def handle_subscription(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('📝 اشتراک یک ماهه', '📝 اشتراک دو ماهه')
    markup.row('📝 اشتراک سه ماهه', '📝 اشتراک شش ماهه')
    markup.row('🔙 منوی اصلی')
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

@bot.message_handler(func=lambda message: message.text == '🔙 منوی اصلی')
def go_to_main_menu(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('🆓 تست پنج روزه رایگان', '💳 خرید اشتراک')
    markup.row('❓ سوالات متداول', '📞 ارتباط با پشتیبانی')
    bot.reply_to(message, 'منوی اصلی:', reply_markup=markup)

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
    app.run(host='0.0.0.0', port=8080)
