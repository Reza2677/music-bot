# utils/message_utils.py (نسخه بسیار ساده شده)

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from music_bot.config import logger

async def send_simple_reply(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE, 
    text: str, 
    reply_markup=None, 
    parse_mode=None
):
    """یک پیام ساده به کاربر ارسال می‌کند."""
    try:
        # اطمینان از اینکه متد ارسال مناسب استفاده می‌شود
        if update.message:
            await update.message.reply_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif update.callback_query and update.callback_query.message:
             await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif update.effective_chat:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            logger.error(f"send_simple_reply: Cannot determine how to send message for update: {update}")
    except Exception as e:
        logger.error(f"Error sending simple reply to user {update.effective_user.id if update.effective_user else 'Unknown'}: {e}", exc_info=True)