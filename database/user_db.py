import sqlite3
import json
from config import logger # استفاده از لاگر مرکزی

class DatabaseHandler:
    def __init__(self, db_name: str):
        self.db_name = db_name
        try:
            self._ensure_table_and_columns()
            logger.info(f"DatabaseHandler for '{db_name}' initialized successfully.")
        except Exception as e:
            logger.critical(f"CRITICAL - Failed to initialize DatabaseHandler for '{db_name}': {e}", exc_info=True)
            raise

    def _ensure_table_and_columns(self):
        # logger.debug(f"DatabaseHandler ({self.db_name}): Ensuring 'users' table.") # لاگ دیباگ اختیاری
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT,
                    last_name TEXT,
                    username TEXT,
                    singer_names TEXT,
                    sent_music TEXT
                )
            ''')
            conn.commit()

    def get_connection(self):
        conn = sqlite3.connect(self.db_name, timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
        except sqlite3.Error as e_wal:
            logger.warning(f"DatabaseHandler ({self.db_name}): Could not set WAL mode: {e_wal}")
        return conn

    def load_user_data(self) -> dict:
        logger.info(f"DatabaseHandler ({self.db_name}): Loading all user data...")
        users_data = {}
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, first_name, last_name, username, singer_names, sent_music FROM users")
                rows = cursor.fetchall()
            for row in rows:
                user_id = str(row['user_id'])
                users_data[user_id] = {
                    "first_name": row['first_name'],
                    "last_name": row['last_name'],
                    "username": row['username'],
                    "singer_names": json.loads(row['singer_names']) if row['singer_names'] else [],
                    "sent_music": json.loads(row['sent_music']) if row['sent_music'] else [],
                }
            logger.info(f"DatabaseHandler ({self.db_name}): Loaded data for {len(users_data)} users.")
        except Exception as e:
            logger.error(f"DatabaseHandler ({self.db_name}): Error loading user data: {e}", exc_info=True)
            # در صورت خطا، یک دیکشنری خالی برگردانده می‌شود، UserManager باید این را مدیریت کند
        return users_data

    def save_user_data(self, users_data: dict):
        if not users_data: # اگر چیزی برای ذخیره نیست، لاگ کن و خارج شو
            logger.info(f"DatabaseHandler ({self.db_name}): No user data provided to save.")
            return
            
        logger.info(f"DatabaseHandler ({self.db_name}): Saving data for {len(users_data)} users...")
        try:
            with self.get_connection() as conn:
                # استفاده از یک تراکنش برای بهبود عملکرد در صورت تعداد زیاد کاربر
                cursor = conn.cursor()
                # conn.execute("BEGIN TRANSACTION;") # شروع تراکنش (اختیاری، context manager خودش commit/rollback می‌کند)
                for user_id, data in users_data.items():
                    cursor.execute('''
                        INSERT OR REPLACE INTO users (user_id, first_name, last_name, username, singer_names, sent_music)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (int(user_id), data.get("first_name"), data.get("last_name"), data.get("username"),
                          json.dumps(data.get("singer_names", []), ensure_ascii=False),
                          json.dumps(data.get("sent_music", []), ensure_ascii=False)
                         ))
                # conn.commit() # در صورت استفاده از BEGIN TRANSACTION، اینجا commit لازم است
                # اما context manager در انتها commit می‌کند
            logger.info(f"DatabaseHandler ({self.db_name}): User data saved successfully.")
        except Exception as e:
            logger.error(f"DatabaseHandler ({self.db_name}): Error saving user data: {e}", exc_info=True)
            # اینجا هم شاید بهتر باشد خطا را raise کنید تا UserManager متوجه شود ذخیره ناموفق بوده
            # raise