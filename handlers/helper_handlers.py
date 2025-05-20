from telegram import Update, constants
from telegram.ext import ContextTypes
from services.user_manager import UserManager
from config import logger, USER_MESSAGES, KEYBOARD_TEXTS
from utils.message_utils import send_reply_message # <--- استفاده از تابع کمکی

async def show_user_singers_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager: UserManager = context.bot_data.get('user_manager')
    user_id = str(update.effective_user.id)

    if not user_manager:
        logger.error(f"UserManager not found for show_user_singers_list (user: {user_id})")
        await send_reply_message(update, context, USER_MESSAGES["error_services_unavailable"])
        return

    user_data = user_manager.get_user(user_id)

    if not user_data or not user_data.get("singer_names"):
        edit_list_text = KEYBOARD_TEXTS.get("edit_list", "ویرایش لیست")
        await send_reply_message(update, context, USER_MESSAGES["no_singers_in_list_prompt_add"].format(edit_list_text=edit_list_text))
        return

    singer_list_text = "🎧 **خوانندگان ذخیره شده شما:**\n\n"
    # ... (بقیه کد ساخت singer_list_text مانند قبل) ...
    for i, singer_info in enumerate(user_data["singer_names"]):
        if isinstance(singer_info, dict) and 'name' in singer_info and 'count' in singer_info:
            singer_list_text += f"▫️ `{singer_info['name']}` (درخواست: {singer_info['count']} آهنگ)\n"
        else:
            logger.warning(f"Malformed singer_info for user {user_id}: {singer_info}")
            singer_list_text += f"▫️ _اطلاعات خواننده شماره {i+1} ناقص است._\n"

    try:
        await send_reply_message(update, context, singer_list_text, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error sending singer list with Markdown for user {user_id}: {e}. Sending as plain text.")
        plain_text = singer_list_text.replace("*", "").replace("_", "").replace("`", "")
        await send_reply_message(update, context, plain_text)