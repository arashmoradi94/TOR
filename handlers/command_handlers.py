from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.operations import get_user, create_user, update_api_keys
from services.woocommerce_service import get_woo_product_price
from services.torob_service import get_torob_price

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("تنظیمات API", callback_data="api_settings")],
        [InlineKeyboardButton("جستجوی قیمت محصول", callback_data="search_product")],
        [InlineKeyboardButton("تنظیمات پیشرفته", callback_data="advanced_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "به ربات مقایسه قیمت خوش آمدید!\n"
        "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=reply_markup
    )

async def api_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("تنظیم API ووکامرس", callback_data="set_woo_api")],
        [InlineKeyboardButton("تنظیم API ترب", callback_data="set_torob_api")],
        [InlineKeyboardButton("بازگشت به منوی اصلی", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.message.edit_text(
        "لطفاً نوع API مورد نظر را انتخاب کنید:",
        reply_markup=reply_markup
    )

async def search_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = "awaiting_product_name"
    await update.callback_query.message.edit_text(
        "لطفاً نام محصول مورد نظر را وارد کنید:"
    )

async def process_product_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    product_name = update.message.text
    user = await get_user(update.effective_user.id)
    
    if not user or not user.woo_key or not user.torob_key:
        await update.message.reply_text(
            "لطفاً ابتدا API های خود را تنظیم کنید."
        )
        return
    
    woo_price = await get_woo_product_price(update.effective_user.id, product_name)
    torob_price = await get_torob_price(product_name, user.torob_key)
    
    if woo_price and torob_price:
        discount = user.discount_percentage / 100
        final_price = torob_price * (1 - discount)
        
        await update.message.reply_text(
            f"نتایج جستجو برای {product_name}:\n"
            f"قیمت در ووکامرس: {woo_price:,} تومان\n"
            f"قیمت در ترب: {torob_price:,} تومان\n"
            f"قیمت پیشنهادی: {final_price:,} تومان"
        )
    else:
        await update.message.reply_text(
            "متأسفانه محصول مورد نظر یافت نشد."
        )
