from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, constants
from telegram.ext import ContextTypes, ConversationHandler, Application, CallbackQueryHandler
from telegram.error import TelegramError
import asyncio
from thefuzz import process as fuzzy_process

from music_bot.config import (logger, MAIN_MENU, LIST_MENU, EDIT_LIST_MENU, ADD_SINGER, CONFIRM_SINGER_SUGGESTION,
                               DELETE_SINGER, REMOVE_LIST_CONFIRM, KEYBOARD_TEXTS, USER_MESSAGES, 
                               FUZZY_MATCH_THRESHOLD, MAX_FUZZY_SUGGESTIONS)
from music_bot.services.user_manager import UserManager
from music_bot.services.track_searcher import TrackSearcher
from music_bot.database.track_db import TrackDatabaseHandler # برای type hinting و فال‌بک
from music_bot.utils.keyboards import (main_menu_keyboard, list_menu_keyboard, edit_list_keyboard,
                                        confirm_remove_list_keyboard, add_singer_keyboard,
                                        delete_singer_keyboard)
from music_bot.handlers.helper_handlers import show_user_singers_list

# --- ثابت‌های تاخیر ---
DELAY_BETWEEN_INDIVIDUAL_MANUAL_MESSAGES_S = 0.3
DELAY_AFTER_PROCESSING_EACH_USER_MANUALLY_S = 1.0

