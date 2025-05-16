from telegram import ReplyKeyboardMarkup
from ..config import VALID_TIMES, KEYBOARD_TEXTS

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KEYBOARD_TEXTS["list"]], [KEYBOARD_TEXTS["set_time"]]], 
        resize_keyboard=True
    )

def list_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KEYBOARD_TEXTS["edit_list"], KEYBOARD_TEXTS["remove_list"]], [KEYBOARD_TEXTS["back"]]], 
        resize_keyboard=True
    )

def edit_list_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KEYBOARD_TEXTS["add"], KEYBOARD_TEXTS["delete"]], [KEYBOARD_TEXTS["back"]]], 
        resize_keyboard=True
    )

def add_singer_keyboard() -> ReplyKeyboardMarkup: # کیبورد در زمان افزودن خواننده
    return ReplyKeyboardMarkup(
        [[KEYBOARD_TEXTS["back"]]], # فقط دکمه بازگشت، چون ورودی متن است
        resize_keyboard=True
    )

def delete_singer_keyboard() -> ReplyKeyboardMarkup: # کیبورد در زمان حذف خواننده
    return ReplyKeyboardMarkup(
        [[KEYBOARD_TEXTS["back"]]], # فقط دکمه بازگشت
        resize_keyboard=True
    )
    
def confirm_remove_list_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KEYBOARD_TEXTS["confirm"], KEYBOARD_TEXTS["cancel_action"]]], 
        resize_keyboard=True
    )

def set_time_keyboard() -> ReplyKeyboardMarkup:
    keyboard = []
    for i in range(0, len(VALID_TIMES), 2):
        row = [VALID_TIMES[i]]
        if i + 1 < len(VALID_TIMES):
            row.append(VALID_TIMES[i+1])
        keyboard.append(row)
    keyboard.append([KEYBOARD_TEXTS["back"]])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)