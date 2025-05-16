from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from ..config import (logger, MAIN_MENU, LIST_MENU, EDIT_LIST_MENU, ADD_SINGER, 
                    DELETE_SINGER, REMOVE_LIST_CONFIRM, SET_TIME, VALID_TIMES, KEYBOARD_TEXTS)
from ..services import UserManager
from ..utils import (main_menu_keyboard, list_menu_keyboard, edit_list_keyboard, 
                   confirm_remove_list_keyboard, set_time_keyboard, add_singer_keyboard,
                   delete_singer_keyboard) # کیبوردهای جدید
from .helper_handlers import show_user_singers_list # تابع کمکی

# --- Main Menu Router ---
async def main_menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Routes user based on main menu selection."""
    text = update.message.text
    if text == KEYBOARD_TEXTS["list"]:
        return await list_menu_prompt_handler(update, context)
    elif text == KEYBOARD_TEXTS["set_time"]:
        return await set_time_prompt_handler(update, context)
    else:
        await update.message.reply_text("گزینه نامعتبر، لطفا از دکمه ها استفاده کنید.", reply_markup=main_menu_keyboard())
        return MAIN_MENU

# --- List Menu Handlers ---
async def list_menu_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays the list menu and current singers."""
    await show_user_singers_list(update, context)
    await update.message.reply_text("گزینه ای را برای مدیریت لیست انتخاب کنید:", reply_markup=list_menu_keyboard())
    return LIST_MENU

async def list_menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Routes user based on list menu selection."""
    text = update.message.text
    if text == KEYBOARD_TEXTS["edit_list"]:
        return await edit_list_menu_prompt_handler(update, context)
    elif text == KEYBOARD_TEXTS["remove_list"]:
        return await remove_list_prompt_handler(update, context)
    elif text == KEYBOARD_TEXTS["back"]:
        return await back_to_main_menu_handler(update, context)
    else:
        await update.message.reply_text("گزینه نامعتبر.", reply_markup=list_menu_keyboard())
        return LIST_MENU

# --- Edit List Menu Handlers ---
async def edit_list_menu_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays the edit list menu."""
    await update.message.reply_text(
        "می توانید خواننده اضافه یا حذف کنید:",
        reply_markup=edit_list_keyboard()
    )
    return EDIT_LIST_MENU

async def edit_list_menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Routes user based on edit list menu selection."""
    text = update.message.text
    if text == KEYBOARD_TEXTS["add"]:
        return await add_singer_prompt_handler(update, context)
    elif text == KEYBOARD_TEXTS["delete"]:
        return await delete_singer_prompt_handler(update, context)
    elif text == KEYBOARD_TEXTS["back"]:
        return await back_to_list_menu_handler(update, context) # باید به منوی لیست برگردد
    else:
        await update.message.reply_text("گزینه نامعتبر.", reply_markup=edit_list_keyboard())
        return EDIT_LIST_MENU

# --- Add Singer Handlers ---
async def add_singer_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts user to add a singer."""
    await show_user_singers_list(update, context)
    await update.message.reply_text(
        "اسم خواننده و تعداد آهنگ‌های جدید درخواستی از او را در دو خط جداگانه وارد کنید (مثال:\nحامیم\n2)\n"
        "اگر تعداد آهنگ را وارد نکنید، ۱ در نظر گرفته می‌شود.",
        reply_markup=add_singer_keyboard() # کیبورد فقط با دکمه بازگشت
    )
    return ADD_SINGER

