import asyncio
from datetime import datetime
import logging
import uuid

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
    WebAppInfo,
)

import config
from database import channels_col, users_col
from plugins.store import (
    get_categories_markup,
    get_items_by_category_markup,
    get_store_text,
)
from utils import get_time_string

logger = logging.getLogger(__name__)

# State Manager (from config or local fallback)
USER_STATES = getattr(config, "USER_STATES", {})


# ─── 1. START HANDLER & DEEP LINK ROUTER ───
@Client.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    USER_STATES[user_id] = {"category": "home", "page": 1}

    # ── DEEP LINK PARAMETER CHECK ──
    if len(message.command) > 1:
        param = message.command[1]

        # Async Motor DB Queries
        data = await channels_col.find_one({"item_id": param})
        if not data and (param.replace("-", "").isdigit()):
            data = await channels_col.find_one({"channel_id": int(param)})

        if data:
            db_id = data.get("item_id") or data.get("channel_id")
            keyboard = []

            # [FLOW A] Combo Pack
            if data.get("is_combo"):
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"💳 🎁 ᴜɴʟᴏᴄᴋ ᴄᴏᴍʙᴏ - ₹{data['price']}",
                            callback_data=f"select_{db_id}_manual",
                        )
                    ]
                )
                display_name = data["combo_name"]
                header = "🎁 <b>ᴘʀᴇᴍɪᴜᴍ sᴘᴇᴄɪᴀʟ ᴄᴏᴍʙᴏ ʙᴜɴᴅʟᴇ</b>"
                desc_text = f"📝 <b>ɪɴᴄʟᴜᴅᴇᴅ sᴛᴏʀɪᴇs:</b>\n<i>{data.get('description', 'Multiple premium stories inside!')}</i>"

            # [FLOW B] Forwarded Channel (/add flow)
            elif "channel_id" in data and not data.get("story_name"):
                if data.get("plans") and isinstance(data["plans"], dict):
                    for p_time, p_price in data["plans"].items():
                        keyboard.append(
                            [
                                InlineKeyboardButton(
                                    f"💳 {get_time_string(p_time)} - ₹{p_price}",
                                    callback_data=f"select_{db_id}_{p_time}",
                                )
                            ]
                        )
                else:
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                f"✅ CONFIRM & PAY - ₹{data.get('price', '49')}",
                                callback_data=f"select_{db_id}_manual",
                            )
                        ]
                    )
                display_name = data.get("name", "Premium Access")
                header = "💎 <b>ᴘʀᴇᴍɪᴜᴍ ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀɴɴᴇʟ</b>"
                desc_text = "🤖 <b>ᴅᴇʟɪᴠᴇʀʏ:</b> <code><b>ᴄʜᴀɴɴᴇʟ ɪɴᴠɪᴛᴇ ʟɪɴᴋ (𝟷-ᴛɪᴍᴇ ᴜsᴇ)</b></code>\nℹ️ <i>Isme join hone ke liye direct temporary invite link milega.</i>"

            # [FLOW C] Direct Story (/add_story flow)
            else:
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"💳 🎧 ᴜɴʟᴏᴄᴋ sᴛᴏʀʏ - ₹{data.get('price', '49')}",
                            callback_data=f"select_{db_id}_manual",
                        )
                    ]
                )
                display_name = data.get("story_name")
                header = f"🔥 <b>ᴘʀᴇᴍɪᴜᴍ ᴇxᴄʟᴜsɪᴠᴇ sᴛᴏʀʏ ({data.get('source', 'audio')})</b>"
                desc_text = "🤖 <b>ᴅᴇʟɪᴠᴇʀʏ:</b> <code><b>ɪsᴛᴀɴᴛ ʙᴏᴛ ʟɪɴᴋ ᴀᴄᴄᴇss</b></code>\nℹ️ <i>Isme payment ke baad direct external link ya redirection button milega.</i>"

            if data.get("demo_link"):
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            "📺 ᴠɪᴇᴡ ǫᴜᴀʟɪᴛʏ ᴅᴇᴍᴏ (ᴛᴇᴀsᴇʀ)",
                            url=data["demo_link"],
                        )
                    ]
                )

            keyboard.append(
                [
                    InlineKeyboardButton(
                        "🏠 ʙᴀᴄᴋ ᴛᴏ ᴍᴇɴᴜ", callback_data="back_to_start"
                    )
                ]
            )

            markup = InlineKeyboardMarkup(keyboard)
            premium_text = f"{header}\n──────────────────────────\n📦 <b>ᴘᴀᴄᴋ ɴᴀᴍᴇ:</b> <code>{display_name}</code>\n\n{desc_text}\n──────────────────────────"

            photo_id = data.get("file_id")
            if photo_id:
                return await client.send_photo(
                    chat_id,
                    photo=photo_id,
                    caption=premium_text,
                    reply_markup=markup,
                    parse_mode=ParseMode.HTML,
                )
            else:
                return await client.send_message(
                    chat_id,
                    premium_text,
                    reply_markup=markup,
                    parse_mode=ParseMode.HTML,
                )

    # ── MAIN DASHBOARD PANEL ──
    miniapp_url = getattr(config, "MINIAPP_URL", "https://your-miniapp-url.com")

    dashboard_keyboard = [
        [
            InlineKeyboardButton(
                "🚀 ᴏᴘᴇɴ ᴍɪɴɪ ᴀᴘᴘ 🚀", web_app=WebAppInfo(url=miniapp_url)
            )
        ],
        [
            InlineKeyboardButton("🛍️ ᴏᴘᴇɴ sᴛᴏʀᴇ", callback_data="open_store"),
            InlineKeyboardButton(
                "🎁 ᴍᴀᴋᴇ ᴄᴜsᴛᴏᴍ ᴄᴏᴍʙᴏ", callback_data="create_combo"
            ),
        ],
        [
            InlineKeyboardButton("👤 ᴍʏ ᴅᴀsʜʙᴏᴀʀᴅ", callback_data="my_plan"),
            InlineKeyboardButton(
                "📞 🌟 ʟɪᴠᴇ sᴜᴘᴘᴏʀᴛ",
                url=f"https://t.me/{config.CONTACT_USERNAME}",
            ),
        ],
    ]

    if user_id == config.ADMIN_ID:
        dashboard_keyboard.extend(
            [
                [
                    InlineKeyboardButton(
                        "➕ ᴀᴅᴅ sᴛᴏʀʏ", callback_data="admin_story"
                    ),
                    InlineKeyboardButton(
                        "📺 ᴀᴅᴅ ᴄʜᴀɴɴᴇʟ", callback_data="admin_add"
                    ),
                    InlineKeyboardButton(
                        "🎁 ᴄʀᴇᴀᴛᴇ ᴄᴏᴍʙᴏ", callback_data="admin_combo"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "⚙️ ᴍᴀɴᴀɢᴇ ᴀʟʟ", callback_data="admin_channels"
                    ),
                    InlineKeyboardButton(
                        "❌ ʀᴇᴍᴏᴠᴇ sᴜʙ", callback_data="admin_remove"
                    ),
                ],
            ]
        )

    markup = InlineKeyboardMarkup(dashboard_keyboard)
    title = "╔════════════════════════════╗\n       ✨ sᴛᴏʀʏ x ᴅᴇᴍᴏ ✨\n╚════════════════════════════╝"
    desc = (
        "ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ᴏғғɪᴄɪᴀʟ sᴛᴏʀʏ sᴇʟʟᴇʀ ʙᴏᴛ!\n\n"
        "ᴛʜɪs ʙᴏᴛ sᴇʟʟs ᴀʟʟ ᴛʜᴇ ᴘʀᴇᴍɪᴜᴍ ᴀɴᴅ ʟᴀᴛᴇsᴛ sᴛᴏʀɪᴇs ᴏғ ᴘᴏᴄᴋᴇᴛ ғᴍ ᴀɴᴅ ᴘʀᴀᴛɪʟɪᴘɪ ғᴍ. "
        "ʏᴏᴜ ᴄʜᴇᴄᴋ ᴛʜᴇ ᴅᴇᴍᴏ ғɪʟᴇs ʜᴇʀᴇ ʙᴇғᴏʀᴇ ᴍᴀᴋɪɴɢ ᴀ ᴘᴜʀᴄʜᴀsᴇ!\n\n"
        "⚡ ɪɴsᴛᴀɴᴛ ᴅᴇᴍᴏ | ᴀᴜᴛᴏ ᴘᴀʏᴍᴇɴᴛ | ᴀᴜᴛᴏ ᴅᴇʟɪᴠᴇʀʏ"
    )

    await client.send_message(
        chat_id,
        f"{title}\n\n{desc}",
        reply_markup=markup,
        parse_mode=ParseMode.HTML,
    )


