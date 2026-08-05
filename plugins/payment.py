import asyncio
import logging
import time
import urllib.parse

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus, ChatType, ParseMode
from pyrogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config
from database import channels_col, users_col

logger = logging.getLogger(__name__)

# FSM dictionary for managing screenshot submission steps
# Format: { user_id: {"item_id": str, "mins": str} }
PAYMENT_STEPS = {}


# ===================================================
# --- EXTRA CONFIG: FRESH START MENU RE-LOAD ---
# ===================================================
async def send_home_menu(client: Client, chat_id: int):
    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("« ʙᴀᴄᴋ ᴛᴏ ᴍᴇɴᴜ", callback_data="back_to_start")]]
    )

    await client.send_message(
        chat_id,
        "❌ <b>ᴘᴀʏᴍᴇɴᴛ ᴄᴀɴᴄᴇʟʟᴇᴅ!</b>\n\n"
        "Aapka current payment process rok diya gaya hai. Aap niche दिए गए menu se fir se shuru kar sakte hain:",
        reply_markup=markup,
        parse_mode=ParseMode.HTML,
    )


# --- 1. PAYMENT SELECTION ---
@Client.on_callback_query(filters.regex(r"^select_"))
async def confirm_step(client: Client, call: CallbackQuery):
    parts = call.data.split("_")
    mins = parts[-1]
    item_id = "_".join(parts[1:-1])

    # Motor Async DB Find
    data = await channels_col.find_one({"item_id": item_id})
    if not data and item_id.replace("-", "").isdigit():
        data = await channels_col.find_one({"channel_id": int(item_id)})

    if not data:
        return await call.answer(
            f"❌ Data not found! (ID: {item_id})", show_alert=True
        )

    if data.get("is_combo"):
        price = data.get("price", "0")
        display_name = data.get("combo_name", "Premium Combo")
    elif "story_name" in data:
        price = data.get("price", "0")
        display_name = data.get("story_name")
    else:
        plans = data.get("plans")
        price = (
            plans.get(mins, "0")
            if isinstance(plans, dict)
            else data.get("price", "0")
        )
        display_name = data.get("name", "Premium Channel")

    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💳 ᴘᴀʏ ᴠɪ VIA ǫʀ sᴄᴀɴ",
                    callback_data=f"man_{item_id}_{mins}_qr",
                )
            ],
            [
                InlineKeyboardButton(
                    "📲 ᴘᴀʏ ᴠɪ VIA ᴜᴘɪ ɪᴅ",
                    callback_data=f"man_{item_id}_{mins}_upi",
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ ᴄᴀɴᴄᴇʟ ᴘᴀʏᴍᴇɴᴛ", callback_data="cancel_payment"
                )
            ],
        ]
    )

    text = (
        f"<b>🛒 ᴄᴏɴғɪʀᴍ sᴇʟᴇᴄᴛɪᴏɴ</b>\n"
        f"────────────────────\n"
        f"📦 ɪᴛᴇᴍ: <b>{display_name}</b>\n"
        f"💰 ᴀᴍᴏᴜɴᴛ: <b>₹{price}</b>\n\n"
        f"➔ Payment method select karein:"
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    await client.send_message(
        call.message.chat.id, text, reply_markup=markup, parse_mode=ParseMode.HTML
    )


# --- 2. MANUAL PAYMENT SYSTEM ---
@Client.on_callback_query(filters.regex(r"^man_"))
async def manual_pay(client: Client, call: CallbackQuery):
    parts = call.data.split("_")
    mode = parts[-1]
    mins = parts[-2]
    item_id = "_".join(parts[1:-2])

    data = await channels_col.find_one({"item_id": item_id})
    if not data and item_id.replace("-", "").isdigit():
        data = await channels_col.find_one({"channel_id": int(item_id)})

    if not data:
        return await call.answer("❌ Data Error on Payment!", show_alert=True)

    if data.get("is_combo") or "story_name" in data:
        price = data.get("price", "0")
    else:
        plans = data.get("plans")
        price = (
            plans.get(mins, "0")
            if isinstance(plans, dict)
            else data.get("price", "0")
        )

    upi_string = f"upi://pay?pa={config.UPI_ID}&am={price}&cu=INR&tn=Pay_{item_id}"
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=350x350&data={urllib.parse.quote(upi_string)}"

    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ sᴜʙᴍɪᴛ sᴄʀᴇᴇɴsʜᴏᴛ", callback_data=f"paid_{item_id}_{mins}"
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ ᴄᴀɴᴄᴇʟ ᴘᴀʏᴍᴇɴᴛ", callback_data="cancel_payment"
                )
            ],
        ]
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    if mode == "qr":
        await client.send_photo(
            call.message.chat.id,
            photo=qr_url,
            caption=f"📥 <b>ǫʀ sᴄᴀɴɴᴇʀ</b>\n\nAmount: <b>₹{price}</b>\n\n➔ Pay karke niche wala button dabayein.",
            reply_markup=markup,
            parse_mode=ParseMode.HTML,
        )
    else:
        await client.send_message(
            call.message.chat.id,
            f"📲 <b>ᴜᴘɪ ɪᴅ:</b> <code>{config.UPI_ID}</code>\nAmount: <b>₹{price}</b>\n\n➔ Pay karne ke baad niche button dabayein.",
            reply_markup=markup,
            parse_mode=ParseMode.HTML,
        )


