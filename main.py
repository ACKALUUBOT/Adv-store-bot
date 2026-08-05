import asyncio
import os
from threading import Thread
from pyrofork import Client
import config
from database import init_db
from server import app as flask_app
from scheduler import start_scheduler

# Pyrofork Client Setup (Auto-loads all handlers inside 'plugins' directory)
bot = Client(
    "story_seller_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    plugins=dict(root="plugins")
)


def run_flask_server():
    """Render पर HTTP Health Check के लिए डमी वेब सर्वर थ्रेड"""
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port, use_reloader=False)


async def main():
    # 1. Async MongoDB Indexing शुरू करें
    print("Initializing Database Indexes...")
    await init_db()

    # 2. Background Expiry Scheduler शुरू करें
    print("Starting Expiry Scheduler...")
    start_scheduler()

    # 3. Flask Server को Background Thread में चलाएं
    print("Starting Flask Web Server...")
    flask_thread = Thread(target=run_flask_server, daemon=True)
    flask_thread.start()

    # 4. Pyrofork Client को Start करें
    print("Starting Pyrofork Bot Client...")
    await bot.start()

    me = await bot.get_me()
    print(f"✅ Bot started successfully as @{me.username}!")

    # Event Loop को अलाइव रखें
    await asyncio.Event().wait()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped gracefully.")
