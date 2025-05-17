from telegram import Update, ReplyKeyboardMarkup, constants, ForceReply
from telegram.ext import ContextTypes, ConversationHandler, Application
from telegram.error import TelegramError
import asyncio

from music_bot.config import (logger, MAIN_MENU, LIST_MENU, EDIT_LIST_MENU, ADD_SINGER,
                               DELETE_SINGER, REMOVE_LIST_CONFIRM, KEYBOARD_TEXTS, USER_MESSAGES)
from music_bot.services.user_manager import UserManager
from music_bot.services.track_searcher import TrackSearcher
from music_bot.utils.keyboards import (main_menu_keyboard, list_menu_keyboard, edit_list_keyboard,
                                        confirm_remove_list_keyboard, add_singer_keyboard,
                                        delete_singer_keyboard)
from music_bot.handlers.helper_handlers import show_user_singers_list
from music_bot.utils.message_utils import send_reply_message # برای پیام‌های ساده


# --- ثابت‌های تاخیر ---
DELAY_BETWEEN_INDIVIDUAL_MANUAL_MESSAGES_S = 0.3
DELAY_AFTER_PROCESSING_EACH_USER_MANUALLY_S = 1.0


# --- تابع کارگر برای صف دستی (manual_request_worker) ---
# این تابع همچنان از context.bot.send_message استفاده می‌کند که مشکلی ندارد
async def manual_request_worker(application: Application):
    queue: asyncio.Queue = application.bot_data.get('manual_request_queue')
    if not queue:
        logger.critical("Manual request queue not found in bot_data. Worker cannot start.")
        return
    logger.info("Manual request worker started.")
    while True:
        try:
            request_data = await queue.get()
            if request_data is None: # Stop signal
                logger.info("Manual request worker received stop signal. Exiting.")
                queue.task_done()
                break

            user_id = request_data.get('user_id')
            chat_id = request_data.get('chat_id')
            if not user_id or not chat_id:
                logger.error(f"Worker: Invalid data in manual_request_queue: {request_data}")
                queue.task_done()
                continue
            
            user_id_str = str(user_id)
            logger.info(f"Worker: Processing manual request for user {user_id_str}")

            user_manager: UserManager = application.bot_data.get('user_manager')
            track_searcher: TrackSearcher = application.bot_data.get('track_searcher')
            bot = application.bot

            if not all([user_manager, track_searcher, bot]):
                logger.error(f"Worker: Critical services not found for user {user_id_str}.")
                try: await bot.send_message(chat_id=chat_id, text=USER_MESSAGES["error_services_unavailable"])
                except Exception: pass
                queue.task_done()
                continue

            user_data = user_manager.get_user(user_id_str)
            if not user_data:
                logger.warning(f"Worker: User data not found for user {user_id_str}.")
                try: await bot.send_message(chat_id=chat_id, text=USER_MESSAGES["error_user_data_not_found"])
                except Exception: pass
                queue.task_done()
                continue

            preferred_singers = user_data.get("singer_names", [])
            if not preferred_singers:
                logger.info(f"Worker: No preferred singers for user {user_id_str}.")
                try: await bot.send_message(chat_id=chat_id, text=USER_MESSAGES["no_singers_in_list_general"])
                except Exception: pass
                queue.task_done()
                continue
            
            try:
                found_tracks = await track_searcher.search_tracks_by_singer_list(preferred_singers)
                current_sent_music_for_user = set(user_data.get("sent_music", []))
                new_tracks_to_send = []
                processed_links_in_this_fetch = set()

                for track in found_tracks:
                    download_link = track.get("download_link")
                    if download_link and \
                       download_link not in ["N/A", "FAILED_ON_JOB", None, ""] and \
                       download_link not in current_sent_music_for_user and \
                       download_link not in processed_links_in_this_fetch:
                        new_tracks_to_send.append(track)
                        processed_links_in_this_fetch.add(download_link)
                
                if not new_tracks_to_send:
                    logger.info(f"Worker: No new tracks found for user {user_id_str}.")
                    try: await bot.send_message(chat_id=chat_id, text=USER_MESSAGES["manual_fetch_no_new_songs"])
                    except Exception: pass
                    queue.task_done()
                    continue
                    
                successfully_sent_links_this_run = set()
                num_total_to_send = len(new_tracks_to_send)
                num_successfully_sent = 0
                te_error_in_loop = None

                try:
                    await bot.send_message(chat_id=chat_id, text=USER_MESSAGES["manual_fetch_found_sending"].format(num_found=num_total_to_send))
                except TelegramError as e_init_send:
                    logger.warning(f"Worker: Could not send 'found tracks' message to user {user_id_str}: {e_init_send}")
                    if "bot was blocked by the user" in str(e_init_send).lower():
                        queue.task_done()
                        continue 

                for i, track_to_send in enumerate(new_tracks_to_send):
                    singer_name = track_to_send.get('fa_name') or track_to_send.get('en_name', 'خواننده نامشخص')
                    track_title = track_to_send.get('fa_track') or track_to_send.get('en_track', 'آهنگ نامشخص')
                    dl_link = track_to_send.get('download_link', '')
                    message_text = (
                        f"({i+1}/{num_total_to_send}) 🎵 آهنگ جدید از: {singer_name}\n"
                        f"🎶 نام آهنگ: {track_title}\n"
                        f"🔗 لینک دانلود: {dl_link}"
                    )
                    try:
                        await bot.send_message(chat_id=chat_id, text=message_text)
                        successfully_sent_links_this_run.add(dl_link)
                        num_successfully_sent += 1
                        if i < num_total_to_send - 1:
                             await asyncio.sleep(DELAY_BETWEEN_INDIVIDUAL_MANUAL_MESSAGES_S)
                    except TelegramError as te:
                        te_error_in_loop = te
                        logger.warning(f"Worker: TelegramError sending message #{i+1} to user {user_id_str}: {te}")
                        if "bot was blocked by the user" in str(te).lower():
                            try: await bot.send_message(chat_id=chat_id, text=USER_MESSAGES["manual_fetch_blocked"])
                            except Exception: pass
                            break 
                    except Exception as e_send:
                        logger.error(f"Worker: General error sending message #{i+1} to user {user_id_str}: {e_send}", exc_info=True)
                
                if successfully_sent_links_this_run:
                    final_sent_music_list = list(current_sent_music_for_user.union(successfully_sent_links_this_run))
                    user_manager.update_user_specific_data(user_id_str, {"sent_music": final_sent_music_list})
                
                final_message_text = ""
                if num_successfully_sent == num_total_to_send and num_total_to_send > 0:
                     final_message_text = USER_MESSAGES["manual_fetch_all_sent_successfully"].format(num_sent=num_successfully_sent)
                elif num_successfully_sent > 0:
                     final_message_text = USER_MESSAGES["manual_fetch_some_sent"].format(num_sent=num_successfully_sent, num_total=num_total_to_send)
                elif num_total_to_send > 0 and num_successfully_sent == 0:
                    if not (te_error_in_loop and "bot was blocked by the user" in str(te_error_in_loop).lower()):
                         final_message_text = USER_MESSAGES["manual_fetch_none_sent_error"]
                if final_message_text:
                    try: await bot.send_message(chat_id=chat_id, text=final_message_text)
                    except Exception: pass

            except Exception as e_process:
                logger.error(f"Worker: Critical error processing request for user {user_id_str}: {e_process}", exc_info=True)
                try: await bot.send_message(chat_id=chat_id, text=USER_MESSAGES["error_generic"])
                except Exception: pass
            
            queue.task_done()
            logger.info(f"Worker: Finished processing for user {user_id_str}. Waiting {DELAY_AFTER_PROCESSING_EACH_USER_MANUALLY_S}s before next user...")
            await asyncio.sleep(DELAY_AFTER_PROCESSING_EACH_USER_MANUALLY_S)
        except asyncio.CancelledError:
            logger.info("Manual request worker task was cancelled.")
            break
        except Exception as e_loop:
            logger.error(f"Manual request worker: Unhandled error in main loop: {e_loop}", exc_info=True)
            await asyncio.sleep(5)