async def save_singer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the singer to the user's list."""
    user_manager: UserManager = context.bot_data['user_manager']
    user_id = str(update.effective_user.id)
    
    input_text = update.message.text.strip()
    if not input_text:
        await update.message.reply_text("ورودی نامعتبر. لطفاً نام خواننده را وارد کنید.")
        return ADD_SINGER # Stay in the same state

    parts = input_text.split("\n")
    singer_name = parts[0].strip()
    
    if not singer_name:
        await update.message.reply_text("نام خواننده نمی‌تواند خالی باشد.")
        return ADD_SINGER

    count = 1 # Default count
    if len(parts) > 1 and parts[1].strip().isdigit():
        count = int(parts[1].strip())
        if count <= 0:
            await update.message.reply_text("تعداد آهنگ باید یک عدد مثبت باشد. ۱ در نظر گرفته شد.")
            count = 1
    
    user_data = user_manager.get_user(user_id)
    singer_names_list = user_data.get("singer_names", [])

    # Check if singer already exists (case-insensitive)
    existing_singer = next((s for s in singer_names_list if s["name"].lower() == singer_name.lower()), None)

    if existing_singer:
        existing_singer["count"] = count # Update count if singer exists
        await update.message.reply_text(f"تعداد آهنگ درخواستی برای '{singer_name}' به {count} به‌روز شد.")
    else:
        singer_names_list.append({"name": singer_name, "count": count})
        await update.message.reply_text(f"خواننده '{singer_name}' با درخواست {count} آهنگ به لیست شما اضافه شد.")
    
    user_manager.update_user_specific_data(user_id, {"singer_names": singer_names_list})
    # await show_user_singers_list(update, context) # نمایش لیست بعد از افزودن
    return await edit_list_menu_prompt_handler(update, context) # بازگشت به منوی ویرایش لیست

# --- Delete Singer Handlers ---
async def delete_singer_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts user to delete a singer."""
    await show_user_singers_list(update, context)
    user_manager: UserManager = context.bot_data['user_manager']
    user_id = str(update.effective_user.id)
    user_data = user_manager.get_user(user_id)
    if not user_data or not user_data.get("singer_names"):
        await update.message.reply_text("لیست خوانندگان شما برای حذف خالی است.", reply_markup=edit_list_keyboard())
        return EDIT_LIST_MENU

    await update.message.reply_text(
        "اسم خواننده‌ای که می‌خواهید از لیست حذف کنید را وارد نمایید:",
        reply_markup=delete_singer_keyboard() # کیبورد فقط با دکمه بازگشت
    )
    return DELETE_SINGER

async def remove_singer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Removes the singer from the user's list."""
    user_manager: UserManager = context.bot_data['user_manager']
    user_id = str(update.effective_user.id)
    singer_name_to_delete = update.message.text.strip()

    user_data = user_manager.get_user(user_id)
    singer_names_list = user_data.get("singer_names", [])
    
    initial_len = len(singer_names_list)
    # Case-insensitive removal
    singer_names_list = [s for s in singer_names_list if s["name"].lower() != singer_name_to_delete.lower()]

    if len(singer_names_list) < initial_len:
        user_manager.update_user_specific_data(user_id, {"singer_names": singer_names_list})
        await update.message.reply_text(f"خواننده '{singer_name_to_delete}' از لیست شما حذف شد.")
    else:
        await update.message.reply_text(f"خواننده '{singer_name_to_delete}' در لیست شما یافت نشد.")
    
    # await show_user_singers_list(update, context)
    return await edit_list_menu_prompt_handler(update, context) # بازگشت به منوی ویرایش لیست


# --- Remove Entire List Handlers ---
async def remove_list_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks for confirmation to remove the entire list."""
    user_manager: UserManager = context.bot_data['user_manager']
    user_id = str(update.effective_user.id)
    user_data = user_manager.get_user(user_id)

    if not user_data or not user_data.get("singer_names"):
        await update.message.reply_text("لیست خوانندگان شما از قبل خالی است!", reply_markup=list_menu_keyboard())
        return LIST_MENU 

    await show_user_singers_list(update, context)
    await update.message.reply_text(
        "آیا مطمئن هستید که می‌خواهید کل لیست خوانندگان خود را حذف کنید؟ این عمل قابل بازگشت نیست.",
        reply_markup=confirm_remove_list_keyboard()
    )
    return REMOVE_LIST_CONFIRM

async def confirm_remove_list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirms and removes the entire singer list."""
    user_manager: UserManager = context.bot_data['user_manager']
    user_id = str(update.effective_user.id)
    
    user_manager.update_user_specific_data(user_id, {"singer_names": []})
    logger.info(f"User {user_id} cleared their singer list.")
    await update.message.reply_text("کل لیست خوانندگان شما با موفقیت پاک شد.")
    return await list_menu_prompt_handler(update, context) # بازگشت به منوی لیست

