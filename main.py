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
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float, BigInteger
from sqlalchemy.orm import sessionmaker, declarative_base, scoped_session
from datetime import datetime
import hashlib
from telebot import types
import pandas as pd
from io import BytesIO
from woocommerce import API

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

from sqlalchemy.pool import QueuePool

# تنظیمات پیشرفته برای اتصال
engine = create_engine(
    DATABASE_URL, 
    poolclass=QueuePool,
    pool_size=10,            # تعداد اتصالات ثابت در پول
    max_overflow=20,         # تعداد اتصالات اضافی مجاز
    pool_timeout=30,         # زمان انتظار برای دریافت اتصال
    pool_recycle=1200,       # بازسازی اتصال هر 20 دقیقه
    pool_pre_ping=True,      # بررسی سلامت اتصال قبل از استفاده
    connect_args={
        'charset': 'utf8mb4',
        'use_unicode': True
    }
)

# ایجاد جلسه با scoped_session برای مدیریت بهتر
Session = scoped_session(sessionmaker(bind=engine))

# پایه مدل‌ها
Base = declarative_base()

# تابع کمکی برای مدیریت جلسات
def get_session():
    """
    ایجاد و بازگرداندن جلسه جدید
    """
    return Session()

def close_session():
    """
    بستن تمام جلسات باز
    """
    Session.remove()

# تابع تست اتصال
def test_database_connection():
    try:
        session = get_session()
        
        # کوئری تست
        result = session.execute("SELECT 1")
        
        session.close()
        print("✅ اتصال به پایگاه داده موفقیت‌آمیز بود")
        return True
    
    except Exception as e:
        print(f"❌ خطا در اتصال به پایگاه داده: {str(e)}")
        return False

# کانتکست منیجر برای مدیریت جلسات
from contextlib import contextmanager

@contextmanager
def session_scope():
    """
    مدیریت جلسات با استفاده از کانتکست منیجر
    """
    session = get_session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

# مثال استفاده از کانتکست منیجر
def example_usage():
    try:
        with session_scope() as session:
            # عملیات مورد نظر
            result = session.query(User).filter_by(username='example').first()
            # انجام عملیات
    except Exception as e:
        print(f"خطا: {str(e)}")


# مدل محصول ساده
class Product(Base):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    woo_id = Column(Integer, unique=True)  # شناسه محصول در ووکامرس
    name = Column(String(255), nullable=False)
    price = Column(Float, default=0.0)
    stock_quantity = Column(Integer, default=0)
    sku = Column(String(100))  # کد محصول
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

def fetch_products_from_woocommerce(user, limit=100, page=1):
    """
    دریافت محصولات از WooCommerce با اطلاعات پایه
    
    :param user: کاربر با اطلاعات اتصال به سایت
    :param limit: تعداد محصولات در هر درخواست
    :param page: شماره صفحه
    :return: True اگر موفق، False در غیر این صورت
    """
    try:
        # ایجاد اتصال به WooCommerce API
        wcapi = API(
            url=user.site_url,
            consumer_key=user.consumer_key,
            consumer_secret=user.consumer_secret,
            version="wc/v3",
            timeout=30  # تایم‌اوت 30 ثانیه
        )

        # پارامترهای درخواست
        params = {
            'per_page': limit,
            'page': page,
            'status': 'publish',  # فقط محصولات منتشر شده
            'orderby': 'date',
            'order': 'desc'
        }

        # دریافت محصولات
        response = wcapi.get("products", params=params)
        
        # بررسی وضعیت پاسخ
        if response.status_code != 200:
            logging.error(f"خطا در دریافت محصولات: {response.text}")
            return False

        products = response.json()

        # ایجاد سشن دیتابیس
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            # حذف محصولات قبلی
            session.query(Product).delete()

            # ذخیره محصولات جدید
            for product_data in products:
                new_product = Product(
                    woo_id=product_data.get('id'),
                    name=product_data.get('name', ''),
                    price=float(product_data.get('price', 0)),
                    stock_quantity=product_data.get('stock_quantity', 0),
                    sku=product_data.get('sku', ''),
                    description=product_data.get('description', '')
                )
                session.add(new_product)

            # کامیت تغییرات
            session.commit()
            logging.info(f"تعداد {len(products)} محصول با موفقیت دریافت و ذخیره شد.")
            
            return True

        except Exception as db_error:
            session.rollback()
            logging.error(f"خطا در ذخیره‌سازی محصولات: {str(db_error)}")
            return False

        finally:
            session.close()

    except Exception as api_error:
        logging.error(f"خطا در اتصال به WooCommerce API: {str(api_error)}")
        return False