# ─── 2. TEXT NAVIGATION HANDLERS ───
NAV_BTNS = [
    "✨ ᴘʀᴀᴛɪʟɪᴘɪ ғᴍ sᴛᴏʀɪᴇs",
    "🔥 ᴘᴏᴄᴋᴇᴛ ғᴍ sᴛᴏʀɪᴇs",
    "🎁 SPECIAL COMBO PACKS (BIG SAVE)",
    "🔙 BACK TO CATEGORIES",
    "« BACK TO MENU",
    "❌ CLOSE STORE",
    "🚫 STORE IS EMPTY",
]


@Client.on_message(
    filters.private
    & filters.text
    & filters.create(lambda _, __, m: m.text in NAV_BTNS)
)
async def store_navigation_text_handler(client: Client, message: Message):
    user_id = message.from_user.id
    text = message.text

    if text == "🚫 STORE IS EMPTY":
        return await message.reply_text(
            "<blockquote>⚠️ ❌ NO STORY AVAILABLE RIGHT NOW.</blockquote>",
            parse_mode=ParseMode.HTML,
        )

    if text in ["❌ CLOSE STORE", "« BACK TO MENU"]:
        USER_STATES[user_id] = {"category": "home", "page": 1}
        await message.reply_text(
            "⬅️ <i>Returning to Dashboard Panel...</i>",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode=ParseMode.HTML,
        )
        return await start_handler(client, message)

    if text == "🔙 BACK TO CATEGORIES":
        USER_STATES[user_id] = {"category": "home", "page": 1}
        return await message.reply_text(
            get_store_text(),
            reply_markup=get_categories_markup(),
            parse_mode=ParseMode.HTML,
        )

    if text == "✨ ᴘʀᴀᴛɪʟɪᴘɪ ғᴍ sᴛᴏʀɪᴇs":
        USER_STATES[user_id] = {"category": "pratilipi", "page": 1}
        cat_title, c_type = "🎬 <b>ᴘʀᴀᴛɪʟɪᴘɪ ғᴍ sᴛᴏʀɪᴇs</b>", "pratilipi"
    elif text == "🔥 ᴘᴏᴄᴋᴇᴛ ғᴍ sᴛᴏʀɪᴇs":
        USER_STATES[user_id] = {"category": "pocket", "page": 1}
        cat_title, c_type = "🎧 <b>ᴘᴏᴄᴋᴇᴛ ғᴍ sᴛᴏʀɪᴇs</b>", "pocket"
    elif text == "🎁 SPECIAL COMBO PACKS (BIG SAVE)":
        USER_STATES[user_id] = {"category": "combo", "page": 1}
        cat_title, c_type = "🎁 <b>✨ ᴘʀᴇᴍɪᴜᴍ ᴄᴏᴍʙᴏ ᴘᴀᴄᴋs ✨</b>", "combo"

    bot_user = (await client.get_me()).username
    markup = get_items_by_category_markup(c_type, bot_user, page=1)

    await message.reply_text(
        f"{cat_title}\n──────────────────────────\n👇 <i>apni pasand ka item select karke full access lein:</i>",
        reply_markup=markup,
        parse_mode=ParseMode.HTML,
    )


