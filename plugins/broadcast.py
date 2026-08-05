import asyncio
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
from pyrogram.types import Message

import config
from database import users_col

# Shared ADMIN_STEPS dictionary (imported or declared for FSM)
# Format: {user_id: {"step": "STEP_NAME"}}
from plugins.admin import ADMIN_STEPS


# ==========================================
# --- 1. COMMAND TRIGGER (/broadcast) ---
# ==========================================
@Client.on_message(
    filters.command("broadcast")
    & filters.user(config.ADMIN_ID)
    & filters.private
)
async def start_broadcast(client: Client, message: Message):
    user_id = message.from_user.id
    ADMIN_STEPS[user_id] = {"step": "WAITING_BROADCAST_MSG"}

    await message.reply_text(
        "📢 <b>ᴀᴅᴍɪɴ ʙʀᴏᴀᴅᴄᴀsᴛ:</b>\n\n"
        "Aap jo bhi message sabhi users ko bhejna chahte hain, woh yahan <b>Forward</b> karein ya direct <b>Type/Upload</b> karein.\n\n"
        "➔ <i>Isme Text, Photo, Video, Animation sab support hoga. Cancel karne ke liye <code>/cancel</code> likhein.</i>",
        parse_mode=ParseMode.HTML,
    )


# ==========================================
# --- 2. ASYNC BACKGROUND BROADCAST LOOP ---
# ==========================================
async def run_broadcast_loop(
    client: Client, media_msg: Message, user_list: list, status_msg: Message
):
    success = 0
    failed = 0
    total = len(user_list)
    chat_id = media_msg.chat.id

    for index, u_id in enumerate(user_list):
        try:
            # Pyrofork message attribute is '.id' instead of '.message_id'
            await client.copy_message(
                chat_id=u_id,
                from_chat_id=chat_id,
                message_id=media_msg.id,
            )
            success += 1
        except FloodWait as e:
            # Telegram rate-limit automatic pause handling
            await asyncio.sleep(e.value)
            try:
                await client.copy_message(
                    chat_id=u_id,
                    from_chat_id=chat_id,
                    message_id=media_msg.id,
                )
                success += 1
            except Exception:
                failed += 1
        except Exception:
            failed += 1

        # Small delay to prevent API flooding
        await asyncio.sleep(0.05)

        # Update status message every 10 users or at the end
        if (index + 1) % 10 == 0 or (index + 1) == total:
            try:
                await status_msg.edit_text(
                    f"📢 <b>ʙʀᴏᴀᴅᴄᴀsᴛ ɪɴ ᴘʀᴏɢʀᴇss:</b>\n"
                    f"────────────────────\n"
                    f"📊 Progress: <code>{index + 1}/{total}</code>\n"
                    f"✅ Successful: <code>{success}</code>\n"
                    f"❌ Failed/Blocked: <code>{failed}</code>",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass

    await client.send_message(
        chat_id,
        f"🏁 <b>ʙʀᴏᴀᴅᴄᴀsᴛ ғɪɴɪsʜᴇᴅ!</b>\n"
        f"────────────────────\n"
        f"✅ Total Delivered: <code>{success}</code>\n"
        f"❌ Total Failed: <code>{failed}</code>\n"
        f"👥 Grand Total: <code>{total}</code>",
        parse_mode=ParseMode.HTML,
    )


# ==========================================================
# --- 3. BROADCAST FSM PROCESSOR (ADMIN ROUTER INTEGRATION) ---
# ==========================================================
# Yeh block aapke admin FSM router ke andar include kiya ja sakta hai
async def handle_broadcast_input(client: Client, message: Message):
    user_id = message.from_user.id

    if message.text and message.text.strip().lower() in ["/cancel", "cancel"]:
        ADMIN_STEPS.pop(user_id, None)
        return await message.reply_text("❌ Broadcast cancelled.")

    ADMIN_STEPS.pop(user_id, None)

    # Async Motor DB distinct query
    all_users = await users_col.distinct("user_id")
    total_users = len(all_users)

    if total_users == 0:
        return await message.reply_text(
            "❌ Database mein koi user nahi mila!"
        )

    status_msg = await message.reply_text(
        f"🚀 <b>Broadcast Shuru Ho Gaya Hai...</b>\n\n👥 Total Targets: <code>{total_users}</code>\n⏳ Processing...",
        parse_mode=ParseMode.HTML,
    )

    # Create background task in asyncio event loop (Replaces threading.Thread)
    asyncio.create_task(
        run_broadcast_loop(client, message, all_users, status_msg)
    )
