# --- START OF FILE services/music_fetcher.py ---

import asyncio
from playwright.sync_api import sync_playwright, Error as PlaywrightError, TimeoutError as PlaywrightSyncTimeoutError
from playwright.async_api import async_playwright, Error as PlaywrightAsyncError, TimeoutError as PlaywrightAsyncTimeoutError
from config import logger
import time
import urllib.parse
from typing import List, Dict, Optional, Tuple # اضافه کردن Tuple

# --- ثابت‌های مربوط به استخراج لینک دانلود ---
DOWNLOAD_MAX_RETRIES = 2
DOWNLOAD_RETRY_DELAY_S = 4 # کمی افزایش تاخیر برای پایداری بیشتر
DOWNLOAD_PAGE_TIMEOUT_MS = 60000  # 60 ثانیه
DOWNLOAD_ELEMENT_TIMEOUT_MS = 25000 # 25 ثانیه
CLICK_TIMEOUT_MS = 20000 # 20 ثانیه

# --- ثابت‌های مربوط به واکشی پیش‌نمایش ---
PREVIEW_PAGE_TIMEOUT_MS = 90000 # 90 ثانیه
PREVIEW_CLICK_DELAY_MS = 3000 # تاخیر پس از کلیک "بیشتر ببینید"
PREVIEW_CONSECUTIVE_FAILURE_LIMIT = 2 # کاهش برای جلوگیری از تلاش‌های بی‌فایده
# MAX_SEE_MORE_CLICKS در __init__ کلاس تعریف می‌شود.

# --- تابع کمکی برای پارس کردن عنوان ---
def _parse_html_title_parts(html_content: Optional[str]) -> Tuple[str, str]:
    if not html_content:
        return "N/A", "N/A"
    # جایگزینی <br> با \n و سپس جداسازی
    parts = html_content.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n').strip().split('\n')
    part1 = parts[0].strip() if len(parts) > 0 and parts[0] else "N/A"
    part2 = parts[1].strip() if len(parts) > 1 and parts[1] else "N/A"
    return part1, part2

