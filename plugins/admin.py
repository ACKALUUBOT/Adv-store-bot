import re
import uuid
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config
from database import channels_col, users_col

# Global storage temporary state and setup holding
ADMIN_STEPS = {}  # Format: {user_id: {"step": "STEP_NAME", "data": {}}}
pending_setups = {}


def is_valid_url(url: str) -> bool:
    """Strict URL Validation Regex"""
    pattern = re.compile(
        r"^https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)$"
    )
    return bool(pattern.match(url))


# ==========================================
# --- 0. CANCEL PROCESS COMMAND ---
# ==========================================
@Client.on_message(
    filters.command("cancel") & filters.user(config.ADMIN_ID) & filters.private
)
async def cancel_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in ADMIN_STEPS:
        ADMIN_STEPS.pop(user_id, None)
        await message.reply_text("❌ Action cancelled.")
    else:
        await message.reply_text("ℹ️ No active action to cancel.")


# ==========================================
# --- 1. REMOVE USER (SECURE DELETE) ---
# ==========================================
@Client.on_message(
    filters.command("remove") & filters.user(config.ADMIN_ID) & filters.private
)
async def remove_user_start(client: Client, message: Message):
    user_id = message.from_user.id
    ADMIN_STEPS[user_id] = {"step": "WAITING_REMOVE_ID", "data": {}}
    await message.reply_text(
        "👤 <b>User ko remove karein:</b>\n\nUs user ki <b>ID</b> bhejein jiska access khatam karna hai (ya /cancel):",
        parse_mode=ParseMode.HTML,
    )


# =====================================================================
# ─── 2. MANAGE CHANNELS & STORIES (PREMIUM INTERFACE & REMOVE) ───
# =====================================================================
async def show_inventory(client: Client, chat_id: int):
    buttons = []
    
    # Async Motor Cursor iterate over channels database
    async for ch in channels_col.find({}):
        name = ch.get("name") or "Unnamed Item"
        icon = "🎁 Combo:" if ch.get("is_combo") else "📺"
        item_id = ch.get("item_id")
        buttons.append(
            [
                InlineKeyboardButton(
                    f"{icon} {name}", callback_data=f"manage_{item_id}"
                )
            ]
        )

    # Danger zone wipeout button
    buttons.append(
        [
            InlineKeyboardButton(
                "💥 DELETE ALL STORIES 💥", callback_data="conf_del_all_start"
            )
        ]
    )

    if len(buttons) > 1:
        markup = InlineKeyboardMarkup(buttons)
        await client.send_message(
            chat_id,
            "📑 <b>ʏᴏᴜʀ  ɪɴᴠᴇɴᴛᴏʀʏ:</b>\nNiche kisi bhi item ko manage ya remove karein:",
            reply_markup=markup,
            parse_mode=ParseMode.HTML,
        )
    else:
        await client.send_message(
            chat_id,
            "❌ Abhi inventory khali hai. /add ya /add_combo use karein.",
        )


@Client.on_message(
    filters.command("channels")
    & filters.user(config.ADMIN_ID)
    & filters.private
)
async def list_channels(client: Client, message: Message):
    await show_inventory(client, message.chat.id)


