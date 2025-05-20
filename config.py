# --- START OF FILE config.py ---

import logging
import os
from logging.handlers import RotatingFileHandler

# --- تنظیمات عمومی ---
# توکن بات را فقط از متغیر محیطی بخوانید
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") # مقدار پیش‌فرض برای تست
if not TOKEN or TOKEN == "YOUR_BOT_TOKEN_HERE": # اگر پیش‌فرض استفاده شد یا مقدار env خالی بود
    logging.critical("FATAL: TELEGRAM_BOT_TOKEN environment variable not set or is default! Please set it in Railway.")
    # در محیط production، اگر توکن معتبر نباشد، بهتر است برنامه متوقف شود.
    # raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

# مسیرهای فایل
APP_DATA_DIR = os.getenv("APP_DATA_DIR", os.getcwd()) # os.getcwd() پوشه کاری فعلی است

DB_NAME = os.path.join(APP_DATA_DIR, "users.db")
TRACK_DB_NAME = os.path.join(APP_DATA_DIR, "tracks.db")
LOG_DIR = os.path.join(APP_DATA_DIR, "logs")
LOG_FILE_NAME = "bot.log"
LOG_FILE_PATH = os.path.join(LOG_DIR, LOG_FILE_NAME)

if not os.path.exists(APP_DATA_DIR) and APP_DATA_DIR != os.getcwd():
    try:
        os.makedirs(APP_DATA_DIR, exist_ok=True)
    except OSError as e:
        logging.error(f"Could not create data directory {APP_DATA_DIR}: {e}")

if not os.path.exists(LOG_DIR):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except OSError as e:
        logging.error(f"Could not create log directory {LOG_DIR}: {e}")


# --- دامنه وب‌هوک و پورت ---
# WEBHOOK_DOMAIN را فقط از متغیر محیطی بخوانید (که در Railway تنظیم خواهید کرد)
WEBHOOK_DOMAIN = os.getenv("WEBHOOK_DOMAIN")
if not WEBHOOK_DOMAIN:
    logging.critical("CRITICAL: WEBHOOK_DOMAIN environment variable not set! Webhook setup will fail.")
    # می‌توانید در اینجا برنامه را متوقف کنید اگر WEBHOOK_DOMAIN حیاتی است
    # raise ValueError("WEBHOOK_DOMAIN environment variable not set!")
else:
    logging.info(f"WEBHOOK_DOMAIN set to: {WEBHOOK_DOMAIN} (from environment variable)")

# پورت را از متغیر محیطی بخوانید (Railway این را تنظیم می‌کند)
PORT = int(os.getenv("PORT", 8080)) # 8080 یک پیش‌فرض برای تست لوکال است


# --- وضعیت‌های مکالمه (بدون تغییر) ---
(MAIN_MENU, LIST_MENU, EDIT_LIST_MENU, ADD_SINGER, DELETE_SINGER,
 REMOVE_LIST_CONFIRM, CONFIRM_SINGER_SUGGESTION,
 CONFIRM_DELETE_HISTORY) = range(8)

# --- محدودیت‌های سیستم (بدون تغییر) ---
MAX_TRACKS_IN_DB = 100000

# --- تنظیمات لاگ‌گیری ---
APP_LOGGER_NAME = "MusicBotLogger"
# سطح لاگ را می‌توان از env خواند یا یک پیش‌فرض ثابت برای production گذاشت
DEFAULT_LOG_LEVEL_STR = os.getenv('APP_LOG_LEVEL', 'INFO') # پیش‌فرض INFO برای production
APP_LOG_LEVEL = logging.getLevelName(DEFAULT_LOG_LEVEL_STR.upper())

DETAILED_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(process)d - %(threadName)s - %(message)s'
SIMPLE_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'


