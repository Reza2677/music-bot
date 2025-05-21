#!/bin/bash
set -ex

echo "--- Starting custom Koyeb build script ---"
PYTHON_EXEC="/app/.heroku/python/bin/python" # مسیر پایتون نصب شده توسط Buildpack

if [ ! -f "$PYTHON_EXEC" ]; then
    echo "ERROR: Python executable not found at $PYTHON_EXEC"
    exit 1
fi

echo "Using Python at $PYTHON_EXEC: $($PYTHON_EXEC --version)"
echo "Attempting to install Playwright browsers..."
"$PYTHON_EXEC" -m playwright install --with-deps chromium

echo "--- Playwright browser installation attempted. ---"
echo "--- Custom Koyeb build script finished. ---"