@Client.on_callback_query(
    filters.regex(r"^manage_") & filters.user(config.ADMIN_ID)
)
async def manage_ch(client: Client, call: CallbackQuery):
    item_id = call.data.split("_")[1]
    ch_data = await channels_col.find_one({"item_id": item_id})

    if not ch_data:
        return await call.answer("Data not found!", show_alert=True)

    bot_user = (await client.get_me()).username
    link = f"https://t.me/{bot_user}?start={item_id}"
    name = ch_data.get("name") or "Unnamed Item"
    source_platform = str(ch_data.get("source", "none")).upper()
    validity_info = ch_data.get("validity", "N/A")
    price_info = ch_data.get("price", "0")
    description = ch_data.get(
        "description", "Koi description nahi dala gaya hai."
    )

    text = (
        f"⚙️ <b>sᴇᴛᴛɪɴɢs:</b> {name}\n"
        f"────────────────────\n"
        f"📂 <b>Source:</b> <code>{source_platform}</code>\n"
        f"⏱️ <b>Validity:</b> {validity_info} Din\n"
        f"💰 <b>Price:</b> ₹{price_info}\n"
        f"📺 <b>Demo:</b> {ch_data.get('demo_link', 'None')}\n\n"
        f"📝 <b>Description / Included Stories:</b>\n<i>{description}</i>\n\n"
        f"🔗 <b>sʜᴀʀᴇ ʟɪɴᴋ:</b>\n<code>{link}</code>\n"
        f"────────────────────"
    )

    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🗑️ Remove This", callback_data=f"single_del_{item_id}"
                ),
                InlineKeyboardButton(
                    "🔙 Back to List", callback_data="back_to_inventory"
                ),
            ]
        ]
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    photo_id = ch_data.get("file_id")
    if photo_id:
        await client.send_photo(
            call.message.chat.id,
            photo=photo_id,
            caption=text,
            reply_markup=markup,
            parse_mode=ParseMode.HTML,
        )
    else:
        await client.send_message(
            call.message.chat.id,
            text=text,
            reply_markup=markup,
            parse_mode=ParseMode.HTML,
        )


@Client.on_callback_query(
    filters.regex(r"^back_to_inventory$") & filters.user(config.ADMIN_ID)
)
async def back_inventory_callback(client: Client, call: CallbackQuery):
    try:
        await call.message.delete()
    except Exception:
        pass
    await show_inventory(client, call.message.chat.id)


@Client.on_callback_query(
    filters.regex(r"^single_del_") & filters.user(config.ADMIN_ID)
)
async def single_delete_confirm(client: Client, call: CallbackQuery):
    item_id = call.data.split("_")[2]
    ch_data = await channels_col.find_one({"item_id": item_id})
    if not ch_data:
        return await call.answer("Item nahi mila!", show_alert=True)

    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Haan, Delete Karein",
                    callback_data=f"execute_del_{item_id}",
                ),
                InlineKeyboardButton(
                    "❌ Cancel", callback_data=f"manage_{item_id}"
                ),
            ]
        ]
    )

    await client.send_message(
        call.message.chat.id,
        f"⚠️ <b>⚠️ DOUBLE CONFIRMATION ⚠️</b>\n\n"
        f"Kya aap sach me <b>{ch_data.get('name')}</b> ko database se permanent remove karna chahte hain?",
        reply_markup=markup,
        parse_mode=ParseMode.HTML,
    )


@Client.on_callback_query(
    filters.regex(r"^execute_del_") & filters.user(config.ADMIN_ID)
)
async def single_delete_execute(client: Client, call: CallbackQuery):
    item_id = call.data.split("_")[2]
    result = await channels_col.delete_one({"item_id": item_id})

    try:
        await call.message.delete()
    except Exception:
        pass

    if result.deleted_count > 0:
        await client.send_message(
            call.message.chat.id,
            "✅ Item database se successfully remove kar diya gaya hai.",
        )
    else:
        await client.send_message(
            call.message.chat.id,
            "❌ Error! Item delete nahi ho paya ya pehle hi hataya ja chuka hai.",
        )
    await show_inventory(client, call.message.chat.id)


@Client.on_callback_query(
    filters.regex(r"^conf_del_all_start$") & filters.user(config.ADMIN_ID)
)
async def delete_all_warning(client: Client, call: CallbackQuery):
    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🛑 HAAN, WIPE OUT KAREIN",
                    callback_data="prompt_security_code",
                ),
                InlineKeyboardButton(
                    "❌ CANCEL", callback_data="back_to_inventory"
                ),
            ]
        ]
    )
    await client.send_message(
        call.message.chat.id,
        "🚨 <b>CRITICAL WARNING !!</b> 🚨\n\n"
        "Aap database ki <b>SAARI STORIES AUR COMBOS</b> ek sath udaane ja rahe hain.\n"
        "Yeh action reverse nahi kiya ja sakta. Kya aap confirm karte hain?",
        reply_markup=markup,
        parse_mode=ParseMode.HTML,
    )


