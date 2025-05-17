from telegram.ext import ContextTypes
from telegram.error import TelegramError # برای مدیریت خطاهای احتمالی تلگرام
from music_bot.config import logger, MAX_TRACKS_IN_DB
from music_bot.services.music_fetcher import MusicFetcher
from music_bot.services.track_searcher import TrackSearcher
from music_bot.services.user_manager import UserManager
from music_bot.database.track_db import TrackDatabaseHandler
import asyncio
from datetime import datetime

DELAY_BETWEEN_DOWNLOAD_PROCESSING_S = 2
# تاخیر بین ارسال پیام به هر کاربر (بر حسب ثانیه)
# این مقدار را می‌توانید بر اساس تعداد کاربران و محدودیت‌های تلگرام تنظیم کنید.
# مقادیر معمول بین 0.1 (برای تعداد کم) تا 1 یا 2 ثانیه (برای تعداد بسیار زیاد)
DELAY_BETWEEN_USER_NOTIFICATIONS_S = 1.5 # 1500 میلی‌ثانیه

# شامل مقادیری است که نشان می‌دهد لینک دانلود نیاز به پردازش/پردازش مجدد دارد.
INVALID_DOWNLOAD_LINK_STATES = [None, "", "N/A", "FAILED_ON_JOB", "FAILED_TO_EXTRACT"] 
# ^^^ مطمئن شوید "FAILED_TO_EXTRACT" یا هر مقدار خاصی که استفاده می‌کنید، اینجا باشد ^^^