async def cancel_remove_list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels removing the list and returns to list menu."""
    await update.message.reply_text("حذف لیست لغو شد.", reply_markup=list_menu_keyboard())
    return await list_menu_prompt_handler(update, context) # بازگشت به منوی لیست

# --- Set Time Handlers ---
async def set_time_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays options to set notification time."""
    user_manager: UserManager = context.bot_data['user_manager']
    user_id = str(update.effective_user.id)
    user_data = user_manager.get_user(user_id)
    current_time = user_data.get("sent_time", "02:00")

    await update.message.reply_text(
        f"زمان فعلی تنظیم شده برای دریافت اعلان آهنگ‌های جدید: {current_time}\n"
        "لطفاً زمان جدید مورد نظر خود را از بین گزینه‌های زیر انتخاب کنید:",
        reply_markup=set_time_keyboard()
    )
    return SET_TIME

async def save_time_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the selected notification time."""
    user_manager: UserManager = context.bot_data['user_manager']
    user_id = str(update.effective_user.id)
    selected_time = update.message.text.strip()

    if selected_time in VALID_TIMES:
        user_manager.update_user_specific_data(user_id, {"sent_time": selected_time})
        logger.info(f"User {user_id} set notification time to {selected_time}.")
        await update.message.reply_text(
            f"زمان ارسال اعلان آهنگ‌های جدید برای شما به {selected_time} تغییر یافت.",
            reply_markup=main_menu_keyboard()
        )
        return MAIN_MENU
    elif selected_time == KEYBOARD_TEXTS["back"]: # اگر کاربر دکمه بازگشت را از کیبورد زمان انتخاب کرده باشد
        return await back_to_main_menu_handler(update, context)
    else:
        await update.message.reply_text(
            "زمان انتخاب شده معتبر نیست. لطفاً فقط از دکمه‌های ارائه شده استفاده کنید.",
            reply_markup=set_time_keyboard()
        )
        return SET_TIME

# --- Navigation Handlers (Back buttons) ---
async def back_to_main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("بازگشت به منوی اصلی.", reply_markup=main_menu_keyboard())
    return MAIN_MENU

async def back_to_list_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # نمایش لیست خوانندگان قبل از نمایش دکمه‌ها
    # await show_user_singers_list(update, context) # این باعث می‌شود لیست دوباره نشان داده شود
    await update.message.reply_text("بازگشت به منوی لیست.", reply_markup=list_menu_keyboard())
    return LIST_MENU

async def back_to_edit_list_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # await show_user_singers_list(update, context) # اینجا هم شاید بهتر باشد لیست دوباره نشان داده نشود
    await update.message.reply_text("بازگشت به منوی ویرایش لیست.", reply_markup=edit_list_keyboard())
    return EDIT_LIST_MENU

# --- Ignore Handlers (برای جلوگیری از تداخل دکمه‌ها در حالت‌های مختلف) ---
async def ignore_delete_in_add_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "شما در حال افزودن خواننده هستید. لطفاً نام خواننده و تعداد آهنگ را وارد کنید یا از دکمه 'Back' استفاده کنید.",
        reply_markup=add_singer_keyboard() # کیبورد حالت افزودن
    )
    return ADD_SINGER # در همین حالت بمان

async def ignore_add_in_delete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "شما در حال حذف خواننده هستید. لطفاً نام خواننده‌ای که می‌خواهید حذف کنید را وارد نمایید یا از دکمه 'Back' استفاده کنید.",
        reply_markup=delete_singer_keyboard() # کیبورد حالت حذف
    )
    return DELETE_SINGER # در همین حالت بمان