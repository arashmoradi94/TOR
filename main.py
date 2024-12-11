import os
import sqlite3
import uuid
from datetime import datetime, timedelta

from dotenv import load_dotenv
from flask import Flask, request
import telebot
import requests
import pandas as pd
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Load environment variables
load_dotenv()

# Configuration
TOKEN = os.environ.get('TOKEN')
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID')
SUPPORT_EMAIL = "support@example.com"
SUPPORT_PHONE = "02112345678"
WHATSAPP = "09123456789"

# Validate token
if not TOKEN:
    raise ValueError("Telegram Bot TOKEN is not set correctly")

# Flask and Telebot setup
app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# Enhanced Database Initialization
def init_db():
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()

    # More comprehensive users table
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            phone_number TEXT,
            registered_at DATETIME,
            api_url TEXT,
            consumer_key TEXT,
            consumer_secret TEXT,
            trial_used BOOLEAN DEFAULT 0,
            trial_start_date DATETIME
        )
    ''')

    # Enhanced subscriptions table
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY,
            subscription_type TEXT,
            start_date DATETIME,
            end_date DATETIME,
            is_active BOOLEAN DEFAULT 1
        )
    ''')

    conn.commit()
    conn.close()

# Enhanced Start Command
@bot.message_handler(commands=['start'])
def start_command(message):
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    contact_button = telebot.types.KeyboardButton('اشتراک‌گذاری شماره تلفن', request_contact=True)
    markup.add(contact_button)

    welcome_text = (
        f"سلام {message.from_user.first_name}! 👋\n\n"
        "به ربات مدیریت محصولات خوش آمدید. برای شروع، لطفاً شماره تماس خود را با زدن دکمه اشتراک‌گذاری ارسال کنید. "
        "این اطلاعات برای احراز هویت و ارتباط با شما استفاده خواهد شد."
    )

    bot.reply_to(message, welcome_text, reply_markup=markup)

# Contact Handling with More Validation
@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    contact = message.contact
    chat_id = message.chat.id

    # Validate contact belongs to the user
    if contact.user_id != message.from_user.id:
        bot.reply_to(message, "❌ لطفاً شماره تلفن خودتان را ارسال کنید.")
        return

    # Store user information
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute(''' 
        INSERT OR REPLACE INTO users 
        (chat_id, first_name, last_name, phone_number, registered_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (chat_id, contact.first_name, contact.last_name, contact.phone_number, datetime.now()))
    conn.commit()
    conn.close()

    # Enhanced Main Menu
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        '🆓 تست پنج روزه رایگان',
        '💳 خرید اشتراک',
        '❓ سوالات متداول',
        '📞 ارتباط با پشتیبانی',
        '🌐 اتصال به سایت'
    )

    bot.reply_to(message, 'منوی اصلی:', reply_markup=markup)

# Free Trial with More Controls
def handle_free_trial(message):
    chat_id = message.chat.id
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    # Check if user has already used free trial
    cursor.execute('SELECT trial_used FROM users WHERE chat_id = ?', (chat_id,))
    result = cursor.fetchone()
    
    if result and result[0]:
        bot.reply_to(message, "❌ شما قبلاً از تست رایگان استفاده کرده‌اید.")
        conn.close()
        return

    # Generate unique trial code
    unique_id = str(uuid.uuid4())
    trial_start = datetime.now()
    
    # Update user's trial status
    cursor.execute('''
        UPDATE users 
        SET trial_used = 1, trial_start_date = ? 
        WHERE chat_id = ?
    ''', (trial_start, chat_id))
    conn.commit()
    conn.close()

    # Send trial details
    trial_text = (
        f"🎉 کد یکتای شما: {unique_id}\n"
        "✅ تست پنج روزه رایگان فعال شد.\n"
        f"📅 تاریخ شروع: {trial_start.strftime('%Y-%m-%d')}\n"
        "⏳ مدت اعتبار: 5 روز"
    )
    bot.reply_to(message, trial_text, parse_mode='Markdown')

    # Notify admin
    bot.send_message(
        chat_id=ADMIN_CHAT_ID, 
        text=f'درخواست تست رایگان از کاربر {message.from_user.id}\nکد یکتا: {unique_id}'
    )

# Subscription Management with Inline Buttons
def handle_subscription(message):
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("🌕 اشتراک یک ماهه", callback_data='sub_1month'),
        InlineKeyboardButton("🌗 اشتراک دو ماهه", callback_data='sub_2months')
    )
    markup.row(
        InlineKeyboardButton("🌖 اشتراک سه ماهه", callback_data='sub_3months'),
        InlineKeyboardButton("🌘 اشتراک شش ماهه", callback_data='sub_6months')
    )
    markup.row(InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data='main_menu'))

    bot.reply_to(
        message, 
        "لطفاً نوع اشتراک مورد نظر را انتخاب کنید:", 
        reply_markup=markup
    )

# Callback Query Handler for Subscriptions
@bot.callback_query_handler(func=lambda call: call.data.startswith('sub_'))
def subscription_callback(call):
    subscription_type = call.data.split('_')[1]
    # Add your payment/subscription logic here
    bot.answer_callback_query(
        call.id, 
        text=f"اشتراک {subscription_type} انتخاب شد. لطفاً منتظر راهنمای پرداخت باشید."
    )

# Enhanced FAQ with Inline Buttons
def handle_faq(message):
    markup = InlineKeyboardMarkup()
    faq_buttons = [
        InlineKeyboardButton("نحوه استفاده از ربات", callback_data='faq_usage'),
        InlineKeyboardButton("شرایط اشتراک رایگان", callback_data='faq_trial'),
        InlineKeyboardButton("نحوه خرید اشتراک", callback_data='faq_purchase'),
        InlineKeyboardButton("پشتیبانی و راهنمایی", callback_data='faq_support')
    ]
    
    # Add buttons to markup
    for button in faq_buttons:
        markup.row(button)
    
    bot.reply_to(message, "سوالات متداول را انتخاب کنید:", reply_markup=markup)

# More robust message handling
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    message_text = message.text
    handlers = {
        '🆓 تست پنج روزه رایگان': handle_free_trial,
        '💳 خرید اشتراک': handle_subscription,
        '❓ سوالات متداول': handle_faq,
        '📞 ارتباط با پشتیبانی': handle_support,
        '🌐 اتصال به سایت': handle_connect_to_site
    }
    
    handler = handlers.get(message_text)
    if handler:
        handler(message)
    else:
        bot.reply_to(message, "متوجه پیام شما نشدم. لطفاً از منوی اصلی استفاده کنید.")

# Support Information with Rich Formatting
def handle_support(message):
    support_text = (
        "🌟 راه‌های ارتباط با پشتیبانی:\n\n"
        f"📧 ایمیل: {SUPPORT_EMAIL}\n"
        f"☎️ تلفن: {SUPPORT_PHONE}\n"
        f"💬 واتساپ: {WHATSAPP}\n\n"
        "⏰ ساعات پاسخگویی: شنبه تا چهارشنبه 9 صبح تا 5 بعد از ظهر"
    )
    
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("ارسال ایمیل", url=f"mailto:{SUPPORT_EMAIL}"),
        InlineKeyboardButton("تماس تلفنی", url=f"tel:{SUPPORT_PHONE}")
    )
    
    bot.reply_to(message, support_text, reply_markup=markup)



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

    app.run(host="0.0.0.0", port=8080)
