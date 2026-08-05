import os

# Telegram API Configuration (Pyrofork Require API_ID & API_HASH)
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')

# Database Config
MONGO_URI = os.getenv('MONGO_URI', '')
DB_NAME = os.getenv('DB_NAME', 'story_seller_db')

# Admin & Contact Details
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
CONTACT_USERNAME = os.getenv('CONTACT_USERNAME', '')
UPI_ID = os.getenv('UPI_ID', '')

# Razorpay Configs
RZP_KEY_ID = os.getenv('RZP_KEY_ID', '')
RZP_KEY_SECRET = os.getenv('RZP_KEY_SECRET', '')
RZP_WEBHOOK_SECRET = os.getenv('RZP_WEBHOOK_SECRET', '')

# Web Server Configuration
BASE_URL = os.getenv('BASE_URL', 'https://ac-sub-bot-tqsd.onrender.com')
PORT = int(os.getenv('PORT', 8080))

# Global User State Storage (Async Memory)
USER_STATES = {}