def setup_logger(logger_name=APP_LOGGER_NAME, level=APP_LOG_LEVEL, log_file_path=LOG_FILE_PATH):
    lg = logging.getLogger(logger_name)
    lg.setLevel(level)
    lg.propagate = False

    if not lg.handlers:
        try:
            log_dir_for_handler = os.path.dirname(log_file_path)
            if not os.path.exists(log_dir_for_handler):
                os.makedirs(log_dir_for_handler, exist_ok=True)

            file_formatter = logging.Formatter(DETAILED_FORMAT)
            file_handler = RotatingFileHandler(log_file_path,
                                               maxBytes=5 * 1024 * 1024,
                                               backupCount=5,
                                               encoding='utf-8')
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(level)
            lg.addHandler(file_handler)
        except Exception as e:
            lg.error(f"Could not set up file logger at {log_file_path}: {e}. Logging to console only for file logs.")

        console_formatter = logging.Formatter(SIMPLE_FORMAT) # همیشه فرمت ساده برای کنسول
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(console_formatter)
        stream_handler.setLevel(level) # سطح لاگ کنسول هم مشابه فایل
        lg.addHandler(stream_handler)
    return lg

logger = setup_logger()

# تنظیم لاگرهای کتابخانه تلگرام
TELEGRAM_LIB_LOGGER_HTTP = "httpx"
TELEGRAM_LIB_LOGGER_API = "telegram.ext.Application"
TELEGRAM_LIB_LOGGER_CONV = "telegram.ext.ConversationHandler"
TELEGRAM_LIB_LOGGER_CALLBACK = "telegram.ext.CallbackQueryHandler"
# سطح لاگ PTB را می‌توان از env خواند یا یک پیش‌فرض ثابت برای production گذاشت
PTB_LOG_LEVEL_STR = os.getenv('PTB_LOG_LEVEL', 'WARNING') # پیش‌فرض WARNING برای PTB در production
PTB_LOG_LEVEL = logging.getLevelName(PTB_LOG_LEVEL_STR.upper())

def configure_ptb_loggers(level):
    logging.getLogger(TELEGRAM_LIB_LOGGER_HTTP).setLevel(level)
    logging.getLogger(TELEGRAM_LIB_LOGGER_API).setLevel(level)
    logging.getLogger(TELEGRAM_LIB_LOGGER_CONV).setLevel(logging.INFO) # مکالمات را INFO نگه می‌داریم
    logging.getLogger(TELEGRAM_LIB_LOGGER_CALLBACK).setLevel(logging.INFO) # کال‌بک‌ها را INFO نگه می‌داریم

configure_ptb_loggers(PTB_LOG_LEVEL)
logger.info(f"MusicBot config loaded. Forcing PRODUCTION-like behavior (Webhook).") # پیام تغییر کرد
logger.info(f"Database path: {DB_NAME}")
logger.info(f"Log file path: {LOG_FILE_PATH}")

# --- متن دکمه‌های صفحه کلید (فارسی با ایموجی) ---
# ... بدون تغییر ...
KEYBOARD_TEXTS = {
    "list": "🎤 لیست خوانندگان من",
    "edit_list": "📝 ویرایش لیست",
    "remove_list": "🗑 حذف کل لیست",
    "back": "⬅️ بازگشت",
    "add": "➕ افزودن خواننده",
    "delete": "➖ حذف خواننده",
    "confirm": "✅ تایید حذف",
    "cancel_action": "❌ لغو عملیات",
    "receive_music_now": "🎶 دریافت آهنگ‌های جدید",
}

