import logging
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import CallbackQuery

import config

logger = logging.getLogger(__name__)


# ─── 1. ADMIN BUTTONS HANDLER (Fix for Add, Remove, Channels & Story) ───
@Client.on_callback_query(filters.regex(r"^admin_"))
async def handle_admin_menu_buttons(client: Client, call: CallbackQuery):
    if call.from_user.id != config.ADMIN_ID:
        return await call.answer("❌ Access Denied!", show_alert=True)

    action = call.data.split("_")[1]
    await call.answer()

    try:
        if action == "story":
            from plugins.story import start_add_story
            await start_add_story(client, call.message)
            
        elif action == "add":
            from plugins.admin import add_start
            await add_start(client, call.message)
            
        elif action == "channels":
            from plugins.admin import list_channels
            await list_channels(client, call.message)
            
        elif action == "remove":
            from plugins.admin import remove_user_start
            await remove_user_start(client, call.message)
            
    except Exception as e:
        logger.error(f"Error handling admin action '{action}': {e}", exc_info=True)
        await client.send_message(
            call.message.chat.id,
            f"❌ <b>Action Error:</b> <code>{str(e)}</code>",
            parse_mode=ParseMode.HTML,
        )


# ─── 2. BACK TO START HANDLER (CIRCULAR IMPORT SAFE ROUTING) ───
@Client.on_callback_query(filters.regex(r"^back_to_start$"))
async def back_to_start_handler(client: Client, call: CallbackQuery):
    await call.answer()
    
    try:
        await call.message.delete()
    except Exception:
        pass

    # Safe Lazy Import pattern to prevent startup circular import loops
    try:
        from plugins.start import start_handler
        await start_handler(client, call.message)
    except Exception as err:
        logger.error(f"Start routing breakdown error: {err}", exc_info=True)
        await client.send_message(
            call.message.chat.id,
            f"❌ System routing breakdown error: <code>{str(err)}</code>",
            parse_mode=ParseMode.HTML,
        )


# ─── 3. USER DASHBOARD / MY PLAN HANDLER ───
@Client.on_callback_query(filters.regex(r"^my_plan$"))
async def user_dashboard_link(client: Client, call: CallbackQuery):
    await call.answer("📊 Loading your plans...", show_alert=False)
