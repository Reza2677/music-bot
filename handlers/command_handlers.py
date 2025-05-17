from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from music_bot.config import logger, MAIN_MENU, USER_MESSAGES # KEYBOARD_TEXTS استفاده مستقیم ندارد
from music_bot.services.user_manager import UserManager
from music_bot.utils.keyboards import main_menu_keyboard
# from music_bot.utils.message_utils import ... # دیگر استفاده نمی‌شود

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    chat_id = update.effective_chat.id # استفاده مستقیم
    logger.info(f"start_command: User {user.id} ({user.username or 'N/A'}) initiated /start.")

    try:
        # دیگر پیام /start کاربر را حذف نمی‌کنیم (برای سادگی)

        user_manager: UserManager = context.bot_data.get('user_manager')
        if not user_manager:
            logger.critical("start_command: 'user_manager' NOT FOUND in bot_data!")
            await update.message.reply_text(USER_MESSAGES["error_services_unavailable"])
            return ConversationHandler.END

        user_manager.add_or_update_user_info(
            user_id=str(user.id),
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username
        )
        
        welcome_text = USER_MESSAGES["welcome"].format(user_name=user.first_name or "کاربر گرامی")
        await update.message.reply_text(welcome_text, reply_markup=main_menu_keyboard())
        
        return MAIN_MENU
    except KeyError:
        logger.critical("start_command: 'user_manager' not found (KeyError)! Initialization error.")
        await update.message.reply_text(USER_MESSAGES["error_services_unavailable"])
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"start_command: Error processing start for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(USER_MESSAGES["error_generic"])
        return ConversationHandler.END

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    logger.info(f"User {user.id} cancelled the conversation.")
    
    await update.message.reply_text(
        USER_MESSAGES["cancel_operation"] + "\n" + USER_MESSAGES["main_menu_return"],
        reply_markup=main_menu_keyboard()
    )
    # پاک کردن user_data های مربوط به مکالمه اگر چیزی ذخیره شده بود (اختیاری)
    # context.user_data.clear() # این همه چیز را پاک می‌کند، با احتیاط استفاده شود
    return MAIN_MENU