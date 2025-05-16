# import sqlite3
# # from ..config import logger # اگر نیاز به لاگ مستقیم در اینجا بود

# class TrackDatabaseHandler:
#     def __init__(self, db_name):
#         self.db_name = db_name
#         self.create_tracks_table()

#     def get_connection(self):
#         return sqlite3.connect(self.db_name)

#     def create_tracks_table(self):
#         with self.get_connection() as conn:
#             cursor = conn.cursor()
#             cursor.execute('''
#                 CREATE TABLE IF NOT EXISTS tracks (
#                     id INTEGER PRIMARY KEY AUTOINCREMENT,
#                     link TEXT UNIQUE,
#                     en_name TEXT,
#                     en_track TEXT,
#                     fa_name TEXT,
#                     fa_track TEXT,
#                     download_link TEXT
#                 )
#             ''')
#             conn.commit()

#     def save_tracks(self, tracks):
#         with self.get_connection() as conn:
#             cursor = conn.cursor()
#             for track in tracks:
#                 cursor.execute('''
#                     INSERT OR IGNORE INTO tracks (link, en_name, en_track, fa_name, fa_track, download_link)
#                     VALUES (?, ?, ?, ?, ?, ?)
#                 ''', (track['link'], track['en_name'], track['en_track'], track['fa_name'], track['fa_track'], track.get('download_link', 'N/A')))
#             conn.commit()

#     def load_tracks(self):
#         with self.get_connection() as conn:
#             cursor = conn.cursor()
#             cursor.execute("SELECT link, en_name, en_track, fa_name, fa_track, download_link FROM tracks ORDER BY id DESC")
#             rows = cursor.fetchall()
#             # تبدیل ردیف‌ها به دیکشنری
#             return [dict(zip(['link', 'en_name', 'en_track', 'fa_name', 'fa_track', 'download_link'], row)) for row in rows]

#     def get_track_by_link(self, link: str):
#         with self.get_connection() as conn:
#             cursor = conn.cursor()
#             cursor.execute("SELECT * FROM tracks WHERE link = ?", (link,))
#             row = cursor.fetchone()
#             if row:
#                 return dict(zip(['id', 'link', 'en_name', 'en_track', 'fa_name', 'fa_track', 'download_link'], row))
#             return None

#     def update_track_download_link(self, link: str, download_link: str):
#         with self.get_connection() as conn:
#             cursor = conn.cursor()
#             cursor.execute("UPDATE tracks SET download_link = ? WHERE link = ?", (download_link, link))
#             conn.commit()






# music_bot/database/track_db.py
import sqlite3
import os
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class TrackDatabaseHandler:
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.db_path = os.path.abspath(db_name)
        self._ensure_table_and_columns() # تغییر نام برای وضوح

    def _ensure_table_and_columns(self): # قبلا _init_db
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir)
            except OSError as e:
                logger.error(f"Could not create directory {db_dir}: {e}")
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
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
            # اطمینان از وجود ستون created_at (مهم برای کد جدید)
            cursor.execute("PRAGMA table_info(tracks)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'created_at' not in columns:
                try:
                    cursor.execute("ALTER TABLE tracks ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                    logger.info("Added 'created_at' column to tracks table.")
                except sqlite3.OperationalError as e:
                    logger.warning(f"Could not add 'created_at' column, might already exist or other issue: {e}")
            conn.commit()

    @contextmanager
    def get_connection(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            yield conn
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database error on {self.db_path}: {e}", exc_info=True)
            if conn: conn.rollback()
            raise
        finally:
            if conn: conn.close()

    # --- متدهای جدید یا اصلاح شده بر اساس کد شما ---
    async def get_all_links_as_set(self) -> set:
        links_set = set()
        try:
            with self.get_connection() as conn:
                cursor = conn.execute('SELECT link FROM tracks')
                for row in cursor.fetchall():
                    if row['link']: # فقط لینک‌های غیر None/empty
                        links_set.add(row['link'])
            # logger.info(f"Fetched {len(links_set)} existing links from {self.db_path} into a set.")
        except Exception as e:
            logger.error(f"Error in get_all_links_as_set ({self.db_path}): {e}", exc_info=True)
        return links_set

    async def get_total_tracks(self) -> int:
        count = 0
        try:
            with self.get_connection() as conn:
                cursor = conn.execute('SELECT COUNT(*) as count FROM tracks')
                row = cursor.fetchone()
                count = row['count'] if row else 0
        except Exception as e:
            logger.error(f"Error in get_total_tracks ({self.db_path}): {e}", exc_info=True)
        return count

    async def save_tracks(self, tracks_data_list: list) -> int:
        """
        درج دسته‌ای آهنگ‌ها با استفاده از INSERT OR IGNORE.
        tracks_data_list: لیستی از دیکشنری‌ها.
        """
        if not tracks_data_list:
            return 0
        
        # تبدیل به لیست تاپل‌ها و اطمینان از وجود کلیدها
        data_to_insert = []
        for track in tracks_data_list:
            data_to_insert.append((
                track.get('link'),
                track.get('en_name'),
                track.get('en_track'),
                track.get('fa_name'),
                track.get('fa_track'),
                track.get('download_link') # باید None باشد در این مرحله
            ))
        
        inserted_count = 0
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany('''
                    INSERT OR IGNORE INTO tracks (link, en_name, en_track, fa_name, fa_track, download_link)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', data_to_insert)
                inserted_count = cursor.rowcount
                if inserted_count > 0:
                    logger.info(f"Bulk inserted {inserted_count} new unique tracks into {self.db_path}.")
                # else:
                #    logger.info(f"No new tracks were inserted (duplicates or empty list) into {self.db_path}.")
        except Exception as e:
            logger.error(f"Error during bulk insert (save_tracks) into {self.db_path}: {e}", exc_info=True)
        return inserted_count

    # --- متدهای موجود که هنوز لازم هستند ---
    async def load_tracks(self) -> list:
        tracks = []
        try:
            with self.get_connection() as conn:
                # مرتب سازی بر اساس created_at (جدیدترین ها اول)
                cursor = conn.execute("SELECT id, link, en_name, en_track, fa_name, fa_track, download_link, created_at FROM tracks ORDER BY created_at DESC, id DESC")
                tracks = [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error in load_tracks from {self.db_path}: {e}", exc_info=True)
        return tracks
        
    async def get_track_by_link(self, link: str):
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM tracks WHERE link = ? LIMIT 1", (link,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
        except Exception as e:
             logger.error(f"Error in get_track_by_link ({link}) for {self.db_path}: {e}", exc_info=True)
        return None

    async def update_track_download_link(self, link: str, download_link: str) -> bool:
        # این متد توسط اسکریپت دوم (پردازشگر لینک دانلود) استفاده خواهد شد
        updated_rows = 0
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE tracks SET download_link = ? WHERE link = ?", (download_link, link))
                updated_rows = cursor.rowcount
            return updated_rows > 0
        except Exception as e:
            logger.error(f"Error updating download link for {link} in {self.db_path}: {e}", exc_info=True)
            return False