# --- هندلر دکمه "دریافت آهنگ‌های جدید" ---
async def receive_music_now_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handles the 'Receive Music Now' button.
    Adds the user's request to a global queue for sequential processing.
    پیام‌های قبلی را حذف یا ویرایش نمی‌کند.
    """
    user = update.effective_user
    chat_id = update.effective_chat.id # برای استفاده احتمالی در لاگ‌ها یا ارسال مستقیم

    queue: asyncio.Queue = context.bot_data.get('manual_request_queue')
    if not queue:
        logger.error(f"Manual request queue not found for user {user.id}. Cannot queue request.")
        # ارسال پیام خطا با کیبورد اصلی
        await update.message.reply_text(
            USER_MESSAGES["error_services_unavailable"], 
            reply_markup=main_menu_keyboard()
        )
        return MAIN_MENU

    logger.info(f"User {user.id} ({user.username or 'N/A'}) pressed '{KEYBOARD_TEXTS['receive_music_now']}'. Adding to queue.")
    
    # دیگر نیازی به حذف پیام منوی اصلی قبلی نیست، چون حالت ساده‌تری داریم.

    try:
        await queue.put({'user_id': user.id, 'chat_id': chat_id})
        # ارسال پیام "در صف قرار گرفت" با کیبورد اصلی
        await update.message.reply_text(
            USER_MESSAGES["manual_fetch_queued"], 
            reply_markup=main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Error adding request to manual queue for user {user.id}: {e}")
        # ارسال پیام خطا با کیبورد اصلی
        await update.message.reply_text(
            USER_MESSAGES["error_generic"], 
            reply_markup=main_menu_keyboard()
        )
    
    return MAIN_MENU # کاربر در منوی اصلی باقی می‌ماند


async def list_menu_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await show_user_singers_list(update, context) # این از send_reply_message استفاده می‌کند
    await update.message.reply_text(USER_MESSAGES["list_menu_prompt"], reply_markup=list_menu_keyboard())
    return LIST_MENU

async def list_menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == KEYBOARD_TEXTS["edit_list"]:
        return await edit_list_menu_prompt_handler(update, context)
    elif text == KEYBOARD_TEXTS["remove_list"]:
        return await remove_list_prompt_handler(update, context)
    elif text == KEYBOARD_TEXTS["back"]:
        return await back_to_main_menu_handler(update, context)
    else:
        await update.message.reply_text("🚫 گزینه نامعتبر.", reply_markup=list_menu_keyboard())
        return LIST_MENU

# --- Edit List Menu Handlers ---
async def edit_list_menu_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(USER_MESSAGES["edit_list_menu_prompt"], reply_markup=edit_list_keyboard())
    return EDIT_LIST_MENU

async def edit_list_menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == KEYBOARD_TEXTS["add"]:
        return await add_singer_prompt_handler(update, context)
    elif text == KEYBOARD_TEXTS["delete"]:
        return await delete_singer_prompt_handler(update, context)
    elif text == KEYBOARD_TEXTS["back"]:
        return await back_to_list_menu_handler(update, context)
    else:
        await update.message.reply_text("🚫 گزینه نامعتبر.", reply_markup=edit_list_keyboard())
        return EDIT_LIST_MENU

# --- Add Singer Handlers ---
async def add_singer_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await show_user_singers_list(update, context) 
    # استفاده از ForceReply برای اینکه کاربر مجبور به تایپ شود و کیبورد قبلی پنهان شود (اختیاری)
    # یا فقط ارسال پیام با کیبورد add_singer_keyboard
    await update.message.reply_text(USER_MESSAGES["add_singer_prompt"], reply_markup=add_singer_keyboard())
    # await update.message.reply_text(USER_MESSAGES["add_singer_prompt"], reply_markup=ForceReply(selective=True)) # اگر می‌خواهید کیبورد قبلی بسته شود
    return ADD_SINGER

async def save_singer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_manager: UserManager = context.bot_data['user_manager']
    user_id = str(update.effective_user.id)
    input_text = update.message.text.strip()

    if not input_text:
        await update.message.reply_text(USER_MESSAGES["add_singer_invalid_input"], reply_markup=add_singer_keyboard())
        return ADD_SINGER 

    parts = input_text.split("\n")
    singer_name = parts[0].strip()
    if not singer_name:
        await update.message.reply_text(USER_MESSAGES["add_singer_name_empty"], reply_markup=add_singer_keyboard())
        return ADD_SINGER

    count = 1
    if len(parts) > 1 and parts[1].strip().isdigit():
        count_val = int(parts[1].strip())
        if count_val <= 0:
            await update.message.reply_text(USER_MESSAGES["add_singer_count_positive"], reply_markup=add_singer_keyboard())
            count = 1 
        elif count_val > 10:
             await update.message.reply_text(USER_MESSAGES["add_singer_count_max"], reply_markup=add_singer_keyboard())
             count = 10
        else:
            count = count_val
    
    user_data = user_manager.get_user(user_id)
    singer_names_list = user_data.get("singer_names", []) if user_data else []
    if not isinstance(singer_names_list, list): singer_names_list = []

    existing_singer = next((s for s in singer_names_list if isinstance(s, dict) and s.get("name","").lower() == singer_name.lower()), None)

    response_text = ""
    if existing_singer:
        existing_singer["count"] = count
        response_text = USER_MESSAGES["add_singer_updated_count"].format(singer_name=singer_name, count=count)
    else:
        singer_names_list.append({"name": singer_name, "count": count})
        response_text = USER_MESSAGES["add_singer_added_new"].format(singer_name=singer_name, count=count)
    
    await update.message.reply_text(response_text) 
    user_manager.update_user_specific_data(user_id, {"singer_names": singer_names_list})
    
    return await edit_list_menu_prompt_handler(update, context)


# --- Delete Singer Handlers ---
async def delete_singer_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_manager: UserManager = context.bot_data['user_manager']
    user_id = str(update.effective_user.id)
    user_data = user_manager.get_user(user_id)
    if not user_data or not user_data.get("singer_names"):
        await update.message.reply_text(USER_MESSAGES["delete_singer_empty_list"], reply_markup=edit_list_keyboard())
        return EDIT_LIST_MENU

    await show_user_singers_list(update, context)
    await update.message.reply_text(USER_MESSAGES["delete_singer_prompt"], reply_markup=delete_singer_keyboard())
    return DELETE_SINGER

async def remove_singer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_manager: UserManager = context.bot_data['user_manager']
    user_id = str(update.effective_user.id)
    singer_name_to_delete = update.message.text.strip()

    user_data = user_manager.get_user(user_id)
    singer_names_list = user_data.get("singer_names", []) if user_data else []
    if not isinstance(singer_names_list, list): singer_names_list = []
    
    initial_len = len(singer_names_list)
    new_singer_list = [s for s in singer_names_list if not (isinstance(s, dict) and s.get("name","").lower() == singer_name_to_delete.lower())]

    response_text = ""
    if len(new_singer_list) < initial_len:
        user_manager.update_user_specific_data(user_id, {"singer_names": new_singer_list})
        response_text = USER_MESSAGES["delete_singer_deleted"].format(singer_name=singer_name_to_delete)
    else:
        response_text = USER_MESSAGES["delete_singer_not_found"].format(singer_name=singer_name_to_delete)
    
    await update.message.reply_text(response_text)
    return await edit_list_menu_prompt_handler(update, context)


# --- Remove Entire List Handlers ---
async def remove_list_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_manager: UserManager = context.bot_data['user_manager']
    user_id = str(update.effective_user.id)
    user_data = user_manager.get_user(user_id)

    if not user_data or not user_data.get("singer_names"):
        await update.message.reply_text(USER_MESSAGES["remove_all_singers_empty_list"], reply_markup=list_menu_keyboard())
        return LIST_MENU 

    await show_user_singers_list(update, context)
    await update.message.reply_text(USER_MESSAGES["remove_all_singers_confirm"],
                                     reply_markup=confirm_remove_list_keyboard(), parse_mode=constants.ParseMode.MARKDOWN)
    return REMOVE_LIST_CONFIRM

async def confirm_remove_list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_manager: UserManager = context.bot_data['user_manager']
    user_id = str(update.effective_user.id)
    
    user_manager.update_user_specific_data(user_id, {"singer_names": []})
    logger.info(f"User {user_id} cleared their entire singer list.")
    await update.message.reply_text(USER_MESSAGES["remove_all_singers_success"])
    return await list_menu_prompt_handler(update, context)

async def cancel_remove_list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(USER_MESSAGES["remove_all_singers_cancelled"])
    return await list_menu_prompt_handler(update, context)


async def back_to_main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(USER_MESSAGES["main_menu_return"], reply_markup=main_menu_keyboard())
    return MAIN_MENU


async def back_to_list_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await list_menu_prompt_handler(update, context)

async def back_to_edit_list_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await edit_list_menu_prompt_handler(update, context)


# --- Ignore Handlers ---
async def ignore_delete_in_add_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        USER_MESSAGES["ignore_action_prompt"].format(back_button_text=KEYBOARD_TEXTS["back"]),
        reply_markup=add_singer_keyboard()
    )
    return ADD_SINGER

async def ignore_add_in_delete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        USER_MESSAGES["ignore_action_prompt"].format(back_button_text=KEYBOARD_TEXTS["back"]),
        reply_markup=delete_singer_keyboard()
    )
    return DELETE_SINGER