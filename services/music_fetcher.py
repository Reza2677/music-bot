# from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
# from typing import List, Dict, Tuple
# from ..config import logger
# from ..utils.helpers import parse_title
# from ..database import TrackDatabaseHandler # برای چک کردن وجود لینک قبل از واکشی

# class MusicFetcher:
#     def __init__(self, track_db_handler: TrackDatabaseHandler):
#         self.track_db_handler = track_db_handler
#         self.base_url = "https://www.ahangimo.com"

#     async def _launch_browser_and_page(self, playwright):
#         browser = await playwright.chromium.launch(headless=True)
#         page = await browser.new_page()
#         return browser, page

#     async def fetch_new_music_previews(self) -> List[Dict]:
#         """Fetches up to 20 new music previews from the website."""
#         logger.info("Fetching new music previews...")
#         details = []
#         async with async_playwright() as playwright:
#             browser, page = await self._launch_browser_and_page(playwright)
#             try:
#                 await page.goto(f"{self.base_url}/new_music", wait_until="domcontentloaded")
                
#                 # تلاش برای یافتن ترک‌ها با چند مهلت زمانی مختلف
#                 # این بخش می‌تواند پیچیده‌تر شود اگر ساختار سایت داینامیک باشد
#                 track_elements_selector = 'a[href*="/track/"]'
                
#                 try:
#                     await page.wait_for_selector(track_elements_selector, timeout=15000) # افزایش تایم‌اوت
#                 except PlaywrightTimeoutError:
#                     logger.warning("Could not find track elements within timeout.")
#                     await page.screenshot(path='debug_fetch_new_music_timeout.png') # برای دیباگ
#                     return details

#                 tracks = await page.query_selector_all(track_elements_selector)
                
#                 count = 0
#                 for track_element in tracks:
#                     if count >= 20: # محدودیت ۲۰ آهنگ
#                         break

#                     link = await track_element.get_attribute('href')
#                     if not link or not link.startswith("/track/"): # بررسی لینک معتبر
#                         continue
                    
#                     # اگر لینک قبلا در دیتابیس موجود است و لینک دانلود هم دارد، از آن رد شو
#                     # این برای جلوگیری از واکشی مجدد اطلاعاتی است که تغییر نکرده‌اند
#                     # existing_track = self.track_db_handler.get_track_by_link(link)
#                     # if existing_track and existing_track.get('download_link') != 'N/A':
#                     #     logger.info(f"Skipping already processed track: {link}")
#                     #     continue

#                     en_title_element = await track_element.query_selector('h4.musicItemBoxSubTitle')
#                     fa_title_element = await track_element.query_selector('h4.musicItemBoxTitle')

#                     en_name, en_track = parse_title(await en_title_element.inner_html()) if en_title_element else ("N/A", "N/A")
#                     fa_track, fa_name = parse_title(await fa_title_element.inner_html()) if fa_title_element else ("N/A", "N/A") # ترتیب برعکس در کد اصلی

#                     if en_name != "N/A" or fa_name != "N/A": # اطمینان از وجود حداقل یک نام
#                         details.append({
#                             "link": link, # Relative link
#                             "en_name": en_name,
#                             "en_track": en_track,
#                             "fa_name": fa_name, 
#                             "fa_track": fa_track,
#                             "download_link": "N/A" #  لینک دانلود بعدا واکشی می‌شود
#                         })
#                         count += 1
#                 logger.info(f"Fetched {len(details)} new music previews.")
#             except Exception as e:
#                 logger.error(f"Error fetching new music previews: {e}", exc_info=True)
#                 await page.screenshot(path='debug_fetch_new_music_error.png') # برای دیباگ
#             finally:
#                 await browser.close()
#         return details

#     async def fetch_single_download_link(self, relative_track_link: str) -> str:
#         """Fetches the download link for a single track page."""
#         logger.info(f"Fetching download link for: {relative_track_link}")
#         download_link = "N/A"
#         full_url = f"{self.base_url}{relative_track_link}"

#         async with async_playwright() as playwright:
#             browser, page = await self._launch_browser_and_page(playwright)
#             try:
#                 await page.goto(full_url, wait_until="networkidle", timeout=30000) # زمان انتظار بیشتر
                
#                 # سلکتور دقیق‌تر برای لینک دانلود
#                 # این سلکتور ممکن است نیاز به تنظیم داشته باشد اگر سایت تغییر کند
#                 download_link_selector = 'div.downloadBoxSingleSong a[href*=".mp3"]' # معمولا لینک دانلود به mp3 ختم میشه
                
