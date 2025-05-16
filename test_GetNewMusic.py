


# import logging
# import sqlite3
# import json
# import re
# from telegram import Update, ReplyKeyboardMarkup
# from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
# from playwright.async_api import async_playwright

# # تنظیمات لاگ‌نویسی
# logging.basicConfig(
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     level=logging.INFO,
#     handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
# )
# logger = logging.getLogger(__name__)

# TOKEN = '6738356391:AAEIYgvmIQv1xa4pSmaqFy70zSDDpl6Ed_w'
# DB_NAME = "users.db"
# TRACK_DB_NAME = "tracks.db"

# # حالت‌های ConversationHandler
# MAIN_MENU, LIST_MENU, EDIT_LIST_MENU, ADD_SINGER, DELETE_SINGER, REMOVE_LIST_CONFIRM, SET_TIME = range(7)

# # لیست زمان‌های معتبر
# VALID_TIMES = [f"{hour:02d}:00" for hour in range(24)]

# # کلاس مدیریت دیتابیس کاربران
# class DatabaseHandler:
#     def __init__(self, db_name):
#         self.db_name = db_name
#         self.create_users_table()

#     def get_connection(self):
#         conn = sqlite3.connect(self.db_name)
#         conn.row_factory = sqlite3.Row
#         return conn

#     def create_users_table(self):
#         with self.get_connection() as conn:
#             cursor = conn.cursor()
#             cursor.execute('''
#                 CREATE TABLE IF NOT EXISTS users (
#                     user_id INTEGER PRIMARY KEY,
#                     first_name TEXT,
#                     last_name TEXT,
#                     username TEXT,
#                     singer_names TEXT,
#                     sent_music TEXT,
#                     sent_time TEXT DEFAULT "02:00"
#                 )
#             ''')
#             conn.commit()

#     def load_user_data(self):
#         with self.get_connection() as conn:
#             cursor = conn.cursor()
#             cursor.execute("SELECT * FROM users")
#             rows = cursor.fetchall()
#         users_data = {}
#         for row in rows:
#             user_id = str(row['user_id'])
#             users_data[user_id] = {
#                 "first_name": row['first_name'],
#                 "last_name": row['last_name'],
#                 "username": row['username'],
#                 "singer_names": json.loads(row['singer_names']) if row['singer_names'] else [],
#                 "sent_music": json.loads(row['sent_music']) if row['sent_music'] else [],
#                 "sent_time": row['sent_time'] if row['sent_time'] else "02:00"
#             }
#         return users_data

#     def save_user_data(self, users_data):
#         with self.get_connection() as conn:
#             cursor = conn.cursor()
#             for user_id, data in users_data.items():
#                 cursor.execute('''
#                     INSERT OR REPLACE INTO users (user_id, first_name, last_name, username, singer_names, sent_music, sent_time)
#                     VALUES (?, ?, ?, ?, ?, ?, ?)
#                 ''', (int(user_id), data["first_name"], data["last_name"], data["username"], 
#                       json.dumps(data["singer_names"], ensure_ascii=False), 
#                       json.dumps(data["sent_music"], ensure_ascii=False), 
#                       data.get("sent_time", "02:00")))
#             conn.commit()

# # کلاس مدیریت دیتابیس آهنگ‌ها
# class TrackDatabaseHandler:
#     def __init__(self, db_name=TRACK_DB_NAME):
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
#             return [dict(zip(['link', 'en_name', 'en_track', 'fa_name', 'fa_track', 'download_link'], row)) for row in rows]

# # کلاس جستجو در آهنگ‌ها
# class TrackSearcher:
#     def __init__(self, track_db_handler):
#         self.track_db_handler = track_db_handler
#         self.logger = logging.getLogger(__name__)

#     def is_english(self, text):
#         return bool(re.match(r'^[a-z0-9\s]+$', text.strip().lower()))

#     async def search_tracks(self, search_list):
#         logger.info("Starting track search...")
#         result = []
#         try:
#             tracks = self.track_db_handler.load_tracks()
#             if not tracks:
#                 logger.warning("No tracks found in database.")
#                 return result

#             for item in search_list:
#                 if not isinstance(item, dict) or "name" not in item or "count" not in item:
#                     logger.warning(f"Invalid search item: {item}. Expected {'name': str, 'count': int}")
#                     continue
                
