import logging
import os
from logging.handlers import RotatingFileHandler

# --- General Configuration ---
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '6738356391:AAEIYgvmIQv1xa4pSmaqFy70zSDDpl6Ed_w')
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_NAME = os.path.join(BASE_DIR, "users.db")
TRACK_DB_NAME = os.path.join(BASE_DIR, "tracks.db")
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE_NAME = "bot.log"
LOG_FILE_PATH = os.path.join(LOG_DIR, LOG_FILE_NAME)

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# --- Conversation States ---
(MAIN_MENU, LIST_MENU, EDIT_LIST_MENU,
 ADD_SINGER, DELETE_SINGER, REMOVE_LIST_CONFIRM,
 CONFIRM_SINGER_SUGGESTION  # وضعیت جدید برای تایید پیشنهاد خواننده
 ) = range(7) # تعداد کل وضعیت‌ها به ۷ افزایش یافت

MAX_TRACKS_IN_DB = 100000

# --- Logging Configuration ---
APP_LOGGER_NAME = "MusicBotLogger"
APP_ENV = os.getenv('APP_ENV', 'DEVELOPMENT').upper()
DEFAULT_LOG_LEVEL = logging.DEBUG if APP_ENV == 'DEVELOPMENT' else logging.INFO
APP_LOG_LEVEL_STR = os.getenv('APP_LOG_LEVEL', logging.getLevelName(DEFAULT_LOG_LEVEL))
APP_LOG_LEVEL = logging.getLevelName(APP_LOG_LEVEL_STR.upper())
DETAILED_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(process)d - %(threadName)s - %(message)s'
SIMPLE_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

def setup_logger(logger_name=APP_LOGGER_NAME, level=APP_LOG_LEVEL, log_file_path=LOG_FILE_PATH):
    lg = logging.getLogger(logger_name)
    lg.setLevel(level)
    lg.propagate = False
    if not lg.hasHandlers():
        file_formatter = logging.Formatter(DETAILED_FORMAT)
        file_handler = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(level)
        lg.addHandler(file_handler)
        console_formatter = logging.Formatter(SIMPLE_FORMAT if APP_ENV == 'PRODUCTION' else DETAILED_FORMAT)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(console_formatter)
        stream_handler.setLevel(logging.DEBUG if APP_ENV == 'DEVELOPMENT' else logging.INFO)
        lg.addHandler(stream_handler)
    return lg
logger = setup_logger()

TELEGRAM_LIB_LOGGER_HTTP = "httpx"
TELEGRAM_LIB_LOGGER_API = "telegram.ext.Application"
TELEGRAM_LIB_LOGGER_CONV = "telegram.ext.ConversationHandler" # برای دیباگ کانورسیشن
TELEGRAM_LIB_LOGGER_CALLBACK = "telegram.ext.CallbackQueryHandler" # برای دیباگ CallbackQueryHandler
# ... (سایر لاگرهای PTB مانند قبل)
PTB_LOG_LEVEL_STR = os.getenv('PTB_LOG_LEVEL', 'DEBUG' if APP_ENV == 'DEVELOPMENT' else 'WARNING')
PTB_LOG_LEVEL = logging.getLevelName(PTB_LOG_LEVEL_STR.upper())

def configure_ptb_loggers(level):
    logging.getLogger(TELEGRAM_LIB_LOGGER_HTTP).setLevel(level)
    logging.getLogger(TELEGRAM_LIB_LOGGER_API).setLevel(level)
    logging.getLogger(TELEGRAM_LIB_LOGGER_CONV).setLevel(logging.DEBUG if APP_ENV == 'DEVELOPMENT' else logging.INFO)
    logging.getLogger(TELEGRAM_LIB_LOGGER_CALLBACK).setLevel(logging.DEBUG if APP_ENV == 'DEVELOPMENT' else logging.INFO)
    # ... (تنظیم سایر لاگرهای PTB مانند قبل)
configure_ptb_loggers(PTB_LOG_LEVEL)

logger.info(f"Logger configured for APP_ENV: {APP_ENV}")

# --- Keyboard Texts (فارسی با ایموجی) ---
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

