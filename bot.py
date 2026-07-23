#!/usr/bin/env python3
"""
Domino's India Telegram Bot
============================
Main bot file — handles all Telegram interactions.

Features:
- 🔐 New Login: OTP-based login via Domino's India
- 👤 My Account: View all saved accounts
- 🛒 Cart: Direct cart access
- 🏠 Home: Main menu
- Telegram WebApp mini window for full Domino's experience
"""
import asyncio
import logging
from typing import Optional

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

from config import BOT_TOKEN, PROXY_PUBLIC_URL
from session_store import session_store
from dominos_browser import DominosBrowser
from keyboards import (
    get_main_keyboard,
    get_home_inline_keyboard,
    get_accounts_inline_keyboard,
    get_cancel_keyboard,
    get_settings_keyboard,
)

# ---- Logging ----
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---- Conversation States ----
PHONE_NUMBER, OTP_CODE = range(2)


# ==================== COMMAND HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    welcome_text = (
        f"🍕 **Welcome {user.first_name}!**\n\n"
        "यह Domino's India Telegram Bot है।\n"
        "आप इस बॉट के माध्यम से Domino's India पर लॉगिन कर सकते हैं "
        "और अपने अकाउंट को मैनेज कर सकते हैं।\n\n"
        "**Features:**\n"
        "🔐 **New Login** — Domino's अकाउंट में OTP से लॉगिन करें\n"
        "👤 **My Account** — सभी सेव किए गए अकाउंट देखें\n"
        "🛒 **Cart** — सीधे कार्ट में जाएँ\n"
        "🏠 **Home** — मुख्य मेनू पर वापस आएँ\n\n"
        "नीचे दिए गए बटन का उपयोग करें ⬇"
    )
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown",
    )


async def home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Home button / go back to main menu."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "🏠 **Home Menu**\nनीचे दिए गए विकल्प चुनें:",
            reply_markup=get_home_inline_keyboard(),
            parse_mode="Markdown",
        )
        return

    msg = update.message
    if msg:
        await msg.reply_text(
            "🏠 **Home Menu**",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown",
        )


# ==================== NEW LOGIN FLOW ====================

async def new_login_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the login process — ask for phone number."""
    # Cancel any existing conversation state
    if context.user_data.get("in_login"):
        await update.message.reply_text(
            "⚠️ आप पहले से ही लॉगिन प्रक्रिया में हैं।\n"
            "पहले ❌ Cancel करें या OTP दर्ज करें।"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "📱 **New Login**\n\n"
        "कृपया अपना Domino's अकाउंट से जुड़ा मोबाइल नंबर दर्ज करें।\n\n"
        "उदाहरण: `9876543210`\n(बिना +91 के)",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown",
    )
    context.user_data["in_login"] = True
    return PHONE_NUMBER


async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive phone number and send OTP via Domino's."""
    phone = update.message.text.strip()
    # Remove any non-digit characters
    phone = "".join(filter(str.isdigit, phone))

    # Validate phone number (10 digits)
    if len(phone) != 10:
        await update.message.reply_text(
            "❌ गलत नंबर! कृपया 10 अंकों का मोबाइल नंबर दर्ज करें।\n"
            "उदाहरण: `9876543210`",
            parse_mode="Markdown",
        )
        return PHONE_NUMBER

    full_phone = f"91{phone}"  # Add India country code

    # Store phone for later use
    context.user_data["login_phone"] = phone
    context.user_data["login_full_phone"] = full_phone

    status_msg = await update.message.reply_text(
        "⏳ Domino's पर OTP भेजा जा रहा है...\nकृपया प्रतीक्षा करें।"
    )

    try:
        # Send OTP via Domino's India website
        result = await DominosBrowser.send_otp(full_phone)

        if result["success"]:
            # Store page and context for OTP verification
            context.user_data["otp_page"] = result.get("page")
            context.user_data["otp_context"] = result.get("context")

            await status_msg.edit_text(
                f"✅ OTP आपके नंबर {phone} पर भेज दिया गया है!\n\n"
                "📩 कृपया अपने फ़ोन पर आया 6 अंकों का OTP कोड दर्ज करें।",
                reply_markup=get_cancel_keyboard(),
            )
            return OTP_CODE
        else:
            await status_msg.edit_text(
                f"❌ OTP भेजने में विफल:\n{result['message']}\n\n"
                "कृपया पुनः प्रयास करें /start",
            )
            context.user_data["in_login"] = False
            return ConversationHandler.END

    except Exception as e:
        logger.error(f"send_otp error: {e}")
        await status_msg.edit_text(
            "❌ कोई त्रुटि हुई। कृपया पुनः प्रयास करें।\n"
            "सुनिश्चित करें कि Playwright/Browser सही से काम कर रहा है।"
        )
        context.user_data["in_login"] = False
        return ConversationHandler.END


