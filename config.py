import logging
import os
from logging.handlers import RotatingFileHandler

# --- تنظیمات عمومی ---
# توکن بات را فقط از متغیر محیطی بخوانید
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "6738356391:AAEIYgvmIQv1xa4pSmaqFy70zSDDpl6Ed_w")
if not TOKEN:
    # اگر توکن در متغیرهای محیطی نبود، برنامه نباید اجرا شود
    # می‌توانید یک مقدار پیش‌فرض برای تست لوکال بگذارید، اما برای production باید از env خوانده شود
    logging.critical("FATAL: TELEGRAM_BOT_TOKEN environment variable not set!")
    # raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!") # یا یک خطا ایجاد کنید

# مسیرهای فایل (با فرض اینکه برنامه در ریشه یک پوشه در کانتینر اجرا می‌شود)
# برای داده‌های پایدار در Railway، از Volume استفاده کنید و این مسیر را به مسیر Volume تغییر دهید
# به عنوان مثال، اگر Volume شما روی /data مانت شده است:
# APP_DATA_DIR = os.getenv("APP_DATA_DIR", "/data")
# اگر از Volume استفاده نمی‌کنید (فقط برای تست، چون داده‌ها موقتی خواهند بود):
APP_DATA_DIR = os.getenv("APP_DATA_DIR", os.getcwd()) # os.getcwd() پوشه کاری فعلی است

DB_NAME = os.path.join(APP_DATA_DIR, "users.db")
TRACK_DB_NAME = os.path.join(APP_DATA_DIR, "tracks.db")
LOG_DIR = os.path.join(APP_DATA_DIR, "logs") # پوشه لاگ
LOG_FILE_NAME = "bot.log"
LOG_FILE_PATH = os.path.join(LOG_DIR, LOG_FILE_NAME)

# اطمینان از وجود پوشه لاگ (و پوشه داده اگر لازم است)
if not os.path.exists(APP_DATA_DIR) and APP_DATA_DIR != os.getcwd(): # اگر APP_DATA_DIR یک مسیر خاص است
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
APP_ENV = os.getenv('APP_ENV', 'DEVELOPMENT').upper() # 'PRODUCTION' در Railway

if not WEBHOOK_DOMAIN and APP_ENV == 'PRODUCTION':
    logging.critical("CRITICAL: WEBHOOK_DOMAIN environment variable not set for PRODUCTION environment!")
elif WEBHOOK_DOMAIN:
    logging.info(f"WEBHOOK_DOMAIN set to: {WEBHOOK_DOMAIN} (from environment variable)")
else:
    logging.info("WEBHOOK_DOMAIN is not set (e.g., local development with polling, or env var missing).")

# پورت را از متغیر محیطی بخوانید (Railway این را تنظیم می‌کند)
PORT = int(os.getenv("PORT", 8080)) # 8080 یک پیش‌فرض برای تست لوکال است


# --- وضعیت‌های مکالمه (بدون تغییر) ---
(MAIN_MENU, LIST_MENU, EDIT_LIST_MENU, ADD_SINGER, DELETE_SINGER,
 REMOVE_LIST_CONFIRM, CONFIRM_SINGER_SUGGESTION,
 CONFIRM_DELETE_HISTORY) = range(8)

# --- محدودیت‌های سیستم (بدون تغییر) ---
MAX_TRACKS_IN_DB = 100000

# --- تنظیمات لاگ‌گیری (بخش زیادی بدون تغییر، فقط اطمینان از استفاده از logger جدید) ---
APP_LOGGER_NAME = "MusicBotLogger"
DEFAULT_LOG_LEVEL = logging.DEBUG if APP_ENV == 'DEVELOPMENT' else logging.INFO
APP_LOG_LEVEL_STR = os.getenv('APP_LOG_LEVEL', logging.getLevelName(DEFAULT_LOG_LEVEL))
APP_LOG_LEVEL = logging.getLevelName(APP_LOG_LEVEL_STR.upper())
DETAILED_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(process)d - %(threadName)s - %(message)s'
SIMPLE_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'