#                 name = item["name"]
#                 count = item["count"]
#                 if not isinstance(count, int) or count < 0:
#                     logger.warning(f"Invalid count for '{name}': {count}. Setting to 1.")
#                     count = 1

#                 logger.info(f"Searching for '{name}' with count {count}...")
#                 found_tracks = [
#                     track for track in tracks 
#                     if track["en_name"].lower() == name.lower() or track["fa_name"].lower() == name.lower()
#                 ]
#                 found_tracks = found_tracks[:count]  # محدود به تعداد درخواستی
#                 result.extend(found_tracks)
#                 logger.info(f"Found {len(found_tracks)} tracks for '{name}'.")
            
#             logger.info(f"Search completed. Total tracks found: {len(result)}")
#             return result
#         except Exception as e:
#             logger.error(f"Error in search_tracks: {e}")
#             return result

# # کلاس مدیریت وظایف موزیک
# class MusicTaskManager:
#     def __init__(self):
#         self.track_db_handler = TrackDatabaseHandler()

#     async def fetch_new_music(self):
#         async with async_playwright() as playwright:
#             browser = await playwright.chromium.launch(headless=True)
#             page = await browser.new_page()
#             try:
#                 await page.goto("https://www.ahangimo.com/new_music")
#                 timeouts = [2000, 5000, 10000]
#                 details = []
#                 for timeout in timeouts:
#                     try:
#                         await page.wait_for_selector('a[href*="/track/"]', timeout=timeout)
#                         tracks = await page.query_selector_all('a[href*="/track/"]')
#                         for track in tracks[:20]:
#                             link = await track.get_attribute('href')
#                             en_title = await track.query_selector('h4.musicItemBoxSubTitle')
#                             fa_title = await track.query_selector('h4.musicItemBoxTitle')
#                             en_name, en_track = self.parse_title(await en_title.inner_html()) if en_title else ("N/A", "N/A")
#                             fa_track, fa_name = self.parse_title(await fa_title.inner_html()) if fa_title else ("N/A", "N/A")
#                             if en_name != "N/A" or fa_name != "N/A":
#                                 details.append({
#                                     "link": link,
#                                     "en_name": en_name,
#                                     "en_track": en_track,
#                                     "fa_name": fa_name,
#                                     "fa_track": fa_track,
#                                     "download_link": "N/A"
#                                 })
#                         break
#                     except Exception as e:
#                         logger.warning(f"Timeout {timeout/1000}s: {e}")
#                 return details
#             finally:
#                 await browser.close()

#     async def fetch_download_links(self, tracks):
#         async with async_playwright() as playwright:
#             browser = await playwright.chromium.launch(headless=True)
#             page = await browser.new_page()
#             try:
#                 for track in tracks:
#                     if track["download_link"] != "N/A":
#                         continue
#                     await page.goto(f"https://www.ahangimo.com{track['link']}", wait_until="networkidle")
#                     for timeout in [5000, 10000, 20000]:
#                         try:
#                             link_elem = await page.wait_for_selector('#swup > div.incontent > div > div:nth-child(5) > div > div.col-md-3.text-center > div > a', timeout=timeout)
#                             track["download_link"] = await link_elem.get_attribute('href')
#                             break
#                         except Exception:
#                             continue
#             finally:
#                 await browser.close()

#     async def run_music_tasks(self, context: ContextTypes.DEFAULT_TYPE):
#         logger.info("Running music tasks...")
#         tracks = await self.fetch_new_music()
#         await self.fetch_download_links(tracks)
#         self.track_db_handler.save_tracks(tracks[::-1])

#     def parse_title(self, html):
#         text = html.replace('<br>', '\n').strip()
#         parts = text.split('\n')
#         return parts[0].strip(), parts[1].strip() if len(parts) > 1 else "N/A"

#     async def run_search_task(self, context: ContextTypes.DEFAULT_TYPE, user_manager, searcher):
#         logger.info("Running search task...")
#         for user_id, user_info in user_manager.users_data.items():
#             search_list = user_info["singer_names"]
#             if not search_list:
#                 continue
#             results = await searcher.search_tracks(search_list)
#             sent_links = user_info.get("sent_music", [])
#             for track in results:
#                 link = track.get("download_link", "N/A")
#                 if link != "N/A" and link not in sent_links:
#                     await context.bot.send_message(chat_id=int(user_id), text=f"خواننده: {track['en_name']}\nموزیک: {track['en_track']}\nدانلود: {link}")
#                     sent_links.append(link)
#             user_manager.update_user(user_id, {"sent_music": sent_links})