@Client.on_callback_query(
    filters.regex(r"^prompt_security_code$") & filters.user(config.ADMIN_ID)
)
async def delete_all_security_step(client: Client, call: CallbackQuery):
    try:
        await call.message.delete()
    except Exception:
        pass

    ADMIN_STEPS[call.from_user.id] = {
        "step": "WAITING_SECURITY_CODE",
        "data": {},
    }
    await client.send_message(
        call.message.chat.id,
        "🔒 <b>SECURITY VERIFICATION:</b>\n\n"
        "Puri tarah clear karne ke liye niche likha hua code capital letters me reply karein:\n"
        "<code>CONFIRM DELETE ALL</code>\n\n"
        "➔ Ya cancel karne ke liye /cancel likhein:",
        parse_mode=ParseMode.HTML,
    )


# =====================================================================
# ─── 3. COMMAND STARTERS FOR /add AND /add_combo ───
# =====================================================================
@Client.on_message(
    filters.command("add") & filters.user(config.ADMIN_ID) & filters.private
)
async def add_start(client: Client, message: Message):
    user_id = message.from_user.id
    ADMIN_STEPS[user_id] = {"step": "ADD_FORWARD_POST", "data": {}}
    await message.reply_text(
        "📢 <b>ᴀ_ᴅ_ᴅ  <b>ᴄ_ʜ_ᴀ_ɴ__ɴ_ᴇ_ʟ</b>:</b>\n\n"
        "➔ Jis channel ko add karna hai, us channel ka koi bhi ek post yahan <b>Forward</b> karein:",
        parse_mode=ParseMode.HTML,
    )


@Client.on_message(
    filters.command("add_combo")
    & filters.user(config.ADMIN_ID)
    & filters.private
)
async def add_combo_start(client: Client, message: Message):
    user_id = message.from_user.id
    ADMIN_STEPS[user_id] = {"step": "COMBO_NAME", "data": {}}
    await message.reply_text(
        "🎁 <b>ᴍ_ᴀ_ɴ_ᴜ_ᴀ_ʟ  <b>ᴄ_ᴏ_ᴍ_ʙ_ᴏ</b>  s_ᴇ_ᴛ_ᴜ_ᴘ:</b>\n\n"
        "➔ Combo Pack ka Jo Naam <u>Store Board</u> par dikhana hai, wo bhejiyen:",
        parse_mode=ParseMode.HTML,
    )


