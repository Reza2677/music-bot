from music_bot.database.user_db import DatabaseHandler
from music_bot.config import logger

class UserManager:
    def __init__(self, db_handler: DatabaseHandler):
        logger.info("UserManager: Initializing...")
        try:
            if not isinstance(db_handler, DatabaseHandler):
                # این خطا باید در تست‌ها یا مراحل اولیه توسعه مشخص شود.
                logger.critical("UserManager: CRITICAL - Received an invalid db_handler instance.")
                raise ValueError("Invalid db_handler provided to UserManager")
            
            self.db_handler = db_handler
            self.users_data = self.db_handler.load_user_data()
            logger.info(f"UserManager: Initialized successfully. Loaded {len(self.users_data)} users.")
        except Exception as e:
            logger.critical(f"UserManager: CRITICAL - Failed to initialize: {e}", exc_info=True)
            # اگر UserManager نتواند مقداردهی اولیه شود، ربات احتمالاً نمی‌تواند کار کند.
            raise

    def get_user(self, user_id: str):
        return self.users_data.get(user_id)

    def add_or_update_user_info(self, user_id: str, first_name: str, last_name: str, username: str):
        user_id_str = str(user_id)
        is_new_user = False
        changed_in_existing = False

        if user_id_str not in self.users_data:
            self.users_data[user_id_str] = {
                "first_name": first_name,
                "last_name": last_name,
                "username": username,
                "singer_names": [],
                "sent_music": [],
            }
            is_new_user = True
            logger.info(f"UserManager: New user added: {user_id_str} - {username or 'N/A'}")
        else:
            user_entry = self.users_data[user_id_str]
            if user_entry.get("first_name") != first_name or \
               user_entry.get("last_name") != last_name or \
               user_entry.get("username") != username:
                
                user_entry["first_name"] = first_name
                user_entry["last_name"] = last_name
                user_entry["username"] = username
                changed_in_existing = True
                logger.info(f"UserManager: User info updated for: {user_id_str} - {username or 'N/A'}")

        if is_new_user or changed_in_existing:
            self.save_all_users_data()

    def update_user_specific_data(self, user_id: str, data: dict):
        user_id_str = str(user_id)
        if user_id_str in self.users_data:
            # logger.debug(f"UserManager: Updating data for user {user_id_str}. Keys: {list(data.keys())}")
            self.users_data[user_id_str].update(data)
            self.save_all_users_data() # ذخیره پس از هر تغییر داده خاص
            logger.info(f"UserManager: Specific data updated for user {user_id_str}.")
        else:
            logger.warning(f"UserManager: Attempted to update specific data for non-existent user: {user_id_str}")

    def get_all_users(self):
        return self.users_data

    def save_all_users_data(self):
        logger.info(f"UserManager: Saving data for all {len(self.users_data)} users...")
        try:
            self.db_handler.save_user_data(self.users_data)
            logger.info("UserManager: All users data saved to DB successfully.")
        except Exception as e:
            logger.error(f"UserManager: Error saving all users data to DB: {e}", exc_info=True)
            # اینجا هم می‌توانید خطا را raise کنید اگر ذخیره نشدن داده‌ها بحرانی است.