# --- 3. DIRECT SCREENSHOT SUBMISSION (FSM TRIGGER & INPUT HANDLER) ---
@Client.on_callback_query(filters.regex(r"^paid_"))
async def handle_paid(client: Client, call: CallbackQuery):
    parts = call.data.split("_")
    mins = parts[-1]
    item_id = "_".join(parts[1:-1])
    await call.answer()

    # Save state to FSM Dictionary
    PAYMENT_STEPS[call.from_user.id] = {"item_id": item_id, "mins": mins}

    try:
        await call.message.delete()
    except Exception:
        pass

    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ ᴘᴀʏᴍᴇɴᴛ", callback_data="cancel_payment")]]
    )

    await client.send_message(
        call.message.chat.id,
        "📸 Payment ka <b>Screenshot</b> bhejein:\n\n"
        "➔ <i>Agar cancel karna chahte hain toh niche button par click karein ya chat me <code>/cancel</code> likhein.</i>",
        reply_markup=markup,
        parse_mode=ParseMode.HTML,
    )


# Private Message Handler for Screenshot Receipt
@Client.on_message(filters.private & ~filters.command)
async def process_screenshot_input(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in PAYMENT_STEPS:
        return

    # Check for text cancellation
    if message.text and message.text.strip().lower() in ["/cancel", "cancel"]:
        PAYMENT_STEPS.pop(user_id, None)
        return await send_home_menu(client, message.chat.id)

    # Reject non-photo messages
    if not message.photo:
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ ᴘᴀʏᴍᴇɴᴛ", callback_data="cancel_payment")]]
        )
        return await message.reply_text(
            "❌ Please sirf Photo (Screenshot) bhejein!\n"
            "Cancel karne ke liye <code>/cancel</code> likhein ya neeche click karein:",
            reply_markup=markup,
            parse_mode=ParseMode.HTML,
        )

    # Process photo
    step_data = PAYMENT_STEPS.pop(user_id)
    item_id = step_data["item_id"]
    mins = step_data["mins"]
    photo_id = message.photo.file_id

    data = await channels_col.find_one({"item_id": item_id})
    if not data and item_id.replace("-", "").isdigit():
        data = await channels_col.find_one({"channel_id": int(item_id)})

    if not data:
        return await message.reply_text("❌ Something went wrong, item not found!")

    display_name = (
        data.get("combo_name") or data.get("story_name") or data.get("name")
    )
    await message.reply_text(
        "⏳ <b>ʀᴇǫᴜᴇsᴛ sᴇɴᴛ!</b>\nAdmin check karke aapka access on kar dega.",
        parse_mode=ParseMode.HTML,
    )

    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Approve",
                    callback_data=f"app_{user_id}_{item_id}_{mins}",
                ),
                InlineKeyboardButton(
                    "❌ Reject", callback_data=f"rej_{user_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "💬 Support", url=f"tg://openmessage?user_id={user_id}"
                )
            ],
        ]
    )

    admin_text = (
        f"📥 <b>ɴᴇᴡ ᴘᴀʏᴍᴇɴᴛ ʀᴇǫᴜᴇsᴛ</b>\n"
        f"────────────────────\n"
        f"👤 User ID: <code>{user_id}</code>\n"
        f"📦 Item: <b>{display_name}</b>\n"
        f"⏳ Plan: {mins if mins != 'manual' else 'Lifetime'}"
    )

    await client.send_photo(
        config.ADMIN_ID,
        photo=photo_id,
        caption=admin_text,
        reply_markup=markup,
        parse_mode=ParseMode.HTML,
    )


