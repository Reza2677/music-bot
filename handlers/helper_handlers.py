from telegram import Update
from telegram.ext import ContextTypes
from ..services import UserManager # برای دسترسی به اطلاعات کاربر

async def show_user_singers_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the user's current list of singers."""
    user_manager: UserManager = context.bot_data['user_manager']
    user_id = str(update.effective_user.id)
    user_data = user_manager.get_user(user_id)

    if not user_data or not user_data.get("singer_names"):
        await update.message.reply_text("لیست خوانندگان شما خالی است.")
        return

    singer_list_text = "لیست خوانندگان شما:\n"
    for i, singer_info in enumerate(user_data["singer_names"]):
        singer_list_text += f"{i+1}. {singer_info['name']} (تعداد آهنگ درخواستی: {singer_info['count']})\n"
    
    await update.message.reply_text(singer_list_text)