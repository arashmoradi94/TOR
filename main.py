import asyncio
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import TELEGRAM_TOKEN
from database.operations import init_db
from handlers.command_handlers import (
    start, api_settings, search_product, process_product_search
)

# اصلی ترین تابع که برنامه رو راه‌اندازی می‌کنه
async def main():
    # ابتدا پایگاه داده را راه‌اندازی می‌کنیم
    await init_db()

    # ساخت اپلیکیشن تلگرام با استفاده از توکن
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # اضافه کردن هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(api_settings, pattern="^api_settings$"))
    application.add_handler(CallbackQueryHandler(search_product, pattern="^search_product$"))

    # اضافه کردن هندلر برای جستجو و پردازش پیام‌ها
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        process_product_search
    ))

    # شروع ربات
    await application.run_polling()

# چک می‌کنیم که آیا event loop در حال اجرا است یا نه
if __name__ == "__main__":
    try:
        # اجرای برنامه با استفاده از asyncio.run
        asyncio.run(main())  # اگر event loop در حال اجرا نباشد، این روش درست است
    except RuntimeError as e:
        if 'This event loop is already running' in str(e):
            # اگر event loop در حال اجرا باشد (مثلاً در Jupyter)، از این روش استفاده می‌کنیم
            asyncio.get_event_loop().run_until_complete(main())