# تابع همگام‌سازی تمام محصولات
def sync_all_products(user):
    """
    همگام‌سازی تمام محصولات با پشتیبانی از صفحه‌بندی
    """
    page = 1
    total_products = 0
    
    while True:
        success = fetch_products_from_woocommerce(user, page=page)
        if not success:
            break
        total_products += len(products)
        page += 1
    
    return total_products

# مدل کاربر
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    # استفاده از BigInteger برای chat_id
    chat_id = Column(BigInteger, primary_key=True)
    
    # افزایش طول ستون‌ها
    username = Column(String(255), nullable=True, default='')
    first_name = Column(String(255), nullable=True, default='')
    last_name = Column(String(255), nullable=True, default='')
    
    # تغییر طول phone_number
    phone_number = Column(String(20), nullable=True, default='')
    
    # استفاده از Text برای فیلدهای بزرگ
    site_url = Column(Text, nullable=True, default='')
    consumer_key = Column(Text, nullable=True, default='')
    consumer_secret = Column(Text, nullable=True, default='')
    
    registration_date = Column(DateTime, default=datetime.now)
    last_activity = Column(DateTime, default=datetime.now, onupdate=datetime.now)

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
                username=message.from_user.username or '',  # استفاده از رشته خالی اگر None باشد
                first_name=first_name or contact.first_name or '',  # اضافه کردن رشته خالی
                last_name=last_name or contact.last_name or '',  # اضافه کردن رشته خالی
                phone_number=contact.phone_number or '',  # اضافه کردن رشته خالی
                site_url='',  # اضافه کردن مقادیر پیش‌فرض
                consumer_key='',
                consumer_secret=''
            )
            session.add(user)
        else:
            user.username = message.from_user.username or user.username or ''
            user.first_name = first_name or contact.first_name or user.first_name or ''
            user.last_name = last_name or contact.last_name or user.last_name or ''
            user.phone_number = contact.phone_number or user.phone_number or ''
            user.last_activity = datetime.now()
        
        session.commit()
        
        # منوی اصلی
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row('👤 پروفایل', '🌐 اتصال به سایت')
        markup.row('🛍️ محصولات')
        markup.row('🌐 تست اتصال به سایت', '❓ راهنما')
        markup.row('📦 دریافت اکسل محصولات')
        markup.row('🔬 تشخیص مشکل محصولات')
        
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
def comprehensive_woocommerce_test(user):
    """
    تست جامع ارتباط با WooCommerce
    """
    try:
        # ایجاد اتصال به WooCommerce API
        wcapi = API(
            url=user.site_url,
            consumer_key=user.consumer_key,
            consumer_secret=user.consumer_secret,
            version="wc/v3",
            timeout=30
        )

        # لاگ‌های تفصیلی
        logging.info("🔍 شروع تست جامع WooCommerce")
        logging.info(f"آدرس سایت: {user.site_url}")
        logging.info(f"Consumer Key (5 حرف اول): {user.consumer_key[:5]}")

        # لیست تست‌های مختلف
        test_methods = [
            # تست 1: درخواست محصولات با پارامترهای مختلف
            {
                'name': 'درخواست محصولات',
                'method': 'get',
                'endpoint': 'products',
                'params': {'per_page': 1}
            },
            # تست 2: درخواست اطلاعات فروشگاه
            {
                'name': 'اطلاعات فروشگاه',
                'method': 'get',
                'endpoint': 'system_status',
                'params': {}
            },
            # تست 3: درخواست دسته‌بندی‌ها
            {
                'name': 'دسته‌بندی‌ها',
                'method': 'get',
                'endpoint': 'products/categories',
                'params': {'per_page': 1}
            }
        ]

        # نتایج تست‌ها
        test_results = {}

        # اجرای تست‌ها
        for test in test_methods:
            logging.info(f"\n🧪 اجرای تست: {test['name']}")
            
            try:
                # اجرای درخواست
                if test['method'] == 'get':
                    response = wcapi.get(test['endpoint'], params=test['params'])
                
                # بررسی وضعیت پاسخ
                logging.info(f"کد وضعیت: {response.status_code}")
                
                # چاپ هدرها
                for key, value in response.headers.items():
                    logging.info(f"{key}: {value}")
                
                # بررسی موفقیت
                if response.status_code in [200, 201]:
                    # پردازش پاسخ
                    data = response.json()
                    
                    # لاگ اطلاعات پایه
                    logging.info(f"تعداد آیتم‌ها: {len(data) if isinstance(data, list) else 'نامشخص'}")
                    
                    # اگر لیست محصولات باشد
                    if test['endpoint'] == 'products' and data:
                        logging.info("نمونه محصول:")
                        logging.info(json.dumps(data[0], indent=2))
                    
                    test_results[test['name']] = True
                else:
                    logging.error(f"خطا در تست {test['name']}: {response.text}")
                    test_results[test['name']] = False
            
            except Exception as test_error:
                logging.error(f"خطای تست {test['name']}: {str(test_error)}")
                test_results[test['name']] = False

        # ارزیابی نهایی
        all_tests_passed = all(test_results.values())
        
        logging.info("\n📊 نتیجه نهایی:")
        for test_name, result in test_results.items():
            logging.info(f"{test_name}: {'✅ موفق' if result else '❌ ناموفق'}")
        
        return all_tests_passed, test_results

    except Exception as e:
        logging.error(f"❌ خطای کلی: {str(e)}")
        return False, {}

