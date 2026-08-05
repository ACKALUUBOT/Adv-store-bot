from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

import config
from database import channels_col

# यूज़र के सेलेक्ट किए गए स्टोरी IDs को स्टोर करने के लिए डिक्शनरी
# Format: { user_id: set(selected_story_ids) }
COMBO_SELECTIONS = {}


# -------------------------------------------------------------
# 📌 हेल्पर्स फ़ंक्शन (Helpers)
# -------------------------------------------------------------
def get_discount_percentage(count: int) -> int:
    """चुनी गई स्टोरीज़ की संख्या के हिसाब से डिस्काउंट % तय करता है"""
    if 1 <= count <= 4:
        return 10  # 1 से 4 पर 10% डिस्काउंट
    elif 5 <= count <= 10:
        return 30  # 5 से 10 पर 30% डिस्काउंट
    elif count > 10:
        return 50  # 10 से ज्यादा पर 50% डिस्काउंट
    return 0


async def get_all_stories_from_db() -> list:
    """Motor MongoDB Async Cursor se stories fetch karta hai"""
    stories = []
    async for ch in channels_col.find({"is_combo": {"$ne": True}}):
        item_id = str(ch.get("item_id") or ch.get("_id"))
        title = ch.get("name") or ch.get("story_name") or "Untitled Story"
        try:
            price = float(ch.get("price", 0))
        except (ValueError, TypeError):
            price = 0.0

        stories.append({"_id": item_id, "title": title, "price": price})
    return stories


def calculate_combo_total(user_id: int, all_stories: list):
    """मूल कीमत, डिस्काउंट और फ़ाइनल कीमत की गणना करता है"""
    user_selected = COMBO_SELECTIONS.get(user_id, set())
    if not user_selected:
        return 0, 0.0, 0, 0.0

    selected_stories = [
        s for s in all_stories if str(s["_id"]) in user_selected
    ]
    total_price = sum(s.get("price", 0.0) for s in selected_stories)
    count = len(selected_stories)
    discount_pct = get_discount_percentage(count)

    discount_amount = (total_price * discount_pct) / 100
    final_price = round(total_price - discount_amount, 2)

    return count, total_price, discount_pct, final_price


def build_combo_keyboard(user_id: int, all_stories: list):
    """स्टोरीज़ चुनने के लिए इनलाइन कीबोर्ड बनाता है"""
    buttons = []
    user_selected = COMBO_SELECTIONS.get(user_id, set())

    # सभी उपलब्ध स्टोरीज़ को बटन के रूप में जोड़ना
    for story in all_stories:
        story_id = str(story["_id"])
        title = story.get("title", "Untitled")
        price = story.get("price", 0)

        # अगर यूज़र ने यह स्टोरी चुनी है तो Tick (✅) दिखाओ
        if story_id in user_selected:
            btn_text = f"✅ {title} - ₹{price}"
        else:
            btn_text = f"▫️ {title} - ₹{price}"

        buttons.append(
            [
                InlineKeyboardButton(
                    btn_text, callback_data=f"toggle_combo_{story_id}"
                )
            ]
        )

    # ऐक्शन बटन्स (Buy / Clear / Back)
    if user_selected:
        buttons.append(
            [
                InlineKeyboardButton(
                    "💳 खरीदें (Proceed to Pay)",
                    callback_data="buy_custom_combo",
                )
            ]
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    "🔄 सब रिसेट करें (Clear All)", callback_data="clear_combo"
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                "🔙 मुख्य मेनू (Back)", callback_data="back_to_start"
            )
        ]
    )
    return InlineKeyboardMarkup(buttons)


# -------------------------------------------------------------
# 📌 कॉल बैक हैंडल्स (Pyrofork Callback Handlers)
# -------------------------------------------------------------


# 1. जब यूज़र 'Create Combo' बटन दबाए
@Client.on_callback_query(filters.regex(r"^(create_combo|custom_combo)$"))
async def start_custom_combo(client: Client, call: CallbackQuery):
    user_id = call.from_user.id
    await call.answer()

    if user_id not in COMBO_SELECTIONS:
        COMBO_SELECTIONS[user_id] = set()

    all_stories = await get_all_stories_from_db()
    count, total_price, discount_pct, final_price = calculate_combo_total(
        user_id, all_stories
    )

    msg_text = (
        "🎁 <b>अपना कस्टम कॉम्बो (Custom Combo) बनाएं!</b>\n\n"
        "अपनी पसंद की स्टोरीज़ पर क्लिक करके सेलेक्ट करें:\n"
        "• <b>1 से 4 स्टोरीज़:</b> 10% डिस्काउंट 🎉\n"
        "• <b>5 से 10 स्टोरीज़:</b> 30% डिस्काउंट 🔥\n"
        "• <b>10 से अधिक स्टोरीज़:</b> 50% भारी डिस्काउंट 💥\n\n"
        f"📊 <b>चुनी गई स्टोरीज़:</b> <code>{count}</code>\n"
        f"💵 <b>मूल कीमत:</b> <code>₹{total_price}</code>\n"
        f"🏷 <b>डिस्काउंट:</b> <code>{discount_pct}%</code>\n"
        f"💰 <b>फ़ाइनल कीमत:</b> <code>₹{final_price}</code>\n\n"
        "👇 <i>नीचे लिस्ट में से अपनी मनपसंद स्टोरीज़ चुनें:</i>"
    )

    try:
        await call.message.edit_text(
            text=msg_text,
            parse_mode=ParseMode.HTML,
            reply_markup=build_combo_keyboard(user_id, all_stories),
        )
    except Exception:
        pass


