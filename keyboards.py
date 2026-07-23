"""
Telegram keyboard layouts for the Domino's bot.
"""
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo,
)

from config import PROXY_PUBLIC_URL, DOMINOS_BASE_URL


def get_main_keyboard():
    """Home screen main keyboard with Reply buttons."""
    buttons = [
        [KeyboardButton("🔐 New Login")],
        [KeyboardButton("👤 My Account")],
        [KeyboardButton("🛒 Cart"), KeyboardButton("🏠 Home")],
    ]
    return ReplyKeyboardMarkup(
        buttons, resize_keyboard=True, is_persistent=True
    )


def get_home_inline_keyboard():
    """Inline keyboard for home screen."""
    keyboard = [
        [
            InlineKeyboardButton(
                "🔐 New Login", callback_data="new_login"
            ),
            InlineKeyboardButton(
                "👤 My Account", callback_data="my_account"
            ),
        ],
        [
            InlineKeyboardButton(
                "🛒 View Cart", callback_data="view_cart"
            ),
            InlineKeyboardButton(
                "⚙️ Settings", callback_data="settings"
            ),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_accounts_inline_keyboard(phone_numbers: list[str], active: str = None):
    """
    Build inline keyboard with saved accounts.
    Active account is highlighted.
    """
    keyboard = []
    for phone in phone_numbers:
        prefix = "✅ " if phone == active else ""
        display = f"{prefix}{phone}"
        # WebApp button that opens the Domino's mini window
        webapp_url = f"{PROXY_PUBLIC_URL}/open-account?phone={phone}"
        keyboard.append([
            InlineKeyboardButton(
                display,
                web_app=WebAppInfo(url=webapp_url),
            )
        ])

    keyboard.append([
        InlineKeyboardButton("🏠 Home", callback_data="go_home")
    ])
    return InlineKeyboardMarkup(keyboard)


def get_cancel_keyboard():
    """Cancel/back keyboard."""
    keyboard = [[KeyboardButton("❌ Cancel")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_settings_keyboard():
    """Settings inline keyboard."""
    keyboard = [
        [
            InlineKeyboardButton(
                "🗑 Clear All Sessions",
                callback_data="clear_sessions",
            )
        ],
        [
            InlineKeyboardButton("🏠 Home", callback_data="go_home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