# # کلاس مدیریت کاربران
# class UserManager:
#     def __init__(self, db_handler):
#         self.db_handler = db_handler
#         self.users_data = self.db_handler.load_user_data()

#     def get_user(self, user_id):
#         return self.users_data.get(user_id, None)

#     def add_user(self, user_id, first_name, last_name, username):
#         if user_id not in self.users_data:
#             self.users_data[user_id] = {
#                 "first_name": first_name,
#                 "last_name": last_name,
#                 "username": username,
#                 "singer_names": [],
#                 "sent_music": [],
#                 "sent_time": "02:00"
#             }
#             self.db_handler.save_user_data(self.users_data)

#     def update_user(self, user_id, data):
#         if user_id in self.users_data:
#             self.users_data[user_id].update(data)
#             self.db_handler.save_user_data(self.users_data)

# # کلاس مدیریت ربات
# class BotHandler:
#     def __init__(self, token, db_handler, user_manager, music_task_manager, searcher):
#         self.application = Application.builder().token(token).build()
#         self.user_manager = user_manager
#         self.music_task_manager = music_task_manager
#         self.searcher = searcher
#         self.setup_handlers()

#     def setup_handlers(self):
#         conv_handler = ConversationHandler(
#             entry_points=[CommandHandler("start", self.start)],
#             states={
#                 MAIN_MENU: [
#                     MessageHandler(filters.Regex("^List$"), self.list_menu),
#                     MessageHandler(filters.Regex("^Set Time$"), self.set_time),
#                 ],
#                 LIST_MENU: [
#                     MessageHandler(filters.Regex("^Edit List$"), self.edit_list_menu),
#                     MessageHandler(filters.Regex("^Remove List$"), self.remove_list),
#                     MessageHandler(filters.Regex("^Back$"), self.back_to_main_menu),
#                 ],
#                 EDIT_LIST_MENU: [
#                     MessageHandler(filters.Regex("^Add$"), self.add_singer),
#                     MessageHandler(filters.Regex("^Delete$"), self.delete_singer_menu),
#                     MessageHandler(filters.Regex("^Back$"), self.back_to_list_menu),
#                 ],
#                 ADD_SINGER: [
#                     MessageHandler(filters.Regex("^Back$"), self.back_to_edit_list_menu),
#                     MessageHandler(filters.Regex("^Delete$"), self.ignore_delete_in_add),
#                     MessageHandler(filters.TEXT & ~filters.COMMAND, self.save_singer),
#                 ],
#                 DELETE_SINGER: [
#                     MessageHandler(filters.Regex("^Back$"), self.back_to_edit_list_menu),
#                     MessageHandler(filters.Regex("^Add$"), self.ignore_add_in_delete),
#                     MessageHandler(filters.TEXT & ~filters.COMMAND, self.remove_singer),
#                 ],
#                 REMOVE_LIST_CONFIRM: [
#                     MessageHandler(filters.Regex("^Confirm$"), self.confirm_remove_list),
#                     MessageHandler(filters.Regex("^Cancel$"), self.cancel_remove_list),
#                 ],
#                 SET_TIME: [
#                     MessageHandler(filters.Regex("^Back$"), self.back_to_main_menu),
#                     MessageHandler(filters.TEXT & ~filters.COMMAND, self.save_time),
#                 ],
#             },
#             fallbacks=[CommandHandler("cancel", self.cancel)]
#         )
#         self.application.add_handler(conv_handler)

#     async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         user = update.effective_user
#         self.user_manager.add_user(str(user.id), user.first_name, user.last_name, user.username)
#         reply_markup = ReplyKeyboardMarkup([["List"], ["Set Time"]], resize_keyboard=True)
#         await update.message.reply_text("سلام! لطفاً یکی از گزینه‌ها رو انتخاب کن:", reply_markup=reply_markup)
#         return MAIN_MENU

