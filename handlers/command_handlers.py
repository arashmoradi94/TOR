from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

# تعریف state های مختلف برای conversation handler
CHOOSING, TYPING_WOO_KEY, TYPING_WOO_SECRET, TYPING_TOROB_KEY, TYPING_PRODUCT = range(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    keyboard = [
        [
            InlineKeyboardButton("تنظیمات API", callback_data="api_settings"),
            InlineKeyboardButton("جستجوی محصول", callback_data="search_product")
        ],
        [InlineKeyboardButton("تنظیمات پیشرفته", callback_data="advanced_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        'سلام! به ربات مقایسه قیمت خوش آمدید.\n'
        'لطفاً یکی از گزینه‌های زیر را انتخاب کنید:',
        reply_markup=reply_markup
    )
    return CHOOSING

async def api_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle API settings selection."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [
            InlineKeyboardButton("تنظیم API ووکامرس", callback_data="set_woo_api"),
            InlineKeyboardButton("تنظیم API ترب", callback_data="set_torob_api")
        ],
        [InlineKeyboardButton("بازگشت به منو اصلی", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        'لطفاً نوع API را انتخاب کنید:',
        reply_markup=reply_markup
    )
    return CHOOSING

async def set_woo_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle WooCommerce API setup."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        'لطفاً کلید API ووکامرس خود را وارد کنید:'
    )
    return TYPING_WOO_KEY

async def set_torob_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Torob API setup."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        'لطفاً کلید API ترب خود را وارد کنید:'
    )
    return TYPING_TOROB_KEY

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to main menu."""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [
            InlineKeyboardButton("تنظیمات API", callback_data="api_settings"),
            InlineKeyboardButton("جستجوی محصول", callback_data="search_product")
        ],
        [InlineKeyboardButton("تنظیمات پیشرفته", callback_data="advanced_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        'منوی اصلی:',
        reply_markup=reply_markup
    )
    return CHOOSING
