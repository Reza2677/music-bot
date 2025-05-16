import logging
import os

# --- General Configuration ---
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '6738356391:AAEIYgvmIQv1xa4pSmaqFy70zSDDpl6Ed_w') # بهتر است از متغیرهای محیطی خوانده شود
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # مسیر ریشه پروژه
DB_NAME = os.path.join(BASE_DIR, "users.db")
TRACK_DB_NAME = os.path.join(BASE_DIR, "tracks.db")
LOG_FILE = os.path.join(BASE_DIR, "bot.log")

# --- Conversation States ---
(MAIN_MENU, LIST_MENU, EDIT_LIST_MENU, 
 ADD_SINGER, DELETE_SINGER, REMOVE_LIST_CONFIRM, SET_TIME) = range(7)

# --- Valid Times for Notification ---
VALID_TIMES = [f"{hour:02d}:00" for hour in range(24)]

# ... سایر تنظیمات ...
MAX_TRACKS_IN_DB = 100000  # یا هر مقدار دلخواه دیگر

# --- Logging Configuration ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Keyboard Texts (Optional, but helps with consistency and i18n later) ---
KEYBOARD_TEXTS = {
    "list": "List",
    "set_time": "Set Time",
    "edit_list": "Edit List",
    "remove_list": "Remove List",
    "back": "Back",
    "add": "Add",
    "delete": "Delete",
    "confirm": "Confirm",
    "cancel_action": "Cancel", # Renamed from "Cancel" to avoid conflict with /cancel command
}