async def receive_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive OTP and complete login."""
    otp = update.message.text.strip()
    otp = "".join(filter(str.isdigit, otp))

    if len(otp) < 4 or len(otp) > 8:
        await update.message.reply_text(
            "❌ कृपया सही OTP (4-8 अंक) दर्ज करें।",
        )
        return OTP_CODE

    phone = context.user_data.get("login_phone")
    page = context.user_data.get("otp_page")
    browser_context = context.user_data.get("otp_context")

    if not page or not browser_context:
        await update.message.reply_text(
            "❌ सत्र समाप्त हो गया है। कृपया /start से पुनः प्रयास करें।",
        )
        context.user_data["in_login"] = False
        return ConversationHandler.END

    status_msg = await update.message.reply_text(
        "⏳ OTP सत्यापित किया जा रहा है..."
    )

    try:
        result = await DominosBrowser.verify_otp(
            page=page,
            context=browser_context,
            otp_code=otp,
            telegram_id=update.effective_user.id,
            phone_number=phone,
        )

        if result["success"]:
            # Clear temp state
            context.user_data["in_login"] = False
            context.user_data.pop("otp_page", None)
            context.user_data.pop("otp_context", None)
            context.user_data.pop("login_phone", None)
            context.user_data.pop("login_full_phone", None)

            await status_msg.edit_text(
                f"✅ **लॉगिन सफल!**\n\n"
                f"नंबर `{phone}` अब आपके अकाउंट में जुड़ गया है।\n"
                "अब आप My Account से Domino's पर ऑर्डर कर सकते हैं।",
                reply_markup=get_main_keyboard(),
                parse_mode="Markdown",
            )
        else:
            await status_msg.edit_text(
                f"❌ {result['message']}\n\n"
                "कृपया सही OTP दर्ज करें या /start से पुनः प्रयास करें।",
            )
            return OTP_CODE

    except Exception as e:
        logger.error(f"verify_otp error: {e}")
        await status_msg.edit_text(
            "❌ OTP सत्यापन में त्रुटि। कृपया पुनः प्रयास करें।",
        )
        context.user_data["in_login"] = False

    return ConversationHandler.END


async def cancel_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the login process."""
    # Close any open browser pages
    page = context.user_data.pop("otp_page", None)
    ctx = context.user_data.pop("otp_context", None)
    if ctx:
        try:
            await ctx.close()
        except Exception:
            pass

    context.user_data["in_login"] = False
    context.user_data.pop("login_phone", None)
    context.user_data.pop("login_full_phone", None)

    await update.message.reply_text(
        "❌ लॉगिन प्रक्रिया रद्द कर दी गई।",
        reply_markup=get_main_keyboard(),
    )
    return ConversationHandler.END


# ==================== MY ACCOUNT ====================

async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all saved Domino's accounts."""
    user_id = update.effective_user.id
    phone_numbers = session_store.get_all_phone_numbers(user_id)
    active = session_store.get_active_account(user_id)

    if not phone_numbers:
        text = (
            "👤 **My Account**\n\n"
            "आपका कोई अकाउंट सेव नहीं है।\n"
            "नया अकाउंट जोड़ने के लिए **🔐 New Login** पर क्लिक करें।"
        )
        keyboard = get_main_keyboard()
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                text, reply_markup=get_home_inline_keyboard(),
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                text, reply_markup=keyboard, parse_mode="Markdown",
            )
        return

    text = (
        "👤 **My Account**\n\n"
        "नीचे आपके सेव किए गए अकाउंट हैं।\n"
        "✅ से मार्क किया गया अकाउंट **Active** है।\n\n"
        "**किसी भी अकाउंट पर क्लिक करें** → "
        "Domino's की mini window खुलेगी जहाँ आप पहले से लॉगिन होंगे।\n"
        "वहाँ से सीधे ऑर्डर कर सकते हैं 🍕"
    )

    keyboard = get_accounts_inline_keyboard(phone_numbers, active)

    msg = update.message or update.callback_query.message
    await msg.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


# ==================== CART ====================

