import os
import logging
from typing import Optional
from functools import wraps
import urllib.parse
from dotenv import load_dotenv
from flask import Flask, request
import telebot
from telebot import TeleBot
import pymysql
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
import hashlib
from telebot import types
import pandas as pd
from io import BytesIO

pymysql.install_as_MySQLdb() 

# بارگذاری متغیرهای محیطی از فایل .env
load_dotenv()

# پیکربندی لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# دریافت اطلاعات از متغیرهای محیطی
TOKEN = os.getenv('TOKEN')
MYSQL_USER = os.getenv('MYSQL_USER')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD')
MYSQL_HOST = os.getenv('MYSQL_HOST')
MYSQL_PORT = os.getenv('MYSQL_PORT')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE')

# بررسی متغیرهای ضروری
if not all([TOKEN, MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE]):
    raise ValueError("توکن یا اطلاعات دیتابیس تنظیم نشده است")

# ساخت آدرس اتصال به دیتابیس MySQL
DATABASE_URL = os.getenv('MYSQL_URL')

# تنظیمات SQLAlchemy
Base = declarative_base()
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)


# مدل کاربر
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone_number = Column(String(20))
    site_url = Column(String(255))
    consumer_key = Column(Text)
    consumer_secret = Column(Text)
    registration_date = Column(DateTime, default=datetime.now)
    last_activity = Column(DateTime, default=datetime.now)
    status = Column(String(20), default='active')

# ایجاد جداول
Base.metadata.create_all(engine)

# تنظیمات فلاسک و تلگرام
app = Flask(__name__)
bot = TeleBot(TOKEN)

# دکوراتور مدیریت خطا
def error_handler(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"خطا در {func.__name__}: {str(e)}")
            try:
                bot.send_message(
                    args[0].chat.id, 
                    "❌ متأسفانه خطایی رخ داده است. لطفاً دوباره تلاش کنید."
                )
            except:
                pass
    return wrapper

# محدودیت درخواست‌ها
request_count = {}
def rate_limit(limit=5, per=60):
    def decorator(func):
        @wraps(func)
        def wrapper(message):
            chat_id = message.chat.id
            current_time = datetime.now()
            
            if chat_id not in request_count:
                request_count[chat_id] = []
            
            request_count[chat_id] = [
                t for t in request_count[chat_id] 
                if (current_time - t).total_seconds() < per
            ]
            
            if len(request_count[chat_id]) >= limit:
                bot.reply_to(message, "⏳ تعداد درخواست‌های شما بیش از حد مجاز است.")
                return
            
            request_count[chat_id].append(current_time)
            return func(message)
        return wrapper
    return decorator

# توابع کمکی
def secure_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()

def validate_url(url):
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