# --- تابع کارگر برای صف دستی (manual_request_worker) ---
async def manual_request_worker(application: Application):
    queue: asyncio.Queue = application.bot_data.get('manual_request_queue')
    if not queue: logger.critical("Worker: Manual request queue not found."); return
    logger.info("Worker: Started.")
    while True:
        try:
            request_data = await queue.get()
            if request_data is None: logger.info("Worker: Stop signal received."); queue.task_done(); break
            user_id, chat_id = request_data.get('user_id'), request_data.get('chat_id')
            if not (user_id and chat_id): logger.error(f"Worker: Invalid data: {request_data}"); queue.task_done(); continue
            
            user_id_str = str(user_id)
            logger.info(f"Worker: Processing for user {user_id_str}")
            
            user_manager: UserManager = application.bot_data.get('user_manager')
            track_searcher: TrackSearcher = application.bot_data.get('track_searcher')
            bot = application.bot
            if not all([user_manager, track_searcher, bot]):
                logger.error(f"Worker: Critical services missing for user {user_id_str}.")
                try: await bot.send_message(chat_id=chat_id, text=USER_MESSAGES["error_services_unavailable"])
                except Exception: pass
                queue.task_done(); continue
            
            user_data = user_manager.get_user(user_id_str)
            if not user_data:
                logger.warning(f"Worker: User data not found for user {user_id_str}.")
                try: await bot.send_message(chat_id=chat_id, text=USER_MESSAGES["error_user_data_not_found"])
                except Exception: pass
                queue.task_done(); continue

            preferred_singers = user_data.get("singer_names", [])
            if not preferred_singers:
                logger.info(f"Worker: No preferred singers for user {user_id_str}.")
                try: await bot.send_message(chat_id=chat_id, text=USER_MESSAGES["no_singers_in_list_general"])
                except Exception: pass
                queue.task_done(); continue
            
            try:
                found_tracks = await track_searcher.search_tracks_by_singer_list(preferred_singers)
                current_sent_music = set(user_data.get("sent_music", []))
                new_tracks_to_send = []
                processed_links_in_this_fetch_for_user = set()

                for track in found_tracks:
                    download_link = track.get("download_link")
                    if download_link and \
                       download_link not in ["N/A", "FAILED_ON_JOB", None, ""] and \
                       download_link not in current_sent_music and \
                       download_link not in processed_links_in_this_fetch_for_user:
                        new_tracks_to_send.append(track)
                        processed_links_in_this_fetch_for_user.add(download_link)
                
                if not new_tracks_to_send:
                    logger.info(f"Worker: No new tracks found for user {user_id_str} to send.")
                    try: await bot.send_message(chat_id=chat_id, text=USER_MESSAGES["manual_fetch_no_new_songs"])
                    except Exception: pass
                    queue.task_done(); continue
                    
                successfully_sent_links = set()
                num_total = len(new_tracks_to_send)
                num_sent_successfully = 0
                last_telegram_error_in_loop = None

                try:
                    await bot.send_message(chat_id=chat_id, text=USER_MESSAGES["manual_fetch_found_sending"].format(num_found=num_total))
                except TelegramError as e_init_send:
                    logger.warning(f"Worker: Could not send 'found tracks' message to user {user_id_str}: {e_init_send}")
                    if "bot was blocked by the user" in str(e_init_send).lower():
                        queue.task_done(); continue 

                for i, track in enumerate(new_tracks_to_send):
                    singer_name = track.get('fa_name') or track.get('en_name', 'خواننده نامشخص')
                    track_title = track.get('fa_track') or track.get('en_track', 'آهنگ نامشخص')
                    dl_link = track.get('download_link', '')
                    message_text = (
                        f"({i+1}/{num_total}) 🎵 آهنگ جدید از: {singer_name}\n"
                        f"🎶 نام آهنگ: {track_title}\n"
                        f"🔗 لینک دانلود: {dl_link}"
                    )
                    try:
                        await bot.send_message(chat_id=chat_id, text=message_text)
                        successfully_sent_links.add(dl_link)
                        num_sent_successfully +=1
                        if i < num_total - 1: await asyncio.sleep(DELAY_BETWEEN_INDIVIDUAL_MANUAL_MESSAGES_S)
                    except TelegramError as te_send:
                        last_telegram_error_in_loop = te_send
                        logger.warning(f"Worker: TelegramError sending message #{i+1} to user {user_id_str}: {te_send}")
                        if "bot was blocked by the user" in str(te_send).lower(): 
                            try: await bot.send_message(chat_id=chat_id, text=USER_MESSAGES["manual_fetch_blocked"])
                            except: pass
                            break
                    except Exception as e_send_loop: 
                        logger.error(f"Worker: Error sending track {i+1} to {user_id_str}: {e_send_loop}", exc_info=True)

                if successfully_sent_links:
                    final_sent_list = list(current_sent_music.union(successfully_sent_links))
                    user_manager.update_user_specific_data(user_id_str, {"sent_music": final_sent_list})
                
                final_msg_text = ""
                if num_sent_successfully == num_total and num_total > 0: 
                    final_msg_text = USER_MESSAGES["manual_fetch_all_sent_successfully"].format(num_sent=num_sent_successfully)
                elif num_sent_successfully > 0: 
                    final_msg_text = USER_MESSAGES["manual_fetch_some_sent"].format(num_sent=num_sent_successfully, num_total=num_total)
                elif num_total > 0 and num_sent_successfully == 0:
                    if not (last_telegram_error_in_loop and "bot was blocked by the user" in str(last_telegram_error_in_loop).lower()):
                        final_msg_text = USER_MESSAGES["manual_fetch_none_sent_error"]
                if final_msg_text: 
                    try: await bot.send_message(chat_id=chat_id, text=final_msg_text)
                    except Exception: pass
            except Exception as e_process_user:
                logger.error(f"Worker: Error processing tracks for user {user_id_str}: {e_process_user}", exc_info=True)
                try: await bot.send_message(chat_id=chat_id, text=USER_MESSAGES["error_generic"])
                except Exception: pass
            
            queue.task_done()
            logger.info(f"Worker: Finished for user {user_id_str}. Delaying {DELAY_AFTER_PROCESSING_EACH_USER_MANUALLY_S}s...")
            await asyncio.sleep(DELAY_AFTER_PROCESSING_EACH_USER_MANUALLY_S)
        except asyncio.CancelledError: 
            logger.info("Worker: Cancelled.")
            break
        except Exception as e_outer_loop: 
            logger.critical(f"Worker: Outer loop error: {e_outer_loop}", exc_info=True)
            await asyncio.sleep(5)


# --- هندلر دکمه "دریافت آهنگ‌های جدید" ---
async def receive_music_now_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    queue: asyncio.Queue = context.bot_data.get('manual_request_queue')
    if not queue:
        logger.error(f"Manual request queue not found for user {user.id}.")
        await update.message.reply_text(USER_MESSAGES["error_services_unavailable"], reply_markup=main_menu_keyboard())
        return MAIN_MENU
    logger.info(f"User {user.id} pressed '{KEYBOARD_TEXTS['receive_music_now']}'. Adding to queue.")
    try:
        await queue.put({'user_id': user.id, 'chat_id': update.effective_chat.id})
        await update.message.reply_text(USER_MESSAGES["manual_fetch_queued"], reply_markup=main_menu_keyboard())
    except Exception as e:
        logger.error(f"Error adding request to manual queue for user {user.id}: {e}")
        await update.message.reply_text(USER_MESSAGES["error_generic"], reply_markup=main_menu_keyboard())
    return MAIN_MENU

# --- List Menu Handlers ---
async def list_menu_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await show_user_singers_list(update, context) 
    await update.message.reply_text(USER_MESSAGES["list_menu_prompt"], reply_markup=list_menu_keyboard())
    return LIST_MENU

