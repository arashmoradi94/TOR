import asyncio
import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from telegram import Update
from config import TELEGRAM_TOKEN
from database.operations import init_db
from handlers.command_handlers import (
    start, api_settings, set_woo_api, set_torob_api, back_to_main,
    CHOOSING, TYPING_WOO_KEY, TYPING_WOO_SECRET, TYPING_TOROB_KEY, TYPING_PRODUCT
)

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def main():
    await init_db()
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Create conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING: [
                CallbackQueryHandler(api_settings, pattern='^api_settings$'),
                CallbackQueryHandler(set_woo_api, pattern='^set_woo_api$'),
                CallbackQueryHandler(set_torob_api, pattern='^set_torob_api$'),
                CallbackQueryHandler(back_to_main, pattern='^back_to_main$'),
            ],
            TYPING_WOO_KEY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_woo_api)
            ],
            TYPING_TOROB_KEY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_torob_api)
            ],
        },
        fallbacks=[CommandHandler('start', start)],
    )

    # Add conversation handler
    application.add_handler(conv_handler)

    try:
        logging.info("Starting bot...")
        await application.initialize()
        await application.start()
        await application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logging.error(f"Error during bot execution: {e}")
        await application.stop()
    finally:
        logging.info("Bot stopped")

def run_bot():
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.error(f"Critical error: {e}")

if __name__ == "__main__":
    run_bot()
