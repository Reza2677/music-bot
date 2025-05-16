import logging
import ijson
import re
import os
from pathlib import Path

class JsonSearcher:
    def __init__(self, log_file="json_search.log", json_file="track_details.json"):
        # تنظیمات لاگ‌نویسی
        self.setup_logging(log_file)
        self.logger = logging.getLogger(__name__)
        self.json_file = json_file  # فایل JSON ورودی

    def setup_logging(self, log_file):
        """Setup logging configuration with INFO level, filtering only specific messages"""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)

        # حذف تمام handlerهای پیش‌فرض
        logger.handlers = []

        # تنظیم handler برای کنسول با کدگذاری پیش‌فرض سیستمی
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(message)s')  # فقط پیام رو نمایش بده
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # تنظیم handler برای فایل با کدگذاری پیش‌فرض سیستمی
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)

    def is_english(self, text):
        """Check if the text is in English (including numbers, case-insensitive) using simple regex"""
        # تبدیل متن به حروف کوچک برای نادیده گرفتن حروف بزرگ/کوچک
        text = text.strip().lower()
        # بررسی اینکه آیا متن فقط شامل کاراکترهای انگلیسی (A-Z, a-z)، اعداد (0-9)، و فاصله هست یا نه
        return bool(re.match(r'^[a-z0-9\s]+$', text))

    def search_json(self, search_list):
        """
        Search the JSON file for names in the search_list using streaming, returning a list of matching tracks.
        Each item in search_list can be a string (converted to (name, 1)) or a tuple (name) or (name, count) where count defaults to 1 if not provided.
        Returns a list of dictionaries matching the search criteria.
        """
        try:
            # بررسی وجود فایل و دسترسی به اون
            path = Path(self.json_file)
            if not path.exists() or not path.is_file():
                return []

            # چک کردن دسترسی خواندن با os.access
            if not os.access(self.json_file, os.R_OK):
                return []

            # لیست نهایی برای ذخیره نتایج
            result = []

            # پردازش هر آیتم توی لیست ورودی
            for item in search_list:
                # اگر آیتم رشته باشه، اون رو به تاپل تک‌عنصری تبدیل کن
                if isinstance(item, str):
                    name = item
                    count = 1  # پیش‌فرض اگر عدد وارد نشده
                elif isinstance(item, tuple):
                    if len(item) == 1:
                        name = item[0]
                        count = 1  # پیش‌فرض اگر عدد وارد نشده
                    elif len(item) == 2:
                        name, count = item
                        # مطمئن شو count یه عدد مثبت هست
                        try:
                            count = int(count)
                            if count <= 0:
                                count = 1
                        except (ValueError, TypeError):
                            count = 1
                    else:
                        continue
                else:
                    continue

                # فقط پیام جستجو رو لاگ کن
                self.logger.info(f"Searching for '{name}' {count} time(s)")
                found_count = 0

                # بررسی اینکه نام انگلیسی هست یا فارسی (با تبدیل به حروف کوچک برای نادیده گرفتن حروف بزرگ/کوچک)
                is_english_name = self.is_english(name)
                search_key = "en_name" if is_english_name else "fa_name"

                # پردازش تدریجی فایل JSON با ijson، با مدیریت دقیق خطاها
                try:
                    with open(self.json_file, 'rb') as f:
                        parser = ijson.parse(f)
                        current_track = {}
                        for prefix, event, value in parser:
                            if prefix == '':
                                if event == 'start_array':
                                    continue
                                elif event == 'end_array':
                                    break
                            elif prefix.endswith('.link') and event == 'string':
                                current_track['link'] = value
                            elif prefix.endswith('.en_name') and event == 'string':
                                current_track['en_name'] = value
                            elif prefix.endswith('.en_track') and event == 'string':
                                current_track['en_track'] = value
                            elif prefix.endswith('.fa_name') and event == 'string':
                                current_track['fa_name'] = value
                            elif prefix.endswith('.fa_track') and event == 'string':
                                current_track['fa_track'] = value
                            elif prefix.endswith('.download_link') and event == 'string':
                                current_track['download_link'] = value
                            elif event == 'end_map':  # وقتی یه دیکشنری کامل شد
                                # تبدیل مقدار سرچ‌شده به حروف کوچک برای نادیده گرفتن حروف بزرگ/کوچک
                                track_value = current_track.get(search_key, "").lower()
                                search_name = name.lower()
                                if track_value == search_name and found_count < count:
                                    result.append(current_track.copy())  # اضافه کردن دیکشنری به لیست نتایج
                                    found_count += 1

                                current_track = {}  # ریست کردن دیکشنری برای دیکشنری بعدی
                except (PermissionError, IOError, ijson.JSONError) as e:
                    self.logger.error(f"Error accessing or parsing file: {e}")
                    return []  # اگر خطای دسترسی یا پارس پیش اومد، لیست خالی برگردون

            if result:
                self.logger.info(f"Search completed. Found {len(result)} matching tracks")
            return result

        except Exception as e:
            self.logger.error(f"Unexpected error searching JSON: {e}")
            return []

def main():
    # لیست ورودی با تاپل‌های تک‌عنصری، دوعنصری، یا رشته‌ها
    search_list = [("Sina Shabankhani"), ("Roozbeh Bemani", 1), "اپیکور"]
    searcher = JsonSearcher()
    result = searcher.search_json(search_list)
    
    # چاپ فقط خروجی (بدون پیام اضافی)
    if result:
        print("Search results:")
        for track in result:
            print(track)
    else:
        print("No results found.")

if __name__ == "__main__":
    main()