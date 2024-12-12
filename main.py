import os
import urllib.parse
from dotenv import load_dotenv
from flask import Flask, request
import telebot
from telebot import TeleBot
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import requests
import pandas as pd
import urllib.parse
from telebot import types

# بارگذاری متغیرهای محیطی
load_dotenv()

# تنظیمات
TOKEN = os.getenv('TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')  # مثال: postgresql://username:password@host:port/database

if not TOKEN or not DATABASE_URL:
    raise ValueError("توکن تلگرام یا URL دیتابیس تنظیم نشده است")

# تنظیم SQLAlchemy
Base = declarative_base()
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

# مدل کاربر
class User(Base):
    __tablename__ = 'users'
    
    chat_id = Column(Integer, primary_key=True)
    first_name = Column(String)
    last_name = Column(String)
    phone_number = Column(String)
    registered_at = Column(DateTime, default=datetime.now)
    site_url = Column(String)
    consumer_key = Column(String)
    consumer_secret = Column(String)

# ایجاد جداول
Base.metadata.create_all(engine)

app = Flask(__name__)
bot = TeleBot(TOKEN)

# دستور شروع
@bot.message_handler(commands=['start'])
def start_command(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    contact_button = types.KeyboardButton('اشتراک‌گذاری شماره تلفن', request_contact=True)
    markup.add(contact_button)
    
    bot.reply_to(message, 
                 f"سلام {message.from_user.first_name}، خوش آمدید! لطفاً شماره تماس خود را ارسال کنید.", 
                 reply_markup=markup)

# دریافت شماره تماس
@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    contact = message.contact
    chat_id = message.chat.id

    # ایجاد جلسه SQLAlchemy
    session = Session()

    # بررسی اینکه آیا کاربر قبلاً ثبت شده است
    existing_user = session.query(User).filter_by(chat_id=chat_id).first()
    
    if existing_user:
        # بروزرسانی اطلاعات موجود
        existing_user.first_name = contact.first_name
        existing_user.last_name = contact.last_name
        existing_user.phone_number = contact.phone_number
    else:
        # ایجاد کاربر جدید
        new_user = User(
            chat_id=chat_id,
            first_name=contact.first_name,
            last_name=contact.last_name,
            phone_number=contact.phone_number,
            registered_at=datetime.now()
        )
        session.add(new_user)

    # ذخیره تغییرات
    session.commit()
    session.close()

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('اتصال به سایت', 'دریافت محصولات به اکسل')
    bot.reply_to(message, 'منوی اصلی:', reply_markup=markup)

# اتصال به سایت
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

    # ایجاد جلسه و بروزرسانی
    session = Session()
    user = session.query(User).filter_by(chat_id=chat_id).first()
    
    if user:
        user.site_url = site_url
        session.commit()
        session.close()

        bot.reply_to(message, "آدرس سایت ذخیره شد. لطفاً Consumer Key را وارد کنید.")
        bot.register_next_step_handler(message, save_consumer_key)
    else:
        bot.reply_to(message, "ابتدا باید شماره تماس خود را ارسال کنید.")

def save_consumer_key(message):
    chat_id = message.chat.id
    consumer_key = message.text.strip()

    # ایجاد جلسه و بروزرسانی
    session = Session()
    user = session.query(User).filter_by(chat_id=chat_id).first()
    
    if user:
        user.consumer_key = consumer_key
        session.commit()
        session.close()

        bot.reply_to(message, "Consumer Key ذخیره شد. لطفاً Consumer Secret را وارد کنید.")
        bot.register_next_step_handler(message, save_consumer_secret)
    else:
        bot.reply_to(message, "ابتدا باید شماره تماس خود را ارسال کنید.")

def save_consumer_secret(message):
    chat_id = message.chat.id
    consumer_secret = message.text.strip()

    # ایجاد جلسه و بروزرسانی
    session = Session()
    user = session.query(User).filter_by(chat_id=chat_id).first()
    
    if user:
        user.consumer_secret = consumer_secret
        session.commit()
        session.close()

        bot.reply_to(message, "Consumer Secret ذخیره شد. اطلاعات اتصال کامل شد.")
    else:
        bot.reply_to(message, "ابتدا باید شماره تماس خود را ارسال کنید.")

# دریافت محصولات به اکسل
@bot.message_handler(func=lambda message: message.text == 'دریافت محصولات به اکسل')
def export_products_to_excel(message):
    chat_id = message.chat.id

    # بازیابی اطلاعات کاربر
    session = Session()
    user = session.query(User).filter_by(chat_id=chat_id).first()
    session.close()

    if not user or not all([user.site_url, user.consumer_key, user.consumer_secret]):
        bot.reply_to(message, "ابتدا اطلاعات اتصال به سایت را وارد کنید.")
        return

    # باقی کد قبلی برای دریافت و ذخیره محصولات به اکسل...

# بقیه تنظیمات وب‌هوک و اجرای اصلی مثل قبل

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url='tor-production.up.railway.app/' + TOKEN)
    app.run(host="0.0.0.0", port=8080)
