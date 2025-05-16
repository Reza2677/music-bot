from telegram.ext import ContextTypes
from ..config import logger, MAX_TRACKS_IN_DB
from ..services import MusicFetcher, TrackSearcher, UserManager
from ..database import TrackDatabaseHandler # برای ذخیره ترک‌ها
import asyncio 

# تاخیر بین تلاش برای دانلود هر لینک (برای جلوگیری از فشار زیاد به سایت)
DELAY_BETWEEN_DOWNLOAD_PROCESSING_S = 2 # 2 ثانیه

async def run_music_processing_job(context: ContextTypes.DEFAULT_TYPE): # تغییر نام جاب برای وضوح
    logger.info("Job: Starting FULL music processing (previews AND download links)...")
    
    music_fetcher: MusicFetcher = context.bot_data.get('music_fetcher')
    track_db_handler: TrackDatabaseHandler = context.bot_data.get('track_db_handler')

    if not music_fetcher or not track_db_handler:
        logger.error("Job: MusicFetcher or TrackDatabaseHandler not found. Aborting.")
        return

    # --- بخش ۱: واکشی و ذخیره اطلاعات اولیه آهنگ‌ها (مانند قبل) ---
    try:
        raw_tracks_from_page = await music_fetcher.fetch_new_music_previews()
        if not raw_tracks_from_page:
            logger.info("Job: MusicFetcher returned no new track previews.")
            # حتی اگر preview جدیدی نباشد، باز هم برای لینک‌های دانلود تلاش می‌کنیم
        else:
            logger.info(f"Job: Fetched {len(raw_tracks_from_page)} raw track previews. Filtering and saving...")
            existing_db_links = await track_db_handler.get_all_links_as_set()
            new_tracks_to_insert = []
            seen_on_this_scrape = set()
            for track_data in raw_tracks_from_page:
                link = track_data.get('link')
                if not link or link in seen_on_this_scrape: continue
                seen_on_this_scrape.add(link)
                if link not in existing_db_links:
                    track_data['download_link'] = None
                    new_tracks_to_insert.append(track_data)
            
            if new_tracks_to_insert:
                current_total_tracks = await track_db_handler.get_total_tracks()
                slots_available = MAX_TRACKS_IN_DB - current_total_tracks
                if slots_available > 0:
                    new_tracks_to_insert.reverse()
                    tracks_to_actually_insert = new_tracks_to_insert[:slots_available]
                    if tracks_to_actually_insert:
                        inserted_count = await track_db_handler.save_tracks(tracks_to_actually_insert)
                        logger.info(f"Job: Saved {inserted_count} new track previews to DB.")
                else:
                    logger.info("Job: DB at max capacity for new previews.")
            else:
                logger.info("Job: No new unique track previews to save.")
    except Exception as e:
        logger.error(f"Job: Error during preview fetching/saving: {e}", exc_info=True)
    # --- پایان بخش ۱ ---

    # --- بخش ۲: واکشی و آپدیت لینک‌های دانلود برای آهنگ‌هایی که لینک ندارند ---
    logger.info("Job: Starting download link extraction for tracks without one...")
    try:
        # ابتدا تمام آهنگ‌هایی که لینک دانلود ندارند را از دیتابیس می‌خوانیم
        # این نیاز به یک متد جدید در TrackDatabaseHandler دارد
        # یا می‌توانیم از load_tracks استفاده کنیم و فیلتر کنیم
        all_tracks_in_db = await track_db_handler.load_tracks() # مرتب شده بر اساس جدیدترین
        tracks_needing_download_link = [
            t for t in all_tracks_in_db 
            if t.get('download_link') is None or t.get('download_link') == '' or t.get('download_link') == "N/A"
        ]
        # می‌توانیم تعداد را محدود کنیم تا جاب خیلی طولانی نشود
        # MAX_DOWNLOAD_LINKS_PER_JOB = 20 # مثال، در config.py تعریف شود
        # tracks_to_process_download = tracks_needing_download_link[:MAX_DOWNLOAD_LINKS_PER_JOB]

        # برای این مثال، همه را پردازش می‌کنیم، اما در عمل شاید محدود کردن بهتر باشد
        tracks_to_process_download = tracks_needing_download_link
        
        if not tracks_to_process_download:
            logger.info("Job: No tracks found needing a download link.")
        else:
            logger.info(f"Job: Found {len(tracks_to_process_download)} tracks to process for download links.")
            successful_link_extractions = 0
            for track_info_from_db in tracks_to_process_download:
                track_page_link = track_info_from_db.get('link')
                track_id = track_info_from_db.get('id')

                if not track_page_link or not track_id:
                    logger.warning(f"Job: Skipping track with missing link or id: {track_info_from_db}")
                    continue

                logger.info(f"Job: Processing track ID {track_id}, Link: {track_page_link} for download link.")
                
                # فراخوانی متد جدید MusicFetcher
                extracted_dl_link = await music_fetcher.get_single_track_download_link(track_page_link)
                
                if extracted_dl_link:
                    # آپدیت دیتابیس
                    updated = await track_db_handler.update_track_download_link(track_page_link, extracted_dl_link)
                    if updated:
                        successful_link_extractions += 1
                        logger.info(f"Job: Successfully updated DB for track ID {track_id} with download link.")
                    else:
                        logger.warning(f"Job: Failed to update DB for track ID {track_id} even after link extraction.")
                else:
                    # اگر استخراج ناموفق بود، می‌توانیم یک مقدار خاص در دیتابیس ثبت کنیم
                    await track_db_handler.update_track_download_link(track_page_link, "FAILED_ON_JOB") 
                    logger.warning(f"Job: Failed to extract download link for track ID {track_id}.")
                
                # تاخیر بین پردازش هر آهنگ
                await asyncio.sleep(DELAY_BETWEEN_DOWNLOAD_PROCESSING_S) 
            
            logger.info(f"Job: Download link extraction phase finished. Successfully extracted and updated {successful_link_extractions} links.")

    except Exception as e:
        logger.error(f"Job: Error during download link extraction phase: {e}", exc_info=True)
    
    logger.info("Job: FULL music processing job finished.")

