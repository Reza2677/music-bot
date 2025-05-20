#!/bin/bash
set -e # در صورت بروز خطا، اسکریپت متوقف شود

echo ">>> Starting custom Koyeb build script..."

# تلاش برای یافتن و اجرای playwright
# این مسیرها فقط حدس هستند و ممکن است نیاز به تغییر داشته باشند
if [ -f "/app/.heroku/python/bin/playwright" ]; then
    echo "Found playwright at /app/.heroku/python/bin/playwright"
    /app/.heroku/python/bin/playwright install --with-deps chromium
elif [ -f "$HOME/.local/bin/playwright" ]; then
    echo "Found playwright at $HOME/.local/bin/playwright"
    "$HOME/.local/bin/playwright" install --with-deps chromium
elif command -v python &>/dev/null && python -m playwright --version &>/dev/null; then
    echo "Found playwright via python -m"
    python -m playwright install --with-deps chromium
else
    echo "ERROR: Could not find playwright executable or run via python -m."
    # تلاش برای یافتن مسیر python و site-packages برای دیباگ بیشتر
    echo "Attempting to find python and site-packages..."
    which python || echo "python not in PATH"
    python -c "import site; print(site.getsitepackages())" || echo "Could not get site-packages"
    exit 1
fi

echo ">>> Playwright browser installation attempted."
echo ">>> Custom Koyeb build script finished."