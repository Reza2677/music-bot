from typing import List, Dict
from config import logger
from database.track_db import TrackDatabaseHandler
# from music_bot.utils.helpers import is_english # is_english استفاده نشده است، فعلا کامنت می‌شود

class TrackSearcher:
    def __init__(self, track_db_handler: TrackDatabaseHandler): 
        self.track_db_handler = track_db_handler

    async def search_tracks_by_singer_list(self, search_list: List[Dict]) -> List[Dict]:
        logger.info(f"Starting track search for list: {search_list}")
        all_found_tracks_details = []
        
        available_tracks = await self.track_db_handler.load_tracks()
        
        if not available_tracks:
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
            
            found_for_singer = []
            singer_name_lower = singer_name.lower()

            for track in available_tracks:
                match_en = track.get("en_name", "").lower() == singer_name_lower
                match_fa = track.get("fa_name", "").lower() == singer_name_lower
                
                if match_en or match_fa:
                    # Ensure download_link is valid and not None or "N/A"
                    dl_link = track.get("download_link")
                    if dl_link and dl_link not in ["N/A", "FAILED_ON_JOB", None, ""]: # Check for various invalid states
                        found_for_singer.append(track)
            
            selected_tracks = found_for_singer[:desired_count] # Already sorted by load_tracks
            
            if selected_tracks:
                all_found_tracks_details.extend(selected_tracks)
                
        logger.info(f"Track search completed. Total unique tracks matching criteria: {len(all_found_tracks_details)}")
        # Ensure unique tracks if a track could match multiple singers in search_list (though unlikely with current logic)
        # This can be done by converting to a list of tuples (for hashing) then to set and back to list of dicts, or more simply:
        unique_tracks_by_link = {track['link']: track for track in all_found_tracks_details}
        return list(unique_tracks_by_link.values())