def setup_logger(logger_name=APP_LOGGER_NAME, level=APP_LOG_LEVEL, log_file_path=LOG_FILE_PATH):
    lg = logging.getLogger(logger_name)
    lg.setLevel(level)
    lg.propagate = False # جلوگیری از ارسال لاگ به ریشه

    if not lg.handlers: # بررسی با lg.handlers به جای lg.hasHandlers() که ممکن است در برخی نسخه‌ها نباشد
        # تنظیم handler برای فایل (فقط اگر مسیر قابل نوشتن باشد)
        try:
            # اطمینان از وجود پوشه لاگ قبل از ایجاد handler
            log_dir_for_handler = os.path.dirname(log_file_path)
            if not os.path.exists(log_dir_for_handler):
                os.makedirs(log_dir_for_handler, exist_ok=True)

            file_formatter = logging.Formatter(DETAILED_FORMAT)
            file_handler = RotatingFileHandler(log_file_path,
                                               maxBytes=5 * 1024 * 1024, # 5MB
                                               backupCount=5,
                                               encoding='utf-8')
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(level) # سطح لاگ فایل را هم تنظیم کن
            lg.addHandler(file_handler)
        except Exception as e:
            # اگر ایجاد فایل لاگ ممکن نبود (مثلاً به خاطر مجوزها در محیط کانتینر بدون ولوم پایدار)
            # فقط به کنسول لاگ کن
            lg.error(f"Could not set up file logger at {log_file_path}: {e}. Logging to console only for file logs.")


        # تنظیم handler برای کنسول
        console_formatter = logging.Formatter(
            SIMPLE_FORMAT if APP_ENV == 'PRODUCTION' else DETAILED_FORMAT
        )
        stream_handler = logging.StreamHandler() # به stdout/stderr می‌فرستد
        stream_handler.setFormatter(console_formatter)
        # سطح لاگ کنسول را می‌توان متفاوت تنظیم کرد، مثلاً برای production کمتر و برای dev بیشتر
        stream_handler.setLevel(logging.DEBUG if APP_ENV == 'DEVELOPMENT' else logging.INFO)
        lg.addHandler(stream_handler)
    return lg

# ایجاد نمونه لاگر اصلی برنامه
logger = setup_logger()

# تنظیم لاگرهای کتابخانه تلگرام (بدون تغییر)
TELEGRAM_LIB_LOGGER_HTTP = "httpx"
TELEGRAM_LIB_LOGGER_API = "telegram.ext.Application" # قبلاً telegram.bot بود، Application صحیح‌تر است
TELEGRAM_LIB_LOGGER_CONV = "telegram.ext.ConversationHandler"
TELEGRAM_LIB_LOGGER_CALLBACK = "telegram.ext.CallbackQueryHandler"
PTB_LOG_LEVEL_STR = os.getenv('PTB_LOG_LEVEL', 'DEBUG' if APP_ENV == 'DEVELOPMENT' else 'WARNING')
PTB_LOG_LEVEL = logging.getLevelName(PTB_LOG_LEVEL_STR.upper())

def configure_ptb_loggers(level):
    logging.getLogger(TELEGRAM_LIB_LOGGER_HTTP).setLevel(level)
    logging.getLogger(TELEGRAM_LIB_LOGGER_API).setLevel(level)
    logging.getLogger(TELEGRAM_LIB_LOGGER_CONV).setLevel(logging.DEBUG if APP_ENV == 'DEVELOPMENT' else logging.INFO)
    logging.getLogger(TELEGRAM_LIB_LOGGER_CALLBACK).setLevel(logging.DEBUG if APP_ENV == 'DEVELOPMENT' else logging.INFO)

configure_ptb_loggers(PTB_LOG_LEVEL)
logger.info(f"Logger configured for APP_ENV: {APP_ENV}. MusicBot config loaded.")
logger.info(f"Database path: {DB_NAME}")
logger.info(f"Log file path: {LOG_FILE_PATH}")

# --- متن دکمه‌های صفحه کلید (فارسی با ایموجی) ---
KEYBOARD_TEXTS = {
    "list": "🎤 لیست خوانندگان من",
    "edit_list": "📝 ویرایش لیست",
    "remove_list": "🗑 حذف کل لیست",
    "back": "⬅️ بازگشت",
    "add": "➕ افزودن خواننده",
    "delete": "➖ حذف خواننده",
    "confirm": "✅ تایید حذف",  # این برای حذف کل لیست است
    "cancel_action": "❌ لغو عملیات",  # این هم برای حذف کل لیست
    "receive_music_now": "🎶 دریافت آهنگ‌های جدید",
}