async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Open cart for the active account via WebApp."""
    user_id = update.effective_user.id
    active_phone = session_store.get_active_account(user_id)

    if not active_phone:
        text = (
            "🛒 **Cart**\n\n"
            "कोई अकाउंट सेव नहीं है।\n"
            "पहले **🔐 New Login** से लॉगिन करें।"
        )
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                text, reply_markup=get_home_inline_keyboard(),
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                text, reply_markup=get_main_keyboard(),
                parse_mode="Markdown",
            )
        return

    # Open the Domino's cart via Telegram WebApp
    webapp_url = f"{PROXY_PUBLIC_URL}/open-cart?phone={active_phone}"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🛒 Open Cart in Mini Window 🍕",
                web_app=WebAppInfo(url=webapp_url),
            )
        ],
        [
            InlineKeyboardButton("🏠 Home", callback_data="go_home"),
        ],
    ])

    text = (
        f"🛒 **Cart**\n\n"
        f"Active Account: `{active_phone}`\n\n"
        "नीचे दिए गए बटन पर क्लिक करें → "
        "Domino's का कार्ट mini window में खुलेगा।\n"
        "वहाँ से सीधे ऑर्डर करें और पेमेंट करें! 🎉"
    )

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text, reply_markup=keyboard, parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            text, reply_markup=keyboard, parse_mode="Markdown",
        )


# ==================== SETTINGS ====================

async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show settings."""
    text = "⚙️ **Settings**\n\nअपने सभी सेव किए गए अकाउंट को साफ़ करें।"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text,
            reply_markup=get_settings_keyboard(),
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=get_settings_keyboard(),
            parse_mode="Markdown",
        )


async def clear_sessions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear all saved sessions for this user."""
    user_id = update.effective_user.id
    phones = session_store.get_all_phone_numbers(user_id)
    for phone in phones:
        session_store.remove_account(user_id, phone)

    await update.callback_query.answer("✅ All sessions cleared!")
    await update.callback_query.edit_message_text(
        "✅ सभी सेव किए गए अकाउंट हटा दिए गए हैं।\n\n"
        "नया लॉगिन करने के लिए 🔐 New Login बटन का उपयोग करें।",
        reply_markup=get_main_keyboard(),
    )


# ==================== CALLBACK QUERY HANDLER ====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all inline button callbacks."""
    query = update.callback_query
    data = query.data

    if data == "go_home":
        await home(update, context)
    elif data == "new_login":
        await query.answer()
        # Trigger new login via message
        await query.message.reply_text(
            "🔐 **New Login** पर आ गए हैं।",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown",
        )
    elif data == "my_account":
        await query.answer()
        await my_account(update, context)
    elif data == "view_cart":
        await query.answer()
        await view_cart(update, context)
    elif data == "settings":
        await query.answer()
        await settings_menu(update, context)
    elif data == "clear_sessions":
        await clear_sessions(update, context)
    else:
        await query.answer("Unknown option")


# ==================== TEXT MESSAGE HANDLER ====================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages (non-conversation)."""
    text = update.message.text.strip()

    if text == "🔐 New Login":
        return await new_login_start(update, context)

    elif text == "👤 My Account":
        return await my_account(update, context)

    elif text == "🛒 Cart":
        return await view_cart(update, context)

    elif text == "🏠 Home":
        return await home(update, context)

    elif text in ("❌ Cancel", "/cancel"):
        return await cancel_login(update, context)

    else:
        await update.message.reply_text(
            "❓ कृपया नीचे दिए गए बटन का उपयोग करें।",
            reply_markup=get_main_keyboard(),
        )


# ==================== ERROR HANDLER ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ कोई त्रुटि हुई। कृपया /start से पुनः प्रयास करें।"
            )
    except Exception:
        pass


# ==================== MAIN ====================

def main():
    """Run the bot."""
    # Create Application
    app = Application.builder().token(BOT_TOKEN).build()

    # ---- Conversation Handler for Login ----
    login_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🔐 New Login$"), new_login_start),
        ],
        states={
            PHONE_NUMBER: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~filters.Regex("^❌ Cancel$"),
                    receive_phone,
                ),
            ],
            OTP_CODE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~filters.Regex("^❌ Cancel$"),
                    receive_otp,
                ),
            ],
        },
        fallbacks=[
            MessageHandler(
                filters.Regex("^❌ Cancel$") | filters.COMMAND,
                cancel_login,
            ),
        ],
        name="login_conversation",
        persistent=False,
    )

    # ---- Register handlers ----
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("home", home))
    app.add_handler(login_conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_error_handler(error_handler)

    # ---- Startup/Shutdown ----
    async def on_shutdown(app):
        await DominosBrowser.close_browser()

    app.post_shutdown = on_shutdown

    # ---- Start polling ----
    logger.info("🤖 Domino's Bot started! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