async def list_menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == KEYBOARD_TEXTS["edit_list"]: return await edit_list_menu_prompt_handler(update, context)
    elif text == KEYBOARD_TEXTS["remove_list"]: return await remove_list_prompt_handler(update, context)
    elif text == KEYBOARD_TEXTS["back"]: return await back_to_main_menu_handler(update, context)
    else: await update.message.reply_text("🚫 گزینه نامعتبر.", reply_markup=list_menu_keyboard()); return LIST_MENU

# --- Edit List Menu Handlers ---
async def edit_list_menu_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(USER_MESSAGES["edit_list_menu_prompt"], reply_markup=edit_list_keyboard())
    return EDIT_LIST_MENU

async def edit_list_menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == KEYBOARD_TEXTS["add"]: return await add_singer_prompt_handler(update, context)
    elif text == KEYBOARD_TEXTS["delete"]: return await delete_singer_prompt_handler(update, context)
    elif text == KEYBOARD_TEXTS["back"]: return await back_to_list_menu_handler(update, context)
    else: await update.message.reply_text("🚫 گزینه نامعتبر.", reply_markup=edit_list_keyboard()); return EDIT_LIST_MENU

# --- Add Singer Handlers ---
async def add_singer_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await show_user_singers_list(update, context) 
    await update.message.reply_text(USER_MESSAGES["add_singer_prompt"], reply_markup=add_singer_keyboard())
    return ADD_SINGER

async def save_singer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_manager: UserManager = context.bot_data.get('user_manager')
    track_db_handler: TrackDatabaseHandler = context.bot_data.get('track_db_handler') # برای فال‌بک لیست خوانندگان
    user_id = str(update.effective_user.id)
    input_text = update.message.text.strip()

    if not input_text:
        await update.message.reply_text(USER_MESSAGES["add_singer_invalid_input"], reply_markup=add_singer_keyboard())
        return ADD_SINGER 
    parts = input_text.split("\n")
    singer_name_input = parts[0].strip()
    if not singer_name_input:
        await update.message.reply_text(USER_MESSAGES["add_singer_name_empty"], reply_markup=add_singer_keyboard())
        return ADD_SINGER
    count = 1
    if len(parts) > 1 and parts[1].strip().isdigit():
        count_val = int(parts[1].strip())
        if count_val <= 0: count = 1
        else: count = count_val
    
    all_singers_list: list[str] = context.bot_data.get('all_singer_names_list', [])
    if not all_singers_list: 
        logger.warning("save_singer_handler: all_singer_names_list not in bot_data or is empty. Fetching now.")
        if track_db_handler:
            all_singers_list = list(await track_db_handler.get_all_unique_singer_names())
            if all_singers_list:
                 context.bot_data['all_singer_names_list'] = all_singers_list
                 logger.info(f"save_singer_handler: Re-cached {len(all_singers_list)} singer names.")
            else: logger.warning("save_singer_handler: Fetched singer list is still empty.")
        else:
            logger.error("save_singer_handler: TrackDatabaseHandler not found to fetch singer names.")
            await update.message.reply_text(USER_MESSAGES["error_services_unavailable"])
            return await edit_list_menu_prompt_handler(update, context)
    
    if not all_singers_list: # اگر پس از همه تلاش‌ها، لیست خوانندگان مرجع خالی است
        logger.error("save_singer_handler: Singer list is definitively empty. Adding user input directly without suggestions.")
        user_data = user_manager.get_user(user_id)
        s_list = user_data.get("singer_names", []) if user_data else []
        if not isinstance(s_list, list): s_list = []
        e_singer = next((s for s in s_list if isinstance(s,dict) and s.get("name","").lower() == singer_name_input.lower()), None)
        response_text = ""
        if e_singer: 
            e_singer["count"]=count
            response_text = USER_MESSAGES["add_singer_updated_count"].format(singer_name=singer_name_input,count=count)
        else: 
            s_list.append({"name":singer_name_input,"count":count})
            response_text = USER_MESSAGES["add_singer_added_new"].format(singer_name=singer_name_input,count=count)
        await update.message.reply_text(response_text)
        user_manager.update_user_specific_data(user_id, {"singer_names": s_list})
        return await edit_list_menu_prompt_handler(update, context)

    exact_match = next((s_name for s_name in all_singers_list if s_name.lower() == singer_name_input.lower()), None)
    if exact_match:
        logger.info(f"save_singer_handler: Exact match for '{singer_name_input}' -> '{exact_match}'")
        user_data = user_manager.get_user(user_id)
        s_list = user_data.get("singer_names", []) if user_data else []
        if not isinstance(s_list, list): s_list = []
        e_singer = next((s for s in s_list if isinstance(s,dict) and s.get("name","").lower() == exact_match.lower()), None)
        response_text = ""
        if e_singer: 
            e_singer["count"]=count
            response_text = USER_MESSAGES["add_singer_updated_count"].format(singer_name=exact_match,count=count)
        else: 
            s_list.append({"name":exact_match,"count":count})
            response_text = USER_MESSAGES["add_singer_added_new"].format(singer_name=exact_match,count=count)
        await update.message.reply_text(response_text)
        user_manager.update_user_specific_data(user_id, {"singer_names": s_list})
        return await edit_list_menu_prompt_handler(update, context)

    best_matches_with_scores = fuzzy_process.extractBests(
        singer_name_input, all_singers_list, score_cutoff=FUZZY_MATCH_THRESHOLD, limit=MAX_FUZZY_SUGGESTIONS
    )
    suggestions = [(name, score) for name, score in best_matches_with_scores if name and name.strip()]

    if suggestions:
        logger.info(f"save_singer_handler: Fuzzy matches for '{singer_name_input}': {suggestions}")
        context.user_data['singer_suggestions_list'] = {
            'original_input': singer_name_input,
            'suggestions': suggestions,
            'requested_count': count
        }
        keyboard_buttons = []
        for i, (suggested_name, score) in enumerate(suggestions):
            button_text = f"✅ {suggested_name}"
            keyboard_buttons.append([InlineKeyboardButton(button_text, callback_data=f"suggest_idx_{i}")])
        
        keyboard_buttons.append([InlineKeyboardButton(USER_MESSAGES["singer_suggestion_none_of_above"], callback_data="suggest_none")])
        reply_markup = InlineKeyboardMarkup(keyboard_buttons)
        prompt_text = USER_MESSAGES["singer_multiple_suggestions_prompt"].format(
            none_button_text=USER_MESSAGES["singer_suggestion_none_of_above"], # برای نمایش در متن اگر لازم بود
            user_input_count=count
        )
        suggestion_msg = await update.message.reply_text(prompt_text, reply_markup=reply_markup)
        context.user_data['suggestion_message_id'] = suggestion_msg.message_id
        return CONFIRM_SINGER_SUGGESTION
    else:
        logger.info(f"save_singer_handler: No good match found for '{singer_name_input}'.")
        await update.message.reply_text(USER_MESSAGES["singer_suggestion_not_found"], reply_markup=add_singer_keyboard())
        return ADD_SINGER

