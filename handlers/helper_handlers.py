from telegram import Update, constants
from telegram.ext import ContextTypes
from music_bot.services.user_manager import UserManager
from music_bot.config import logger, USER_MESSAGES, KEYBOARD_TEXTS
from music_bot.utils.message_utils import send_reply_message # برای ارسال پیام لیست یا خطا

async def show_user_singers_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لیست خوانندگان کاربر را با فرمت Markdown نمایش می‌دهد."""
    user_manager: UserManager = context.bot_data.get('user_manager')
    user_id = str(update.effective_user.id)

    if not user_manager:
        logger.error(f"UserManager not found in bot_data for show_user_singers_list (user: {user_id})")
        await send_reply_message(update, context, USER_MESSAGES["error_services_unavailable"])
        return

    user_data = user_manager.get_user(user_id)

    if not user_data or not user_data.get("singer_names"):
        edit_list_text = KEYBOARD_TEXTS.get("edit_list", "ویرایش لیست") # گرفتن متن دکمه از config
        await send_reply_message(update, context, USER_MESSAGES["no_singers_in_list_prompt_add"].format(edit_list_text=edit_list_text))
        return

    singer_list_text = "🎧 **خوانندگان ذخیره شده شما:**\n\n"
    for i, singer_info in enumerate(user_data["singer_names"]):
        if isinstance(singer_info, dict) and 'name' in singer_info and 'count' in singer_info:
            singer_list_text += f"▫️ `{singer_info['name']}` (درخواست: {singer_info['count']} آهنگ)\n"
        else:
            logger.warning(f"Malformed singer_info for user {user_id}: {singer_info}")
            singer_list_text += f"▫️ _اطلاعات خواننده شماره {i+1} ناقص است._\n"
    
    try:
        # این پیام یک پیام اطلاعاتی است، ID آن را برای حذف بعدی ذخیره نمی‌کنیم
        await send_reply_message(update, context, singer_list_text, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error sending singer list with Markdown for user {user_id}: {e}. Sending as plain text.")
        plain_text = singer_list_text.replace("*", "").replace("_", "").replace("`", "")
        await send_reply_message(update, context, plain_text)