#                 # یک سلکتور جایگزین که در کد اصلی بود
#                 alternative_selector = '#swup > div.incontent > div > div:nth-child(5) > div > div.col-md-3.text-center > div > a'

#                 link_element = None
#                 try:
#                     link_element = await page.wait_for_selector(download_link_selector, timeout=10000)
#                 except PlaywrightTimeoutError:
#                     logger.warning(f"Primary download link selector not found for {relative_track_link}. Trying alternative.")
#                     try:
#                         link_element = await page.wait_for_selector(alternative_selector, timeout=10000)
#                     except PlaywrightTimeoutError:
#                         logger.error(f"Could not find download link for {relative_track_link} using both selectors.")
#                         await page.screenshot(path=f'debug_download_link_timeout_{relative_track_link.replace("/", "_")}.png')


#                 if link_element:
#                     href = await link_element.get_attribute('href')
#                     if href:
#                         download_link = href if href.startswith('http') else f"{self.base_url}{href}"
#                         logger.info(f"Download link found for {relative_track_link}: {download_link}")
#                     else:
#                         logger.warning(f"Download link element found for {relative_track_link}, but href is empty.")
                
#             except Exception as e:
#                 logger.error(f"Error fetching download link for {relative_track_link}: {e}", exc_info=True)
#                 await page.screenshot(path=f'debug_download_link_error_{relative_track_link.replace("/","_")}.png')
#             finally:
#                 await browser.close()
#         return download_link


















# music_bot/services/music_fetcher.py
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from ..config import logger # logger از config ربات
# music_bot/services/music_fetcher.py
import time # برای تاخیرها
import urllib.parse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError # استفاده از sync_api
from typing import List, Dict, Optional



# تابع parse_title از کد جدید شما (یا مشابه آن)
def _parse_html_title_parts(html_content: str) -> tuple[str, str]:
    if not html_content:
        return "N/A", "N/A"
    parts = html_content.replace('<br>', '\n').strip().split('\n')
    part1 = parts[0].strip() if len(parts) > 0 else "N/A"
    part2 = parts[1].strip() if len(parts) > 1 else "N/A"
    return part1, part2




# تنظیمات از کد اصلی شما (می‌توانید در config.py بگذارید)
DOWNLOAD_MAX_RETRIES = 2
DOWNLOAD_RETRY_DELAY_S = 3
# DELAY_BETWEEN_DOWNLOAD_ATTEMPTS_S = 0.5 # تاخیر بین پردازش هر آهنگ

