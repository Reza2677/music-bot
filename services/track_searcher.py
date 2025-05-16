from typing import List, Dict
from ..config import logger
from ..database import TrackDatabaseHandler
from ..utils.helpers import is_english # تابع کمکی



class TrackSearcher:
    def __init__(self, track_db_handler: 'TrackDatabaseHandler'): # اضافه کردن Type hint در '' برای جلوگیری از circular import
        self.track_db_handler = track_db_handler

    async def search_tracks_by_singer_list(self, search_list: List[Dict]) -> List[Dict]:
        logger.info(f"Starting track search for list: {search_list}")
        all_found_tracks_details = []
        
        # --- تغییر کلیدی اینجا ---
        available_tracks = await self.track_db_handler.load_tracks() # اضافه کردن await
        # --------------------------
        
        if not available_tracks: # حالا available_tracks یک لیست است یا None/[]
            logger.warning("No tracks available in the database to search from.")
            return []

        for search_item in search_list:
            if not isinstance(search_item, dict) or "name" not in search_item or "count" not in search_item:
                logger.warning(f"Invalid search item format: {search_item}. Skipping.")
                continue

            singer_name = search_item["name"]
            try:
                desired_count = int(search_item["count"])
                if desired_count <= 0:
                    logger.warning(f"Invalid count '{search_item['count']}' for singer '{singer_name}'. Defaulting to 1.")
                    desired_count = 1
            except ValueError:
                logger.warning(f"Non-integer count '{search_item['count']}' for singer '{singer_name}'. Defaulting to 1.")
                desired_count = 1
            
            # logger.info(f"Searching for {desired_count} track(s) by '{singer_name}'...")
            
            found_for_singer = []
            singer_name_lower = singer_name.lower()

            for track in available_tracks: # حالا این حلقه باید درست کار کند
                match_en = track.get("en_name", "").lower() == singer_name_lower
                match_fa = track.get("fa_name", "").lower() == singer_name_lower
                
                if match_en or match_fa:
                    if track.get("download_link") and track["download_link"] != "N/A" and track["download_link"] is not None : # اطمینان از اینکه None هم نیست
                        found_for_singer.append(track)
            
            # مرتب‌سازی بر اساس ID (جدیدترین‌ها اول) - load_tracks باید این کار را انجام داده باشد
            # اگر load_tracks بر اساس created_at DESC, id DESC مرتب می‌کند، نیازی به مرتب‌سازی مجدد نیست
            selected_tracks = found_for_singer[:desired_count]
            
            if selected_tracks:
                # logger.info(f"Found {len(selected_tracks)} track(s) for '{singer_name}'.")
                all_found_tracks_details.extend(selected_tracks)
            # else:
                # logger.info(f"No tracks found for '{singer_name}'.")
                
        logger.info(f"Track search completed. Total unique tracks matching criteria: {len(all_found_tracks_details)}")
        return all_found_tracks_details