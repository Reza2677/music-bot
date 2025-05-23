import asyncio
import sqlite3
import os
import logging
from contextlib import contextmanager
from config import logger # استفاده از لاگر مرکزی

class TrackDatabaseHandler:
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.db_path = os.path.abspath(db_name)
        self._ensure_table_and_columns() 

    def _ensure_table_and_columns(self):
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
            conn = sqlite3.connect(self.db_path, timeout=15) # افزایش timeout
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
            except sqlite3.Error as e_wal:
                logger.warning(f"TrackDatabaseHandler ({self.db_path}): Could not set WAL mode: {e_wal}")
            yield conn
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database error on {self.db_path}: {e}", exc_info=True)
            if conn: conn.rollback()
            raise
        finally:
            if conn: conn.close()

    def _execute_get_all_links_sync(self):
        links_set_sync = set()
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT link FROM tracks')
            for row in cursor.fetchall():
                if row['link']:
                    links_set_sync.add(row['link'])
        return links_set_sync

    async def get_all_links_as_set(self) -> set:
        links_set = set()
        try:
            links_set = await asyncio.to_thread(self._execute_get_all_links_sync)
            # logger.debug(f"Fetched {len(links_set)} existing links from {self.db_path} into a set.") # لاگ دیباگ
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
        if not tracks_data_list:
            return 0
        
        data_to_insert = []
        for track in tracks_data_list:
            data_to_insert.append((
                track.get('link'), track.get('en_name'), track.get('en_track'),
                track.get('fa_name'), track.get('fa_track'), track.get('download_link')
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
        except Exception as e:
            logger.error(f"Error during bulk insert (save_tracks) into {self.db_path}: {e}", exc_info=True)
        return inserted_count

    async def load_tracks(self) -> list:
        tracks = []
        try:
            with self.get_connection() as conn:
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
                return dict(row) if row else None
        except Exception as e:
             logger.error(f"Error in get_track_by_link ({link}) for {self.db_path}: {e}", exc_info=True)
        return None

    async def update_track_download_link(self, link: str, download_link: str) -> bool:
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

    async def get_all_unique_singer_names(self) -> set[str]:
        """تمام نام‌های خوانندگان (فارسی و انگلیسی) را به صورت یک مجموعه از رشته‌ها برمی‌گرداند."""
        singer_names = set()
        logger.debug(f"TrackDatabaseHandler ({self.db_name}): Fetching all unique singer names...")
        try:
            with self.get_connection() as conn:
                # خواندن نام‌های فارسی
                cursor_fa = conn.execute("SELECT DISTINCT fa_name FROM tracks WHERE fa_name IS NOT NULL AND fa_name != '' AND fa_name != 'N/A'")
                for row in cursor_fa.fetchall():
                    singer_names.add(row['fa_name'].strip())
                
                # خواندن نام‌های انگلیسی
                cursor_en = conn.execute("SELECT DISTINCT en_name FROM tracks WHERE en_name IS NOT NULL AND en_name != '' AND en_name != 'N/A'")
                for row in cursor_en.fetchall():
                    singer_names.add(row['en_name'].strip())
            logger.info(f"TrackDatabaseHandler ({self.db_name}): Fetched {len(singer_names)} unique singer names.")
        except Exception as e:
            logger.error(f"TrackDatabaseHandler ({self.db_name}): Error fetching unique singer names: {e}", exc_info=True)
        return singer_names