import config
from database import channels_col
from pyrogram.types import KeyboardButton, ReplyKeyboardMarkup


# ─── 1. BOTTOM KEYBOARD CATEGORIES MENU (WITH COMBO PACKS) ───
def get_categories_markup() -> ReplyKeyboardMarkup:
    """User ko niche keyboard me categories dikhane ke liye"""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("✨ ᴘʀᴀᴛɪʟɪᴘɪ ғᴍ sᴛᴏʀɪᴇs")],
            [KeyboardButton("🔥 ᴘᴏᴄᴋᴇᴛ ғᴍ sᴛᴏʀɪᴇs")],
            [KeyboardButton("🎁 SPECIAL COMBO PACKS (BIG SAVE)")],
            [KeyboardButton("« BACK TO MENU")],
        ],
        resize_keyboard=True,
    )


# ─── 2. PAGINATED ITEMS MENU BY CATEGORY (ASYNC MOTOR DB FIXED) ───
async def get_items_by_category_markup(
    category_type: str, bot_username: str = None, page: int = 1
) -> ReplyKeyboardMarkup:
    """Source aur combo ke hisab se database se items filter karega (8 items per page)"""

    # 🌟 REAL-TIME MOTOR ASYNC DB FETCH FILTER
    if category_type == "pratilipi":
        all_items = await channels_col.find(
            {
                "story_name": {"$exists": True},
                "source": "pratilipi",
                "is_combo": {"$exists": False},
            }
        ).to_list(length=None)
    elif category_type == "pocket":
        all_items = await channels_col.find(
            {
                "story_name": {"$exists": True},
                "source": "pocket",
                "is_combo": {"$exists": False},
            }
        ).to_list(length=None)
    elif category_type == "combo":
        all_items = await channels_col.find({"is_combo": True}).to_list(
            length=None
        )
    else:
        all_items = []

    # Agar data nahi hai toh direct ye button show hoga
    if not all_items:
        return ReplyKeyboardMarkup(
            [
                [KeyboardButton("🚫 STORE IS EMPTY")],
                [KeyboardButton("🔙 BACK TO CATEGORIES")],
            ],
            resize_keyboard=True,
        )

    per_page = 8
    total_items = len(all_items)
    total_pages = (total_items + per_page - 1) // per_page

    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    sliced_items = all_items[start_idx:end_idx]

    keyboard = []

    # Buttons display generation loop
    for index, item in enumerate(sliced_items, start=start_idx + 1):
        if category_type == "combo":
            btn_text = f"🎁 {item['combo_name']} ➔ [ ₹{item['price']} ]"
        else:
            btn_text = f"{index}. {item['story_name']} [ ₹{item['price']} ]"

        keyboard.append([KeyboardButton(btn_text)])

    # Navigation Row (Next/Prev Setup)
    nav_buttons = []
    if page > 1:
        nav_buttons.append(KeyboardButton("‹ PREV"))
    if page < total_pages:
        nav_buttons.append(KeyboardButton("NEXT ›"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([KeyboardButton("🔙 BACK TO CATEGORIES")])
    keyboard.append([KeyboardButton("❌ CLOSE STORE")])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# ─── 3. TEXT FOR CATEGORIES PAGE ───
def get_store_text() -> str:
    return (
        "🛍️ <b>ᴘʀᴇᴍɪᴜᴍ sᴛᴏʀỹ ᴄᴀᴛᴇɢᴏʀɪᴇs</b> 🛍️\n"
        "──────────────────────────\n"
        "ᴀᴀᴘ ᴋɪs ᴘʟᴀᴛғᴏʀᴍ ᴋɪ sᴛᴏʀɪᴇs ᴅᴇᴋʜɴᴀ ᴄʜᴀʜᴛᴇ ʜᴀɪɴ? ɴɪᴄʜᴇ sᴇ sᴇʟᴇᴄᴛ ᴋᴀʀᴇɪɴ:\n\n"
        "✨ <b>ᴘʀᴀᴛɪʟɪᴘɪ ғᴍ sᴛᴏʀɪᴇs:</b> sᴇʟᴇᴄᴛ ᴛᴏ ᴠɪᴇᴡ ᴀʟʟ ᴘʀᴀᴛɪʟɪᴘɪ sᴛᴏʀɪᴇs.\n"
        "🔥 <b>ᴘᴏᴄᴋᴇᴛ ғᴍ sᴛᴏʀɪᴇs:</b> sᴇʟᴇᴄᴛ ᴛᴏ ᴠɪᴇᴡ ᴀʟʟ ᴘᴏᴄᴋᴇᴛ ғᴍ sᴛᴏʀɪᴇs.\n"
        "🎁 <b>sᴘᴇᴄɪᴀʟ ᴄᴏᴍʙᴏ ᴘᴀᴄᴋs:</b> ᴍᴜʟᴛɪ-sᴛᴏʀɪᴇs ʙᴜɴᴅʟᴇ ᴀᴛ ᴀ ᴄʜᴇᴀᴘ ᴘʀɪᴄᴇ!\n"
        "──────────────────────────"
    )