# --- تابع همگام برای استخراج لینک دانلود (برای اجرا در ترد جداگانه) ---
def _sync_extract_music_link_task(page_url: str, base_music_url: str) -> Optional[str]:
    playwright_instance = None
    browser_instance = None
    context_instance = None # اضافه شد برای مدیریت context
    page_instance = None
    extracted_link_value = None

    logger.info(f"[SyncThreadDL] Starting Playwright task for URL: {page_url}")

    try:
        playwright_instance = sync_playwright().start()
        logger.debug(f"[SyncThreadDL] Launching Chromium for {page_url}")
        browser_instance = playwright_instance.chromium.launch(
            headless=True,
            args=[
                '--disable-extensions', '--disable-gpu', '--no-sandbox',
                '--disable-dev-shm-usage', '--single-process', # تست کنید --single-process
                '--disable-setuid-sandbox', '--disable-accelerated-2d-canvas',
                '--no-zygote', '--blink-settings=imagesEnabled=false' # غیرفعال کردن تصاویر
            ]
        )
        logger.debug(f"[SyncThreadDL] Browser launched for {page_url}")

        context_instance = browser_instance.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",
            ignore_https_errors=True,
            # می‌توانید viewport را هم برای سازگاری بیشتر تنظیم کنید
            # viewport={'width': 1280, 'height': 800}
        )
        logger.debug(f"[SyncThreadDL] Browser context created for {page_url}")
        page_instance = context_instance.new_page()
        logger.debug(f"[SyncThreadDL] New page created for {page_url}")

        # بلاک کردن منابع غیر ضروری
        def block_unnecessary_resources(route):
            if route.request.resource_type in ["font", "media", "websocket", "other", "manifest", "texttrack"]:
                return route.abort()
            # می‌توانید stylesheet را هم بلاک کنید اگر برای عملکرد سایت ضروری نیست
            # if route.request.resource_type == "stylesheet" and "critical.css" not in route.request.url:
            #    return route.abort()
            return route.continue_()
        page_instance.route("**/*", block_unnecessary_resources)
        logger.debug(f"[SyncThreadDL] Resource blocking rule set for {page_url}")

        logger.info(f"[SyncThreadDL] Navigating to: {page_url}")
        page_instance.goto(page_url, wait_until="domcontentloaded", timeout=DOWNLOAD_PAGE_TIMEOUT_MS)
        logger.info(f"[SyncThreadDL] Navigation complete for: {page_url}")
        # page_instance.wait_for_timeout(1000) # حذف شد، بهتر است از wait_for_selector استفاده شود

        online_play_button_selector = "button.pflikebtn.likedBtnNotActive.justify-content-center.w-100"
        download_link_selector = "#downloadTrackBtn > a" # انتخابگر شما

        current_retry = 0
        while current_retry <= DOWNLOAD_MAX_RETRIES:
            logger.info(f"[SyncThreadDL] Attempt {current_retry + 1}/{DOWNLOAD_MAX_RETRIES + 1} for {page_url}")
            try:
                logger.debug(f"[SyncThreadDL] Waiting for play button: {online_play_button_selector}")
                page_instance.wait_for_selector(online_play_button_selector, timeout=DOWNLOAD_ELEMENT_TIMEOUT_MS, state="visible")
                play_button_element = page_instance.query_selector(online_play_button_selector)

                if not play_button_element: # این شرط احتمالاً با wait_for_selector پوشش داده می‌شود
                    logger.warning(f"[SyncThreadDL] Play button not found after wait for {page_url}")
                    raise PlaywrightSyncTimeoutError("Play button not found even after wait_for_selector")

                logger.debug(f"[SyncThreadDL] Play button found, scrolling and clicking for {page_url}")
                play_button_element.scroll_into_view_if_needed(timeout=CLICK_TIMEOUT_MS / 2)
                page_instance.wait_for_timeout(500) # کمی تاخیر پس از اسکرول
                play_button_element.click(timeout=CLICK_TIMEOUT_MS)
                logger.debug(f"[SyncThreadDL] Play button clicked for {page_url}")

                logger.debug(f"[SyncThreadDL] Waiting for download link: {download_link_selector}")
                page_instance.wait_for_selector(download_link_selector, timeout=DOWNLOAD_ELEMENT_TIMEOUT_MS, state="visible")
                download_link_element = page_instance.query_selector(download_link_selector)

                if download_link_element:
                    logger.debug(f"[SyncThreadDL] Download link element found for {page_url}. Extracting href...")
                    # تلاش برای خواندن href چند بار با کمی تاخیر اگر لازم شد
                    for attempt_href in range(3):
                        link = download_link_element.get_attribute('href')
                        if link and link.strip() and link != "#" and "javascript:void(0)" not in link:
                            if not link.startswith(('http://', 'https://')):
                                if link.startswith('/'):
                                    link = urllib.parse.urljoin(base_music_url, link)
                                else:
                                    logger.warning(f"[SyncThreadDL] Invalid relative link format: {link} for {page_url}")
                                    link = None
                            if link and link.startswith(('http://', 'https://')):
                                extracted_link_value = link
                                logger.info(f"[SyncThreadDL] Successfully extracted download link: {extracted_link_value} from {page_url}")
                                break # خروج از حلقه تلاش برای href
                        logger.debug(f"[SyncThreadDL] Href attempt {attempt_href + 1} for {page_url} yielded: {link}. Retrying if possible.")
                        if attempt_href < 2 : page_instance.wait_for_timeout(500) # تاخیر کوتاه بین تلاش‌ها

                    if extracted_link_value:
                        break # خروج از حلقه retry اصلی

                if not extracted_link_value:
                    logger.warning(f"[SyncThreadDL] Href not extracted or invalid after attempts for {page_url}")
                    raise PlaywrightSyncTimeoutError("Href not extracted or invalid")

            except PlaywrightSyncTimeoutError as pte:
                logger.warning(f"[SyncThreadDL] Playwright Timeout on {page_url} (Retry {current_retry + 1}): {str(pte)}")
                current_retry += 1
                if current_retry > DOWNLOAD_MAX_RETRIES:
                    logger.error(f"[SyncThreadDL] Max retries reached for {page_url}. Failed to extract link.")
                    break
                logger.info(f"[SyncThreadDL] Retrying in {DOWNLOAD_RETRY_DELAY_S}s...")
                time.sleep(DOWNLOAD_RETRY_DELAY_S)
            except Exception as e_inner:
                logger.error(f"[SyncThreadDL] Unexpected error during extraction for {page_url} (Retry {current_retry + 1}): {e_inner}", exc_info=False) # exc_info=False برای خلاصه بودن لاگ در retry
                current_retry += 1
                if current_retry > DOWNLOAD_MAX_RETRIES:
                    logger.error(f"[SyncThreadDL] Max retries reached for {page_url} after general error.")
                    break
                time.sleep(DOWNLOAD_RETRY_DELAY_S)

    except Exception as e_outer:
        logger.error(f"[SyncThreadDL] Critical error in _sync_extract_music_link_task for {page_url}: {e_outer}", exc_info=True)
        # extracted_link_value در ابتدا None است، پس نیازی به تغییر نیست
    finally:
        logger.debug(f"[SyncThreadDL] Starting cleanup for {page_url}")
        if page_instance:
            try: page_instance.close()
            except Exception as e: logger.warning(f"[SyncThreadDL] Error closing page: {e}")
        if context_instance:
            try: context_instance.close()
            except Exception as e: logger.warning(f"[SyncThreadDL] Error closing context: {e}")
        if browser_instance:
            try: browser_instance.close()
            except Exception as e: logger.warning(f"[SyncThreadDL] Error closing browser: {e}")
        if playwright_instance:
            try: playwright_instance.stop()
            except Exception as e: logger.warning(f"[SyncThreadDL] Error stopping playwright: {e}")
        logger.info(f"[SyncThreadDL] Playwright resources closed for {page_url}. Link extracted: {extracted_link_value is not None}")

    return extracted_link_value


