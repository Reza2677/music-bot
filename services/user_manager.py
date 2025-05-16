from ..database import DatabaseHandler # از __init__.py در database ایمپورت می‌شود
# from ..config import logger # اگر نیاز به لاگ مستقیم در اینجا بود

class UserManager:
    def __init__(self, db_handler: DatabaseHandler):
        self.db_handler = db_handler
        self.users_data = self.db_handler.load_user_data() # بارگذاری اولیه

    def get_user(self, user_id: str):
        return self.users_data.get(user_id)

    def add_or_update_user_info(self, user_id: str, first_name: str, last_name: str, username: str):
        """Adds a new user or updates existing user's name details if they change."""
        user_id_str = str(user_id)
        if user_id_str not in self.users_data:
            self.users_data[user_id_str] = {
                "first_name": first_name,
                "last_name": last_name,
                "username": username,
                "singer_names": [],
                "sent_music": [],
                "sent_time": "02:00"  # Default time
            }
            # logger.info(f"New user added: {user_id_str} - {username}")
        else: # Update names if changed
            changed = False
            if self.users_data[user_id_str].get("first_name") != first_name:
                self.users_data[user_id_str]["first_name"] = first_name
                changed = True
            if self.users_data[user_id_str].get("last_name") != last_name:
                self.users_data[user_id_str]["last_name"] = last_name
                changed = True
            if self.users_data[user_id_str].get("username") != username:
                self.users_data[user_id_str]["username"] = username
                changed = True
            # if changed:
                # logger.info(f"User info updated for: {user_id_str} - {username}")

        self.save_all_users_data() # ذخیره تغییرات

    def update_user_specific_data(self, user_id: str, data: dict):
        user_id_str = str(user_id)
        if user_id_str in self.users_data:
            self.users_data[user_id_str].update(data)
            self.save_all_users_data() # ذخیره تغییرات
            # logger.info(f"Data updated for user {user_id_str}: {data}")
        # else:
            # logger.warning(f"Attempted to update non-existent user: {user_id_str}")

    def get_all_users(self):
        return self.users_data

    def save_all_users_data(self):
        """Saves all current user data to the database."""
        self.db_handler.save_user_data(self.users_data)