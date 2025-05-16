

import logging
import time
import sqlite3
import os
import concurrent.futures
from queue import Queue, Empty
from threading import Lock
from playwright.sync_api import sync_playwright, TimeoutError
import urllib.parse

# ----- تنظیمات اجرایی -----
# تعداد پردازش‌های موازی - بسته به سیستم تنظیم کنید (معمولاً 4-8 مناسب است)
CONCURRENT_PROCESSES = 4

# تاخیر بین درخواست‌ها در هر مرورگر
DELAY_BETWEEN_TRACKS_S = 0.1  # کاهش از 0.2 ثانیه

# تنظیمات تلاش مجدد
MAX_RETRIES = 2  # تعداد تلاش مجدد برای هر لینک قبل از علامت‌گذاری شکست
RETRY_DELAY_S = 3  # تاخیر بین تلاش‌های مجدد

# حجم دسته‌های پردازش 
BATCH_SIZE = 100  # تعداد رکوردهایی که هر پردازش دریافت می‌کند


class TrackDownloader:
    """کلاس مسئول استخراج لینک‌های دانلود برای یک گروه از ترک‌ها"""
    
    def __init__(self, process_id, db_path, log_file_base="download_music"):
        self.process_id = process_id
        self.db_path = db_path
        
        # تنظیم لاگر مجزا برای هر پردازش
        log_file = f"{log_file_base}_{process_id}.log"
        self.logger = self._setup_logger(log_file)
        
        self.playwright = None
        self.browser = None
        self.page = None
        self.conn = None
        self.cursor = None
        
    def _setup_logger(self, log_file):
        """راه‌اندازی لاگر برای این پردازش"""
        logger = logging.getLogger(f"{__name__}_{self.process_id}")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            file_handler = logging.FileHandler(log_file)
            console_handler = logging.StreamHandler()
            
            formatter = logging.Formatter('%(asctime)s - [Process-%(name)s] - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
            
        return logger
    
    def start_resources(self):
        """راه‌اندازی منابع مورد نیاز: مرورگر و پایگاه داده"""
        try:
            # اتصال به پایگاه داده
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            self.logger.info(f"Process {self.process_id}: Connected to database: {self.db_path}")
            
            # راه‌اندازی مرورگر
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=True)
            self.page = self.browser.new_page()
            self.page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            })
            self.logger.info(f"Process {self.process_id}: Playwright browser started successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Process {self.process_id}: Error starting resources: {e}", exc_info=True)
            self.close_resources()
            return False
    
    def extract_music_link(self, page_url, retry_count=0):
        """استخراج لینک دانلود موسیقی از URL صفحه با امکان تلاش مجدد"""
        try:
            self.logger.info(f"Process {self.process_id}: Navigating to page: {page_url}")
            
            # تلاش برای باز کردن صفحه با تایم‌اوت کمتر
            self.page.goto(page_url, wait_until="domcontentloaded", timeout=60000)
            self.page.wait_for_timeout(1000)  # کاهش بیشتر زمان انتظار اولیه

            # انتخابگرهای مورد نیاز
            online_play_button_selector = "button.pflikebtn.likedBtnNotActive.justify-content-center.w-100"
            download_link_selector = "#downloadTrackBtn > a"

            # تلاش برای یافتن دکمه پخش آنلاین
            try:
                self.page.wait_for_selector(online_play_button_selector, timeout=20000, state="visible")
                play_button_element = self.page.query_selector(online_play_button_selector)
                if not play_button_element:
                    self.logger.error(f"Process {self.process_id}: 'Online Play' button not found on {page_url}")
                    return None
            except TimeoutError:
                if retry_count < MAX_RETRIES:
                    self.logger.warning(f"Process {self.process_id}: Timeout waiting for button on {page_url}. Retrying ({retry_count+1}/{MAX_RETRIES})...")
                    time.sleep(RETRY_DELAY_S)
                    return self.extract_music_link(page_url, retry_count + 1)
                else:
                    self.logger.error(f"Process {self.process_id}: Failed to find play button after {MAX_RETRIES} retries on {page_url}")
                    return None
            
            # کلیک روی دکمه پخش
            try:
                play_button_element.scroll_into_view_if_needed()
                self.page.wait_for_timeout(300)  # تاخیر کمتر بعد از اسکرول
                play_button_element.click(timeout=15000)
                self.logger.info(f"Process {self.process_id}: 'Online Play' button clicked on {page_url}")
            except Exception as e_click:
                self.logger.error(f"Process {self.process_id}: Error clicking play button on {page_url}: {e_click}")
                if retry_count < MAX_RETRIES:
                    self.logger.warning(f"Process {self.process_id}: Retrying after click error ({retry_count+1}/{MAX_RETRIES})...")
                    time.sleep(RETRY_DELAY_S)
                    return self.extract_music_link(page_url, retry_count + 1)
                return None
            
            # انتظار برای لینک دانلود
            try:
                self.page.wait_for_selector(download_link_selector, timeout=30000, state="visible")
                download_link_element = self.page.query_selector(download_link_selector)
            except TimeoutError:
                if retry_count < MAX_RETRIES:
                    self.logger.warning(f"Process {self.process_id}: Timeout waiting for download link on {page_url}. Retrying ({retry_count+1}/{MAX_RETRIES})...")
                    time.sleep(RETRY_DELAY_S)
                    return self.extract_music_link(page_url, retry_count + 1)
                else:
                    self.logger.error(f"Process {self.process_id}: Failed to find download link after {MAX_RETRIES} retries on {page_url}")
                    return None
            
            # استخراج لینک دانلود
            if download_link_element:
                for attempt in range(3):  # کاهش تعداد تلاش‌ها
                    link = download_link_element.get_attribute('href')
                    if link and link.strip() and link != "#" and "javascript:void(0)" not in link:
                        # تبدیل مسیر نسبی به URL کامل
                        if not link.startswith(('http://', 'https://')):
                            if link.startswith('/'):
                                current_url = self.page.url
                                scheme, netloc, _, _, _ = urllib.parse.urlsplit(current_url)
                                base_url = f"{scheme}://{netloc}"
                                link = base_url + link
                            else:
                                self.logger.warning(f"Process {self.process_id}: Invalid link format: {link}")
                                link = None
                        
                        if link and link.startswith(('http://', 'https://')):
                            self.logger.info(f"Process {self.process_id}: Extracted download link: {link}")
                            return link
                    
                    # انتظار کوتاه‌تر بین تلاش‌ها
                    if attempt < 2:
                        self.page.wait_for_timeout(1000)
                
                self.logger.warning(f"Process {self.process_id}: Failed to extract valid href from download link on {page_url}")
                return None
            else:
                self.logger.warning(f"Process {self.process_id}: Download link element not found on {page_url}")
                return None
                
        except Exception as e:
            self.logger.error(f"Process {self.process_id}: Error extracting link from {page_url}: {e}", exc_info=True)
            if retry_count < MAX_RETRIES:
                self.logger.warning(f"Process {self.process_id}: Retrying after general error ({retry_count+1}/{MAX_RETRIES})...")
                time.sleep(RETRY_DELAY_S)
                return self.extract_music_link(page_url, retry_count + 1)
            return None
    
    def process_track_batch(self, track_batch):
        """پردازش یک دسته از ترک‌ها"""
        if not self.conn or not self.cursor:
            self.logger.error(f"Process {self.process_id}: Database connection not available")
            return 0
        
        success_count = 0
        base_url = "https://www.ahangimo.com"
        
        for pk_value, link_from_db in track_batch:
            if not link_from_db or not link_from_db.strip():
                self.logger.warning(f"Process {self.process_id}: Track with PK {pk_value} has empty link. Skipping.")
                continue
            
            # ساخت URL کامل
            clean_link = link_from_db.strip()
            if clean_link.startswith(("http://", "https://")):
                full_url = clean_link
            elif clean_link.startswith("/"):
                full_url = f"{base_url}{clean_link}"
            else:
                full_url = f"{base_url}/{clean_link}"
            
            # استخراج لینک دانلود
            extracted_link = self.extract_music_link(full_url)
            
            # بروزرسانی پایگاه داده
            try:
                if extracted_link:
                    self.cursor.execute(
                        "UPDATE tracks SET download_link = ? WHERE id = ?",
                        (extracted_link, pk_value)
                    )
                    self.conn.commit()
                    self.logger.info(f"Process {self.process_id}: Updated track {pk_value} with link: {extracted_link}")
                    success_count += 1
                else:
                    self.cursor.execute(
                        "UPDATE tracks SET download_link = ? WHERE id = ?",
                        ("FAILED_TO_EXTRACT", pk_value)
                    )
                    self.conn.commit()
                    self.logger.warning(f"Process {self.process_id}: Failed to extract link for track {pk_value}")
            except sqlite3.Error as e:
                self.logger.error(f"Process {self.process_id}: Database error updating track {pk_value}: {e}")
            
            # تاخیر کوتاه بین پردازش ترک‌ها
            if DELAY_BETWEEN_TRACKS_S > 0:
                time.sleep(DELAY_BETWEEN_TRACKS_S)
        
        return success_count
    
    def close_resources(self):
        """بستن تمام منابع"""
        if self.page:
            try: 
                self.page.close()
                self.logger.info(f"Process {self.process_id}: Page closed")
            except: pass
        
        if self.browser:
            try: 
                self.browser.close() 
                self.logger.info(f"Process {self.process_id}: Browser closed")
            except: pass
        
        if self.playwright:
            try: 
                self.playwright.stop()
                self.logger.info(f"Process {self.process_id}: Playwright stopped")
            except: pass
        
        if self.conn:
            try: 
                self.conn.close()
                self.logger.info(f"Process {self.process_id}: Database connection closed")
            except: pass


