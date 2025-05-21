#!/bin/bash
set -ex # خروج در صورت خطا و چاپ دستورات قبل از اجرا

echo "--- Starting custom Koyeb build script ---"

echo "Current PATH: $PATH"
echo "Current Python version: $(python --version || echo 'python not found')" # ممکن است اینجا هم خطا بدهد اگر LD_LIBRARY_PATH نباشد
echo "Current pip version: $(pip --version || echo 'pip not found')"

# مسیر کتابخانه‌های پایتون را به LD_LIBRARY_PATH اضافه می‌کنیم
PYTHON_LIB_DIR="/app/.heroku/python/lib" # این مسیر رایج برای Buildpack Heroku است
if [ -d "$PYTHON_LIB_DIR" ]; then
    echo "Setting LD_LIBRARY_PATH to include $PYTHON_LIB_DIR"
    export LD_LIBRARY_PATH="$PYTHON_LIB_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
else
    echo "WARNING: Python lib directory $PYTHON_LIB_DIR not found. LD_LIBRARY_PATH not set."
fi
echo "Current LD_LIBRARY_PATH: $LD_LIBRARY_PATH"


echo "Listing site-packages (if possible):"
python -c "import site; print(site.getsitepackages())" || echo "Failed to get site-packages (might be due to LD_LIBRARY_PATH)"

PLAYWRIGHT_EXEC="/app/.heroku/python/bin/playwright"

if [ -f "$PLAYWRIGHT_EXEC" ]; then
    echo "Found playwright at $PLAYWRIGHT_EXEC. Attempting to install browsers..."
    "$PLAYWRIGHT_EXEC" install --with-deps chromium
else
    echo "Playwright executable not found at $PLAYWRIGHT_EXEC. Trying python -m playwright..."
    # به عنوان fallback، اگر مسیر مستقیم کار نکرد، python -m را امتحان می‌کنیم
    # (اگرچه با مشکل LD_LIBRARY_PATH، این هم ممکن است شکست بخورد تا زمانی که LD_LIBRARY_PATH درست شود)
    python -m playwright install --with-deps chromium
fi

echo "--- Playwright browser installation attempted. ---"
echo "--- Custom Koyeb build script finished. ---"