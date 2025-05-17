from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler # ConversationHandler برای نوع‌دهی
from music_bot.config import logger, MAIN_MENU, USER_MESSAGES, CONFIRM_DELETE_HISTORY # اضافه شدن CONFIRM_DELETE_HISTORY
from music_bot.services.user_manager import UserManager
from music_bot.utils.keyboards import main_menu_keyboard
# از message_utils برای سادگی استفاده نمی‌کنیم

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    logger.info(f"start_command: User {user.id} ({user.username or 'N/A'}) initiated /start.")
    try:
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
    except Exception as e: # مدیریت خطای کلی‌تر
        logger.error(f"start_command: Error processing start for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(USER_MESSAGES["error_generic"])
        return ConversationHandler.END

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username or 'N/A'}) cancelled a conversation.")
    
    # پاک کردن داده‌های موقت مکالمه
    context.user_data.pop('singer_suggestion', None)
    context.user_data.pop('singer_suggestions_list', None)
    context.user_data.pop('suggestion_message_id', None)
    context.user_data.pop('confirm_delete_history_message_id', None) # برای اطمینان

    await update.message.reply_text(
        USER_MESSAGES["cancel_operation"] + "\n" + USER_MESSAGES["main_menu_return"],
        reply_markup=main_menu_keyboard()
    )
    return MAIN_MENU


# --- هندلرهای جدید برای /delete_history ---
async def delete_history_prompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    با دستور /delete_history فراخوانی می‌شود.
    از کاربر برای پاک کردن تاریخچه آهنگ‌های ارسالی (فقط داده sent_music) تاییدیه می‌گیرد.
    """
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username or 'N/A'}) initiated /delete_history command.")

    keyboard = [
        [
            InlineKeyboardButton(USER_MESSAGES["confirm_action_delete_history"], callback_data="history_delete_confirm_yes"),
            InlineKeyboardButton(USER_MESSAGES["cancel_action_delete_history"], callback_data="history_delete_confirm_no"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = await update.message.reply_text(USER_MESSAGES["delete_history_prompt"], reply_markup=reply_markup)
    context.user_data['confirm_delete_history_message_id'] = message.message_id # ذخیره ID برای ویرایش
    
    return CONFIRM_DELETE_HISTORY

async def delete_history_confirmation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """پاسخ کاربر به تاییدیه پاک کردن تاریخچه آهنگ‌های ارسالی را مدیریت می‌کند."""
    query = update.callback_query
    await query.answer() 

    user_id_str = str(query.from_user.id)
    # خواندن و حذف ID پیام از user_data (اگر در prompt ذخیره شده) یا استفاده از ID پیام فعلی
    message_id_to_edit = context.user_data.pop('confirm_delete_history_message_id', query.message.message_id)
    final_message_for_user = "" # پیامی که پیام دکمه‌ها را ویرایش خواهد کرد

    if query.data == "history_delete_confirm_yes":
        logger.info(f"User {user_id_str} confirmed deletion of sent music history.")
        user_manager: UserManager = context.bot_data.get('user_manager')
        if user_manager:
            try:
                user_manager.update_user_specific_data(user_id_str, {"sent_music": []})
                logger.info(f"Sent music history cleared for user {user_id_str}.")
                final_message_for_user = USER_MESSAGES["delete_history_success"]
            except Exception as e:
                logger.error(f"Error clearing sent_music for user {user_id_str}: {e}", exc_info=True)
                final_message_for_user = USER_MESSAGES["error_generic"]
        else:
            logger.error(f"UserManager not found while trying to delete history for user {user_id_str}.")
            final_message_for_user = USER_MESSAGES["error_services_unavailable"]
        
    elif query.data == "history_delete_confirm_no":
        logger.info(f"User {user_id_str} cancelled deletion of sent music history.")
        final_message_for_user = USER_MESSAGES["delete_history_cancelled"]
    
    else: 
        logger.warning(f"Unknown callback_data '{query.data}' in delete_history_confirmation.")
        final_message_for_user = USER_MESSAGES["error_generic"] # پیام خطای عمومی

    # ویرایش پیام دکمه‌های شیشه‌ای با نتیجه نهایی
    try:
        if message_id_to_edit:
            await context.bot.edit_message_text(
                chat_id=query.message.chat_id,
                message_id=message_id_to_edit,
                text=final_message_for_user,
                reply_markup=None # حذف دکمه‌های شیشه‌ای
            )
    except Exception as e_edit:
        logger.error(f"Error editing confirmation message for delete_history: {e_edit}")
        # اگر ویرایش ناموفق بود، پیام جدید بفرست (بدون کیبورد قبلی)
        await context.bot.send_message(chat_id=query.message.chat_id, text=final_message_for_user)

    # پس از اتمام (چه موفق چه ناموفق چه لغو)، کاربر را به منوی اصلی برمی‌گردانیم
    # این پیام جدید است و پیام قبلی (که ویرایش شد) را تحت تاثیر قرار نمی‌دهد.
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=USER_MESSAGES["main_menu_return"],
        reply_markup=main_menu_keyboard()
    )
    
    return ConversationHandler.END # پایان مکالمه مربوط به /delete_history