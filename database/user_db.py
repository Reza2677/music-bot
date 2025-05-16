import sqlite3
import json
# from ..config import logger # اگر نیاز به لاگ مستقیم در اینجا بود

class DatabaseHandler:
    def __init__(self, db_name):
        self.db_name = db_name
        self.create_users_table()

    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn

    def create_users_table(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT,
                    last_name TEXT,
                    username TEXT,
                    singer_names TEXT,
                    sent_music TEXT,
                    sent_time TEXT DEFAULT "02:00"
                )
            ''')
            conn.commit()

    def load_user_data(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            rows = cursor.fetchall()
        users_data = {}
        for row in rows:
            user_id = str(row['user_id'])
            users_data[user_id] = {
                "first_name": row['first_name'],
                "last_name": row['last_name'],
                "username": row['username'],
                "singer_names": json.loads(row['singer_names']) if row['singer_names'] else [],
                "sent_music": json.loads(row['sent_music']) if row['sent_music'] else [],
                "sent_time": row['sent_time'] if row['sent_time'] else "02:00"
            }
        return users_data

    def save_user_data(self, users_data):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for user_id, data in users_data.items():
                cursor.execute('''
                    INSERT OR REPLACE INTO users (user_id, first_name, last_name, username, singer_names, sent_music, sent_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (int(user_id), data["first_name"], data["last_name"], data["username"], 
                      json.dumps(data["singer_names"], ensure_ascii=False), 
                      json.dumps(data["sent_music"], ensure_ascii=False), 
                      data.get("sent_time", "02:00")))
            conn.commit()