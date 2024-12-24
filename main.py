import asyncio
import logging
import nest_asyncio
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ConversationHandler
)
from telegram import Update
from config import TELEGRAM_TOKEN
from database.operations import init_db
from handlers.command_handlers import (
    start, api_settings, set_woo_api, set_torob_api, back_to_main,
    CHOOSING, TYPING_WOO_KEY, TYPING_WOO_SECRET, TYPING_TOROB_KEY, TYPING_PRODUCT
)

# Apply nest_asyncio to fix event loop issues
nest_asyncio.apply()

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    # Initialize database
    await init_db()
    
    # Build application
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
        per_message=False
    )

    # Add conversation handler
    application.add_handler(conv_handler)

    # Start the bot
    logger.info("Starting bot...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await application.updater.idle()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Critical error: {e}")
