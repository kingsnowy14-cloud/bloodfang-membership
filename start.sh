#!/usr/bin/env bash
set -e

# Run the Discord bot in the background and keep the Flask website in the foreground.
python -u bot.py &
BOT_PID=$!

# If Gunicorn exits, stop the bot process as well.
cleanup() {
  kill "$BOT_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

exec gunicorn app:app --bind "0.0.0.0:${PORT:-8080}" --workers 1 --threads 4 --timeout 120