#     async def list_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         user_id = str(update.effective_user.id)
#         user = self.user_manager.get_user(user_id)
#         singers = user["singer_names"]
#         reply_markup = ReplyKeyboardMarkup([["Edit List"], ["Remove List"], ["Back"]], resize_keyboard=True)
#         text = "\n".join([f"{i+1}. {s['name']} ({s['count']} آهنگ)" for i, s in enumerate(singers)]) if singers else "لیست خوانندگان خالی است."
#         await update.message.reply_text(text, reply_markup=reply_markup)
#         return LIST_MENU

#     async def back_to_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         reply_markup = ReplyKeyboardMarkup([["List"], ["Set Time"]], resize_keyboard=True)
#         await update.message.reply_text("برگشت به منوی قبل", reply_markup=reply_markup)
#         return MAIN_MENU

#     async def back_to_list_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         reply_markup = ReplyKeyboardMarkup([["Edit List"], ["Remove List"], ["Back"]], resize_keyboard=True)
#         await update.message.reply_text("برگشت به منوی قبل", reply_markup=reply_markup)
#         return LIST_MENU

#     async def back_to_edit_list_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         reply_markup = ReplyKeyboardMarkup([["Add"], ["Delete"], ["Back"]], resize_keyboard=True)
#         await update.message.reply_text("برگشت به منوی قبل", reply_markup=reply_markup)
#         return EDIT_LIST_MENU

#     async def ignore_delete_in_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         await update.message.reply_text("لطفاً اسم خواننده و تعداد آهنگ‌ها رو وارد کن، Delete اینجا کار نمی‌کنه!")
#         return ADD_SINGER

#     async def ignore_add_in_delete(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         await update.message.reply_text("لطفاً اسم خواننده‌ای که می‌خوای حذف کنی رو وارد کن، Add اینجا کار نمی‌کنه!")
#         return DELETE_SINGER

#     async def show_singers(self, user_id, update):
#         user = self.user_manager.get_user(user_id)
#         singers = user["singer_names"]
#         text = "\n".join([f"{i+1}. {s['name']} ({s['count']} آهنگ)" for i, s in enumerate(singers)]) if singers else "لیست خالی است."
#         await update.message.reply_text(text)

#     async def edit_list_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         reply_markup = ReplyKeyboardMarkup([["Add"], ["Delete"], ["Back"]], resize_keyboard=True)
#         await update.message.reply_text("با Add خواننده جدید به لیست خوانندگان خود اضافه کنید\nبا Delete خواننده‌ای که می‌خواهید را حذف کنید", reply_markup=reply_markup)
#         return EDIT_LIST_MENU

#     async def add_singer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         user_id = str(update.effective_user.id)
#         await self.show_singers(user_id, update)
#         await update.message.reply_text("اسم خواننده و تعداد آهنگ‌ها رو در دو خط جداگانه وارد کن (مثال:\nحامیم\n2):")
#         return ADD_SINGER

#     async def save_singer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         user_id = str(update.effective_user.id)
#         user = self.user_manager.get_user(user_id)
#         text = update.message.text.strip().split("\n")
#         name, count = (text[0], 1) if len(text) == 1 else (text[0], int(text[1]) if text[1].isdigit() else 1)
#         if name.lower() not in [s["name"].lower() for s in user["singer_names"]]:
#             user["singer_names"].append({"name": name, "count": count})
#             self.user_manager.update_user(user_id, user)
#             await update.message.reply_text(f"خواننده '{name}' با {count} آهنگ اضافه شد.")
#         await self.show_singers(user_id, update)
#         return await self.edit_list_menu(update, context)

#     async def delete_singer_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         user_id = str(update.effective_user.id)
#         await self.show_singers(user_id, update)
#         await update.message.reply_text("اسم خواننده‌ای که می‌خوای حذف کنی رو وارد کن:")
#         return DELETE_SINGER

#     async def remove_singer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         user_id = str(update.effective_user.id)
#         user = self.user_manager.get_user(user_id)
#         name = update.message.text.strip()
#         for i, singer in enumerate(user["singer_names"]):
#             if singer["name"].lower() == name.lower():
#                 user["singer_names"].pop(i)
#                 self.user_manager.update_user(user_id, user)
#                 await update.message.reply_text(f"خواننده '{name}' حذف شد.")
#                 break
#         await self.show_singers(user_id, update)
#         return await self.edit_list_menu(update, context)