# --- پیام‌های کاربر (فارسی با ایموجی) ---
# ... بدون تغییر ...
USER_MESSAGES = {
    "welcome":
    ("🎉 سلام {user_name}! به ربات موزیک‌یاب خوش آمدید.\n\n"
     "با این ربات می‌تونید خوانندگان مورد علاقه‌تون رو اضافه کنید \n"
     " و هر زمان که آهنگ‌ جدیدی منتشر کنند به صورت خودکار ربات آنها رابرای شما ارسال میکند .\n\n"
     "چون ربات در حالت توسعه میباشد اگر دکمه های ان کار نکرد /start را در ربات ارسال کنید تا همه چیز به حالت طبیعی بازگردد\n\n"
     "گزینه‌ای رو از منو انتخاب کنید:"),
    "processing_busy":
    ("⏳ ربات در حال انجام عملیات پس‌زمینه است (ممکن است چند دقیقه طول بکشد).\n"
     "لطفاً کمی صبر کنید و دوباره تلاش کنید."),
    "generic_processing":
    "⏳ در حال پردازش، لطفا کمی صبر کنید...",
    "error_generic":
    "⚠️ متاسفانه مشکلی پیش آمد. لطفاً بعداً دوباره تلاش کنید.",
    "error_services_unavailable":
    "🛠️ سرویس‌های ربات در حال حاضر در دسترس نیستند. لطفاً بعداً تلاش کنید.",
    "error_user_data_not_found":
    "🤔 اطلاعات شما یافت نشد. لطفاً با دستور /start ربات را مجدداً راه‌اندازی کنید.",
    "no_singers_in_list_general":
    "🎤 لیست خوانندگان شما در حال حاضر خالی است.",
    "no_singers_in_list_prompt_add":
    "🎤 لیست خوانندگان شما خالی است. برای افزودن، از گزینه «{edit_list_text}» استفاده کنید.",
    "manual_fetch_queued":
    "✅ درخواست شما برای دریافت آهنگ‌ها در صف قرار گرفت. به زودی پردازش خواهد شد.",
    "manual_fetch_no_new_songs":
    "✨ در حال حاضر آهنگ جدیدی مطابق با لیست شما یافت نشد. آهنگ‌های قبلی قبلاً ارسال شده‌اند.",
    "manual_fetch_found_sending":
    "🎶 تعداد {num_found} آهنگ جدید برای شما یافت شد. در حال ارسال...",
    "manual_fetch_all_sent_successfully":
    "🎉 تمام {num_sent} آهنگ جدید با موفقیت برای شما ارسال شد!",
    "manual_fetch_some_sent":
    "👍 {num_sent} از {num_total} آهنگ جدید برای شما ارسال شد.",
    "manual_fetch_none_sent_error":
    "⚠️ متاسفانه در ارسال آهنگ‌ها مشکلی پیش آمد. هیچ آهنگی ارسال نشد.",
    "manual_fetch_blocked":
    "🚫 ارسال متوقف شد. به نظر می‌رسد شما ربات را بلاک کرده‌اید.",
    "cancel_operation":
    "👍 عملیات لغو شد.",
    "main_menu_return":
    "🏠 به منوی اصلی بازگشتید.",
    "list_menu_prompt":
    "◄ مدیریت فهرست خوانندگان ►\nگزینه مورد نظر را انتخاب کنید:",
    "edit_list_menu_prompt":
    "◄ ویرایش فهرست خوانندگان ►\nمی‌توانید خواننده‌ای را اضافه یا حذف کنید:",
    "add_singer_prompt":
    ("➕ لطفاً نام خواننده و تعداد آهنگ‌های جدید درخواستی از او را در دو خط جداگانه وارد کنید.\n"
     "مثال:\nحامیم\n۲\n\n"
     "🔸 اگر تعداد آهنگ را وارد نکنید، ۱ آهنگ در نظر گرفته می‌شود."),
    "add_singer_invalid_input":
    "⚠️ ورودی نامعتبر است. لطفاً نام خواننده را (در صورت نیاز همراه با تعداد) وارد کنید.",
    "add_singer_name_empty":
    "⚠️ نام خواننده نمی‌تواند خالی باشد.",
    "add_singer_count_positive":
    "⚠️ تعداد آهنگ باید عددی مثبت باشد. ۱ آهنگ در نظر گرفته شد.",
    "add_singer_count_max":
    "⚠️ حداکثر ۱۰ آهنگ می‌توانید درخواست کنید. ۱۰ آهنگ در نظر گرفته شد.",
    "add_singer_updated_count":
    "✅ تعداد آهنگ درخواستی برای «{singer_name}» به {count} آهنگ به‌روز شد.",
    "add_singer_added_new":
    "✅ خواننده «{singer_name}» با درخواست {count} آهنگ به لیست شما اضافه شد.",
    "delete_singer_empty_list":
    "⚠️ لیست خوانندگان شما خالی است و خواننده‌ای برای حذف وجود ندارد.",
    "delete_singer_prompt":
    "➖ لطفاً نام خواننده‌ای که می‌خواهید از لیست حذف شود را دقیقاً وارد کنید:",
    "delete_singer_deleted":
    "🗑 خواننده «{singer_name}» از لیست شما حذف شد.",
    "delete_singer_not_found":
    "🤔 خواننده «{singer_name}» در لیست شما یافت نشد.",
    "remove_all_singers_empty_list":
    "⚠️ لیست خوانندگان شما از قبل خالی است!",
    "remove_all_singers_confirm":
    ("🗑️ آیا مطمئن هستید که می‌خواهید **کل لیست خوانندگان** خود را حذف کنید؟\n"
     "این عمل قابل بازگشت نیست!"),
    "remove_all_singers_success":
    "✅ کل لیست خوانندگان شما با موفقیت پاک شد.",
    "remove_all_singers_cancelled":
    "👍 حذف کل لیست لغو شد.",
    "ignore_action_prompt":
    "⚠️ شما در حال انجام عملیات دیگری هستید. لطفاً ابتدا آن را تکمیل یا لغو کنید، یا از دکمه «{back_button_text}» استفاده کنید.",
    "daily_notification_title":
    "🎧 آهنگ جدید روزانه برای شما:",
    "singer_suggestion_prompt":
    "🤔 آیا منظور شما «{suggested_name}» است؟\n(تعداد آهنگ درخواستی برای این خواننده: {user_input_count} عدد)",
    "singer_multiple_suggestions_prompt":
    ("🤔 چندین خواننده با نام مشابه یافت شد. لطفاً یکی را انتخاب کنید یا گزینه «{none_button_text}» را بزنید:\n"
     "(تعداد آهنگ درخواستی برای خواننده انتخابی: {user_input_count} عدد)"),
    "singer_suggestion_none_of_above":
    "❌ هیچکدام / ورود مجدد نام",
    "singer_suggestion_confirm_chosen":
    "✅ خواننده «{suggested_name}» انتخاب و به لیست شما اضافه/به‌روز شد.",
    "singer_suggestion_retry_prompt":
    "🙏 لطفاً نام خواننده را دوباره و با دقت بیشتری وارد کنید:",
    "singer_suggestion_not_found":
    "⚠️ خواننده‌ای با نام وارد شده یا مشابه آن در آرشیو ما یافت نشد. لطفاً نام را دقیق‌تر وارد کنید یا از وجود آن مطمئن شوید.",
    "singer_suggestion_callback_error":
    "⚠️ خطایی در پردازش انتخاب شما رخ داد. لطفاً دوباره برای افزودن خواننده تلاش کنید.",
    "fallback_in_suggestion_state":
    "☝️ لطفاً از دکمه‌های زیر پیام برای پاسخ به پیشنهاد استفاده کنید، یا با دستور /cancel خارج شوید.",
    "delete_history_prompt":
    ("⚠️ **توجه: پاک کردن سابقه آهنگ‌های ارسالی** ⚠️\n\n"
     "آیا مطمئن هستید که می‌خواهید سابقه آهنگ‌هایی که تاکنون برای شما ارسال شده است را پاک کنید؟\n"
     "با این کار، ربات فراموش می‌کند چه آهنگ‌هایی را قبلاً دریافت کرده‌اید و ممکن است در آینده آهنگ‌های تکراری برایتان ارسال شود.\n\n"
     "این عمل فقط بر روی داده‌های ذخیره شده در ربات تاثیر دارد و پیام‌های موجود در این چت را پاک **نمی‌کند**."
     ),
    "delete_history_success":
    ("✅ سابقه آهنگ‌های ارسال شده برای شما با موفقیت پاک شد.\n"
     "از این پس، آهنگ‌ها را مجدداً دریافت خواهید کرد، گویی اولین بار است.\n\n"
     "ℹ️ برای پاک کردن پیام‌های این چت، لطفاً از گزینه مربوطه در اپلیکیشن تلگرام خود استفاده کنید."
     ),
    "delete_history_cancelled":
    "👍 عملیات پاک کردن سابقه آهنگ‌های ارسالی لغو شد.",
    "confirm_action_delete_history":
    "✅ بله، سابقه را پاک کن",
    "cancel_action_delete_history":
    "❌ خیر، لغو کن"
}

# --- تنظیمات پیشنهاد خواننده (بدون تغییر) ---
FUZZY_MATCH_THRESHOLD = 80
MAX_FUZZY_SUGGESTIONS = 10
# --- END OF FILE config.py ---