# Cancel Payment Button
@Client.on_callback_query(filters.regex(r"^cancel_payment$"))
async def process_inline_cancel(client: Client, call: CallbackQuery):
    await call.answer("Process Cancelled!")
    PAYMENT_STEPS.pop(call.from_user.id, None)

    try:
        await call.message.delete()
    except Exception:
        pass

    await send_home_menu(client, call.message.chat.id)


# --- 4. ADMIN APPROVAL CONTROL PANEL ---
@Client.on_callback_query(filters.regex(r"^app_"))
async def admin_approve(client: Client, call: CallbackQuery):
    parts = call.data.split("_")
    u_id = parts[1]
    mins = parts[-1]

    # Handle item_id with embedded underscores
    if "_join" in call.data:
        item_id = "_join".join(parts[2:-1])
    else:
        item_id = "_".join(parts[2:-1])

    data = await channels_col.find_one({"item_id": item_id})
    if not data and item_id.replace("-", "").isdigit():
        data = await channels_col.find_one({"channel_id": int(item_id)})

    if not data:
        return await call.answer(
            "❌ Data not found on Approval!", show_alert=True
        )

    expiry = (
        int(time.time()) + (int(mins) * 60)
        if mins != "manual"
        else int(time.time()) + (365 * 24 * 60 * 60)
    )
    markup = InlineKeyboardMarkup([])

    # ─── CASE A: COMBO PACK APPROVAL ───
    if data.get("is_combo") and "channels_list" in data:
        msg = "🎁 <b>ᴄᴏᴍʙᴏ ᴘᴀᴄᴋ ᴀᴘᴘʀᴏᴠᴇᴅ!</b>\n\nAapko sabhi linked channels ka access de diya gaya hai. Niche diye buttons se join karein:\n\n"
        for ch_id in data["channels_list"]:
            await users_col.update_one(
                {"user_id": int(u_id), "channel_id": int(ch_id)},
                {"$set": {"expiry": expiry}},
                upsert=True,
            )
            try:
                invite = await client.create_chat_invite_link(
                    int(ch_id), member_limit=1
                )
                ch_info = await channels_col.find_one({"channel_id": int(ch_id)})
                ch_title = (
                    ch_info.get("name") or ch_info.get("story_name")
                    if ch_info
                    else f"VIP Channel {ch_id}"
                )
                markup.inline_keyboard.append(
                    [InlineKeyboardButton(f"📢 Join: {ch_title}", url=invite.invite_link)]
                )
            except Exception as e:
                logger.error(f"Combo Link Error: {e}")
        msg += "⚠️ <i>Links single-use hain, ek baar join hone ke baad automatic expire ho jayengi!</i>"

    # ─── CASE B: FORWARDED CHANNEL (/add Flow) ───
    elif data.get("type") == "channel" or (
        "channel_id" in data
        and data.get("source") not in ["pocket", "pratilipi"]
        and not data.get("is_combo")
    ):
        target_channel = int(data["channel_id"])
        await users_col.update_one(
            {"user_id": int(u_id), "channel_id": target_channel},
            {"$set": {"expiry": expiry}},
            upsert=True,
        )
        try:
            invite = await client.create_chat_invite_link(
                chat_id=target_channel, member_limit=1, name=f"Paid_{u_id}"
            )
            markup.inline_keyboard.append(
                [InlineKeyboardButton("🔐 JOIN PREMIUM CHANNEL", url=invite.invite_link)]
            )

            validity_display = data.get("validity", mins)
            msg = (
                f"✅ <b>ᴀᴘᴘʀᴏᴠᴇᴅ!</b>\n\n"
                f"📂 <b>ᴄʜᴀɴɴᴇʟ:</b> <b>{data.get('name', 'VIP Channel')}</b>\n"
                f"⏱️ <b>ᴠᴀʟɪᴅɪᴛʏ:</b> {validity_display if validity_display != 'manual' else 'Lifetime'}\n\n"
                f"Join karne ke liye neeche button par click karein:\n\n"
                f"⚠️ <i>Yeh link single use hai, ek baar use hone ke baad automatic expire ho jayegi!</i>"
            )
        except Exception as e:
            logger.error(f"Invite Link Error: {e}")
            msg = "✅ <b>ᴀᴘᴘʀᴏᴠᴇᴅ!</b>\n\nBot link generate nahi kar saka, admin rights setup check karein."

    # ─── CASE C: MANUAL PREMIUM STORY (/add_story Flow) ───
    else:
        await users_col.update_one(
            {"user_id": int(u_id), "channel_id": data.get("channel_id", 0)},
            {"$set": {"expiry": expiry}},
            upsert=True,
        )
        target_link = (
            data.get("bot_link") or data.get("final_link") or "https://t.me"
        )

        markup.inline_keyboard.append(
            [InlineKeyboardButton("🚀 sᴛᴀʀᴛ sᴛᴏʀỹ", url=target_link)]
        )

        platform_info = (
            f"\n📂 Platform: <code>{data.get('source')}</code>"
            if data.get("source")
            else ""
        )
        msg = (
            f"🎉 <b>ᴘᴀʏᴍᴇɴᴛ ᴀᴘᴘʀᴏᴠᴇᴅ!</b>\n"
            f"────────────────────\n"
            f"📖 <b>sᴛᴏʀỹ:</b> {data.get('story_name', 'Premium Story')}"
            f"{platform_info}\n"
            f"💰 <b>ᴘʀɪᴄᴇ:</b> ₹{data.get('price', '49')}\n"
            f"────────────────────\n"
            f"➔ Niche diye gaye button par click karke apni full story access karein 👇"
        )

    try:
        if (
            "story_name" in data
            and data.get("file_id")
            and data.get("type") != "channel"
        ):
            await client.send_photo(
                u_id,
                photo=data["file_id"],
                caption=msg,
                reply_markup=markup,
                parse_mode=ParseMode.HTML,
                protect_content=True,
            )
        else:
            await client.send_message(
                u_id,
                msg,
                reply_markup=markup,
                parse_mode=ParseMode.HTML,
                protect_content=True,
            )
    except Exception as e:
        logger.error(f"Delivery Error: {e}")

    await call.edit_message_caption(f"✅ Approved for User: {u_id}")