# تابع کمکی برای اجرای بخش همزمان (sync) در یک نخ جداگانه
def _sync_extract_music_link_task(page_url: str, base_music_url: str) -> Optional[str]:
    """
    این تابع منطق اصلی extract_music_link از کد شما را به صورت همزمان اجرا می‌کند.
    این تابع در یک نخ جداگANE توسط asyncio.to_thread فراخوانی خواهد شد.
    """
    # logger.info(f"[Thread] Starting sync extraction for {page_url}") # لاگ از نخ ممکن است با لاگ اصلی تداخل کند
    
    # --- کپی مستقیم منطق از TrackDownloader.extract_music_link ---
    # با کمی تغییرات برای استفاده به عنوان تابع مستقل و بدون process_id
    
    playwright_instance = None
    browser_instance = None
    page_instance = None
    extracted_link_value = None

    try:
        playwright_instance = sync_playwright().start()
        browser_instance = playwright_instance.chromium.launch(headless=True, 
            args=['--disable-extensions', '--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage']) # آرگومان‌های بهینه
        page_instance = browser_instance.new_page()
        page_instance.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })

        # logger.info(f"[Thread] Navigating to page: {page_url}")
        page_instance.goto(page_url, wait_until="domcontentloaded", timeout=60000)
        page_instance.wait_for_timeout(1000)

        online_play_button_selector = "button.pflikebtn.likedBtnNotActive.justify-content-center.w-100"
        download_link_selector = "#downloadTrackBtn > a"

        current_retry = 0
        while current_retry <= DOWNLOAD_MAX_RETRIES:
            try:
                page_instance.wait_for_selector(online_play_button_selector, timeout=20000, state="visible")
                play_button_element = page_instance.query_selector(online_play_button_selector)
                if not play_button_element:
                    # logger.error(f"[Thread] 'Online Play' button not found on {page_url}")
                    raise PlaywrightTimeoutError("Play button not found") # ایجاد خطا برای رفتن به retry

                play_button_element.scroll_into_view_if_needed()
                page_instance.wait_for_timeout(300)
                play_button_element.click(timeout=15000)
                # logger.info(f"[Thread] 'Online Play' button clicked on {page_url}")

                page_instance.wait_for_selector(download_link_selector, timeout=30000, state="visible")
                download_link_element = page_instance.query_selector(download_link_selector)
                
                if download_link_element:
                    for attempt in range(3):
                        link = download_link_element.get_attribute('href')
                        if link and link.strip() and link != "#" and "javascript:void(0)" not in link:
                            if not link.startswith(('http://', 'https://')):
                                if link.startswith('/'):
                                    # base_music_url باید پاس داده شود یا از page_url استخراج شود
                                    # current_url_page = page_instance.url
                                    # scheme, netloc, _, _, _ = urllib.parse.urlsplit(current_url_page)
                                    # base_url_parsed = f"{scheme}://{netloc}"
                                    link = urllib.parse.urljoin(base_music_url, link) # استفاده از base_music_url
                                else:
                                    link = None # فرمت نامعتبر
                            
                            if link and link.startswith(('http://', 'https://')):
                                # logger.info(f"[Thread] Extracted download link: {link}")
                                extracted_link_value = link
                                break # از حلقه attempt خارج شو
                    if extracted_link_value:
                        break # از حلقه retry خارج شو
                
                if not extracted_link_value: # اگر بعد از 3 تلاش href معتبر نبود
                    # logger.warning(f"[Thread] Failed to extract valid href from download link on {page_url}")
                    raise PlaywrightTimeoutError("Href not extracted")

            except PlaywrightTimeoutError as pte: # شامل TimeoutError از wait_for_selector
                # logger.warning(f"[Thread] Playwright Timeout on {page_url} (Retry {current_retry}/{DOWNLOAD_MAX_RETRIES}): {pte}")
                current_retry += 1
                if current_retry > DOWNLOAD_MAX_RETRIES:
                    # logger.error(f"[Thread] Max retries reached for {page_url}. Failed to extract link.")
                    break
                # logger.info(f"[Thread] Retrying in {DOWNLOAD_RETRY_DELAY_S}s...")
                time.sleep(DOWNLOAD_RETRY_DELAY_S)
            except Exception as e_inner:
                # logger.error(f"[Thread] Unexpected error during extraction for {page_url} (Retry {current_retry}): {e_inner}", exc_info=True)
                current_retry += 1
                if current_retry > DOWNLOAD_MAX_RETRIES:
                    # logger.error(f"[Thread] Max retries reached for {page_url} after general error.")
                    break
                time.sleep(DOWNLOAD_RETRY_DELAY_S)
        
    except Exception as e_outer:
        # logger.error(f"[Thread] Critical error in _sync_extract_music_link_task for {page_url}: {e_outer}", exc_info=True)
        extracted_link_value = None # یا "FAILED_TO_EXTRACT_SYNC"
    finally:
        if page_instance: page_instance.close()
        if browser_instance: browser_instance.close()
        if playwright_instance: playwright_instance.stop()
        # logger.info(f"[Thread] Playwright resources closed for {page_url}")

    return extracted_link_value
# --- پایان تابع کمکی ---


