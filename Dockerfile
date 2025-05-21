# 1. استفاده از یک ایمیج پایه پایتون
# از نسخه‌ای استفاده کنید که با کد شما سازگار است و Playwright آن را پشتیبانی می‌کند.
# python:3.10-slim یا python:3.11-slim گزینه‌های خوبی هستند.
FROM python:3.10-slim

# 2. تنظیم متغیرهای محیطی برای پایتون (جلوگیری از بافر شدن خروجی و نوشتن pyc)
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

# 3. نصب وابستگی‌های سیستمی مورد نیاز Playwright و سایر ابزارها
# این لیست ممکن است نیاز به تنظیم دقیق‌تری داشته باشد، اما برای شروع خوب است.
RUN apt-get update && apt-get install -y --no-install-recommends \
    # وابستگی‌های اصلی Playwright برای Chromium
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 \
    # فونت‌ها برای رندر صحیح صفحات وب
    fonts-liberation \
    # ابزارهای دیگر که ممکن است مفید باشند
    curl \
    bash \
    # پاک کردن کش apt برای کاهش حجم ایمیج
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 4. تنظیم پوشه کاری داخل کانتینر
WORKDIR /app

# 5. کپی کردن فایل‌های نیازمندی‌ها و نصب پکیج‌های پایتون
COPY requirements.txt .
# ابتدا پکیج‌های پایتون را نصب می‌کنیم تا از کش Docker بهتر استفاده شود
RUN pip install --no-cache-dir -r requirements.txt

# 6. نصب مرورگرهای Playwright
# --with-deps قبلاً وابستگی‌های سیستم را نصب کرده، اما اینجا هم بی‌ضرر است.
# یا می‌توانید فقط playwright install chromium را بزنید.
RUN python -m playwright install --with-deps chromium
# اگر به مرورگرهای دیگر هم نیاز دارید، آنها را هم اضافه کنید:
# RUN python -m playwright install firefox webkit

# 7. کپی کردن بقیه کدهای پروژه به داخل کانتینر
COPY . .

# 8. مشخص کردن پورتی که برنامه شما روی آن گوش می‌دهد (Koyeb از $PORT استفاده می‌کند)
# این دستور به خودی خود پورت را باز نمی‌کند، فقط به Docker اطلاع می‌دهد.
EXPOSE 8080

# 9. دستور اجرای برنامه شما
# Koyeb از متغیر محیطی PORT استفاده می‌کند، پس ما هم از آن استفاده می‌کنیم.
# CMD ["uvicorn", "main:create_starlette_app", "--host", "0.0.0.0", "--port", "8080", "--factory", "--workers", "1"]
# یا بهتر است از متغیر محیطی PORT که Koyeb می‌دهد استفاده کنیم:
CMD uvicorn main:create_starlette_app --host 0.0.0.0 --port $PORT --factory --workers 1


