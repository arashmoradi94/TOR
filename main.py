import asyncio
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import TELEGRAM_TOKEN
from database.operations import init_db
from handlers.command_handlers import (
    start, api_settings, search_product, process_product_search
)

async def main():
    # Initialize database
    await init_db()
    
    # Build application
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
    
    # Start the bot without using run_polling()
    await application.initialize()
    await application.start()
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

def run_bot():
    """Run the bot with proper error handling"""
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        print(f"Error running bot: {e}")

if __name__ == "__main__":
    run_bot()