async def run_user_notification_job(context: ContextTypes.DEFAULT_TYPE):
    """
    Periodically checks for new music for users based on their preferences
    and sends notifications.
    """
    logger.info("Job: Starting user notification process...")
    user_manager: UserManager = context.bot_data['user_manager']
    track_searcher: TrackSearcher = context.bot_data['track_searcher']
    
    all_users_data = user_manager.get_all_users()

    for user_id_str, user_data in all_users_data.items():
        user_id = int(user_id_str)
        preferred_singers = user_data.get("singer_names", [])
        if not preferred_singers:
            # logger.debug(f"Job: User {user_id} has no preferred singers. Skipping.")
            continue

        # بررسی زمان ارسال برای کاربر
        # این بخش برای ارسال دقیق در زمان تعیین شده توسط کاربر است
        # فعلا این جاب هر یک دقیقه اجرا می‌شود و برای همه کاربران چک می‌کند
        # اگر بخواهیم دقیقا سر ساعت تعیین شده کاربر ارسال شود، باید منطق جاب‌ها تغییر کند
        # یا اینکه این جاب زمان فعلی را با sent_time کاربر مقایسه کند.
        # current_hour_str = f"{datetime.now().hour:02d}:00"
        # if user_data.get("sent_time") != current_hour_str:
        #     # logger.debug(f"Job: Not notification time for user {user_id}. Current: {current_hour_str}, User's: {user_data.get('sent_time')}")
        #     continue
        # logger.info(f"Job: Processing notifications for user {user_id} at their preferred time {user_data.get('sent_time')}.")


        try:
            # جستجوی آهنگ‌ها بر اساس لیست خوانندگان کاربر
            # search_tracks_by_singer_list باید آهنگ‌هایی را برگرداند که لینک دانلود معتبر دارند
            found_tracks = await track_searcher.search_tracks_by_singer_list(preferred_singers)
            
            if not found_tracks:
                # logger.info(f"Job: No new tracks found for user {user_id} based on their preferences.")
                continue

            sent_music_links_for_user = set(user_data.get("sent_music", []))
            new_tracks_to_send_to_user = []

            for track in found_tracks:
                download_link = track.get("download_link")
                # فقط آهنگ‌هایی که لینک دانلود معتبر دارند و قبلا ارسال نشده‌اند
                if download_link and download_link != "N/A" and download_link not in sent_music_links_for_user:
                    new_tracks_to_send_to_user.append(track)
                    sent_music_links_for_user.add(download_link) # به لیست ارسال شده‌ها اضافه کن

            if new_tracks_to_send_to_user:
                logger.info(f"Job: Sending {len(new_tracks_to_send_to_user)} new track(s) to user {user_id}.")
                for track_to_send in new_tracks_to_send_to_user:
                    # نام خواننده را سعی کن از en_name یا fa_name بگیری
                    singer_display_name = track_to_send.get('en_name') or track_to_send.get('fa_name', 'خواننده نامشخص')
                    track_display_name = track_to_send.get('en_track') or track_to_send.get('fa_track', 'آهنگ نامشخص')
                    
                    message_text = (
                        f"🎵 آهنگ جدید از: {singer_display_name}\n"
                        f"🎶 نام آهنگ: {track_display_name}\n"
                        f"🔗 لینک دانلود: {track_to_send['download_link']}"
                    )
                    try:
                        await context.bot.send_message(chat_id=user_id, text=message_text)
                    except Exception as e:
                        logger.error(f"Job: Failed to send message to user {user_id}: {e}")
                
                # آپدیت لیست آهنگ‌های ارسال شده برای کاربر در دیتابیس
                user_manager.update_user_specific_data(str(user_id), {"sent_music": list(sent_music_links_for_user)})
            # else:
                # logger.info(f"Job: No *new* tracks to send to user {user_id} after filtering sent ones.")

        except Exception as e:
            logger.error(f"Job: Error processing notifications for user {user_id}: {e}", exc_info=True)
            
    logger.info("Job: User notification process finished.")