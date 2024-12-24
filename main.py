import asyncio
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import TELEGRAM_TOKEN
from database.operations import init_db
from handlers.command_handlers import (
    start, api_settings, search_product, process_product_search
)

async def main():
    await init_db()
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(api_settings, pattern="^api_settings$"))
    application.add_handler(CallbackQueryHandler(search_product, pattern="^search_product$"))
    
    # Add message handler for product search
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        process_product_search
    ))
    
    # Start the bot
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
