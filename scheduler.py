from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import users_col

async def check_expiries():
    """
    सब्सक्रिप्शन एक्सपायर होने वाले यूज़र्स को चैनल से ऑटो-रिमूव करता है।
    """
    from main import bot  # Circular import रोकने के लिए फ़ंक्शन के अंदर इंपोर्ट किया गया है

    current_timestamp = datetime.now().timestamp()
    
    # Motor Async Cursor से एक्सपायर हो चुके यूज़र्स को ढूंढें
    async for user in users_col.find({"expiry": {"$lte": current_timestamp}}):
        channel_id = user.get('channel_id')
        user_id = user.get('user_id')
        
        if channel_id and user_id:
            try:
                # Pyrofork Async Kick & Unban (चैनल से रिमूव करने के लिए)
                await bot.ban_chat_member(chat_id=channel_id, user_id=user_id)
                await bot.unban_chat_member(chat_id=channel_id, user_id=user_id)
            except Exception as e:
                print(f"[Scheduler Warning] Could not kick user {user_id} from {channel_id}: {e}")
        
        # एक्सपायर्ड रिकॉर्ड को डेटाबेस से हटाएं
        await users_col.delete_one({"_id": user['_id']})


def start_scheduler():
    scheduler = AsyncIOScheduler()
    # हर 1 मिनट में Async एक्सपिरी चेकर फ़ंक्शन रन होगा
    scheduler.add_job(check_expiries, 'interval', minutes=1)
    scheduler.start()
    print("AsyncIOScheduler started successfully.")
  
