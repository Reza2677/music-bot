from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from music_bot.config import logger

EDITABLE_MESSAGE_ID_KEY = 'last_menu_message_id' # کلید برای ذخیره ID پیام منو

async def delete_previous_menu_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """
    پیام منوی قبلی که ID آن در context.user_data[EDITABLE_MESSAGE_ID_KEY] ذخیره شده را حذف می‌کند.
    """
    previous_message_id = context.user_data.pop(EDITABLE_MESSAGE_ID_KEY, None)
    if previous_message_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=previous_message_id)
            logger.debug(f"Deleted previous menu message {previous_message_id} for chat {chat_id}")
        except Exception as e:
            logger.debug(f"Could not delete previous menu message {previous_message_id} for chat {chat_id}: {e}")

async def send_menu_message(
    update_or_chat_id, 
    context: ContextTypes.DEFAULT_TYPE, 
    text: str, 
    reply_markup: ReplyKeyboardMarkup = None,
    parse_mode: str = None
):
    """
    ابتدا پیام منوی قبلی را (در صورت وجود) حذف می‌کند، سپس پیام منوی جدید را ارسال کرده
    و ID آن را در context.user_data[EDITABLE_MESSAGE_ID_KEY] ذخیره می‌کند.
    """
    chat_id: int
    message_method = None
    is_update_object = isinstance(update_or_chat_id, Update)

    if is_update_object:
        chat_id = update_or_chat_id.effective_chat.id
        if update_or_chat_id.message:
             message_method = update_or_chat_id.message.reply_text
        elif update_or_chat_id.callback_query and update_or_chat_id.callback_query.message:
             # برای callback query، معمولا پیام جدیدی ارسال می‌کنیم نه reply_text به پیام قبلی callback
             # مگر اینکه بخواهیم پیام اصلی دکمه‌ها را ویرایش کنیم که منطق متفاوتی دارد.
             # برای سادگی، فرض می‌کنیم پیام جدیدی ارسال می‌شود.
             message_method = context.bot.send_message
        else:
            message_method = context.bot.send_message
    elif isinstance(update_or_chat_id, int):
        chat_id = update_or_chat_id
        message_method = context.bot.send_message
    else:
        logger.error(f"send_menu_message: Invalid type for update_or_chat_id: {type(update_or_chat_id)}")
        return None

    await delete_previous_menu_message(context, chat_id) # حذف پیام منوی قبلی
    
    message_to_store = None
    try:
        if message_method == context.bot.send_message:
            message_to_store = await message_method(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        else: # استفاده از reply_text از شیء message
            message_to_store = await message_method(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        
        if message_to_store:
            context.user_data[EDITABLE_MESSAGE_ID_KEY] = message_to_store.message_id
            logger.debug(f"Sent and saved menu message {message_to_store.message_id} for chat {chat_id}")
        return message_to_store
    except Exception as e:
        logger.error(f"Error sending message in send_menu_message for chat {chat_id}: {e}", exc_info=True)
        return None

async def send_reply_message(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE, 
    text: str, 
    reply_markup=None, 
    parse_mode=None
):
    """فقط یک پیام به کاربر ارسال می‌کند (بدون حذف پیام قبلی یا ذخیره ID)."""
    try:
        # اطمینان از اینکه متد ارسال مناسب استفاده می‌شود
        if update.message:
            await update.message.reply_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif update.callback_query and update.callback_query.message:
             # برای callback query، reply_text به پیام اصلی که دکمه‌ها را دارد، پاسخ می‌دهد.
             # اگر می‌خواهید پیام جدیدی در چت بفرستید:
             await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif update.effective_chat: # اگر update.message یا callback_query.message نیست اما effective_chat هست
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            logger.error(f"send_reply_message: Cannot determine how to send message for update: {update}")

    except Exception as e:
        logger.error(f"Error sending reply message to user {update.effective_user.id if update.effective_user else 'Unknown'}: {e}", exc_info=True)