class MusicFetcher:
    def __init__(self, max_see_more_clicks=1): # اجازه تنظیم از خارج
        self.base_url = "https://www.ahangimo.com"
        self.max_see_more_clicks = max_see_more_clicks
        self.consecutive_failure_limit = PREVIEW_CONSECUTIVE_FAILURE_LIMIT
        self.click_delay_ms = PREVIEW_CLICK_DELAY_MS
        self.see_more_button_selector = 'div.dataloaderError.datalist1ErrorBtn > button.btn.btn-primary.w-100'
        logger.info(f"MusicFetcher initialized. Max 'See More' clicks: {self.max_see_more_clicks}")

    async def fetch_new_music_previews(self) -> List[Dict]:
        logger.info("Starting optimized music preview fetching...")
        raw_tracks_from_page: List[Dict] = []
        playwright = None
        browser = None
        context = None # اضافه شد
        page = None

        try:
            playwright = await async_playwright().start()
            logger.debug("[PreviewFetcher] Launching Chromium for previews...")
            browser_args = [
                '--disable-extensions', '--disable-gpu', '--no-sandbox',
                '--disable-dev-shm-usage', '--single-process', # تست کنید --single-process
                '--disable-setuid-sandbox', '--disable-accelerated-2d-canvas',
                '--no-zygote', '--blink-settings=imagesEnabled=false' # غیرفعال کردن تصاویر
            ]
            browser = await playwright.chromium.launch(headless=True, args=browser_args)
            logger.debug("[PreviewFetcher] Browser launched for previews.")
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",
                ignore_https_errors=True,
            )
            logger.debug("[PreviewFetcher] Browser context created for previews.")
            page = await context.new_page()
            logger.debug("[PreviewFetcher] New page created for previews.")

            # بلاک کردن منابع غیر ضروری برای صفحه پیش‌نمایش هم مفید است
            def block_preview_resources(route):
                if route.request.resource_type in ["font", "media", "websocket", "other", "manifest", "texttrack"]:
                    return route.abort()
                # برای صفحه پیش‌نمایش ممکن است به تصاویر کوچک یا CSS نیاز باشد، پس با احتیاط بلاک کنید.
                # if route.request.resource_type == "image" and "thumbnail" not in route.request.url:
                #    return route.abort()
                return route.continue_()
            await page.route("**/*", block_preview_resources)
            logger.debug("[PreviewFetcher] Resource blocking rule set for previews page.")

            main_page_url = f"{self.base_url}/new_music"
            logger.info(f"[PreviewFetcher] Navigating to: {main_page_url}")
            await page.goto(main_page_url, timeout=PREVIEW_PAGE_TIMEOUT_MS, wait_until='domcontentloaded')
            logger.info(f"[PreviewFetcher] Navigation to {main_page_url} complete.")

            consecutive_see_more_failures = 0
            for i in range(self.max_see_more_clicks):
                logger.info(f"[PreviewFetcher] Attempting 'See More' click {i+1}/{self.max_see_more_clicks}")
                if await self._attempt_click_see_more_internal(page, self.click_delay_ms):
                    logger.info(f"[PreviewFetcher] 'See More' click {i+1} successful.")
                    consecutive_see_more_failures = 0
                    # پس از هر کلیک موفق، کمی صبر می‌کنیم تا محتوای جدید بارگذاری شود
                    await asyncio.sleep(self.click_delay_ms / 1000 * 0.75) # 75% از تاخیر کلیک
                else:
                    logger.warning(f"[PreviewFetcher] 'See More' click {i+1} failed or button not found.")
                    consecutive_see_more_failures += 1
                    if consecutive_see_more_failures >= self.consecutive_failure_limit:
                        logger.warning(f"[PreviewFetcher] Reached consecutive 'See More' failure limit ({self.consecutive_failure_limit}). Stopping clicks.")
                        break
                    await asyncio.sleep(self.click_delay_ms / 1000 * 0.5) # تاخیر کمتر در صورت عدم موفقیت

            track_elements_selector = 'a[href*="/track/"]' # انتخابگر شما برای لینک‌های آهنگ
            logger.debug(f"[PreviewFetcher] Querying for track elements with selector: {track_elements_selector}")
            elements = await page.query_selector_all(track_elements_selector)
            logger.info(f"[PreviewFetcher] Found {len(elements)} track elements on page after 'See More' clicks.")

            for el_idx, el in enumerate(elements):
                link = await el.get_attribute('href')
                if not link or not link.strip().startswith("/track/"): # فیلتر اولیه برای لینک‌های معتبر
                    logger.debug(f"[PreviewFetcher] Element {el_idx}: Invalid or missing link: '{link}'. Skipping.")
                    continue
                
                track_detail = {'link': urllib.parse.urljoin(self.base_url, link), 'download_link': None}

                # استفاده از try-except برای هر بخش استخراج برای جلوگیری از خطای کلی
                try:
                    en_title_el = await el.query_selector('h4.musicItemBoxSubTitle')
                    if en_title_el:
                        en_name, en_track = _parse_html_title_parts(await en_title_el.inner_html())
                        track_detail['en_name'] = en_name
                        track_detail['en_track'] = en_track
                except Exception as e_en:
                    logger.warning(f"[PreviewFetcher] Element {el_idx}: Error parsing EN title for {link}: {e_en}")

                try:
                    fa_title_el = await el.query_selector('h4.musicItemBoxTitle')
                    if fa_title_el:
                        fa_track_val, fa_name_val = _parse_html_title_parts(await fa_title_el.inner_html())
                        track_detail['fa_track'] = fa_track_val
                        track_detail['fa_name'] = fa_name_val
                except Exception as e_fa:
                    logger.warning(f"[PreviewFetcher] Element {el_idx}: Error parsing FA title for {link}: {e_fa}")

                for key_default in ['en_name', 'en_track', 'fa_name', 'fa_track']:
                    if key_default not in track_detail:
                        track_detail[key_default] = "N/A"
                
                raw_tracks_from_page.append(track_detail)
            logger.info(f"Fetched {len(raw_tracks_from_page)} valid raw track previews.")

        except PlaywrightAsyncTimeoutError as e_timeout:
            logger.error(f"[PreviewFetcher] Playwright timeout during preview fetching: {str(e_timeout)}")
            if page: await page.screenshot(path='debug_fetch_previews_timeout.png')
        except PlaywrightAsyncError as e_playwright:
            logger.error(f"[PreviewFetcher] Generic Playwright error during preview fetching: {str(e_playwright)}")
            if page: await page.screenshot(path='debug_fetch_previews_playwright_error.png')
        except Exception as e:
            logger.error(f"[PreviewFetcher] Critical error during music preview fetching: {e}", exc_info=True)
            if page: await page.screenshot(path='debug_fetch_previews_general_error.png')
        finally:
            logger.debug("[PreviewFetcher] Starting cleanup for previews.")
            if page:
                try: await page.close()
                except Exception as e_cp: logger.warning(f"[PreviewFetcher] Error closing page: {e_cp}")
            if context:
                try: await context.close()
                except Exception as e_cc: logger.warning(f"[PreviewFetcher] Error closing context: {e_cc}")
            if browser:
                try: await browser.close()
                except Exception as e_cb: logger.warning(f"[PreviewFetcher] Error closing browser: {e_cb}")
            if playwright:
                try: await playwright.stop()
                except Exception as e_spw: logger.warning(f"[PreviewFetcher] Error stopping playwright: {e_spw}")
            logger.info("[PreviewFetcher] Preview fetching Playwright resources closed.")
        return raw_tracks_from_page

    async def _attempt_click_see_more_internal(self, page, click_delay_ms: int) -> bool:
        try:
            button = await page.query_selector(self.see_more_button_selector)
            if button and await button.is_visible(timeout=5000) and await button.is_enabled(timeout=5000): # افزایش تایم‌اوت برای is_visible/is_enabled
                logger.debug("[PreviewFetcher] 'See More' button found and clickable. Clicking...")
                await button.click(timeout=CLICK_TIMEOUT_MS) # تایم‌اوت برای کلیک
                # پس از کلیک، برای بارگذاری محتوای جدید صبر می‌کنیم
                # استفاده از page.wait_for_load_state('networkidle', timeout=click_delay_ms) می‌تواند بهتر باشد
                # اما برای سادگی فعلاً از wait_for_timeout استفاده می‌کنیم.
                await page.wait_for_timeout(click_delay_ms) 
                logger.debug("[PreviewFetcher] Waited after 'See More' click.")
                return True
            logger.debug("[PreviewFetcher] 'See More' button not found, not visible, or not enabled.")
            return False
        except PlaywrightAsyncTimeoutError:
            logger.warning("[PreviewFetcher] Timeout during 'See More' button interaction (visibility, enabled, or click).")
            return False
        except Exception as e:
            logger.error(f"[PreviewFetcher] Error interacting with 'See More' button: {e}")
            return False

    async def get_single_track_download_link(self, track_page_relative_url: str) -> Optional[str]:
        if not track_page_relative_url:
            logger.warning("get_single_track_download_link called with empty URL.")
            return None

        full_page_url = track_page_relative_url
        if isinstance(track_page_relative_url, str) and track_page_relative_url.startswith('/'):
            full_page_url = urllib.parse.urljoin(self.base_url, track_page_relative_url)
        elif not isinstance(track_page_relative_url, str) or not track_page_relative_url.startswith(('http://', 'https://')):
            logger.error(f"Invalid track_page_relative_url format: {track_page_relative_url}")
            return None # یا یک مقدار خطای مشخص

        logger.info(f"Preparing to extract download link for: {full_page_url}")
        
        try:
            # اجرای تابع همگام (sync) در یک ترد جداگانه برای جلوگیری از بلاک شدن event loop اصلی
            loop = asyncio.get_running_loop()
            download_link = await loop.run_in_executor(
                None,  # استفاده از ThreadPoolExecutor پیش‌فرض
                _sync_extract_music_link_task,
                full_page_url,
                self.base_url
            )
            
            if download_link:
                logger.info(f"Successfully processed {full_page_url}. Extracted link: {download_link is not None}")
            else:
                logger.warning(f"Failed to extract download link for {full_page_url} after all attempts in sync task.")
            return download_link
        except Exception as e:
            logger.error(f"Error in get_single_track_download_link calling to_thread for {full_page_url}: {e}", exc_info=True)
            return None # یا مقدار خطای مشخص "FAILED_TO_EXTRACT"

# --- END OF FILE services/music_fetcher.py ---