# --- پیام‌های کاربر (فارسی با ایموجی) ---
USER_MESSAGES = {
    # --- پیام‌های عمومی ---
    "welcome":
    ("🎉 سلام {user_name}! به ربات موزیک‌یاب خوش آمدید.\n\n"
     "با این ربات می‌تونید خوانندگان مورد علاقه‌تون رو اضافه کنید \n"
     " و هر زمان که آهنگ‌ جدیدی منتشر کنند به صورت خودکار ربات آنها رابرای شما ارسال میکند .\n\n"
     "چون ربات در حالت توسعه میباشد اگر دکمه های ان کار نکرد /start را در ربات ارسال کنید تا همه چیز به حالت طبیعی بازگردد\n\n"
     "گزینه‌ای رو از منو انتخاب کنید:"),

    # --- پیام‌های مربوط به پردازش ---
    "processing_busy":
    ("⏳ ربات در حال انجام عملیات پس‌زمینه است (ممکن است چند دقیقه طول بکشد).\n"
     "لطفاً کمی صبر کنید و دوباره تلاش کنید."),
    "generic_processing":
    "⏳ در حال پردازش، لطفا کمی صبر کنید...",

    # --- پیام‌های خطا ---
    "error_generic":
    "⚠️ متاسفانه مشکلی پیش آمد. لطفاً بعداً دوباره تلاش کنید.",
    "error_services_unavailable":
    "🛠️ سرویس‌های ربات در حال حاضر در دسترس نیستند. لطفاً بعداً تلاش کنید.",
    "error_user_data_not_found":
    "🤔 اطلاعات شما یافت نشد. لطفاً با دستور /start ربات را مجدداً راه‌اندازی کنید.",

    # --- پیام‌های مدیریت لیست ---
    "no_singers_in_list_general":
    "🎤 لیست خوانندگان شما در حال حاضر خالی است.",
    "no_singers_in_list_prompt_add":
    "🎤 لیست خوانندگان شما خالی است. برای افزودن، از گزینه «{edit_list_text}» استفاده کنید.",

    # --- پیام‌های مرتبط با دریافت موسیقی ---
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

    # --- پیام‌های منو و گفتگو ---
    "cancel_operation":
    "👍 عملیات لغو شد.",
    "main_menu_return":
    "🏠 به منوی اصلی بازگشتید.",
    "list_menu_prompt":
    "◄ مدیریت فهرست خوانندگان ►\nگزینه مورد نظر را انتخاب کنید:",
    "edit_list_menu_prompt":
    "◄ ویرایش فهرست خوانندگان ►\nمی‌توانید خواننده‌ای را اضافه یا حذف کنید:",

    # --- پیام‌های مربوط به افزودن خواننده ---
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

    # --- پیام‌های مربوط به حذف خواننده ---
    "delete_singer_empty_list":
    "⚠️ لیست خوانندگان شما خالی است و خواننده‌ای برای حذف وجود ندارد.",
    "delete_singer_prompt":
    "➖ لطفاً نام خواننده‌ای که می‌خواهید از لیست حذف شود را دقیقاً وارد کنید:",
    "delete_singer_deleted":
    "🗑 خواننده «{singer_name}» از لیست شما حذف شد.",
    "delete_singer_not_found":
    "🤔 خواننده «{singer_name}» در لیست شما یافت نشد.",

    # --- پیام‌های مربوط به حذف کل لیست ---
    "remove_all_singers_empty_list":
    "⚠️ لیست خوانندگان شما از قبل خالی است!",
    "remove_all_singers_confirm":
    ("🗑️ آیا مطمئن هستید که می‌خواهید **کل لیست خوانندگان** خود را حذف کنید؟\n"
     "این عمل قابل بازگشت نیست!"),
    "remove_all_singers_success":
    "✅ کل لیست خوانندگان شما با موفقیت پاک شد.",
    "remove_all_singers_cancelled":
    "👍 حذف کل لیست لغو شد.",

    # --- پیام‌های متفرقه ---
    "ignore_action_prompt":
    "⚠️ شما در حال انجام عملیات دیگری هستید. لطفاً ابتدا آن را تکمیل یا لغو کنید، یا از دکمه «{back_button_text}» استفاده کنید.",
    "daily_notification_title":
    "🎧 آهنگ جدید روزانه برای شما:",

    # --- پیام‌های مربوط به پیشنهاد خواننده ---
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

    # --- پیام‌های مربوط به حذف تاریخچه ---
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
    "✅ بله، سابقه را پاک کن",  # متن دکمه تایید مخصوص این عمل
    "cancel_action_delete_history":
    "❌ خیر، لغو کن"  # متن دکمه لغو مخصوص این عمل
}

# --- تنظیمات پیشنهاد خواننده ---
FUZZY_MATCH_THRESHOLD = 80  # آستانه تطابق فازی برای پیشنهاد نام خواننده
MAX_FUZZY_SUGGESTIONS = 10  # حداکثر تعداد پیشنهادات مشابه
