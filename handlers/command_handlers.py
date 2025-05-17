from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from music_bot.config import logger, MAIN_MENU, USER_MESSAGES
from music_bot.services.user_manager import UserManager
from music_bot.utils.keyboards import main_menu_keyboard
from music_bot.utils.message_utils import send_menu_message, send_reply_message # استفاده از نام جدید send_menu_message

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"start_command: User {user.id} ({user.username or 'N/A'}) initiated /start.")

    try:
        # حذف پیام /start کاربر (اختیاری، برای تمیزتر شدن چت)
        try:
            if update.message: # فقط اگر از پیام آمده
                await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
        except Exception: pass

        user_manager: UserManager = context.bot_data.get('user_manager')
        if not user_manager: # بررسی مهم
            logger.critical("start_command: 'user_manager' NOT FOUND in bot_data!")
            await send_reply_message(update, context, USER_MESSAGES["error_services_unavailable"])
            return ConversationHandler.END

        user_manager.add_or_update_user_info(
            user_id=str(user.id),
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username
        )
        
        welcome_text = USER_MESSAGES["welcome"].format(user_name=user.first_name or "کاربر گرامی")
        await send_menu_message(update, context, welcome_text, reply_markup=main_menu_keyboard())
        
        return MAIN_MENU
    except KeyError as e: # اگر user_manager در bot_data نباشد (نباید اتفاق بیفتد اگر بالا چک شده)
        logger.critical(f"start_command: KeyError - {e}! This indicates a serious issue with bot_data setup.")
        await send_reply_message(update, context, USER_MESSAGES["error_services_unavailable"])
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"start_command: Error processing start for user {user.id}: {e}", exc_info=True)
        await send_reply_message(update, context, USER_MESSAGES["error_generic"])
        return ConversationHandler.END

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"User {user.id} cancelled the conversation.")
    
    # send_menu_message پیام قبلی را حذف می‌کند و پیام جدید را با کیبورد اصلی می‌فرستد
    await send_menu_message(
        update, 
        context, 
        USER_MESSAGES["cancel_operation"] + "\n" + USER_MESSAGES["main_menu_return"],
        reply_markup=main_menu_keyboard()
    )
    return MAIN_MENU