class MusicFetcher:
    def __init__(self):
        self.base_url = "https://www.ahangimo.com" # این باید برای لینک صفحه آهنگ استفاده شود
        # ... سایر تنظیمات MusicFetcher ...

    async def fetch_new_music_previews(self) -> List[Dict]:
        # این متد همانطور که در پاسخ قبلی اصلاح شد، باقی می‌ماند
        # و فقط اطلاعات اولیه آهنگ‌ها را (بدون لینک دانلود) برمی‌گرداند.
        # ... (کد از پاسخ قبلی برای fetch_new_music_previews) ...
        logger.info("Starting optimized music preview fetching...")
        raw_tracks_from_page: List[Dict] = []
        playwright = None
        browser = None

        try:
            playwright = await async_playwright().start()
            browser_args = ['--disable-extensions', '--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage']
            browser = await playwright.chromium.launch(headless=True, args=browser_args)
            page = await browser.new_page()
            
            await page.goto(f"{self.base_url}/new_music", timeout=60000, wait_until='networkidle')
            
            # ... (منطق کلیک See More و جمع آوری اولیه از پاسخ قبلی) ...
            # برای خلاصه، فرض می‌کنیم این بخش تکمیل شده و raw_tracks_from_page پر شده.
            # کپی کردن از پاسخ قبلی:
            consecutive_see_more_failures = 0
            max_see_more_clicks = getattr(self, 'max_see_more_clicks', 1) # گرفتن از self یا مقدار پیش فرض
            consecutive_failure_limit = getattr(self, 'consecutive_failure_limit', 3)
            click_delay_ms = getattr(self, 'click_delay_ms', 2000)

            for i in range(max_see_more_clicks):
                logger.info(f"Attempting 'See More' click {i+1}/{max_see_more_clicks}")
                # فرض میکنیم _attempt_click_see_more یک متد async در همین کلاس است
                if await self._attempt_click_see_more_internal(page, click_delay_ms): # تغییر نام برای جلوگیری از تداخل
                    logger.info(f"'See More' click {i+1} successful.")
                    consecutive_see_more_failures = 0
                else:
                    consecutive_see_more_failures += 1
                    if consecutive_see_more_failures >= consecutive_failure_limit:
                        break
                    await asyncio.sleep(click_delay_ms / 1000) # استفاده از asyncio.sleep

            track_elements_selector = 'a[href*="/track/"]'
            elements = await page.query_selector_all(track_elements_selector)
            logger.info(f"Found {len(elements)} track elements on page.")
            # تابع _parse_html_title_parts باید اینجا تعریف یا وارد شده باشد
            for el in elements:
                link = await el.get_attribute('href')
                if not link: continue
                track_detail = {'link': link, 'download_link': None}
                en_title_el = await el.query_selector('h4.musicItemBoxSubTitle')
                fa_title_el = await el.query_selector('h4.musicItemBoxTitle')
                if en_title_el:
                    en_name, en_track = _parse_html_title_parts(await en_title_el.inner_html())
                    track_detail['en_name'] = en_name; track_detail['en_track'] = en_track
                if fa_title_el:
                    fa_track_val, fa_name_val = _parse_html_title_parts(await fa_title_el.inner_html())
                    track_detail['fa_track'] = fa_track_val; track_detail['fa_name'] = fa_name_val
                for key_default in ['en_name', 'en_track', 'fa_name', 'fa_track']:
                    if key_default not in track_detail: track_detail[key_default] = "N/A"
                raw_tracks_from_page.append(track_detail)
            # --- پایان کپی ---
        except Exception as e:
            logger.error(f"Critical error during music preview fetching: {e}", exc_info=True)
        finally:
            if 'page' in locals() and page: await page.close()
            if browser: await browser.close()
            if playwright: await playwright.stop()
        return raw_tracks_from_page

    async def _attempt_click_see_more_internal(self, page, click_delay_ms) -> bool: # متد کمکی که قبلا داشتیم
        see_more_button_selector = getattr(self, 'see_more_button_selector', 'div.dataloaderError.datalist1ErrorBtn > button.btn.btn-primary.w-100')
        try:
            button = await page.query_selector(see_more_button_selector)
            if button and await button.is_visible() and await button.is_enabled():
                await button.click(timeout=10000)
                await page.wait_for_load_state('domcontentloaded', timeout=15000)
                await asyncio.sleep(click_delay_ms / 2000) # تقسیم بر 2000 به جای 2
                return True
            return False
        except PlaywrightTimeoutError: return False
        except Exception: return False


    async def get_single_track_download_link(self, track_page_relative_url: str) -> Optional[str]:
        """
        واکشی لینک دانلود برای یک آهنگ با استفاده از منطق sync در نخ جداگانه.
        """
        if not track_page_relative_url:
            return None

        full_page_url = track_page_relative_url
        if track_page_relative_url.startswith('/'):
            full_page_url = urllib.parse.urljoin(self.base_url, track_page_relative_url)
        
        logger.info(f"Attempting to extract download link for: {full_page_url}")
        
        try:
            # اجرای تابع همزمان در یک نخ جداگانه
            download_link = await asyncio.to_thread(
                _sync_extract_music_link_task, 
                full_page_url,
                self.base_url # برای ساخت لینک کامل در صورت نیاز
            )
            
            if download_link:
                logger.info(f"Successfully extracted download link for {track_page_relative_url}: {download_link}")
            else:
                logger.warning(f"Failed to extract download link for {track_page_relative_url} after all retries.")
            return download_link
        except Exception as e:
            logger.error(f"Error calling to_thread for {full_page_url}: {e}", exc_info=True)
            return None # یا "FAILED_TO_EXTRACT_ASYNC_WRAPPER"