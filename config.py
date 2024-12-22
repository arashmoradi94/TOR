import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot.db')
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', 'your-secure-encryption-key')
ADMIN_IDS = list(map(int, os.getenv('ADMIN_IDS', '').split(',')))
