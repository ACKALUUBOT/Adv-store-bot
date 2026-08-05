from datetime import datetime, timedelta
import config
from database import users_col
from pyrogram.enums import ParseMode


def get_time_string(mins: int) -> str:
    """मिनटों को पढ़ने योग्य समय (Min, Hours, Days) में बदलता है"""
    mins = int(mins)
    if mins < 60:
        return f"{mins} Min"
    if mins < 1440:
        return f"{mins // 60} Hours"
    return f"{mins // 1440} Days"


async def approve_user_logic(u_id: int, ch_id: int, mins: int, method: str = "Automatic"):
    """
    यूज़र की पेमेंट अप्रूव करके सिंगल-यूज़ इनवाइट लिंक जेनरेट करता है
    और डेटाबेस में एक्सपिरी अपडेट करता है।
    """
    from main import bot  # Circular Import रोकने के लिए

    # Async DB Query: यूज़र का मौजूदा सब्सक्रिप्शन चेक करें
    user_record = await users_col.find_one({"user_id": u_id, "channel_id": ch_id})
    now = datetime.now()
    
    # अगर पुराना टाइम बचा है तो उसमें नया टाइम जोड़ें, वर्ना अभी से कैलकुलेट करें
    if user_record and user_record.get('expiry', 0) > now.timestamp():
        base_time = datetime.fromtimestamp(user_record['expiry'])
    else:
        base_time = now

    new_expiry = base_time + timedelta(minutes=mins)

    try:
        # Pyrofork Async Single-Use Invite Link Generation
        link = await bot.create_chat_invite_link(
            chat_id=ch_id,
            member_limit=1,
            expire_date=new_expiry
        )
        
        # Async DB Update
        await users_col.update_one(
            {"user_id": u_id, "channel_id": ch_id},
            {"$set": {"expiry": new_expiry.timestamp()}},
            upsert=True
        )
        
        msg_text = (
            f"🥳 <b>Subscription Activated!</b>\n\n"
            f"<b>Plan:</b> {get_time_string(mins)}\n"
            f"<b>Expires:</b> {new_expiry.strftime('%Y-%m-%d %H:%M')}\n"
            f"<b>Method:</b> {method}\n\n"
            f"🔗 <b>Join Link:</b> {link.invite_link}"
        )
        
        # यूज़र और एडमिन को नोटिफिकेशन भेजें
        await bot.send_message(chat_id=u_id, text=msg_text, parse_mode=ParseMode.HTML)
        
        if config.ADMIN_ID:
            await bot.send_message(
                chat_id=config.ADMIN_ID,
                text=f"✅ <b>Approved:</b> User <code>{u_id}</code> via {method}",
                parse_mode=ParseMode.HTML
            )
            
    except Exception as e:
        print(f"[Approval Error]: {e}")
        if config.ADMIN_ID:
            await bot.send_message(
                chat_id=config.ADMIN_ID,
                text=f"❌ <b>Approval Error for User {u_id}:</b> <code>{str(e)}</code>",
                parse_mode=ParseMode.HTML
            )