# ─── 3. PAGINATION HANDLER ───
@Client.on_message(
    filters.private
    & filters.text
    & filters.create(lambda _, __, m: m.text in ["NEXT ›", "‹ PREV"])
)
async def store_pagination_handler(client: Client, message: Message):
    user_id = message.from_user.id
    state = USER_STATES.get(user_id, {"category": "home", "page": 1})
    if state["category"] == "home":
        return

    if message.text == "NEXT ›":
        state["page"] += 1
    else:
        state["page"] = max(1, state["page"] - 1)

    USER_STATES[user_id] = state
    bot_user = (await client.get_me()).username
    markup = get_items_by_category_markup(
        state["category"], bot_user, page=state["page"]
    )

    await message.reply_text(
        f"<b>AVAILABLE STORIES — {state['category'].upper()}</b>\n<code>PAGE {state['page']}</code>\n──────────────────────────",
        reply_markup=markup,
        parse_mode=ParseMode.HTML,
    )


# ─── 4. STORY CLICK ROUTER ───
@Client.on_message(
    filters.private
    & filters.text
    & filters.create(
        lambda _, __, m: m.text and any(char in m.text for char in ["[ ₹", "➔ ["])
    )
)
async def item_selection_handler(client: Client, message: Message):
    input_text = message.text
    clean_name = input_text

    if "." in input_text:
        try:
            clean_name = input_text.split(".", 1)[1].split("[")[0].strip()
        except Exception:
            clean_name = input_text.split("[")[0].strip()
    elif "🎁" in input_text:
        clean_name = input_text.replace("🎁", "").split("➔")[0].strip()

    state = USER_STATES.get(message.from_user.id, {"category": "pratilipi"})

    # Async Motor Lookup
    if state["category"] == "combo":
        data = await channels_col.find_one({"combo_name": clean_name})
    elif state["category"] == "pocket":
        data = await channels_col.find_one(
            {"story_name": clean_name, "source": "pocket"}
        )
    elif state["category"] == "pratilipi":
        data = await channels_col.find_one(
            {"story_name": clean_name, "source": "pratilipi"}
        )
    else:
        data = await channels_col.find_one({"name": clean_name}) or await channels_col.find_one(
            {"story_name": clean_name}
        )

    if not data:
        return await message.reply_text("❌ Is item ki details load nahi ho payi.")

    load_msg = await message.reply_text(
        "⌛ <i>Loading Details...</i>",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode=ParseMode.HTML,
    )

    keyboard = []
    db_id = data.get("item_id") or data.get("channel_id")

    # Flow 1: Combo Pack
    if data.get("is_combo"):
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"✅ CONFIRM & PAY COMBO - ₹{data['price']}",
                    callback_data=f"select_{db_id}_manual",
                )
            ]
        )
        header = "🎁 <b>ᴘʀᴇᴍɪᴜᴍ sᴘᴇᴄɪᴀʟ ᴄᴏᴍʙᴏ ʙᴜɴᴅʟᴇ</b>"
        item_label = data.get("combo_name")
        desc_text = f"📝 <b>ɪɴᴄʟᴜᴅᴇᴅ sᴛᴏʀɪᴇs:</b>\n<i>{data.get('description', 'Multiple bundles inside!')}</i>"

    # Flow 2: Forwarded Channel (/add Flow)
    elif "channel_id" in data and not data.get("story_name"):
        if data.get("plans") and isinstance(data["plans"], dict):
            for p_time, p_price in data["plans"].items():
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"💳 {get_time_string(p_time)} - ₹{p_price}",
                            callback_data=f"select_{db_id}_{p_time}",
                        )
                    ]
                )
        else:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"✅ CONFIRM & PAY - ₹{data.get('price', '49')}",
                        callback_data=f"select_{db_id}_manual",
                    )
                ]
            )

        header = "📢 <b>ᴘʀᴇᴍɪᴜᴍ ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀɴɴᴇʟ</b>"
        item_label = data.get("name", "VIP Channel")
        desc_text = "🤖 <b>ᴅᴇʟɪᴠᴇʀʏ:</b> <code>ᴄʜᴀɴɴᴇʟ ɪɴᴠɪᴛᴇ ʟɪɴᴋ (𝟷-ᴛɪᴍᴇ ᴜsᴇ)</code>\nℹ️ <i>Is pack me aapko private channel join karne ka temporary link milega.</i>"

    # Flow 3: Manual Story (/add_story Flow)
    else:
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"💳 UNLOCK PREMIUM STORY - ₹{data.get('price', '49')}",
                    callback_data=f"select_{db_id}_manual",
                )
            ]
        )
        header = f"🔥 <b>ᴘʀᴇᴍɪᴜᴍ ᴇxᴄʟᴜsɪᴠᴇ sᴛᴏʀʏ ({data.get('source', 'audio')})</b>"
        item_label = data.get("story_name")
        desc_text = "🤖 <b>ᴅᴇʟɪᴠᴇʀʏ:</b> <code>ɪɴsᴛᴀɴᴛ ʙᴏᴛ ʟɪɴᴋ ᴀᴄᴄᴇss</code>\nℹ️ <i>Is pack me aapko direct bot file redirection button milega.</i>"

    if data.get("demo_link"):
        keyboard.append(
            [
                InlineKeyboardButton(
                    "📺 ᴠɪᴇᴡ ǫᴜᴀʟɪᴛʏ ᴅᴇᴍᴏ (ᴛᴇᴀsᴇʀ)", url=data["demo_link"]
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "⬅️ BACK TO LIST", callback_data="return_to_list_True"
            )
        ]
    )
    inline_markup = InlineKeyboardMarkup(keyboard)

    details_text = f"{header}\n──────────────────────────\n📦 <b>ɪᴛᴇᴍ:</b> <code>{item_label}</code>\n\n{desc_text}\n──────────────────────────"

    photo_id = data.get("file_id")
    if photo_id:
        await client.send_photo(
            message.chat.id,
            photo=photo_id,
            caption=details_text,
            reply_markup=inline_markup,
            parse_mode=ParseMode.HTML,
        )
    else:
        await client.send_message(
            message.chat.id,
            details_text,
            reply_markup=inline_markup,
            parse_mode=ParseMode.HTML,
        )

    try:
        await load_msg.delete()
    except Exception:
        pass