# --- هندلرهای CallbackQuery برای پیشنهاد خواننده ---
async def singer_suggestion_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer() 
    user_id = str(query.from_user.id)
    chat_id = query.message.chat_id
    suggestion_message_id = context.user_data.get('suggestion_message_id', query.message.message_id)
    suggestions_info = context.user_data.get('singer_suggestions_list') # دیگر pop نمی‌کنیم تا در صورت نیاز دوباره استفاده شود

    if not suggestions_info:
        logger.warning(f"Callback: No singer_suggestions_list data found for user {user_id}.")
        if suggestion_message_id:
            try: await context.bot.edit_message_text(chat_id=chat_id, message_id=suggestion_message_id, text=USER_MESSAGES["singer_suggestion_callback_error"])
            except Exception: pass
        # بازگشت به منوی ویرایش که پیام خودش را دارد
        await context.bot.send_message(chat_id=chat_id, text=USER_MESSAGES["edit_list_menu_prompt"], reply_markup=edit_list_keyboard())
        return EDIT_LIST_MENU

    original_input = suggestions_info['original_input']
    all_suggestions = suggestions_info['suggestions'] 
    requested_count = suggestions_info['requested_count']
    chosen_singer_name = None

    if query.data.startswith("suggest_idx_"):
        try:
            selected_idx = int(query.data.split("_")[-1])
            if 0 <= selected_idx < len(all_suggestions):
                chosen_singer_name = all_suggestions[selected_idx][0]
        except (ValueError, IndexError):
            logger.error(f"Callback: Invalid index from data '{query.data}'")
    elif query.data == "suggest_none":
        logger.info(f"Callback: User {user_id} chose 'none' for input '{original_input}'.")
        if suggestion_message_id:
            try: await context.bot.edit_message_text(chat_id=chat_id, message_id=suggestion_message_id, text=USER_MESSAGES["singer_suggestion_retry_prompt"])
            except Exception: pass
        context.user_data.pop('singer_suggestions_list', None)
        context.user_data.pop('suggestion_message_id', None)
        await context.bot.send_message(chat_id=chat_id, text=USER_MESSAGES["add_singer_prompt"], reply_markup=add_singer_keyboard())
        return ADD_SINGER

    if chosen_singer_name:
        logger.info(f"Callback: User {user_id} selected '{chosen_singer_name}'.")
        if suggestion_message_id:
            try: await context.bot.edit_message_text(chat_id=chat_id, message_id=suggestion_message_id, text=USER_MESSAGES["singer_suggestion_confirm_chosen"].format(suggested_name=chosen_singer_name))
            except Exception: pass
        
        user_manager: UserManager = context.bot_data['user_manager']
        user_data = user_manager.get_user(user_id)
        s_list = user_data.get("singer_names", []) if user_data else []
        if not isinstance(s_list, list): s_list = []
        e_singer = next((s for s in s_list if isinstance(s,dict) and s.get("name","").lower() == chosen_singer_name.lower()), None)
        response_text = ""
        if e_singer: 
            e_singer["count"]=requested_count
            response_text = USER_MESSAGES["add_singer_updated_count"].format(singer_name=chosen_singer_name,count=requested_count)
        else: 
            s_list.append({"name":chosen_singer_name,"count":requested_count})
            response_text = USER_MESSAGES["add_singer_added_new"].format(singer_name=chosen_singer_name,count=requested_count)
        await context.bot.send_message(chat_id=chat_id, text=response_text)
        user_manager.update_user_specific_data(user_id, {"singer_names": s_list})
        
        context.user_data.pop('singer_suggestions_list', None)
        context.user_data.pop('suggestion_message_id', None)
        await context.bot.send_message(chat_id=chat_id, text=USER_MESSAGES["edit_list_menu_prompt"], reply_markup=edit_list_keyboard())
        return EDIT_LIST_MENU
    else: # callback_data ناشناخته یا ایندکس نامعتبر
        logger.warning(f"Callback: Could not determine choice from data '{query.data}'.")
        if suggestion_message_id:
             try: await context.bot.edit_message_text(chat_id=chat_id, message_id=suggestion_message_id, text=USER_MESSAGES["singer_suggestion_callback_error"])
             except Exception: pass
        context.user_data.pop('singer_suggestions_list', None)
        context.user_data.pop('suggestion_message_id', None)
        await context.bot.send_message(chat_id=chat_id, text=USER_MESSAGES["edit_list_menu_prompt"], reply_markup=edit_list_keyboard())
        return EDIT_LIST_MENU