#     async def remove_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         user_id = str(update.effective_user.id)
#         user = self.user_manager.get_user(user_id)
#         if not user["singer_names"]:
#             await update.message.reply_text("لیست خالی است!")
#             return LIST_MENU
#         await self.show_singers(user_id, update)
#         reply_markup = ReplyKeyboardMarkup([["Confirm"], ["Cancel"]], resize_keyboard=True)
#         await update.message.reply_text("آیا می‌خواهید لیست خوانندگان را حذف کنید؟", reply_markup=reply_markup)
#         return REMOVE_LIST_CONFIRM

#     async def confirm_remove_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         user_id = str(update.effective_user.id)
#         user = self.user_manager.get_user(user_id)
#         user["singer_names"] = []
#         self.user_manager.update_user(user_id, user)
#         await update.message.reply_text("لیست با موفقیت پاک شد.")
#         return await self.back_to_list_menu(update, context)

#     async def cancel_remove_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         reply_markup = ReplyKeyboardMarkup([["List"], ["Set Time"]], resize_keyboard=True)
#         await update.message.reply_text("برگشت به منوی اصلی", reply_markup=reply_markup)
#         return MAIN_MENU

#     async def set_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         user_id = str(update.effective_user.id)
#         keyboard = []
#         for hour in range(0, 24, 2):
#             row = [f"{hour:02d}:00", f"{hour+1:02d}:00"]
#             keyboard.append(row)
#         keyboard.append(["Back"])
#         reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
#         await update.message.reply_text("زمان ارسال موزیک‌های جدید را برای خود تعیین کنید:", reply_markup=reply_markup)
#         return SET_TIME

#     async def save_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         user_id = str(update.effective_user.id)
#         selected_time = update.message.text.strip()
#         if selected_time in VALID_TIMES:
#             self.user_manager.update_user(user_id, {"sent_time": selected_time})
#             reply_markup = ReplyKeyboardMarkup([["List"], ["Set Time"]], resize_keyboard=True)
#             await update.message.reply_text(f"زمان ارسال تنظیم شد: {selected_time}", reply_markup=reply_markup)
#             return MAIN_MENU
#         else:
#             await update.message.reply_text("لطفاً یکی از دکمه‌ها را برای زمان ارسال انتخاب کنید:")
#             return SET_TIME

#     async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         reply_markup = ReplyKeyboardMarkup([["List"], ["Set Time"]], resize_keyboard=True)
#         await update.message.reply_text("عملیات لغو شد.", reply_markup=reply_markup)
#         return MAIN_MENU

#     def run(self):
#         self.application.job_queue.run_repeating(self.music_task_manager.run_music_tasks, interval=14400, first=0)
#         self.application.job_queue.run_repeating(lambda context: self.music_task_manager.run_search_task(context, self.user_manager, self.searcher), interval=60, first=0)
#         self.application.run_polling()

# # اجرای ربات
# if __name__ == "__main__":
#     db_handler = DatabaseHandler(DB_NAME)
#     user_manager = UserManager(db_handler)
#     music_task_manager = MusicTaskManager()
#     searcher = TrackSearcher(music_task_manager.track_db_handler)
#     bot = BotHandler(TOKEN, db_handler, user_manager, music_task_manager, searcher)
#     bot.run()
























import sqlite3

DB_PATH = 'tracks.db'

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# حذف ۱۰ ردیف آخر از جدول tracks بر اساس id
cursor.execute("SELECT id FROM tracks ORDER BY id DESC LIMIT 10")
last_10_ids = [row[0] for row in cursor.fetchall()]

if last_10_ids:
    cursor.executemany("DELETE FROM tracks WHERE id = ?", [(id,) for id in last_10_ids])
    print(f"{len(last_10_ids)} ردیف آخر از جدول 'tracks' حذف شدند.")
else:
    print("ردیفی برای حذف وجود ندارد.")

# کاهش مقدار seq در جدول sqlite_sequence
cursor.execute("SELECT seq FROM sqlite_sequence")
row = cursor.fetchone()

if row:
    current_seq = row[0]
    new_seq = max(0, current_seq - 10)
    cursor.execute("UPDATE sqlite_sequence SET seq = ?", (new_seq,))
    print(f"مقدار seq در جدول sqlite_sequence تغییر کرد: {current_seq} → {new_seq}")
else:
    print("ردیفی در جدول sqlite_sequence پیدا نشد.")

conn.commit()
conn.close()