# ─── 5. CALLBACK QUERY HANDLERS ───
@Client.on_callback_query(filters.regex(r"^return_to_list_"))
async def return_to_list_callback(client: Client, call: CallbackQuery):
    await call.answer()
    state = USER_STATES.get(call.from_user.id, {"category": "pratilipi", "page": 1})
    try:
        await call.message.delete()
    except Exception:
        pass

    bot_user = (await client.get_me()).username
    markup = get_items_by_category_markup(
        state["category"], bot_user, page=state["page"]
    )
    await client.send_message(
        call.message.chat.id,
        "👇 <i>apni pasand ka item select karke full access lein:</i>",
        reply_markup=markup,
        parse_mode=ParseMode.HTML,
    )


@Client.on_callback_query(filters.regex(r"^open_store$"))
async def open_store_callback(client: Client, call: CallbackQuery):
    await call.answer()
    try:
        await call.message.delete()
    except Exception:
        pass

    await client.send_message(
        call.message.chat.id,
        get_store_text(),
        reply_markup=get_categories_markup(),
        parse_mode=ParseMode.HTML,
    )


@Client.on_callback_query(filters.regex(r"^back_to_start$"))
async def back_to_start_callback(client: Client, call: CallbackQuery):
    await call.answer()
    try:
        await call.message.delete()
    except Exception:
        pass

    await start_handler(client, call.message)