@bot.message_handler(func=lambda message: message.text == '🌐 تست اتصال به سایت')
@error_handler
def test_site_connection(message):
    chat_id = message.chat.id
    
    # بررسی اطلاعات کاربر
    session = Session()
    user = session.query(User).filter_by(chat_id=chat_id).first()
    session.close()
    
    if not user or not all([user.site_url, user.consumer_key, user.consumer_secret]):
        bot.reply_to(message, "❌ ابتدا اطلاعات اتصال به سایت را کامل کنید.")
        return
    
    # ارسال پیام در حال تست
    status_message = bot.reply_to(message, "🔍 در حال تست جامع اتصال...")

    try:
        # اجرای تست جامع
        all_passed, test_results = comprehensive_woocommerce_test(user)

        # متن گزارش
        report_text = "🌐 گزارش تست اتصال به سایت:\n\n"
        for test_name, result in test_results.items():
            report_text += f"{'✅' if result else '❌'} {test_name}\n"
        
        # به‌روزرسانی پیام
        if all_passed:
            bot.edit_message_text(
                chat_id=chat_id, 
                message_id=status_message.message_id,
                text=f"✅ تست اتصال کامل موفق بود!\n\n{report_text}"
            )
        else:
            bot.edit_message_text(
                chat_id=chat_id, 
                message_id=status_message.message_id,
                text=f"⚠️ برخی تست‌ها ناموفق بودند.\n\n{report_text}"
            )
    
    except Exception as e:
        bot.edit_message_text(
            chat_id=chat_id, 
            message_id=status_message.message_id,
            text=f"❌ خطای کلی در تست اتصال: {str(e)}"
        )

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

def detailed_fetch_products(user, limit=100, page=1):
    try:
        # ایجاد اتصال به WooCommerce API
        wcapi = API(
            url=user.site_url,
            consumer_key=user.consumer_key,
            consumer_secret=user.consumer_secret,
            version="wc/v3",
            timeout=30
        )
        
        # پارامترهای مختلف برای درخواست
        params_list = [
            {},  # بدون فیلتر
            {'per_page': limit, 'page': page},
            {'status': 'publish'},
            {'status': 'draft'},
            {'status': ['publish', 'draft']},
        ]
        
        # لاگ کامل برای هر پارامتر
        for params in params_list:
            logging.info(f"\n--- تلاش با پارامترها: {params} ---")
            
            try:
                # درخواست محصولات
                response = wcapi.get("products", params=params)
                
                # اطلاعات کامل پاسخ
                logging.info(f"کد وضعیت: {response.status_code}")
                logging.info(f"هدرها: {response.headers}")
                
                # بررسی پاسخ
                if response.status_code in [200, 201]:
                    products = response.json()
                    
                    # چاپ اطلاعات محصولات
                    logging.info(f"تعداد محصولات: {len(products)}")
                    
                    for product in products:
                        logging.info(f"محصول: {product.get('name', 'بدون نام')}")
                        logging.info(f"شناسه: {product.get('id')}")
                        logging.info(f"وضعیت: {product.get('status')}")
                        logging.info(f"قیمت: {product.get('price')}")
                        logging.info("---")
                    
                    # اگر محصول پیدا شد، برگردان
                    if products:
                        return products
                
                else:
                    logging.error(f"خطا در درخواست: {response.text}")
            
            except Exception as param_error:
                logging.error(f"خطا با پارامترهای {params}: {str(param_error)}")
        
        # اگر هیچ محصولی پیدا نشد
        return []
    
    except Exception as e:
        logging.error(f"خطای کلی: {str(e)}")
        return []

