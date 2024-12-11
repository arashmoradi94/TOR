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
            registered_at DATETIME,
            api_url TEXT,
            api_key TEXT
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
        handle_connect_to_site(message)


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
    markup.row('منوی اصلی')

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



# ذخیره‌سازی آدرس سایت
def handle_connect_to_site(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("منوی اصلی")

    bot.reply_to(message, "لطفاً آدرس سایت خود را وارد کنید (مثلاً: https://yoursite.com):", reply_markup=markup)
    bot.register_next_step_handler(message, save_site_url)

def save_site_url(message):
    chat_id = message.chat.id
    api_url = message.text.strip()

    conn = sqlite3.connect('bot_database.db')
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

    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute(''' 
        UPDATE users SET api_key_public = ? WHERE chat_id = ?
    ''', (customer_key, chat_id))
    conn.commit()
    conn.close()

    bot.reply_to(message, "Customer Key ذخیره شد. لطفاً Secret Key را وارد کنید.")
    bot.register_next_step_handler(message, save_secret_key)

    def save_secret_key(message):
    chat_id = message.chat.id
    secret_key = message.text.strip()

    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute(''' 
        UPDATE users SET api_key_secret = ? WHERE chat_id = ?
    ''', (secret_key, chat_id))
    conn.commit()
    conn.close()

    bot.reply_to(message, "Secret Key ذخیره شد. حالا در حال بررسی اتصال به سایت هستیم...")

    # بررسی اتصال
    test_api_connection(chat_id)

def test_api_connection(chat_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT api_url, api_key_public, api_key_secret FROM users WHERE chat_id = ?', (chat_id,))
    user = cursor.fetchone()
    conn.close()

    if not user or not user[0] or not user[1] or not user[2]:
        bot.reply_to(chat_id, "اطلاعات ناقص است. لطفاً دوباره تلاش کنید.")
        return

    api_url, customer_key, secret_key = user

    try:
        response = requests.get(f"{api_url}/wp-json/wc/v3/products", auth=(customer_key, secret_key))
        if response.status_code == 200:
            bot.reply_to(chat_id, "اتصال به سایت با موفقیت برقرار شد.")

            # منوی محصولات
            markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("دریافت لیست محصولات", "منوی اصلی")
            bot.reply_to(chat_id, "اکنون می‌توانید لیست محصولات را دریافت کنید.", reply_markup=markup)
        else:
            raise Exception("خطا در اعتبارسنجی اطلاعات API.")
    except Exception as e:
        bot.reply_to(chat_id, "اتصال برقرار نشد. لطفاً اطلاعات وارد شده را بررسی کنید و دوباره امتحان کنید.")


@bot.message_handler(func=lambda message: message.text == 'دریافت لیست محصولات')
def handle_get_products(message):
    chat_id = message.chat.id

    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT api_url, api_key_public, api_key_secret FROM users WHERE chat_id = ?', (chat_id,))
    user = cursor.fetchone()
    conn.close()

    if not user or not user[0] or not user[1] or not user[2]:
        bot.reply_to(chat_id, "ابتدا باید اطلاعات اتصال به سایت را وارد کنید.")
        return

    api_url, customer_key, secret_key = user

    try:
        # ارسال پیام ساعت شنی برای اطلاع از پردازش
        loading_message = bot.reply_to(message, "⏳")

        # دریافت محصولات از API
        response = requests.get(f"{api_url}/wp-json/wc/v3/products", auth=(customer_key, secret_key))
        if response.status_code != 200:
            raise Exception("خطا در دریافت لیست محصولات.")

        products = response.json()
        product_list = []

        # ساخت دیتافریم از محصولات
        for product in products:
            product_list.append({
                "ID": product['id'],
                "Name": product['name'],
                "Stock": product.get('stock_quantity', 'نامشخص'),
                "Price": product['price']
            })

        df = pd.DataFrame(product_list)
        excel_file_path = "/tmp/products.xlsx"
        df.to_excel(excel_file_path, index=False)

        # حذف پیام ساعت شنی پس از آماده شدن اکسل
        bot.delete_message(message.chat.id, loading_message.message_id)

        # ارسال فایل اکسل به کاربر
        with open(excel_file_path, 'rb') as file:
            bot.send_document(message.chat.id, file, caption="لیست محصولات سایت شما")
    except Exception as e:
        bot.reply_to(chat_id, f"خطا: {e}")


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