async def fallback_text_in_suggestion_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(USER_MESSAGES["fallback_in_suggestion_state"])
    # برای نمایش مجدد دکمه‌های شیشه‌ای، باید پیام قبلی را داشت یا دوباره ارسال کرد.
    # ساده‌تر: کاربر را راهنمایی می‌کنیم که از دکمه‌ها استفاده کند.
    # اگر پیام پیشنهاد حذف شده باشد، این حالت پیچیده می‌شود.
    # فعلا فقط پیام می‌دهیم و در همین وضعیت می‌مانیم.
    return CONFIRM_SINGER_SUGGESTION

async def back_to_add_singer_from_suggestion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.debug(f"User {update.effective_user.id} pressed back from suggestion state.")
    suggestion_message_id = context.user_data.pop('suggestion_message_id', None)
    chat_id = update.effective_chat.id
    if suggestion_message_id:
        try: await context.bot.delete_message(chat_id=chat_id, message_id=suggestion_message_id)
        except Exception: pass
    context.user_data.pop('singer_suggestions_list', None)
    
    # بازگشت به صفحه افزودن خواننده (که لیست و پیام راهنما را نمایش می‌دهد)
    # add_singer_prompt_handler پیام خودش را ارسال می‌کند
    await show_user_singers_list(update, context) # نمایش لیست خوانندگان فعلی
    await update.message.reply_text(USER_MESSAGES["add_singer_prompt"], reply_markup=add_singer_keyboard())
    return ADD_SINGER


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
    s_list = user_data.get("singer_names", []) if user_data else []
    if not isinstance(s_list, list): s_list = []
    initial_len = len(s_list)
    new_s_list = [s for s in s_list if not (isinstance(s,dict) and s.get("name","").lower() == singer_name_to_delete.lower())]
    response_text = ""
    if len(new_s_list) < initial_len:
        user_manager.update_user_specific_data(user_id, {"singer_names": new_s_list})
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

# --- Navigation Handlers ---
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
        reply_markup=add_singer_keyboard() )
    return ADD_SINGER

async def ignore_add_in_delete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        USER_MESSAGES["ignore_action_prompt"].format(back_button_text=KEYBOARD_TEXTS["back"]),
        reply_markup=delete_singer_keyboard() )
    return DELETE_SINGER