# تابع سینک محصولات با جزئیات بیشتر
def sync_products(user):
    # دریافت محصولات با جزئیات کامل
    products = comprehensive_product_fetch(user)
    
    if not products:
        logging.warning("⚠️ هیچ محصولی دریافت نشد")
        return 0
    
    # ایجاد سشن دیتابیس
    session = Session()
    
    try:
        # حذف محصولات قبلی
        session.query(Product).delete()
        
        # ذخیره محصولات جدید
        for product_data in products:
            # مدیریت قیمت‌های خالی یا نامعتبر
            price = product_data.get('price')
            try:
                price = float(price) if price and price != '' else 0.0
            except (ValueError, TypeError):
                price = 0.0
            
            # مدیریت موجودی
            stock_quantity = product_data.get('stock_quantity')
            try:
                stock_quantity = int(stock_quantity) if stock_quantity and stock_quantity != '' else 0
            except (ValueError, TypeError):
                stock_quantity = 0
            
            new_product = Product(
                woo_id=product_data.get('id'),
                name=product_data.get('name', ''),
                price=price,
                stock_quantity=stock_quantity,
                sku=product_data.get('sku', ''),
                description=product_data.get('description', '')
            )
            
            # چاپ اطلاعات محصول برای بررسی
            logging.info(f"محصول: {new_product.name}")
            logging.info(f"قیمت: {new_product.price}")
            logging.info(f"موجودی: {new_product.stock_quantity}")
            
            session.add(new_product)
        
        # کامیت تغییرات
        session.commit()
        logging.info(f"✅ تعداد {len(products)} محصول با موفقیت ذخیره شد")
        
        return len(products)
    
    except Exception as e:
        session.rollback()
        logging.error(f"❌ خطا در ذخیره‌سازی محصولات: {str(e)}")
        logging.error(traceback.format_exc())
        return 0
    finally:
        session.close()


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@bot.message_handler(func=lambda message: message.text == '🛍️ محصولات')
@error_handler
def product_handler(message):
    """
    Handle initial product search request
    """
    bot.reply_to(message, "🆔 لطفاً شناسه یا نام محصول را وارد کنید:", reply_markup=main_menu_markup())
    bot.register_next_step_handler(message, search_product)

def search_product(message):
    """
    Search for product by ID or name
    """
    search_term = message.text.strip()
    session = Session()
    
    try:
        # Search by ID first
        product = session.query(Product).filter_by(id=search_term).first()
        
        # If not found, try searching by name
        if not product:
            product = session.query(Product).filter(Product.name.ilike(f'%{search_term}%')).first()
        
        if product:
            # Create markup for product actions
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row('💰 تغییر قیمت', '📦 تغییر موجودی')
            markup.row('✏️ تغییر نام و اطلاعات', '❌ حذف محصول')
            markup.row('🔗 اطلاعات کامل', '🔙 بازگشت به منوی اصلی')

            # Detailed product info display
            product_info = (
                f"✅ محصول یافت شد:\n"
                f"🆔 شناسه: {product.id}\n"
                f"📛 نام: {product.name}\n"
                f"💰 قیمت: {product.price:,} تومان\n"
                f"📦 موجودی: {product.stock}\n"
                f"ℹ️ اطلاعات تکمیلی: {product.info or 'نامشخص'}"
            )
            
            bot.reply_to(
                message,
                product_info,
                reply_markup=markup
            )
            bot.register_next_step_handler(message, product_action_handler, product)
        else:
            bot.reply_to(message, "❌ محصولی با این شناسه یا نام یافت نشد.", reply_markup=main_menu_markup())
    
    except Exception as e:
        logging.error(f"خطا در جستجوی محصول: {str(e)}")
        bot.reply_to(message, "❌ خطای سیستمی در جستجوی محصول.", reply_markup=main_menu_markup())
    
    finally:
        session.close()