@Client.on_callback_query(filters.regex(r"^my_plan$"))
async def my_plan_callback(client: Client, call: CallbackQuery):
    u_id = call.from_user.id
    await call.answer()

    load_title_msg = await client.send_message(
        u_id,
        "⌛ <i>Opening Dashboard...</i>",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode=ParseMode.HTML,
    )

    back_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🛍️ Open Store", callback_data="open_store"),
                InlineKeyboardButton(
                    "« ʙᴀᴄᴋ ᴛᴏ ᴍᴇɴᴜ", callback_data="back_to_start"
                ),
            ]
        ]
    )

    # Admin Dashboard
    if u_id == config.ADMIN_ID:
        # Motor async find all
        all_subs = await users_col.find().sort("expiry", 1).to_list(length=None)

        try:
            await load_title_msg.delete()
        except Exception:
            pass

        if not all_subs:
            return await client.send_message(
                u_id,
                "📋 <b>Database clear hai. Koi active premium member nahi mila.</b>",
                reply_markup=back_markup,
                parse_mode=ParseMode.HTML,
            )

        report = "📋 <b>ᴀʟʟ ᴀᴄᴛɪᴠᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴs (ᴀᴅᴍɪɴ)</b>\n──────────────────────────\n\n"
        for s in all_subs:
            ch = await channels_col.find_one({"channel_id": s["channel_id"]})
            ch_name = (
                (ch.get("story_name") or ch.get("combo_name", "Deleted Pack"))
                if ch
                else "Unknown Pack"
            )
            days_left = (
                datetime.fromtimestamp(s["expiry"]) - datetime.now()
            ).days
            report += f"👤 <code>{s['user_id']}</code>\n➔ 📦 {ch_name}\n➔ ⏳ Left: <b>{max(0, days_left)} Days</b>\n─────────────────\n"

        await client.send_message(
            u_id, report, reply_markup=back_markup, parse_mode=ParseMode.HTML
        )

    # User Personal Dashboard
    else:
        subs = await users_col.find({"user_id": u_id}).to_list(length=None)

        try:
            await load_title_msg.delete()
        except Exception:
            pass

        if not subs:
            return await client.send_message(
                u_id,
                "❌ <b>NO ACTIVE PLAN</b>\n\nAapka filhal koi active plan nahi chal raha hai.",
                reply_markup=back_markup,
                parse_mode=ParseMode.HTML,
            )

        res = "👤 <b>ᴍʏ ᴘᴇʀsᴏɴᴀʟ ᴅᴀsʜʙᴏᴀʀᴅ</b>\n──────────────────────────\n\n"
        for s in subs:
            ch = await channels_col.find_one({"channel_id": s["channel_id"]})
            name = (
                (ch.get("story_name") or ch.get("combo_name", "Premium Bundle"))
                if ch
                else "Premium Access"
            )
            expiry = datetime.fromtimestamp(s["expiry"]).strftime(
                "%d %b %Y | %I:%M %p"
            )
            res += f"🎬 <b>ɪᴛᴇᴍ:</b> {name}\n⌛ <b>ᴇxᴘɪʀʏ:</b> <code>{expiry}</code>\n──────────────────────────\n"

        await client.send_message(
            u_id, res, reply_markup=back_markup, parse_mode=ParseMode.HTML
        )