@Client.on_callback_query(filters.regex(r"^rej_"))
async def admin_reject(client: Client, call: CallbackQuery):
    u_id = call.data.split("_")[1]
    await call.edit_message_caption("❌ Payment Rejected!")
    try:
        await client.send_message(
            u_id, "❌ Aapka payment reject ho gaya hai. Support se baat karein."
        )
    except Exception:
        pass


# --- 5. AUTOMATIC LINK REVOKE ---
@Client.on_chat_member_updated()
async def handle_chat_member_updates(client: Client, update: ChatMemberUpdated):
    if update.chat.type != ChatType.CHANNEL:
        return

    old_status = update.old_chat_member.status if update.old_chat_member else None
    new_status = update.new_chat_member.status if update.new_chat_member else None

    # Check if a user joined via invite link
    if new_status == ChatMemberStatus.MEMBER and old_status in [
        ChatMemberStatus.LEFT,
        ChatMemberStatus.BANNED,
        ChatMemberStatus.RESTRICTED,
    ]:
        if update.invite_link and update.invite_link.invite_link:
            used_link = update.invite_link.invite_link
            channel_id = update.chat.id
            try:
                await client.revoke_chat_invite_link(
                    chat_id=channel_id, invite_link=used_link
                )
                logger.info(f"[SUCCESS] Revoked: {used_link}")
            except Exception as e:
                logger.error(f"[ERROR] Revoke failed: {e}")