@bot.message_handler(func=lambda message: message.text == '📦 دریافت اکسل محصولات')
@error_handler
def export_products_to_excel(message):
    """
    Export products to Excel file
    """
    chat_id = message.chat.id
    
    # Check user connection details
    session = Session()
    try:
        user = session.query(User).filter_by(chat_id=chat_id).first()
        
        if not user or not all([user.site_url, user.consumer_key, user.consumer_secret]):
            bot.reply_to(message, "❌ ابتدا اطلاعات اتصال به سایت را کامل کنید.")
            return

        # Send initial status message
        status_message = bot.reply_to(message, "📦 در حال دریافت محصولات...")

        try:
            # Fetch products from WooCommerce
            products = fetch_woocommerce_products(user)
            
            if not products:
                bot.edit_message_text(
                    chat_id=chat_id, 
                    message_id=status_message.message_id,
                    text="⚠️ هیچ محصولی یافت نشد."
                )
                return

            # Prepare product data
            product_data = prepare_detailed_product_data(products)

            # Create DataFrame
            df = pd.DataFrame(product_data)

            # Generate filename with timestamp
            excel_filename = f"products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            # Save Excel file
            df.to_excel(excel_filename, index=False, encoding='utf-8-sig')

            # Send Excel file
            with open(excel_filename, 'rb') as excel_file:
                sent_file = bot.send_document(
                    chat_id=chat_id, 
                    document=excel_file, 
                    caption=f"📊 فایل اکسل محصولات ({len(products)} محصول)",
                    timeout=60
                )
            
            # Delete temporary file
            os.remove(excel_filename)
            
            # Delete status message
            bot.delete_message(chat_id=chat_id, message_id=status_message.message_id)

        except Exception as export_error:
            logging.error(f"خطا در دریافت محصولات: {str(export_error)}")
            bot.edit_message_text(
                chat_id=chat_id, 
                message_id=status_message.message_id,
                text=f"❌ خطا در دریافت محصولات: {str(export_error)}"
            )

    except Exception as session_error:
        logging.error(f"خطا در جلسه کاربری: {str(session_error)}")
        bot.reply_to(message, "❌ خطای سیستمی رخ داده است.")
    
    finally:
        session.close()

def fetch_woocommerce_products(user, max_products=1000):
    """
    دریافت محصولات با تنظیمات دقیق‌تر
    """
    all_products = []
    page = 1
    total_pages = 1

    try:
        # اتصال API با تنظیمات کامل‌تر
        wcapi = API(
            url=user.site_url,  # آدرس کامل سایت
            consumer_key=user.consumer_key,
            consumer_secret=user.consumer_secret,
            wp_api=True,  # فعال‌سازی WP API
            version="wc/v3",
            timeout=60  # افزایش زمان انتظار
        )

        # پارامترهای درخواست
        params = {
            'per_page': 100,
            'page': page,
            'status': 'any',  # دریافت تمام وضعیت‌ها
            'orderby': 'date',
            'order': 'desc'
        }

        while page <= total_pages and len(all_products) < max_products:
            # چاپ اطلاعات برای دیباگ
            logging.info(f"درخواست صفحه {page}")

            # درخواست با پارامترهای کامل‌تر
            response = wcapi.get("products", params=params)
            
            # بررسی دقیق‌تر پاسخ
            if response.status_code not in [200, 201]:
                logging.error(f"خطا در دریافت: {response.text}")
                break

            products = response.json()
            
            if not products:
                break

            all_products.extend(products)

            # به‌روزرسانی صفحات
            total_pages = int(response.headers.get('X-WP-TotalPages', 1))
            page += 1
            params['page'] = page

        return all_products

    except Exception as e:
        logging.error(f"خطای کلی: {str(e)}")
        return []


def prepare_detailed_product_data(products):
    """
    Prepare comprehensive product data for Excel export
    """
    product_data = []

    for product in products:
        try:
            # Handle price
            price = float(product.get('price', 0)) if product.get('price') else 0.0
            
            # Handle stock
            stock = int(product.get('stock_quantity', 0)) if product.get('stock_quantity') is not None else 0
            
            # Categories
            categories = ', '.join([cat.get('name', '') for cat in product.get('categories', [])])
            
            # Tags
            tags = ', '.join([tag.get('name', '') for tag in product.get('tags', [])])

            # Remove HTML tags from description
            description = strip_html_tags(product.get('description', ''))

            product_entry = {
                "شناسه محصول": product.get('id', ''),
                "نام محصول": product.get('name', ''),
                "قیمت": price,
                "موجودی انبار": stock,
                "کد محصول (SKU)": product.get('sku', ''),
                "وضعیت": product.get('status', ''),
                "لینک محصول": product.get('permalink', ''),
                "دسته‌بندی‌ها": categories,
                "برچسب‌ها": tags,
                "توضیحات": description
            }
            
            product_data.append(product_entry)
        
        except Exception as product_error:
            logging.error(f"خطا در پردازش محصول: {str(product_error)}")

    return product_data

def strip_html_tags(text):
    """
    Remove HTML tags from text
    """
    if text:
        clean = re.compile('<.*?>')
        return re.sub(clean, '', text)
    return ''

# Additional helper functions and error handlers would be defined here
def main_menu_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('👤 پروفایل', '🌐 اتصال به سایت')
    markup.row('🛍️ محصولات')
    markup.row('🌐 تست اتصال به سایت', '❓ راهنما')
    markup.row('📦 دریافت اکسل محصولات')
    markup.row('🔬 تشخیص مشکل محصولات')
    return markup


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
