from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from config import logger # استفاده از لاگر مرکزی

EDITABLE_MESSAGE_ID_KEY = 'last_menu_message_id' # این کلید را نگه می‌داریم برای استفاده احتمالی آینده

async def delete_previous_menu_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """
    (Placeholder - فعلاً غیرفعال)
    پیام منوی قبلی که ID آن در context.user_data[EDITABLE_MESSAGE_ID_KEY] ذخیره شده را حذف می‌کند.
    """
    # previous_message_id = context.user_data.pop(EDITABLE_MESSAGE_ID_KEY, None)
    # if previous_message_id:
    #     try:
    #         await context.bot.delete_message(chat_id=chat_id, message_id=previous_message_id)
    #         logger.debug(f"Deleted previous menu message {previous_message_id} for chat {chat_id}")
    #     except Exception as e:
    #         logger.debug(f"Could not delete previous menu message {previous_message_id} for chat {chat_id}: {e}")
    logger.debug("delete_previous_menu_message called but is currently a placeholder.") # لاگ برای اطلاع
    pass # فعلاً کاری انجام نمی‌دهد


async def send_menu_message(
    update_or_chat_id, 
    context: ContextTypes.DEFAULT_TYPE, 
    text: str, 
    reply_markup: ReplyKeyboardMarkup = None,
    parse_mode: str = None
):
    """
    (Placeholder - فعلاً پیام را مستقیماً ارسال می‌کند بدون حذف قبلی یا ذخیره ID)
    در آینده می‌تواند برای حذف پیام قبلی و ذخیره ID پیام جدید استفاده شود.
    """
    chat_id: int
    message_method = None
    is_update_object = isinstance(update_or_chat_id, Update)

    if is_update_object:
        chat_id = update_or_chat_id.effective_chat.id
        if update_or_chat_id.message:
             message_method = update_or_chat_id.message.reply_text
        elif update_or_chat_id.callback_query and update_or_chat_id.callback_query.message:
             message_method = context.bot.send_message 
        else:
            message_method = context.bot.send_message
    elif isinstance(update_or_chat_id, int):
        chat_id = update_or_chat_id
        message_method = context.bot.send_message
    else:
        logger.error(f"send_menu_message: Invalid type for update_or_chat_id: {type(update_or_chat_id)}")
        return None

    # await delete_previous_menu_message(context, chat_id) # <--- فعلاً این را غیرفعال می‌کنیم
    
    message_to_store = None
    try:
        if message_method == context.bot.send_message:
            message_to_store = await message_method(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            message_to_store = await message_method(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        
        # context.user_data[EDITABLE_MESSAGE_ID_KEY] = message_to_store.message_id # <--- فعلاً ID را ذخیره نمی‌کنیم
        logger.debug(f"Sent message (menu - currently no ID saved) for chat {chat_id}")
        return message_to_store
    except Exception as e:
        logger.error(f"Error sending message in send_menu_message for chat {chat_id}: {e}", exc_info=True)
        return None


async def send_reply_message( # این تابع همانطور که هست باقی می‌ماند و استفاده می‌شود
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE, 
    text: str, 
    reply_markup=None, 
    parse_mode=None
):
    """فقط یک پیام به کاربر ارسال می‌کند (بدون حذف پیام قبلی یا ذخیره ID)."""
    try:
        target_chat_id = update.effective_chat.id
        if not target_chat_id: # فال‌بک اگر effective_chat موجود نیست
            if update.message: target_chat_id = update.message.chat_id
            elif update.callback_query: target_chat_id = update.callback_query.message.chat_id
        
        if not target_chat_id:
            logger.error(f"send_reply_message: Could not determine chat_id from update.")
            return

        # همیشه از context.bot.send_message استفاده می‌کنیم برای سادگی و یکنواختی در این تابع
        await context.bot.send_message(chat_id=target_chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)

    except Exception as e:
        user_id_for_log = update.effective_user.id if update.effective_user else "UnknownUser"
        logger.error(f"Error sending reply message to user {user_id_for_log}: {e}", exc_info=True)