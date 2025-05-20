



import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightAsyncTimeoutError
from config import logger # logger از config ربات
import time 
import urllib.parse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightSyncTimeoutError # استفاده از sync_api و تغییر نام TimeoutError
from typing import List, Dict, Optional

def _parse_html_title_parts(html_content: str) -> tuple[str, str]:
    if not html_content:
        return "N/A", "N/A"
    parts = html_content.replace('<br>', '\n').strip().split('\n')
    part1 = parts[0].strip() if len(parts) > 0 else "N/A"
    part2 = parts[1].strip() if len(parts) > 1 else "N/A"
    return part1, part2

DOWNLOAD_MAX_RETRIES = 2
DOWNLOAD_RETRY_DELAY_S = 3

def _sync_extract_music_link_task(page_url: str, base_music_url: str) -> Optional[str]:
    playwright_instance = None
    browser_instance = None
    page_instance = None
    extracted_link_value = None

    try:
        playwright_instance = sync_playwright().start()
        browser_instance = playwright_instance.chromium.launch(headless=True, 
            args=['--disable-extensions', '--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage'])
        page_instance = browser_instance.new_page()
        page_instance.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })

        page_instance.goto(page_url, wait_until="domcontentloaded", timeout=60000)
        page_instance.wait_for_timeout(1000) # ms

        online_play_button_selector = "button.pflikebtn.likedBtnNotActive.justify-content-center.w-100"
        download_link_selector = "#downloadTrackBtn > a"

        current_retry = 0
        while current_retry <= DOWNLOAD_MAX_RETRIES:
            try:
                page_instance.wait_for_selector(online_play_button_selector, timeout=20000, state="visible")
                play_button_element = page_instance.query_selector(online_play_button_selector)
                if not play_button_element:
                    raise PlaywrightSyncTimeoutError("Play button not found")

                play_button_element.scroll_into_view_if_needed()
                page_instance.wait_for_timeout(300) # ms
                play_button_element.click(timeout=15000)

                page_instance.wait_for_selector(download_link_selector, timeout=30000, state="visible")
                download_link_element = page_instance.query_selector(download_link_selector)
                
                if download_link_element:
                    for _attempt in range(3): # Renamed attempt to _attempt
                        link = download_link_element.get_attribute('href')
                        if link and link.strip() and link != "#" and "javascript:void(0)" not in link:
                            if not link.startswith(('http://', 'https://')):
                                if link.startswith('/'):
                                    link = urllib.parse.urljoin(base_music_url, link)
                                else:
                                    link = None 
                            
                            if link and link.startswith(('http://', 'https://')):
                                extracted_link_value = link
                                break 
                    if extracted_link_value:
                        break 
                
                if not extracted_link_value:
                    raise PlaywrightSyncTimeoutError("Href not extracted")

            except PlaywrightSyncTimeoutError as pte:
                logger.warning(f"[SyncThread] Playwright Timeout on {page_url} (Retry {current_retry}/{DOWNLOAD_MAX_RETRIES}): {pte}")
                current_retry += 1
                if current_retry > DOWNLOAD_MAX_RETRIES:
                    logger.error(f"[SyncThread] Max retries reached for {page_url}. Failed to extract link.")
                    break
                logger.info(f"[SyncThread] Retrying in {DOWNLOAD_RETRY_DELAY_S}s...")
                time.sleep(DOWNLOAD_RETRY_DELAY_S)
            except Exception as e_inner:
                logger.error(f"[SyncThread] Unexpected error during extraction for {page_url} (Retry {current_retry}): {e_inner}", exc_info=True)
                current_retry += 1
                if current_retry > DOWNLOAD_MAX_RETRIES:
                    logger.error(f"[SyncThread] Max retries reached for {page_url} after general error.")
                    break
                time.sleep(DOWNLOAD_RETRY_DELAY_S)
        
    except Exception as e_outer:
        logger.error(f"[SyncThread] Critical error in _sync_extract_music_link_task for {page_url}: {e_outer}", exc_info=True)
        extracted_link_value = None
    finally:
        if page_instance: page_instance.close()
        if browser_instance: browser_instance.close()
        if playwright_instance: playwright_instance.stop()
        logger.info(f"[SyncThread] Playwright resources closed for {page_url}")

    return extracted_link_value

