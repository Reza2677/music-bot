from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from ..config import logger, MAIN_MENU, KEYBOARD_TEXTS
from ..services import UserManager
from ..utils import main_menu_keyboard

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the /start command and initializes or updates user."""
    user = update.effective_user
    user_manager: UserManager = context.bot_data['user_manager']
    
    logger.info(f"User {user.id} ({user.username}) started the bot.")
    user_manager.add_or_update_user_info(
        user_id=str(user.id),
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username
    )
    
    await update.message.reply_text(
        "سلام! به ربات مدیریت و دریافت آهنگ خوش آمدید.\n"
        "لطفاً یکی از گزینه‌ها رو انتخاب کن:",
        reply_markup=main_menu_keyboard()
    )
    return MAIN_MENU

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the current conversation and returns to the main menu."""
    user = update.effective_user
    logger.info(f"User {user.id} cancelled the conversation.")
    await update.message.reply_text(
        "عملیات لغو شد. به منوی اصلی بازگشتید.",
        reply_markup=main_menu_keyboard()
    )
    return MAIN_MENU # یا ConversationHandler.END اگر میخواهید کاملا خارج شوید و با /start دوباره شروع شود