async def run_music_processing_job(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Job: Starting FULL music processing (previews AND download links)...")
    
    music_fetcher: MusicFetcher = context.bot_data.get('music_fetcher')
    track_db_handler: TrackDatabaseHandler = context.bot_data.get('track_db_handler')

    if not music_fetcher or not track_db_handler:
        logger.error("Job: MusicFetcher or TrackDatabaseHandler not found in bot_data. Aborting music processing job.")
        return

    # --- بخش ۱: واکشی و ذخیره اطلاعات اولیه آهنگ‌ها (پیش‌نمایش‌ها) ---
    logger.info("Job: Starting music preview fetching and saving part...")
    try:
        raw_tracks_from_page = await music_fetcher.fetch_new_music_previews()
        if not raw_tracks_from_page:
            logger.info("Job: MusicFetcher returned no new track previews.")
        else:
            logger.info(f"Job: Fetched {len(raw_tracks_from_page)} raw track previews. Filtering and saving...")
            existing_db_links = await track_db_handler.get_all_links_as_set()
            new_tracks_to_insert = []
            seen_on_this_scrape = set() 
            for track_data in raw_tracks_from_page:
                link = track_data.get('link')
                if not link or link in seen_on_this_scrape: 
                    continue
                seen_on_this_scrape.add(link)
                if link not in existing_db_links:
                    # اطمینان از اینکه download_link برای آهنگ‌های جدید None است
                    track_data['download_link'] = None 
                    new_tracks_to_insert.append(track_data)
            
            if new_tracks_to_insert:
                current_total_tracks = await track_db_handler.get_total_tracks()
                slots_available = MAX_TRACKS_IN_DB - current_total_tracks
                if slots_available > 0:
   
                    tracks_to_actually_insert = new_tracks_to_insert[:slots_available]
                    if tracks_to_actually_insert:
                        inserted_count = await track_db_handler.save_tracks(tracks_to_actually_insert)
                        logger.info(f"Job: Saved {inserted_count} new track previews to DB.")
                else:
                    logger.info(f"Job: DB at max capacity ({MAX_TRACKS_IN_DB}). No new previews saved.")
            else:
                logger.info("Job: No new unique track previews to save from this fetch.")
        logger.info("Job: Music preview fetching and saving part COMPLETED.")
    except Exception as e:
        logger.error(f"Job: EXCEPTION during preview fetching/saving: {e}", exc_info=True)
    
    # --- بخش ۲: واکشی و آپدیت لینک‌های دانلود برای آهنگ‌هایی که لینک معتبر ندارند ---
    logger.info("Job: Starting download link extraction/update part...")
    try:
        all_tracks_in_db = await track_db_handler.load_tracks() # مرتب شده بر اساس جدیدترین (created_at DESC)
        
        tracks_needing_download_link_update = [
            track for track in all_tracks_in_db 
            if track.get('download_link') in INVALID_DOWNLOAD_LINK_STATES # <--- شرط اصلی
        ]
        

        tracks_to_process_this_run = tracks_needing_download_link_update # پردازش همه موارد یافت شده

        if not tracks_to_process_this_run:
            logger.info("Job: No tracks found needing a download link update in this run.")
        else:
            logger.info(f"Job: Found {len(tracks_to_process_this_run)} tracks to process/re-process for download links.")
            successful_link_updates_this_run = 0
            
            for track_info_from_db in tracks_to_process_this_run:
                track_page_link = track_info_from_db.get('link')
                track_id_for_log = track_info_from_db.get('id', 'UnknownID')
                current_dl_status = track_info_from_db.get('download_link', 'None')

                if not track_page_link:
                    logger.warning(f"Job: Skipping track ID {track_id_for_log} due to missing page link.")
                    continue

                logger.info(f"Job: Processing track ID {track_id_for_log}, Link: {track_page_link} (Current DL Status: '{current_dl_status}')")
                
                extracted_dl_link = await music_fetcher.get_single_track_download_link(track_page_link)
                
                # بررسی اینکه آیا لینک استخراج شده معتبر است یا خیر
                # یک لینک معتبر نباید در INVALID_DOWNLOAD_LINK_STATES باشد و باید یک رشته غیرتهی باشد
                is_extracted_link_valid = extracted_dl_link and isinstance(extracted_dl_link, str) and extracted_dl_link not in INVALID_DOWNLOAD_LINK_STATES

                if is_extracted_link_valid:
                    updated_in_db = await track_db_handler.update_track_download_link(track_page_link, extracted_dl_link)
                    if updated_in_db:
                        successful_link_updates_this_run += 1
                        logger.info(f"Job: Successfully extracted and updated DB for track ID {track_id_for_log} with new download link: {extracted_dl_link[:50]}...") # نمایش بخشی از لینک
                    else:
                        logger.warning(f"Job: Extracted download link for track ID {track_id_for_log} but FAILED to update DB (link: {track_page_link}). This might be a DB issue.")
                else:
                    # اگر استخراج ناموفق بود یا لینک استخراج شده نامعتبر بود،
                    # دوباره وضعیت را به "FAILED_ON_JOB" آپدیت می‌کنیم تا در اجرای بعدی جاب دوباره تلاش شود.
                    # این کار باعث می‌شود created_at رکورد تغییر نکند (مگر اینکه بخواهید زمان آخرین تلاش را ذخیره کنید).
                    logger.warning(f"Job: Failed to extract a valid download link for track ID {track_id_for_log} (Extracted: '{extracted_dl_link}'). Marking as FAILED_ON_JOB.")
                    await track_db_handler.update_track_download_link(track_page_link, "FAILED_ON_JOB") 
                
                await asyncio.sleep(DELAY_BETWEEN_DOWNLOAD_PROCESSING_S) 
            
            logger.info(f"Job: Download link extraction/update phase finished. Successfully updated {successful_link_updates_this_run} links in this run.")

    except Exception as e:
        logger.error(f"Job: EXCEPTION during download link extraction/update phase: {e}", exc_info=True)
    
    logger.info("Job: FULL music processing job COMPLETED.")


async def run_user_notification_job(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Job: Starting user notification process (daily automatic)...")
    user_manager: UserManager = context.bot_data.get('user_manager')
    track_searcher: TrackSearcher = context.bot_data.get('track_searcher')

    if not user_manager or not track_searcher:
        logger.error("Job: UserManager or TrackSearcher not found. Aborting notification job.")
        return

    all_users_data = user_manager.get_all_users()
    notification_queue: list[tuple[int, str, list[str]]] = []
    user_newly_sent_links_map: dict[str, set[str]] = {}

    logger.debug(f"Job: Checking {len(all_users_data)} users for notifications.")
    for user_id_str, user_data in all_users_data.items():
        try:
            user_id_int = int(user_id_str)
        except ValueError:
            logger.warning(f"Job: Invalid user_id_str: {user_id_str}. Skipping.")
            continue
            
        preferred_singers = user_data.get("singer_names", [])
        if not preferred_singers:
            continue # اگر لیست خواننده ندارد، برایش جستجو نکن

        try:
            found_tracks = await track_searcher.search_tracks_by_singer_list(preferred_singers)
            
            current_sent_music_for_user = set(user_data.get("sent_music", []))
            tracks_to_send_to_this_user_in_batch = []


            for track in found_tracks:
                download_link = track.get("download_link")
                if download_link and \
                   download_link not in ["N/A", "FAILED_ON_JOB", None, ""] and \
                   download_link not in current_sent_music_for_user: # and \
                   # download_link not in processed_links_for_this_user_in_batch: # اگر track_searcher یونیک برمی‌گرداند، این لازم نیست
                    
                    # برای جلوگیری از ارسال چندباره یک لینک به یک کاربر اگر track_searcher یونیک نکرده باشد
                    # (این با user_newly_sent_links_map کنترل می‌شود که برای کل جاب است)
                    already_queued_for_this_user_this_run = False
                    if user_id_str in user_newly_sent_links_map:
                        if download_link in user_newly_sent_links_map[user_id_str]:
                            already_queued_for_this_user_this_run = True
                    
                    if not already_queued_for_this_user_this_run:
                        tracks_to_send_to_this_user_in_batch.append(track)
                        if user_id_str not in user_newly_sent_links_map:
                            user_newly_sent_links_map[user_id_str] = set()
                        user_newly_sent_links_map[user_id_str].add(download_link)

            # **نکته کلیدی: فقط اگر آهنگی برای ارسال وجود دارد، پیام‌ها را به صف اضافه کن**
            if tracks_to_send_to_this_user_in_batch:
                logger.info(f"Job: User {user_id_int} has {len(tracks_to_send_to_this_user_in_batch)} new track(s) for daily notification.")
                for track_to_send in tracks_to_send_to_this_user_in_batch:
                    singer_display_name = track_to_send.get('en_name') or track_to_send.get('fa_name', 'خواننده نامشخص')
                    track_display_name = track_to_send.get('en_track') or track_to_send.get('fa_track', 'آهنگ نامشخص')
                    
                    message_text = (
                        f"🎵 آهنگ جدید از: {singer_display_name}\n"
                        f"🎶 نام آهنگ: {track_display_name}\n"
                        f"🔗 لینک دانلود: {track_to_send['download_link']}"
                    )
                    notification_queue.append(
                        (user_id_int, message_text, [track_to_send['download_link']])
                    )
            # **اگر آهنگی برای ارسال نبود (tracks_to_send_to_this_user_in_batch خالی بود)، هیچ کاری انجام نمی‌شود و پیامی به کاربر ارسال نخواهد شد.**

        except Exception as e:
            logger.error(f"Job: Error processing user {user_id_int} for daily notifications: {e}", exc_info=True)

    # --- پردازش صف نوتیفیکیشن‌ها با تاخیر ---
    # (این بخش مانند قبل باقی می‌ماند: ارسال پیام‌ها از notification_queue با تاخیر و آپدیت sent_music)
    if not notification_queue:
        logger.info("Job: Daily notification queue is empty. No messages to send.")
    else:
        logger.info(f"Job: Starting to send {len(notification_queue)} daily notification messages from the queue.")
        # ... (منطق حلقه ارسال، مدیریت خطا، و آپدیت sent_music مانند پاسخ قبلی) ...
        successfully_sent_count = 0
        all_successful_sends_this_run_map: dict[str, set[str]] = {}

        for user_id_int, message_text, track_links_in_this_message in notification_queue:
            user_id_str_for_map = str(user_id_int)
            send_attempt_successful = False 
            try:
                await context.bot.send_message(chat_id=user_id_int, text=message_text)
                logger.debug(f"Job: Successfully sent daily notification to user {user_id_int}.")
                successfully_sent_count += 1
                send_attempt_successful = True

                if user_id_str_for_map not in all_successful_sends_this_run_map:
                    all_successful_sends_this_run_map[user_id_str_for_map] = set()
                for link in track_links_in_this_message:
                     all_successful_sends_this_run_map[user_id_str_for_map].add(link)
            except TelegramError as te:
                logger.warning(f"Job: TelegramError sending daily notification to user {user_id_int}: {te}")
                error_message_lower = str(te).lower()
                if "bot was blocked by the user" in error_message_lower or \
                   "user is deactivated" in error_message_lower or \
                   "chat not found" in error_message_lower:
                    logger.info(f"Job: User {user_id_int} is unreachable for daily notification ({te}). Skipping.")
            except Exception as e:
                logger.error(f"Job: General error sending daily notification to user {user_id_int}: {e}", exc_info=True)
            
            await asyncio.sleep(DELAY_BETWEEN_USER_NOTIFICATIONS_S) # تاخیر بین کاربران
        
        logger.info(f"Job: Finished sending daily notifications. Successfully sent {successfully_sent_count}/{len(notification_queue)} messages.")

        if all_successful_sends_this_run_map:
            logger.info("Job: Updating sent_music for users after daily notifications...")
            for user_id_str_processed, newly_sent_links_set in all_successful_sends_this_run_map.items():
                if not newly_sent_links_set: continue
                user_data_to_update = user_manager.get_user(user_id_str_processed)
                if user_data_to_update:
                    existing_sent_music_list = user_data_to_update.get("sent_music", [])
                    if not isinstance(existing_sent_music_list, list):
                        final_sent_music_list = list(newly_sent_links_set)
                    else:
                        final_sent_music_list = list(set(existing_sent_music_list).union(newly_sent_links_set))
                    user_manager.update_user_specific_data(user_id_str_processed, {"sent_music": final_sent_music_list})
            logger.info("Job: Finished updating sent_music after daily notifications.")
            
    logger.info("Job: Daily user notification process finished.")