# 2. जब यूज़र किसी स्टोरी को सेलेक्ट या अन-सेलेक्ट (Toggle) करे
@Client.on_callback_query(filters.regex(r"^toggle_combo_"))
async def toggle_story_selection(client: Client, call: CallbackQuery):
    user_id = call.from_user.id
    story_id = call.data.split("toggle_combo_")[1]

    if user_id not in COMBO_SELECTIONS:
        COMBO_SELECTIONS[user_id] = set()

    # सेलेक्ट / डि-सेलेक्ट टॉगल
    if story_id in COMBO_SELECTIONS[user_id]:
        COMBO_SELECTIONS[user_id].remove(story_id)
        await call.answer("❌ स्टोरी हटाई गई", show_alert=False)
    else:
        COMBO_SELECTIONS[user_id].add(story_id)
        await call.answer("✅ स्टोरी जोड़ी गई", show_alert=False)

    all_stories = await get_all_stories_from_db()
    count, total_price, discount_pct, final_price = calculate_combo_total(
        user_id, all_stories
    )

    msg_text = (
        "🎁 <b>अपना कस्टम कॉम्बो (Custom Combo) बनाएं!</b>\n\n"
        "अपनी पसंद की स्टोरीज़ पर क्लिक करके सेलेक्ट करें:\n"
        "• <b>1 से 4 स्टोरीज़:</b> 10% डिस्काउंट 🎉\n"
        "• <b>5 से 10 स्टोरीज़:</b> 30% डिस्काउंट 🔥\n"
        "• <b>10 से अधिक स्टोरीज़:</b> 50% भारी डिस्काउंट 💥\n\n"
        f"📊 <b>चुनी गई स्टोरीज़:</b> <code>{count}</code>\n"
        f"💵 <b>मूल कीमत:</b> <code>₹{total_price}</code>\n"
        f"🏷 <b>डिस्काउंट:</b> <code>{discount_pct}%</code>\n"
        f"💰 <b>फ़ाइनल कीमत:</b> <code>₹{final_price}</code>\n\n"
        "👇 <i>नीचे लिस्ट में से अपनी मनपसंद स्टोरीज़ चुनें:</i>"
    )

    try:
        await call.message.edit_text(
            text=msg_text,
            parse_mode=ParseMode.HTML,
            reply_markup=build_combo_keyboard(user_id, all_stories),
        )
    except Exception:
        pass


# 3. सेलेक्शन रिसेट करना (Clear All)
@Client.on_callback_query(filters.regex(r"^clear_combo$"))
async def clear_combo_selection(client: Client, call: CallbackQuery):
    user_id = call.from_user.id
    COMBO_SELECTIONS[user_id] = set()
    await call.answer("🔄 सभी स्टोरीज़ हटा दी गईं!", show_alert=False)
    await start_custom_combo(client, call)


# 4. पेमेंट (Checkout) का प्रोसेस शुरू करना
@Client.on_callback_query(filters.regex(r"^buy_custom_combo$"))
async def process_custom_combo_checkout(client: Client, call: CallbackQuery):
    user_id = call.from_user.id
    user_selected = COMBO_SELECTIONS.get(user_id, set())

    if not user_selected:
        return await call.answer(
            "⚠️ आपने कोई स्टोरी नहीं चुनी है!", show_alert=True
        )

    all_stories = await get_all_stories_from_db()
    count, total_price, discount_pct, final_price = calculate_combo_total(
        user_id, all_stories
    )

    await call.answer()

    checkout_msg = (
        f"🛍 <b>आपका कस्टम कॉम्बो रेडी है!</b>\n\n"
        f"📚 <b>कुल स्टोरीज़:</b> <code>{count}</code>\n"
        f"💵 <b>कुल मूल्य:</b> <code>₹{total_price}</code>\n"
        f"🏷 <b>डिस्काउंट लागू:</b> <code>{discount_pct}%</code>\n"
        f"💰 <b>आपको भुगतान करना है:</b> <code>₹{final_price}</code>\n\n"
        f"👇 <i>नीचे दिए गए बटन पर क्लिक करके पेमेंट करें:</i>"
    )

    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"💳 ₹{final_price} Pay Now",
                    callback_data=f"pay_combo_{final_price}",
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 Back to Combo", callback_data="create_combo"
                )
            ],
        ]
    )

    try:
        await call.message.edit_text(
            text=checkout_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=markup,
        )
    except Exception:
        pass