def worker_process(process_id, db_path, track_batch):
    """تابع اصلی برای هر پردازش کارگر"""
    downloader = TrackDownloader(process_id, db_path)
    success_count = 0
    
    try:
        if downloader.start_resources():
            success_count = downloader.process_track_batch(track_batch)
    except Exception as e:
        downloader.logger.error(f"Process {process_id}: Critical error in worker: {e}", exc_info=True)
    finally:
        downloader.close_resources()
    
    return success_count


def get_remaining_tracks(db_path):
    """گرفتن لیست ترک‌های باقی‌مانده از پایگاه داده"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # بررسی وجود ستون download_link
        cursor.execute("PRAGMA table_info(tracks);")
        cols = [c[1] for c in cursor.fetchall()]
        
        if 'download_link' not in cols:
            cursor.execute("ALTER TABLE tracks ADD COLUMN download_link TEXT;")
            conn.commit()
            print("Column 'download_link' added to the tracks table.")
        
        # انتخاب ترک‌های پردازش نشده
        cursor.execute("SELECT id, link FROM tracks WHERE download_link IS NULL OR download_link = ''")
        tracks = cursor.fetchall()
        return tracks
    
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []
    
    finally:
        conn.close()


def split_tracks_into_batches(tracks, num_processes, batch_size=BATCH_SIZE):
    """تقسیم ترک‌ها به دسته‌های کوچکتر برای پردازش موازی"""
    batches = []
    
    # تقسیم به دسته‌های مناسب
    for i in range(0, len(tracks), batch_size):
        batches.append(tracks[i:i+batch_size])
    
    # اگر تعداد دسته‌ها از تعداد پردازش‌ها کمتر است
    if len(batches) < num_processes:
        return batches
    
    # درغیر اینصورت، تقسیم متعادل دسته‌ها بین پردازش‌ها
    process_batches = [[] for _ in range(num_processes)]
    for i, batch in enumerate(batches):
        process_batches[i % num_processes].extend(batch)
    
    return [batch for batch in process_batches if batch]  # حذف دسته‌های خالی


def main_parallel():
    """تابع اصلی برای پردازش موازی"""
    db_path = "tracks.db"
    start_time = time.time()
    
    # دریافت ترک‌های باقی‌مانده
    remaining_tracks = get_remaining_tracks(db_path)
    total_tracks = len(remaining_tracks)
    
    if total_tracks == 0:
        print("No tracks to process. Exiting.")
        return
    
    print(f"Found {total_tracks} tracks to process.")
    
    # تعیین تعداد پردازش‌ها (حداکثر CONCURRENT_PROCESSES)
    num_processes = min(CONCURRENT_PROCESSES, total_tracks)
    
    # تقسیم ترک‌ها به دسته‌های مناسب برای هر پردازش
    process_batches = split_tracks_into_batches(remaining_tracks, num_processes)
    
    print(f"Starting {len(process_batches)} worker processes...")
    
    # شروع پردازش موازی
    total_success = 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=len(process_batches)) as executor:
        futures = []
        
        # ارسال کار به هر پردازش
        for i, batch in enumerate(process_batches):
            future = executor.submit(worker_process, i+1, db_path, batch)
            futures.append(future)
        
        # جمع‌آوری نتایج
        for future in concurrent.futures.as_completed(futures):
            try:
                success_count = future.result()
                total_success += success_count
                print(f"A worker completed processing {success_count} tracks successfully.")
            except Exception as e:
                print(f"A worker failed with error: {e}")
    
    total_time = time.time() - start_time
    print(f"\nProcessing Summary:")
    print(f"Total tracks: {total_tracks}")
    print(f"Successfully processed: {total_success}")
    print(f"Failed: {total_tracks - total_success}")
    print(f"Total time: {total_time:.2f} seconds")
    print(f"Average time per track: {total_time/total_tracks:.2f} seconds")
    print(f"Tracks per second: {total_tracks/total_time:.2f}")


if __name__ == "__main__":
    # تنظیم لاگر اصلی
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("parallel_download.log")
        ]
    )
    
    try:
        main_parallel()
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Exiting...")
    except Exception as e:
        logging.error(f"Critical error in main program: {e}", exc_info=True)