class MusicFetcher:
    def __init__(self):
        self.base_url = "https://www.ahangimo.com"
        self.max_see_more_clicks = 1 # Example value, adjust as needed
        self.consecutive_failure_limit = 3
        self.click_delay_ms = 2000
        self.see_more_button_selector = 'div.dataloaderError.datalist1ErrorBtn > button.btn.btn-primary.w-100'


    async def fetch_new_music_previews(self) -> List[Dict]:
        logger.info("Starting optimized music preview fetching...")
        raw_tracks_from_page: List[Dict] = []
        playwright = None
        browser = None
        page = None # Define page here to ensure it's available in finally

        try:
            playwright = await async_playwright().start()
            browser_args = ['--disable-extensions', '--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage']
            browser = await playwright.chromium.launch(headless=True, args=browser_args)
            page = await browser.new_page()
            
            await page.goto(f"{self.base_url}/new_music", timeout=60000, wait_until='networkidle')
            
            consecutive_see_more_failures = 0
            for i in range(self.max_see_more_clicks):
                logger.info(f"Attempting 'See More' click {i+1}/{self.max_see_more_clicks}")
                if await self._attempt_click_see_more_internal(page, self.click_delay_ms):
                    logger.info(f"'See More' click {i+1} successful.")
                    consecutive_see_more_failures = 0
                else:
                    logger.warning(f"'See More' click {i+1} failed.")
                    consecutive_see_more_failures += 1
                    if consecutive_see_more_failures >= self.consecutive_failure_limit:
                        logger.warning(f"Reached consecutive 'See More' failure limit ({self.consecutive_failure_limit}). Stopping clicks.")
                        break
                    await asyncio.sleep(self.click_delay_ms / 1000) 

            track_elements_selector = 'a[href*="/track/"]'
            elements = await page.query_selector_all(track_elements_selector)
            logger.info(f"Found {len(elements)} track elements on page after 'See More' clicks.")
            
            for el in elements:
                link = await el.get_attribute('href')
                if not link: continue
                track_detail = {'link': link, 'download_link': None} # download_link is initially None
                
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
            logger.info(f"Fetched {len(raw_tracks_from_page)} raw track previews.")

        except Exception as e:
            logger.error(f"Critical error during music preview fetching: {e}", exc_info=True)
            if page: # Screenshot for debugging if page exists
                 await page.screenshot(path='debug_fetch_previews_error.png')
        finally:
            if page: await page.close()
            if browser: await browser.close()
            if playwright: await playwright.stop()
        return raw_tracks_from_page

    async def _attempt_click_see_more_internal(self, page, click_delay_ms) -> bool:
        try:
            button = await page.query_selector(self.see_more_button_selector)
            if button and await button.is_visible() and await button.is_enabled():
                await button.click(timeout=10000)
                # Wait for potential content loading; networkidle might be too long here
                await page.wait_for_timeout(click_delay_ms / 2) # Wait half the delay
                return True
            logger.debug("See More button not found or not clickable.")
            return False
        except PlaywrightAsyncTimeoutError: 
            logger.warning("Timeout clicking 'See More' button.")
            return False
        except Exception as e: 
            logger.error(f"Error clicking 'See More' button: {e}")
            return False

    async def get_single_track_download_link(self, track_page_relative_url: str) -> Optional[str]:
        if not track_page_relative_url:
            return None

        full_page_url = track_page_relative_url
        if track_page_relative_url.startswith('/'):
            full_page_url = urllib.parse.urljoin(self.base_url, track_page_relative_url)
        
        logger.info(f"Attempting to extract download link for: {full_page_url}")
        
        try:
            download_link = await asyncio.to_thread(
                _sync_extract_music_link_task, 
                full_page_url,
                self.base_url 
            )
            
            if download_link:
                logger.info(f"Successfully extracted download link for {track_page_relative_url}: {download_link}")
            else:
                logger.warning(f"Failed to extract download link for {track_page_relative_url} after all retries.")
            return download_link
        except Exception as e:
            logger.error(f"Error calling to_thread for {full_page_url}: {e}", exc_info=True)
            return None