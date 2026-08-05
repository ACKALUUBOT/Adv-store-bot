import uuid
from database import channels_col
import config
from pymongo import ReturnDocument
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

# Admin step tracking dictionary
ADMIN_STEPS = {}


# --- 1. ADMIN COMMAND TO START STORY SETUP ---
@Client.on_message(filters.command("add_story") & filters.user(config.ADMIN_ID) & filters.private)
async def start_add_story(client: Client, message: Message):
    user_id = message.from_user.id

    # Reset/Init State
    ADMIN_STEPS[user_id] = {"step": "get_story_name", "data": {}}

    await message.reply_text(
        "🎬 <b>sᴛᴏʀʏ sᴇᴛᴜᴘ:</b>\n\n"
        "Story ka naam kya hai?\n"
        "<i>(Aap direct <b>Photo</b> bhi bhej sakte hain, bas uske <b>Caption</b> mein Story ka naam likh dein)</i>\n\n"
        "❌ Cancel karne ke liye <code>/cancel</code> likhein.",
        parse_mode="HTML",
    )


# --- 2. MULTI-STEP CONVERSATION HANDLER ---
@Client.on_message(filters.private & filters.user(config.ADMIN_ID) & ~filters.command("add_story"))
async def handle_admin_story_steps(client: Client, message: Message):
    user_id = message.from_user.id

    # Ignore if user is not in active add_story flow
    if user_id not in ADMIN_STEPS:
        return

    state = ADMIN_STEPS[user_id]
    step = state["step"]
    data = state["data"]

    # Cancel command check
    if message.text and message.text.strip() == "/cancel":
        del ADMIN_STEPS[user_id]
        await message.reply_text("❌ Setup cancelled.")
        return

    # --- STEP 1: GET STORY NAME / PHOTO ---
    if step == "get_story_name":
        story_name = None
        file_id = None

        if message.photo:
            file_id = message.photo.file_id  # Pyrogram has direct photo.file_id
            story_name = (
                message.caption.split("\n")[0]
                if message.caption
                else "Untitled Story"
            )
        elif message.text:
            story_name = message.text
        else:
            await message.reply_text(
                "❌ Please ek valid text naam ya photo bhejein:"
            )
            return

        data["story_name"] = story_name
        data["file_id"] = file_id
        state["step"] = "get_demo_link"

        await message.reply_text(
            "🔗 <b>ᴅᴇᴍᴏ ʟɪɴᴋ:</b>\nDemo channel ya video link dein (Ya 'skip' likhein):",
            parse_mode="HTML",
        )

    # --- STEP 2: GET DEMO LINK ---
    elif step == "get_demo_link":
        if message.text and message.text.lower().strip() == "skip":
            demo = None
        else:
            demo = message.text

        data["demo"] = demo
        state["step"] = "get_final_link"

        await message.reply_text(
            "🤖 <b>ғɪɴᴀʟ ʙᴏᴛ ʟɪɴᴋ:</b>\nPayment ke baad milne wala main link dein:",
            parse_mode="HTML",
        )

    # --- STEP 3: GET FINAL BOT LINK ---
    elif step == "get_final_link":
        data["final_link"] = message.text
        state["step"] = "ask_category"

        await message.reply_text(
            "💰 <b>ᴘʀɪᴄᴇ:</b>\nSirf number likhein (Example: 49):",
            parse_mode="HTML",
        )

    # --- STEP 4: ASK PRICE & SAVE PENDING DATA TO DB ---
    elif step == "ask_category":
        if not message.text or not message.text.isdigit():
            await message.reply_text("❌ Price sirf number mein likhein:")
            return

        price = message.text
        story_id = str(uuid.uuid4())[:10]

        # Motor Async DB Insert
        await channels_col.insert_one(
            {
                "item_id": story_id,
                "story_name": data["story_name"],
                "demo_link": data["demo"],
                "bot_link": data["final_link"],
                "price": price,
                "file_id": data["file_id"],
                "type": "story",
                "status": "pending",
            }
        )

        # Clear state after successful save
        del ADMIN_STEPS[user_id]

        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🎧 pocket", callback_data=f"src_pocket_{story_id}"
                    ),
                    InlineKeyboardButton(
                        "📚 pratilipi", callback_data=f"src_pratilipi_{story_id}"
                    ),
                ]
            ]
        )

        await message.reply_text(
            "📂 <b>ᴄᴀᴛᴇɢᴏʀʏ sᴇʟᴇᴄᴛ ᴋᴀʀᴇɪɴ:</b>\nYeh story kiski hai?",
            reply_markup=markup,
            parse_mode="HTML",
        )


# --- 3. CALLBACK QUERY HANDLER FOR CATEGORY SELECTION ---
@Client.on_callback_query(filters.regex(r"^src_"))
async def save_story_with_source(client: Client, call: CallbackQuery):
    if call.from_user.id != config.ADMIN_ID:
        return await call.answer("Unauthorized!", show_alert=True)

    parts = call.data.split("_")
    platform = "pocket" if parts[1] == "pocket" else "pratilipi"
    story_id = parts[2]

    # Motor Async DB Update
    story_data = await channels_col.find_one_and_update(
        {"item_id": story_id, "status": "pending"},
        {"$set": {"source": platform}, "$unset": {"status": ""}},
        return_document=ReturnDocument.AFTER,
    )

    if not story_data:
        return await call.answer(
            "❌ Session expired ya data nahi mila!", show_alert=True
        )

    try:
        await call.message.delete()
    except Exception:
        pass

    bot_info = await client.get_me()
    share_link = f"https://t.me/{bot_info.username}?start={story_id}"

    res = (
        f"✅ <b>sᴛᴏʀʏ ᴀᴅᴅᴇs sᴜᴄᴄᴇssғᴜʟʟʏ!</b>\n"
        f"────────────────────\n"
        f"📖 Name: <b>{story_data['story_name']}</b>\n"
        f"📂 Platform: <code>{platform}</code>\n"
        f"💰 Price: <b>₹{story_data['price']}</b>\n"
        f"🖼️ Media: <b>{'Saved' if story_data['file_id'] else 'No Photo'}</b>\n\n"
        f"🔗 <b>ʏᴏᴜʀ sʜᴀʀᴇ ʟɪɴᴋ:</b>\n<code>{share_link}</code>\n"
        f"────────────────────\n"
        f"➔ Is link ko copy karke promote karein."
    )

    if story_data.get("file_id"):
        await client.send_photo(
            chat_id=call.message.chat.id,
            photo=story_data["file_id"],
            caption=res,
            parse_mode="HTML",
        )
    else:
        await client.send_message(
            chat_id=call.message.chat.id, text=res, parse_mode="HTML"
        )