# =====================================================================
# ─── 4. CATEGORY CALLBACK & FINAL CHANNEL SAVE ───
# =====================================================================
@Client.on_callback_query(
    filters.regex(r"^newsrc_") & filters.user(config.ADMIN_ID)
)
async def handle_category_selection(client: Client, call: CallbackQuery):
    parts = call.data.split("_")
    platform = "pocket" if parts[1] == "pocket" else "pratilipi"
    state_id = parts[2]

    data = pending_setups.get(state_id)
    if not data:
        return await call.answer(
            "Session Expired! Dubara /add karein.", show_alert=True
        )

    try:
        await call.message.delete()
    except Exception:
        pass

    item_id = str(uuid.uuid4())[:10]

    await channels_col.update_one(
        {"item_id": item_id},
        {
            "$set": {
                "item_id": item_id,
                "channel_id": data["ch_id"],
                "name": data["ch_name"],
                "story_name": data["ch_name"],
                "validity": data["validity_days"],
                "price": data["price"],
                "description": data["description"],
                "file_id": data["file_id"],
                "demo_link": data["demo_link"],
                "source": platform,
                "type": "channel",
            },
            "$unset": {"is_combo": ""},
        },
        upsert=True,
    )

    pending_setups.pop(state_id, None)

    bot_user = (await client.get_me()).username
    bot_link = f"https://t.me/{bot_user}?start={item_id}"

    success_text = (
        f"✅ <b>sᴛᴏʀỹ  sᴇᴛᴜᴘ  ғɪɴɪsʜᴇᴅ!</b>\n"
        f"──────────────────────────\n"
        f"📂 <b>Source:</b> <code>{platform.upper()}</code>\n"
        f"⏱️ <b>Validity:</b> {data['validity_days']} Din\n"
        f"💰 <b>Price:</b> ₹{data['price']}\n"
        f"📝 <b>Description:</b> {data['description']}\n"
        f"📺 <b>Demo:</b> {data['demo_link'] if data['demo_link'] else 'None'}\n\n"
        f"🔗 <b>sʜᴀʀᴇ ʟɪɴᴋ (ꜰᴏʀ ᴜsᴇʀs):</b>\n<code>{bot_link}</code>\n"
        f"──────────────────────────"
    )

    if data["file_id"]:
        await client.send_photo(
            call.message.chat.id,
            photo=data["file_id"],
            caption=success_text,
            parse_mode=ParseMode.HTML,
        )
    else:
        await client.send_message(
            call.message.chat.id, text=success_text, parse_mode=ParseMode.HTML
        )


