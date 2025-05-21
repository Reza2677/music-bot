# # 1. استفاده از یک ایمیج پایه پایتون
# # از نسخه‌ای استفاده کنید که با کد شما سازگار است و Playwright آن را پشتیبانی می‌کند.
# # python:3.10-slim یا python:3.11-slim گزینه‌های خوبی هستند.
# FROM python:3.10-slim

# # 2. تنظیم متغیرهای محیطی برای پایتون (جلوگیری از بافر شدن خروجی و نوشتن pyc)
# ENV PYTHONUNBUFFERED 1
# ENV PYTHONDONTWRITEBYTECODE 1

# # 3. نصب وابستگی‌های سیستمی مورد نیاز Playwright و سایر ابزارها
# # این لیست ممکن است نیاز به تنظیم دقیق‌تری داشته باشد، اما برای شروع خوب است.
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     # وابستگی‌های اصلی Playwright برای Chromium
#     libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
#     libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
#     libpango-1.0-0 libcairo2 libasound2 \
#     # فونت‌ها برای رندر صحیح صفحات وب
#     fonts-liberation \
#     # ابزارهای دیگر که ممکن است مفید باشند
#     curl \
#     bash \
#     # پاک کردن کش apt برای کاهش حجم ایمیج
#     && apt-get clean \
#     && rm -rf /var/lib/apt/lists/*

# # 4. تنظیم پوشه کاری داخل کانتینر
# WORKDIR /app

# # 5. کپی کردن فایل‌های نیازمندی‌ها و نصب پکیج‌های پایتون
# COPY requirements.txt .
# # ابتدا پکیج‌های پایتون را نصب می‌کنیم تا از کش Docker بهتر استفاده شود
# RUN pip install --no-cache-dir -r requirements.txt

# # 6. نصب مرورگرهای Playwright
# # --with-deps قبلاً وابستگی‌های سیستم را نصب کرده، اما اینجا هم بی‌ضرر است.
# # یا می‌توانید فقط playwright install chromium را بزنید.
# RUN python -m playwright install --with-deps chromium
# # اگر به مرورگرهای دیگر هم نیاز دارید، آنها را هم اضافه کنید:
# # RUN python -m playwright install firefox webkit

# # 7. کپی کردن بقیه کدهای پروژه به داخل کانتینر
# COPY . .

# # 8. مشخص کردن پورتی که برنامه شما روی آن گوش می‌دهد (Koyeb از $PORT استفاده می‌کند)
# # این دستور به خودی خود پورت را باز نمی‌کند، فقط به Docker اطلاع می‌دهد.
# EXPOSE 8080

# # 9. دستور اجرای برنامه شما
# # Koyeb از متغیر محیطی PORT استفاده می‌کند، پس ما هم از آن استفاده می‌کنیم.
# # CMD ["uvicorn", "main:create_starlette_app", "--host", "0.0.0.0", "--port", "8080", "--factory", "--workers", "1"]
# # یا بهتر است از متغیر محیطی PORT که Koyeb می‌دهد استفاده کنیم:
# CMD uvicorn main:create_starlette_app --host 0.0.0.0 --port $PORT --factory --workers 1



# --- STAGE 1: Build Stage ---
# استفاده از یک ایمیج کامل‌تر پایتون برای بیلد کردن وابستگی‌ها،
# چون ممکن است برخی پکیج‌ها برای کامپایل به ابزارهای بیشتری نیاز داشته باشند.
FROM python:3.10 as builder

# تنظیم متغیرهای محیطی
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    # متغیرهای مربوط به Poetry یا Pipenv اگر استفاده می‌کنید
    POETRY_VERSION=1.7.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    PATH="$POETRY_HOME/bin:$PATH"

# نصب وابستگی‌های سیستمی مورد نیاز Playwright و ابزارهای بیلد
RUN apt-get update && apt-get install -y --no-install-recommends \
    # وابستگی‌های اصلی Playwright برای Chromium
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 \
    # فونت‌ها
    fonts-liberation \
    curl \
    bash \
    build-essential \
    # پاک کردن کش apt
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ایجاد یک محیط مجازی برای نصب پکیج‌های پایتون
WORKDIR /opt/venv
RUN python -m venv .
ENV PATH="/opt/venv/bin:$PATH"

# کپی کردن فایل نیازمندی‌ها و نصب پکیج‌های پایتون در محیط مجازی
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نصب مرورگرهای Playwright
# این دستور از محیط مجازی فعال شده استفاده خواهد کرد
RUN python -m playwright install --with-deps chromium
# اگر به مرورگرهای دیگر هم نیاز دارید:
# RUN python -m playwright install firefox webkit


# --- STAGE 2: Runtime Stage ---
# استفاده از یک ایمیج پایه بسیار سبک‌تر برای اجرای برنامه
FROM python:3.10-slim

# تنظیم متغیرهای محیطی برای پایتون
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONHOME=/usr/local # برای ایمیج‌های slim رسمی پایتون معمولاً این است
ENV PYTHONPATH=/usr/local/lib/python3.10:/usr/local/lib/python3.10/site-packages # و مسیر site-packages

# نصب فقط وابستگی‌های سیستمی *ضروری* برای اجرای Playwright (نه بیلد آن)
# این لیست باید با لیستی که Playwright برای اجرای مرورگر نیاز دارد مطابقت داشته باشد.
# دستور playwright install --with-deps chromium در مرحله بیلد، این‌ها را نصب می‌کند،
# اما برای اطمینان و کامل بودن، برخی از مهم‌ترین‌ها را اینجا هم می‌آوریم.
# توجه: این بخش ممکن است نیاز به تنظیم دقیق داشته باشد.
# اگر playwright install --with-deps در مرحله builder همه چیز را نصب کرده،
# ممکن است این بخش در runtime stage خیلی ضروری نباشد یا بتوان آن را خلاصه‌تر کرد.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 \
    fonts-liberation \
    # پاک کردن کش apt
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# تنظیم پوشه کاری
WORKDIR /app

# کپی کردن محیط مجازی و مرورگرهای نصب شده از Build Stage
# این مهمترین بخش multi-stage build برای Playwright است
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright # مسیر پیش‌فرض کش Playwright برای مرورگرها

# فعال کردن محیط مجازی برای دستورات بعدی و برای اجرای برنامه
ENV PATH="/opt/venv/bin:$PATH"
# تنظیم متغیر محیطی که Playwright برای پیدا کردن مرورگرها استفاده می‌کند
# این مسیر باید با جایی که playwright install مرورگرها را نصب کرده مطابقت داشته باشد
# معمولاً در /root/.cache/ms-playwright یا اگر کاربر دیگری استفاده شده، مسیر مشابهی خواهد بود.
# اگر PLAYWRIGHT_BROWSERS_PATH را تنظیم نکنید، Playwright سعی می‌کند از مسیرهای پیش‌فرض استفاده کند.
# ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

# کپی کردن فقط کدهای برنامه از Build Stage (یا از هاست)
COPY . .
# اگر کدها در مرحله builder هم کپی شده بودند و تغییری نکرده‌اند، می‌توان از آنجا کپی کرد:
# COPY --from=builder /app /app

# مشخص کردن پورتی که برنامه روی آن گوش می‌دهد
EXPOSE 8080

# دستور اجرای برنامه
# Koyeb متغیر PORT را تنظیم می‌کند
CMD uvicorn main:create_starlette_app --host 0.0.0.0 --port $PORT --factory --workers 1