# هندلرهای اصلی ربات
@bot.message_handler(commands=['start'])
@error_handler
def start_command(message):
    bot.reply_to(
        message, 
        f"👋 سلام {message.from_user.first_name}! لطفاً نام خود را وارد کنید.",
        reply_markup=types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(message, get_first_name)

def get_first_name(message):
    first_name = message.text.strip()
    bot.reply_to(
        message, 
        "🏷️ نام خانوادگی خود را وارد کنید."
    )
    bot.register_next_step_handler(message, get_last_name, first_name)

def get_last_name(message, first_name):
    last_name = message.text.strip()
    
    # ارسال دکمه اشتراک‌گذاری شماره تلفن
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    contact_button = types.KeyboardButton('🔖 اشتراک‌گذاری شماره تلفن', request_contact=True)
    markup.add(contact_button)
    
    bot.reply_to(
        message, 
        f"👤 نام شما: {first_name} {last_name}\n"
        "لطفاً شماره تماس خود را ارسال کنید.",
        reply_markup=markup
    )
    
    # ذخیره نام و نام خانوادگی در سشن برای مرحله بعد
    bot.register_next_step_handler(message, handle_contact, first_name, last_name)

@bot.message_handler(content_types=['contact'])
@error_handler
def handle_contact(message, first_name=None, last_name=None):
    contact = message.contact
    chat_id = message.chat.id

    session = Session()
    
    try:
        # بررسی یا ایجاد کاربر
        user = session.query(User).filter_by(chat_id=chat_id).first()
        
        if not user:
            user = User(
                chat_id=chat_id,
                username=message.from_user.username,
                first_name=first_name or contact.first_name,
                last_name=last_name or contact.last_name,
                phone_number=contact.phone_number
            )
            session.add(user)
        else:
            user.first_name = first_name or user.first_name
            user.last_name = last_name or user.last_name
            user.phone_number = contact.phone_number
            user.last_activity = datetime.now()
        
        session.commit()
        
        # منوی اصلی
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row('👤 پروفایل', '🌐 اتصال به سایت')
        markup.row('📦 دریافت محصولات', '🛍️ محصولات')
        markup.row('❓ راهنما')
        
        bot.reply_to(
            message, 
            '✅ ثبت نام شما با موفقیت انجام شد! لطفاً یک گزینه را انتخاب کنید.',
            reply_markup=markup
        )
    
    except Exception as e:
        session.rollback()  # اصلاح شده
        logger.error(f"خطا در ذخیره کاربر: {str(e)}")
        bot.reply_to(message, "❌ متأسفانه خطایی در ذخیره اطلاعات شما رخ داده است.")
    
    finally:
        session.close()

# نمایش پروفایل کاربر
@bot.message_handler(func=lambda message: message.text == '👤 پروفایل')
@error_handler
def show_profile(message):
    chat_id = message.chat.id
    session = Session()
    
    user = session.query(User).filter_by(chat_id=chat_id).first()
    
    if user:
        profile_info = (
            f"👤 نام: {user.first_name} {user.last_name}\n"
            f"📞 شماره تماس: {user.phone_number}\n"
            f"🌐 آدرس سایت: {user.site_url or 'تنظیم نشده'}\n"
            f"🔑 Consumer Key: {user.consumer_key or 'تنظیم نشده'}\n"
            f"🔒 Consumer Secret: {user.consumer_secret or 'تنظیم نشده'}\n"
            f"📅 تاریخ ثبت نام: {user.registration_date.strftime('%Y-%m-%d')}\n"
        )
        bot.reply_to(message, profile_info)
    else:
        bot.reply_to(message, "❌ اطلاعات پروفایل شما موجود نیست.")
    
    session.close()

# اتصال به سایت
@bot.message_handler(func=lambda message: message.text == '🌐 اتصال به سایت')
@error_handler
def connect_to_site(message):
    bot.reply_to(message, "لطفاً آدرس سایت خود را وارد کنید:")
    bot.register_next_step_handler(message, save_site_url)

def save_site_url(message):
    chat_id = message.chat.id
    site_url = message.text.strip()

    if not validate_url(site_url):
        bot.reply_to(message, "❌ آدرس سایت معتبر نیست. دوباره تلاش کنید.")
        return

    session = Session()
    user = session.query(User).filter_by(chat_id=chat_id).first()
    
    if user:
        user.site_url = site_url
        session.commit()
        bot.reply_to(message, "✅ آدرس سایت ذخیره شد. لطفاً Consumer Key را وارد کنید.")
        bot.register_next_step_handler(message, save_consumer_key)
    else:
        bot.reply_to(message, "❌ ابتدا باید شماره تماس خود را ارسال کنید.")
    
    session.close()

def save_consumer_key(message):
    chat_id = message.chat.id
    consumer_key = message.text.strip()

    session = Session()
    user = session.query(User).filter_by(chat_id=chat_id).first()
    
    if user:
        user.consumer_key = consumer_key
        session.commit()
        bot .reply_to(message, "✅ Consumer Key ذخیره شد. لطفاً Consumer Secret را وارد کنید.")
        bot.register_next_step_handler(message, save_consumer_secret)
    else:
        bot.reply_to(message, "❌ ابتدا باید شماره تماس خود را ارسال کنید.")
    
    session.close()

def save_consumer_secret(message):
    chat_id = message.chat.id
    consumer_secret = message.text.strip()

    session = Session()
    user = session.query(User).filter_by(chat_id=chat_id).first()
    
    if user:
        user.consumer_secret = consumer_secret
        session.commit()
        bot.reply_to(message, "✅ Consumer Secret ذخیره شد. اطلاعات اتصال کامل شد.")
    else:
        bot.reply_to(message, "❌ ابتدا باید شماره تماس خود را ارسال کنید.")
    
    session.close()

# دریافت محصولات
import pandas as pd
from io import BytesIO

@bot.message_handler(func=lambda message: message.text == '📦 دریافت محصولات')
@error_handler
def export_products_to_excel(message):
    chat_id = message.chat.id

    # ابتدا بررسی می‌کنیم که کاربر اطلاعات اتصال به سایت را وارد کرده باشد
    session = Session()
    user = session.query(User).filter_by(chat_id=chat_id).first()
    
    if not user or not all([user.site_url, user.consumer_key, user.consumer_secret]):
        bot.reply_to(message, "❌ ابتدا اطلاعات اتصال به سایت را وارد کنید.")
        session.close()  # بستن سشن دیتابیس
        return

    # نمایش پیام در حال دریافت محصولات
    bot.reply_to(message, "📊 در حال دریافت محصولات...")

    # فرض می‌کنیم که مدل Product به درستی تعریف شده است
    products = session.query(Product).all()
    session.close()  # بستن سشن دیتابیس

    if not products:
        bot.reply_to(message, "❌ هیچ محصولی در سیستم موجود نیست.")
        return
    
    # ساخت داده‌ها برای تبدیل به DataFrame
    product_data = []
    for product in products:
        product_data.append({
            "شناسه محصول": product.id,
            "نام محصول": product.name,
            "قیمت": product.price,
            "موجودی": product.stock,
            "اطلاعات": product.info,
        })
    
    # تبدیل داده‌ها به DataFrame
    df = pd.DataFrame(product_data)
    
    # ایجاد فایل Excel در حافظه
    excel_file = BytesIO()
    df.to_excel(excel_file, index=False, engine='openpyxl')
    excel_file.seek(0)  # بازگشت به ابتدای فایل برای ارسال
    
    # ارسال فایل به کاربر
    bot.send_document(chat_id, excel_file, caption="📊 لیست محصولات")




# راهنمای ربات
@bot.message_handler(func=lambda message: message.text == '❓ راهنما')
@error_handler
def help_command(message):
    help_text = (
        "📚 راهنمای استفاده از ربات:\n"
        "1. برای شروع، نام و نام خانوادگی خود را وارد کنید.\n"
        "2. شماره تماس خود را به اشتراک بگذارید.\n"
        "3. اطلاعات اتصال به سایت را وارد کنید.\n"
        "4. از منوی اصلی، گزینه‌های مختلف را انتخاب کنید."
    )
    bot.reply_to(message, help_text)

#دریافت محصولات 
@bot.message_handler(func=lambda message: message.text == '🛍️ محصولات')
@error_handler
def product_handler(message):
    bot.reply_to(message, "🆔 لطفاً شناسه محصول را وارد کنید:", reply_markup=main_menu_markup())
    bot.register_next_step_handler(message, search_product_by_id)

def search_product_by_id(message):
    product_id = message.text.strip()

    session = Session()
    product = session.query(Product).filter_by(id=product_id).first()
    session.close()

    if product:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row('💰 تغییر قیمت', '📦 تغییر موجودی')
        markup.row('✏️ تغییر نام و اطلاعات', '❌ حذف محصول')
        markup.row('🔙 بازگشت به منوی اصلی')

        bot.reply_to(
            message,
            f"✅ محصول یافت شد:\n"
            f"🆔 شناسه: {product.id}\n"
            f"📛 نام: {product.name}\n"
            f"💰 قیمت: {product.price}\n"
            f"📦 موجودی: {product.stock}\n",
            reply_markup=markup
        )
        bot.register_next_step_handler(message, product_action_handler, product)
    else:
        bot.reply_to(message, "❌ محصولی با این شناسه یافت نشد.", reply_markup=main_menu_markup())

def product_action_handler(message, product):
    action = message.text.strip()

    if action == '💰 تغییر قیمت':
        bot.reply_to(message, "💰 لطفاً قیمت جدید را وارد کنید:")
        bot.register_next_step_handler(message, change_product_price, product)
    elif action == '📦 تغییر موجودی':
        bot.reply_to(message, "📦 لطفاً موجودی جدید را وارد کنید:")
        bot.register_next_step_handler(message, change_product_stock, product)
    elif action == '✏️ تغییر نام و اطلاعات':
        bot.reply_to(message, "✏️ لطفاً نام جدید و اطلاعات جدید را وارد کنید (فرمت: نام | اطلاعات):")
        bot.register_next_step_handler(message, change_product_info, product)
    elif action == '❌ حذف محصول':
        confirm_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        confirm_markup.row('⚠️ بله، حذف شود', '🔙 بازگشت به منوی اصلی')
        bot.reply_to(
            message,
            f"⚠️ آیا مطمئن هستید که می‌خواهید محصول {product.name} را حذف کنید؟ این عملیات قابل بازگشت نیست.",
            reply_markup=confirm_markup
        )
        bot.register_next_step_handler(message, delete_product, product)
    elif action == '🔙 بازگشت به منوی اصلی':
        bot.reply_to(message, "🔙 بازگشت به منوی اصلی.", reply_markup=main_menu_markup())
    else:
        bot.reply_to(message, "❌ گزینه نامعتبر.", reply_markup=main_menu_markup())

def change_product_price(message, product):
    try:
        new_price = float(message.text.strip())
        session = Session()
        product.price = new_price
        session.commit()
        session.close()
        bot.reply_to(message, f"✅ قیمت محصول به {new_price} تغییر یافت.", reply_markup=main_menu_markup())
    except ValueError:
        bot.reply_to(message, "❌ قیمت نامعتبر. لطفاً دوباره تلاش کنید.")
        bot.register_next_step_handler(message, change_product_price, product)

def change_product_stock(message, product):
    try:
        new_stock = int(message.text.strip())
        session = Session()
        product.stock = new_stock
        session.commit()
        session.close()
        bot.reply_to(message, f"✅ موجودی محصول به {new_stock} تغییر یافت.", reply_markup=main_menu_markup())
    except ValueError:
        bot.reply_to(message, "❌ موجودی نامعتبر. لطفاً دوباره تلاش کنید.")
        bot.register_next_step_handler(message, change_product_stock, product)

def change_product_info(message, product):
    try:
        new_name, new_info = message.text.split('|', 1)
        session = Session()
        product.name = new_name.strip()
        product.info = new_info.strip()
        session.commit()
        session.close()
        bot.reply_to(message, "✅ اطلاعات محصول با موفقیت به‌روز شد.", reply_markup=main_menu_markup())
    except ValueError:
        bot.reply_to(message, "❌ فرمت نامعتبر. لطفاً دوباره تلاش کنید.")
        bot.register_next_step_handler(message, change_product_info, product)

def delete_product(message, product):
    if message.text.strip() == '⚠️ بله، حذف شود':
        session = Session()
        session.delete(product)
        session.commit()
        session.close()
        bot.reply_to(message, "✅ محصول با موفقیت حذف شد.", reply_markup=main_menu_markup())
    else:
        bot.reply_to(message, "🔙 بازگشت به منوی اصلی.", reply_markup=main_menu_markup())



@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK"
# بقیه تنظیمات وب‌هوک و اجرای اصلی مثل قبل
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url='https://tor-production.up.railway.app/' + TOKEN)
    app.run(host="0.0.0.0", port=8080)