# =====================================================================
# ─── 5. FINITE STATE MACHINE (FSM) MESSAGE HANDLER ───
# =====================================================================
@Client.on_message(
    filters.private
    & filters.user(config.ADMIN_ID)
    & ~filters.command(["remove", "channels", "add", "add_combo", "cancel"])
)
async def admin_fsm_router(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in ADMIN_STEPS:
        return

    state_info = ADMIN_STEPS[user_id]
    step = state_info.get("step")
    data = state_info.get("data", {})

    # --- 1. REMOVE USER STEP ---
    if step == "WAITING_REMOVE_ID":
        try:
            u_id = int(message.text.strip())
            result = await users_col.delete_many({"user_id": u_id})
            ADMIN_STEPS.pop(user_id, None)

            if result.deleted_count > 0:
                await message.reply_text(
                    f"✅ <b>Success!</b>\nUser <code>{u_id}</code> ka access hata diya gaya.",
                    parse_mode=ParseMode.HTML,
                )
                try:
                    await client.send_message(
                        u_id,
                        "⚠️ <b>Access Revoked:</b> Aapka subscription khatam kar diya gaya hai.",
                    )
                except Exception:
                    pass
            else:
                await message.reply_text(
                    "❓ Is ID ka koi active subscription nahi mila."
                )
        except ValueError:
            await message.reply_text("❌ Invalid ID! Sirf numbers bhejein.")

    # --- 2. DELETE ALL SECURITY CODE STEP ---
    elif step == "WAITING_SECURITY_CODE":
        ADMIN_STEPS.pop(user_id, None)
        if message.text and message.text.strip() == "CONFIRM DELETE ALL":
            result = await channels_col.delete_many({})
            await message.reply_text(
                f"💥 <b>DATABASE WIPED OUT!</b>\n\nInventory se saari <code>{result.deleted_count}</code> items ko permanently uda diya gaya hai.",
                parse_mode=ParseMode.HTML,
            )
        else:
            await message.reply_text(
                "🚫 <b>Security Code Match Nahi Hua!</b> Operation block kar diya gaya hai.",
                parse_mode=ParseMode.HTML,
            )

    # --- 3. ADD CHANNEL FLOW ---
    elif step == "ADD_FORWARD_POST":
        is_forwarded = bool(
            message.forward_from_chat or message.forward_from or message.forward_date
        )

        if is_forwarded:
            if message.forward_from_chat:
                ch_id = message.forward_from_chat.id
                ch_name = message.forward_from_chat.title
            else:
                ch_id = message.chat.id
                ch_name = "Private/Hidden Channel"

            data["ch_id"] = ch_id
            data["ch_name"] = ch_name
            ADMIN_STEPS[user_id] = {"step": "ADD_VALIDITY", "data": data}

            await message.reply_text(
                f"✅ <b>Channel Detected:</b> {ch_name}\n"
                f"🆔 <b>ID:</b> <code>{ch_id}</code>\n\n"
                f"⏱| <b>⏳ ᴠᴀʟɪᴅɪᴛʏ:</b>\n"
                f"Yeh data kitne din tak valid rakhna hai? (Sirf numbers likhein, jaise: 30):",
                parse_mode=ParseMode.HTML,
            )
        else:
            await message.reply_text(
                "❌ <b>Galat Input!</b> Kripya channel se post forward karein (ya /cancel):",
                parse_mode=ParseMode.HTML,
            )

    elif step == "ADD_VALIDITY":
        validity_days = message.text.strip() if message.text else ""
        if not validity_days.isdigit():
            return await message.reply_text(
                "❌ <b>Invalid Days!</b> Kripya sirf digits/numbers bhejein (Eg: 30):",
                parse_mode=ParseMode.HTML,
            )

        data["validity_days"] = validity_days
        ADMIN_STEPS[user_id] = {"step": "ADD_PRICE", "data": data}

        await message.reply_text(
            f"💰 <b>ᴘʀɪᴄɪɴɢ:</b>\n"
            f"Is <code>{validity_days}</code> Din ke liye kitna <b>Price (₹)</b> rakhna hai? (Jaise: 49):",
            parse_mode=ParseMode.HTML,
        )

    elif step == "ADD_PRICE":
        price = message.text.strip() if message.text else ""
        if not price.isdigit():
            return await message.reply_text(
                "❌ <b>Invalid Price!</b> Kripya sirf plain number bhejein (Eg: 49):",
                parse_mode=ParseMode.HTML,
            )

        data["price"] = price
        ADMIN_STEPS[user_id] = {"step": "ADD_DESC", "data": data}

        await message.reply_text(
            "📝 <b>sᴛᴏʀʏ  ᴅᴇsᴄʀɪᴘᴛɪᴏɴ:</b>\n\n"
            "Is channel ke andar kaun-kaun si hot/premium stories milengi? Unki ek list ya description bhejiyen "
            "(Taaki user buy karne se pehle padh sake):",
            parse_mode=ParseMode.HTML,
        )

    elif step == "ADD_DESC":
        desc = message.text.strip() if message.text else ""
        data["description"] = desc
        ADMIN_STEPS[user_id] = {"step": "ADD_PHOTO", "data": data}

        await message.reply_text(
            "🖼️ <b>**ᴄʜᴀɴɴᴇʟ ᴘʜᴏᴛᴏ:**</b>\n"
            "Aap is channel ke liye koi custom photo lagana chahte hain?\n\n"
            "➔ Ek <b>Photo</b> bhejein.\n"
            "➔ Ya bina photo ke aage badhne ke liye <code>skip</code> likhein:",
            parse_mode=ParseMode.HTML,
        )

    elif step == "ADD_PHOTO":
        file_id = None
        if message.photo:
            file_id = message.photo.file_id
        elif message.text and message.text.strip().lower() != "skip":
            return await message.reply_text(
                "⚠️ Kripya ya toh ek <b>Photo</b> upload karein ya fir plain text me <code>skip</code> likhein:",
                parse_mode=ParseMode.HTML,
            )

        data["file_id"] = file_id
        ADMIN_STEPS[user_id] = {"step": "ADD_DEMO", "data": data}
        await message.reply_text("🔗 <b>Demo Link bhejein</b> (Ya 'skip' ya 'none' likhein):")

    elif step == "ADD_DEMO":
        raw_text = message.text.strip() if message.text else ""
        demo = None if raw_text.lower() in ["none", "skip", ""] else raw_text

        if demo and not is_valid_url(demo):
            return await message.reply_text(
                "❌ <b>Format Error!</b> Aapne jo link bheja hai vo sahi URL format me nahi hai. Kripya valid http/https link bhejein ya <code>skip</code> karein:",
                parse_mode=ParseMode.HTML,
            )

        data["demo_link"] = demo
        state_id = str(uuid.uuid4())[:8]
        pending_setups[state_id] = data
        ADMIN_STEPS.pop(user_id, None)

        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Pocket", callback_data=f"newsrc_pocket_{state_id}"
                    ),
                    InlineKeyboardButton(
                        "Pratilipi", callback_data=f"newsrc_pratilipi_{state_id}"
                    ),
                ]
            ]
        )
        await message.reply_text(
            "📂 <b>Select Category:</b>",
            reply_markup=markup,
            parse_mode=ParseMode.HTML,
        )

    # --- 4. ADD COMBO FLOW ---
    elif step == "COMBO_NAME":
        combo_name = message.text.strip() if message.text else ""
        data["combo_name"] = combo_name
        ADMIN_STEPS[user_id] = {"step": "COMBO_VALIDITY", "data": data}

        await message.reply_text(
            "⏱️ <b>⏳ ᴠᴀʟɪᴅɪᴛʏ:</b>\n"
            "Yeh combo bundle kitne din tak valid rahega? (Jaise: 30):",
            parse_mode=ParseMode.HTML,
        )

    elif step == "COMBO_VALIDITY":
        validity_days = message.text.strip() if message.text else ""
        if not validity_days.isdigit():
            return await message.reply_text(
                "❌ <b>Invalid Days!</b> Kripya sirf numbers bhejein (Eg: 30):",
                parse_mode=ParseMode.HTML,
            )

        data["validity_days"] = validity_days
        ADMIN_STEPS[user_id] = {"step": "COMBO_PRICE", "data": data}

        await message.reply_text(
            "💰 <b>ᴘʀɪᴄɪɴɢ:</b>\n"
            "Is total combo package ka <b>Price (₹)</b> kitna rakhna hai? (Jaise: 149):",
            parse_mode=ParseMode.HTML,
        )

    elif step == "COMBO_PRICE":
        price = message.text.strip() if message.text else ""
        if not price.isdigit():
            return await message.reply_text(
                "❌ <b>Invalid Price!</b> Kripya sirf number dalein (Eg: 149):",
                parse_mode=ParseMode.HTML,
            )

        data["price"] = price
        ADMIN_STEPS[user_id] = {"step": "COMBO_DESC", "data": data}

        await message.reply_text(
            "📝 <b>ᴄᴏᴍʙᴏ  ᴅᴇsᴄʀɪᴘᴛɪᴏɴ:</b>\n\n"
            "Is combo bundle pack ke andar <b>kaun-kaun si stories</b> milne vali hain, details me likh kar send karein:",
            parse_mode=ParseMode.HTML,
        )

    elif step == "COMBO_DESC":
        desc = message.text.strip() if message.text else ""
        data["description"] = desc
        ADMIN_STEPS[user_id] = {"step": "COMBO_PHOTO", "data": data}

        await message.reply_text(
            "🖼️ <b>ᴄᴏᴍʙᴏ ᴘʜᴏᴛᴏ:</b>\n"
            "Is bundle banner ke liye koi photo lagani hai?\n\n"
            "➔ Ek <b>Photo</b> send karein.\n"
            "➔ Ya skip karne ke liye <code>skip</code> likhein:",
            parse_mode=ParseMode.HTML,
        )

    elif step == "COMBO_PHOTO":
        file_id = None
        if message.photo:
            file_id = message.photo.file_id
        elif message.text and message.text.strip().lower() != "skip":
            return await message.reply_text(
                "⚠️ Kripya photo send karein ya <code>skip</code> text likhein:",
                parse_mode=ParseMode.HTML,
            )

        data["file_id"] = file_id
        ADMIN_STEPS[user_id] = {"step": "COMBO_DEMO", "data": data}
        await message.reply_text("🔗 <b>Demo Link bhejein</b> (Ya 'skip' ya 'none' likhein):")

    elif step == "COMBO_DEMO":
        raw_text = message.text.strip() if message.text else ""
        demo = None if raw_text.lower() in ["none", "skip", ""] else raw_text

        if demo and not is_valid_url(demo):
            return await message.reply_text(
                "❌ <b>Format Error!</b> Sahi URL structure bhejein (Eg: https://...) ya skip likhein:",
                parse_mode=ParseMode.HTML,
            )

        data["demo_link"] = demo
        ADMIN_STEPS[user_id] = {"step": "COMBO_CHANNELS", "data": data}

        await message.reply_text(
            "🆔 <b>ᴄʜᴀɴɴᴇʟ ɪᴅs ʟɪsᴛ:</b>\n"
            "Is combo bundle ke andar aane wale saare channels ki <b>IDs</b> comma ( , ) laga kar dein:\n\n"
            "➔ <code>-100123456,-100987654</code>",
            parse_mode=ParseMode.HTML,
        )

    elif step == "COMBO_CHANNELS":
        raw_ids = message.text.strip().replace(" ", "") if message.text else ""
        try:
            channel_ids_list = [int(cid) for cid in raw_ids.split(",") if cid]
            if not channel_ids_list:
                raise ValueError
        except ValueError:
            return await message.reply_text(
                "❌ <b>Format Error!</b> Keval Valid Channel IDs aur comma ka use karein. Dobara valid IDs bhejein:"
            )

        combo_name = data.get("combo_name")
        validity_days = data.get("validity_days")
        price = data.get("price")
        desc = data.get("description")
        file_id = data.get("file_id")
        demo = data.get("demo_link")

        item_id = f"combo_{str(uuid.uuid4())[:10]}"

        await channels_col.insert_one(
            {
                "item_id": item_id,
                "name": combo_name,
                "combo_name": combo_name,
                "is_combo": True,
                "validity": validity_days,
                "price": price,
                "description": desc,
                "file_id": file_id,
                "demo_link": demo,
                "channels_list": channel_ids_list,
                "source": "combo",
                "type": "combo",
            }
        )

        ADMIN_STEPS.pop(user_id, None)

        bot_user = (await client.get_me()).username
        bot_link = f"https://t.me/{bot_user}?start={item_id}"

        success_text = (
            f"✅ <b>🎁 sᴘᴇᴄɪᴀʟ ᴄᴏᴍʙᴏ sᴀᴠᴇᴅ ɪɴ sᴛᴏʀᴇ!</b>\n"
            f"──────────────────────────\n"
            f"🎁 <b>ᴄᴏᴍʙᴏ ɴᴀ:</b> <code>{combo_name}</code>\n"
            f"⏱️ <b>ᴠᴀʟɪᴅɪᴛʏ:</b> {validity_days} Din\n"
            f"💰 <b>ᴘʀɪᴄᴇ:</b> ₹{price}\n"
            f"📝 <b>ᴅᴇsᴄʀɪᴘᴛɪᴏɴ:</b> <i>{desc}</i>\n"
            f"📊 <b>ᴄʜᴀɴɴᴇʟs:</b> {len(channel_ids_list)} Linked\n\n"
            f"🔗 <b>sʜᴀʀᴇ ʟɪɴᴋ (ᴜsᴇʀs):</b>\n<code>{bot_link}</code>\n"
            f"──────────────────────────"
        )

        if file_id:
            await message.reply_photo(
                photo=file_id, caption=success_text, parse_mode=ParseMode.HTML
            )
        else:
            await message.reply_text(
                text=success_text, parse_mode=ParseMode.HTML
            )