# --- User Messages (فارسی با ایموجی) ---
USER_MESSAGES = {
    "welcome": (
        "🎉 سلام {user_name}! به ربات موزیک‌یاب خوش آمدید.\n\n"
        "با این ربات می‌تونید خوانندگان مورد علاقه‌تون رو اضافه کنید و آهنگ‌های جدیدشون رو دریافت کنید.\n\n"
        "گزینه‌ای رو از منو انتخاب کنید:"
    ),
    "processing_busy": (
        "⏳ ربات در حال انجام عملیات پس‌زمینه است (ممکن است چند دقیقه طول بکشد).\n"
        "لطفاً کمی صبر کنید و دوباره تلاش کنید."
    ),
    "generic_processing": "⏳ در حال پردازش، لطفا کمی صبر کنید...",
    "error_generic": "⚠️ متاسفانه مشکلی پیش آمد. لطفاً بعداً دوباره تلاش کنید.",
    "error_services_unavailable": "🛠️ سرویس‌های ربات در حال حاضر در دسترس نیستند. لطفاً بعداً تلاش کنید.",
    "error_user_data_not_found": "🤔 اطلاعات شما یافت نشد. لطفاً با دستور /start ربات را مجدداً راه‌اندازی کنید.",
    "no_singers_in_list_general": "🎤 لیست خوانندگان شما در حال حاضر خالی است.",
    "no_singers_in_list_prompt_add": "🎤 لیست خوانندگان شما خالی است. برای افزودن، از گزینه «{edit_list_text}» استفاده کنید.", # .format(edit_list_text=KEYBOARD_TEXTS["edit_list"])
    "manual_fetch_searching": "🔎 در حال جستجو برای آهنگ‌های جدید شما... لطفاً کمی صبر کنید.", # این دیگر مستقیم استفاده نمی‌شود، در worker است
    "manual_fetch_queued": "✅ درخواست شما برای دریافت آهنگ‌ها در صف قرار گرفت. به زودی پردازش خواهد شد.",
    "manual_fetch_no_new_songs": "✨ در حال حاضر آهنگ جدیدی مطابق با لیست شما یافت نشد. آهنگ‌های قبلی قبلاً ارسال شده‌اند.",
    "manual_fetch_found_sending": "🎶 تعداد {num_found} آهنگ جدید برای شما یافت شد. در حال ارسال...", # .format(num_found=...)
    "manual_fetch_all_sent_successfully": "🎉 تمام {num_sent} آهنگ جدید با موفقیت برای شما ارسال شد!", # .format(num_sent=...)
    "manual_fetch_some_sent": "👍 {num_sent} از {num_total} آهنگ جدید برای شما ارسال شد.", # .format(num_sent=..., num_total=...)
    "manual_fetch_none_sent_error": "⚠️ متاسفانه در ارسال آهنگ‌ها مشکلی پیش آمد. هیچ آهنگی ارسال نشد.",
    "manual_fetch_blocked": "🚫 ارسال متوقف شد. به نظر می‌رسد شما ربات را بلاک کرده‌اید.",
    "cancel_operation": "👍 عملیات لغو شد.",
    "main_menu_return": "🏠 به منوی اصلی بازگشتید.",
    "list_menu_prompt": "◄ مدیریت فهرست خوانندگان ►\nگزینه مورد نظر را انتخاب کنید:",
    "edit_list_menu_prompt": "◄ ویرایش فهرست خوانندگان ►\nمی‌توانید خواننده‌ای را اضافه یا حذف کنید:",
    "add_singer_prompt": (
        "➕ لطفاً نام خواننده و تعداد آهنگ‌های جدید درخواستی از او را در دو خط جداگانه وارد کنید.\n"
        "مثال:\nحامیم\n۲\n\n"
        "🔸 اگر تعداد آهنگ را وارد نکنید، ۱ آهنگ در نظر گرفته می‌شود.\n"
        "🔸 حداکثر تعداد آهنگ درخواستی برای هر خواننده ۱۰ عدد است."
    ),
    "add_singer_invalid_input": "⚠️ ورودی نامعتبر است. لطفاً نام خواننده را (در صورت نیاز همراه با تعداد) وارد کنید.",
    "add_singer_name_empty": "⚠️ نام خواننده نمی‌تواند خالی باشد.",
    "add_singer_count_positive": "⚠️ تعداد آهنگ باید عددی مثبت باشد. ۱ آهنگ در نظر گرفته شد.",
    "add_singer_count_max": "⚠️ حداکثر ۱۰ آهنگ می‌توانید درخواست کنید. ۱۰ آهنگ در نظر گرفته شد.",
    "add_singer_updated_count": "✅ تعداد آهنگ درخواستی برای «{singer_name}» به {count} آهنگ به‌روز شد.", # .format(singer_name=..., count=...)
    "add_singer_added_new": "✅ خواننده «{singer_name}» با درخواست {count} آهنگ به لیست شما اضافه شد.", # .format(singer_name=..., count=...)
    "delete_singer_empty_list": "⚠️ لیست خوانندگان شما خالی است و خواننده‌ای برای حذف وجود ندارد.",
    "delete_singer_prompt": "➖ لطفاً نام خواننده‌ای که می‌خواهید از لیست حذف شود را دقیقاً وارد کنید:",
    "delete_singer_deleted": "🗑 خواننده «{singer_name}» از لیست شما حذف شد.", # .format(singer_name=...)
    "delete_singer_not_found": "🤔 خواننده «{singer_name}» در لیست شما یافت نشد.", # .format(singer_name=...)
    "remove_all_singers_empty_list": "⚠️ لیست خوانندگان شما از قبل خالی است!",
    "remove_all_singers_confirm": (
        "🗑️ آیا مطمئن هستید که می‌خواهید **کل لیست خوانندگان** خود را حذف کنید؟\n"
        "این عمل قابل بازگشت نیست!"
    ),
    "remove_all_singers_success": "✅ کل لیست خوانندگان شما با موفقیت پاک شد.",
    "remove_all_singers_cancelled": "👍 حذف کل لیست لغو شد.",
    "ignore_action_prompt": "⚠️ شما در حال انجام عملیات دیگری هستید. لطفاً ابتدا آن را تکمیل یا لغو کنید، یا از دکمه «{back_button_text}» استفاده کنید.", # .format(back_button_text=...)
    "daily_notification_title": "🎧 آهنگ جدید روزانه برای شما:",
    "singer_suggestion_prompt": "🤔 آیا منظور شما «{suggested_name}» است؟\n(تعداد آهنگ درخواستی برای این خواننده: {user_input_count} عدد)",
    "singer_multiple_suggestions_prompt": ( # پیام جدید
        "🤔 چندین خواننده با نام مشابه یافت شد. لطفاً یکی را انتخاب کنید یا گزینه «{none_button_text}» را بزنید:\n"
        "(تعداد آهنگ درخواستی برای خواننده انتخابی: {user_input_count} عدد)"
    ), # .format(none_button_text=..., user_input_count=...)
    "singer_suggestion_none_of_above": "❌ هیچکدام / ورود مجدد نام", # متن دکمه جدید
    "singer_suggestion_confirm_chosen": "✅ خواننده «{suggested_name}» انتخاب و به لیست شما اضافه/به‌روز شد.", # .format(suggested_name=...)
    "singer_suggestion_retry_prompt": "🙏 لطفاً نام خواننده را دوباره و با دقت بیشتری وارد کنید:",
    "singer_suggestion_not_found": "⚠️ خواننده‌ای با نام وارد شده یا مشابه آن در آرشیو ما یافت نشد. لطفاً نام را دقیق‌تر وارد کنید یا از وجود آن مطمئن شوید.",
    "singer_suggestion_callback_error": "⚠️ خطایی در پردازش انتخاب شما رخ داد. لطفاً دوباره برای افزودن خواننده تلاش کنید.",
    "fallback_in_suggestion_state": "☝️ لطفاً از دکمه‌های زیر پیام برای پاسخ به پیشنهاد استفاده کنید، یا با دستور /cancel خارج شوید.",
}

# آستانه تطابق فازی برای پیشنهاد نام خواننده
FUZZY_MATCH_THRESHOLD = 80 # از ۱۰۰، قابل تنظیم
MAX_FUZZY_SUGGESTIONS = 5 # حداکثر تعداد پیشنهاد برای نمایش