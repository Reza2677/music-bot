from telegram import ReplyKeyboardMarkup
from config import KEYBOARD_TEXTS # VALID_TIMES دیگر ایمپورت نمی‌شود

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KEYBOARD_TEXTS["list"]],
            # [KEYBOARD_TEXTS["set_time"], KEYBOARD_TEXTS["receive_music_now"]] # Set Time حذف شد
            [KEYBOARD_TEXTS["receive_music_now"]] # Receive Music Now در یک ردیف جدا یا کنار List
            # یا چینش دلخواه دیگر:
            # [[KEYBOARD_TEXTS["list"], KEYBOARD_TEXTS["receive_music_now"]]]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
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

def add_singer_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KEYBOARD_TEXTS["back"]]],
        resize_keyboard=True
    )

def delete_singer_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KEYBOARD_TEXTS["back"]]],
        resize_keyboard=True
    )

def confirm_remove_list_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KEYBOARD_TEXTS["confirm"], KEYBOARD_TEXTS["cancel_action"]]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


