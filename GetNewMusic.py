

import logging
import os
import sqlite3
import psutil
from playwright.async_api import async_playwright, TimeoutError
from async_generator import async_generator, yield_
from contextlib import contextmanager
import asyncio

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("optimized.log"), logging.StreamHandler()]
)

class DatabaseManager:
    def __init__(self, db_name='tracks.db'):
        self.db_name = db_name
        self.db_path = os.path.abspath(db_name)
        self._init_db()

    def _init_db(self):
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
        with self.db_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tracks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    link TEXT UNIQUE,
                    en_name TEXT,
                    en_track TEXT,
                    fa_name TEXT,
                    fa_track TEXT,
                    download_link TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    @contextmanager
    def db_connection(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            yield conn
            conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Database error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    # متد insert_track برای سازگاری یا استفاده‌های خاص می‌تواند باقی بماند
    # اما در جریان اصلی از insert_many_tracks استفاده خواهیم کرد.
    async def insert_track(self, track_data): # دیگر در جریان اصلی استفاده نمی‌شود
        with self.db_connection() as conn:
            try:
                conn.execute('''
                    INSERT INTO tracks (link, en_name, en_track, fa_name, fa_track, download_link)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    track_data['link'],
                    track_data['en_name'],
                    track_data['en_track'],
                    track_data['fa_name'],
                    track_data['fa_track'],
                    track_data.get('download_link', None)
                ))
                return True
            except sqlite3.IntegrityError: # link UNIQUE constraint
                return False

    # 1. متد جدید برای خواندن تمام لینک‌های موجود در دیتابیس یکجا
    async def get_all_links_as_set(self):
        links_set = set()
        with self.db_connection() as conn:
            cursor = conn.execute('SELECT link FROM tracks')
            for row in cursor.fetchall():
                links_set.add(row['link'])
        logging.info(f"Fetched {len(links_set)} existing links from DB into a set.")
        return links_set

    # متد link_exists برای سازگاری می‌تواند باقی بماند، اما در جریان اصلی استفاده نمی‌شود
    async def link_exists(self, link): # دیگر در جریان اصلی استفاده نمی‌شود
        with self.db_connection() as conn:
            cursor = conn.execute('SELECT 1 FROM tracks WHERE link = ? LIMIT 1', (link,))
            row = cursor.fetchone()
            return row is not None

    async def get_total_links(self): # این متد همچنان مفید است
        with self.db_connection() as conn:
            cursor = conn.execute('SELECT COUNT(*) as count FROM tracks')
            row = cursor.fetchone()
            return row['count'] if row else 0

    # 3. متد جدید برای درج دسته‌ای ترک‌ها
    async def insert_many_tracks(self, tracks_data_list):
        if not tracks_data_list:
            return 0
        
        # تبدیل لیست دیکشنری‌ها به لیست تاپل‌ها برای executemany
        data_to_insert = [
            (
                track['link'],
                track['en_name'],
                track['en_track'],
                track['fa_name'],
                track['fa_track'],
                track.get('download_link', None)
            ) for track in tracks_data_list
        ]
        
        with self.db_connection() as conn:
            try:
                # استفاده از INSERT OR IGNORE برای نادیده گرفتن لینک‌های تکراری بدون ایجاد خطا
                # اگرچه ما از قبل فیلتر می‌کنیم، این یک لایه اطمینان اضافی است.
                cursor = conn.cursor()
                cursor.executemany('''
                    INSERT OR IGNORE INTO tracks (link, en_name, en_track, fa_name, fa_track, download_link)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', data_to_insert)
                inserted_count = cursor.rowcount # تعداد ردیف‌هایی که واقعاً درج شدند
                logging.info(f"Attempted to insert {len(data_to_insert)} tracks. Successfully inserted {inserted_count} new unique tracks.")
                return inserted_count
            except sqlite3.Error as e:
                logging.error(f"Error during bulk insert: {e}")
                return 0 # یا raise e اگر می‌خواهید خطا بالاتر برود

class GetNewMusic:
    def __init__(self, max_links_to_store=50):
        self.logger = logging.getLogger(__name__)
        self.max_links_to_store = max_links_to_store
        self.db = DatabaseManager()
        self.playwright = None
        self.browser = None
        self.page = None
        self.see_more_button_selector = 'div.dataloaderError.datalist1ErrorBtn > button.btn.btn-primary.w-100'

    async def start(self):
        self.logger.info("Starting Playwright with optimized settings")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=['--disable-extensions', '--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage']
        )
        self.page = await self.browser.new_page()
        await self.page.wait_for_timeout(3000)
        self.log_memory("After browser start")

    async def open_link(self, url):
        self.logger.info(f"Navigating to {url}")
        await self.page.goto(url, timeout=60000, wait_until='networkidle')
        self.log_memory("After page load")

    @async_generator
    async def collect_track_details(self): # بدون تغییر در این بخش
        selector = 'a[href*="/track/"]'
        self.logger.info(f"Collecting all available tracks from current page state")
        elements = await self.page.query_selector_all(selector)
        self.logger.info(f"Found {len(elements)} track elements on the page")
        for idx, element in enumerate(elements, 1):
            link = await element.get_attribute('href')
            if not link:
                await element.dispose(); del element; continue
            en_title_element = await element.query_selector('h4.musicItemBoxSubTitle')
            fa_title_element = await element.query_selector('h4.musicItemBoxTitle')
            detail = {'link': link, 'en_name': "N/A", 'en_track': "N/A", 'fa_name': "N/A", 'fa_track': "N/A", 'download_link': None}
            if en_title_element:
                html_content = await en_title_element.inner_html()
                parts = html_content.replace('<br>', '\n').strip().split('\n')
                detail['en_name'] = parts[0].strip() if len(parts) > 0 else "N/A"
                detail['en_track'] = parts[1].strip() if len(parts) > 1 else "N/A"
            if fa_title_element:
                html_content = await fa_title_element.inner_html()
                parts = html_content.replace('<br>', '\n').strip().split('\n')
                detail['fa_track'] = parts[0].strip() if len(parts) > 0 else "N/A"
                detail['fa_name'] = parts[1].strip() if len(parts) > 1 else "N/A"
            await yield_(detail)
            await element.dispose(); del element
        self.logger.info(f"Finished yielding all track details from the current page DOM.")

    async def click_see_more(self):
        try:
            button = await self.page.query_selector(self.see_more_button_selector)
            if not button: return False
            self.logger.debug("Attempting to click 'See More' button.")
            await button.click(timeout=10000)
            await self.page.wait_for_load_state('networkidle', timeout=35000)
            await self.page.wait_for_timeout(2000)
            return True
        except TimeoutError as e:
            self.logger.warning(f"Timeout during 'See More' click or subsequent network idle: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Generic error clicking 'See More' button: {e}")
            return False

    # متد save_to_db دیگر در جریان اصلی optimized_main استفاده نمی‌شود
    # async def save_to_db(self, track_data): ...

    def log_memory(self, context=""):
        process = psutil.Process(os.getpid())
        mem = process.memory_info().rss / 1024 / 1024
        self.logger.info(f"Memory Usage {context}: {mem:.2f} MB")

    async def close(self):
        if self.page: await self.page.close(); self.page = None
        if self.browser: await self.browser.close(); self.browser = None
        if self.playwright: await self.playwright.stop(); self.playwright = None
        self.logger.info("Resources cleaned up")

async def optimized_main():
    max_total_links_in_db = 100000
    scraper = GetNewMusic(max_links_to_store=max_total_links_in_db)
    url = "https://www.ahangimo.com/new_music"
    
    max_see_more_click_attempts = 1
    MAX_CONSECUTIVE_FAILURES_TO_STOP = 10 
    DELAY_IF_BUTTON_NOT_FOUND_MS = 6000 

    try:
        await scraper.start()
        if not scraper.page:
            scraper.logger.error("Page object not initialized. Exiting.")
            return
            
        await scraper.open_link(url)

        scraper.logger.info(f"Starting 'See More' click phase: up to {max_see_more_click_attempts} attempts, stop if {MAX_CONSECUTIVE_FAILURES_TO_STOP} consecutive misses.")
        actual_successful_clicks = 0
        consecutive_failures = 0
        attempt_num = 0 # برای لاگ کردن دقیق‌تر تعداد تلاش‌ها
        for attempt_num_loop in range(1, max_see_more_click_attempts + 1):
            attempt_num = attempt_num_loop # بروزرسانی attempt_num برای استفاده در لاگ پس از حلقه
            scraper.logger.info(f"See More - Attempt #{attempt_num}/{max_see_more_click_attempts}. Successful clicks so far: {actual_successful_clicks}.")
            button_element = await scraper.page.query_selector(scraper.see_more_button_selector)
            if button_element and await button_element.is_visible() and await button_element.is_enabled():
                scraper.logger.info("Found 'See More' button, attempting click.")
                if await scraper.click_see_more():
                    actual_successful_clicks += 1
                    consecutive_failures = 0
                    scraper.logger.info(f"'See More' click #{actual_successful_clicks} successful.")
                    if actual_successful_clicks % 10 == 0:
                        scraper.log_memory(f"After {actual_successful_clicks} successful 'See More' clicks")
                else:
                    scraper.logger.warning(f"click_see_more() returned False for attempt #{attempt_num}. Incrementing failure count.")
                    consecutive_failures += 1
                    scraper.logger.info(f"Applying delay of {DELAY_IF_BUTTON_NOT_FOUND_MS / 1000}s due to click failure.")
                    await scraper.page.wait_for_timeout(DELAY_IF_BUTTON_NOT_FOUND_MS) 
            else:
                scraper.logger.info(f"'See More' button not found or not interactable on attempt #{attempt_num}. Incrementing failure count.")
                consecutive_failures += 1
                scraper.logger.info(f"Applying delay of {DELAY_IF_BUTTON_NOT_FOUND_MS / 1000}s as button was not found.")
                await scraper.page.wait_for_timeout(DELAY_IF_BUTTON_NOT_FOUND_MS)
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES_TO_STOP:
                scraper.logger.warning(f"Failed to find or click 'See More' button for {MAX_CONSECUTIVE_FAILURES_TO_STOP} consecutive attempts. Stopping 'See More' clicks.")
                break
            if attempt_num_loop >= max_see_more_click_attempts: # استفاده از شمارنده حلقه برای اطمینان
                scraper.logger.info(f"Reached maximum configured 'See More' click attempts ({max_see_more_click_attempts}).")
                break
        
        scraper.logger.info(f"Finished 'See More' clicks phase. Total successful clicks performed: {actual_successful_clicks} out of {attempt_num} attempts.")
        scraper.log_memory("After all 'See More' click attempts, before collecting details")

        scraper.logger.info("Proceeding to collect all visible track details from the page...")
        all_tracks_details_from_page = []
        async for track_detail in scraper.collect_track_details():
            all_tracks_details_from_page.append(track_detail)
        
        scraper.logger.info(f"Collected details for {len(all_tracks_details_from_page)} track elements from the page.")
        scraper.log_memory("After collecting all track details from DOM")

        if not all_tracks_details_from_page:
            scraper.logger.info("No track elements found on the page to process.")
            await scraper.close(); return

        # --- شروع بهینه‌سازی‌های دیتابیس ---
        scraper.logger.info("Filtering tracks against existing database entries...")
        # 1. خواندن تمام لینک‌های موجود در دیتابیس یکجا
        existing_db_links_set = await scraper.db.get_all_links_as_set()
        
        new_tracks_to_process = []
        unique_links_on_page_set = set() 
        for track in all_tracks_details_from_page:
            if track['link'] in unique_links_on_page_set: # فیلتر تکراری‌های خود صفحه
                scraper.logger.debug(f"Duplicate link within current page scrape batch, skipping: {track['link']}")
                continue
            unique_links_on_page_set.add(track['link'])

            # استفاده از set در حافظه برای بررسی وجود لینک
            if track['link'] not in existing_db_links_set:
                new_tracks_to_process.append(track)
            else:
                scraper.logger.debug(f"Link already in DB (checked via in-memory set), skipping: {track['link']}")
        
        scraper.logger.info(f"Found {len(new_tracks_to_process)} new unique tracks after initial filtering.")
        if not new_tracks_to_process:
            scraper.logger.info("No new tracks to save after checking the database.")
            await scraper.close(); return

        new_tracks_to_process.reverse() # معکوس کردن برای ترتیب درج مورد نظر
        scraper.logger.info(f"Reversed the list of {len(new_tracks_to_process)} new tracks.")

        # 2. خواندن تعداد کل لینک‌ها یکبار قبل از درج
        initial_db_count = await scraper.db.get_total_links()
        slots_available = scraper.max_links_to_store - initial_db_count
        
        if slots_available <= 0:
            scraper.logger.info(f"Database already has {initial_db_count} links, which meets or exceeds the max limit of {scraper.max_links_to_store}. No new tracks will be inserted.")
            await scraper.close(); return

        tracks_for_bulk_insert = new_tracks_to_process[:slots_available]
        
        if not tracks_for_bulk_insert:
            scraper.logger.info("No tracks to insert after considering max links limit.")
            await scraper.close(); return

        scraper.logger.info(f"Attempting to bulk insert up to {len(tracks_for_bulk_insert)} new tracks (available slots: {slots_available}).")
        
        # 3. درج دسته‌ای با استفاده از executemany
        inserted_count = await scraper.db.insert_many_tracks(tracks_for_bulk_insert)
        
        scraper.logger.info(f"Bulk insert operation completed. {inserted_count} tracks were actually inserted into the database.")
        # --- پایان بهینه‌سازی‌های دیتابیس ---
        
    except Exception as e:
        scraper.logger.error(f"An critical error occurred in optimized_main: {e}", exc_info=True)
    finally:
        if scraper: await scraper.close()
        scraper.logger.info("Scraping process finished.")

if __name__ == "__main__":
    asyncio.run(optimized_main())