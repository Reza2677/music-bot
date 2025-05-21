#!/bin/bash
set -ex

echo "--- Starting custom Koyeb build script (simple version) ---"

echo "Attempting to install Playwright browsers using 'python -m playwright'..."
# مستقیماً از python -m استفاده می‌کنیم، با این امید که Buildpack
# محیط را برای اجرای صحیح دستورات پایتون آماده کرده باشد.
python -m playwright install --with-deps chromium

echo "--- Playwright browser installation attempted. ---"
echo "--- Custom Koyeb build script finished. ---"