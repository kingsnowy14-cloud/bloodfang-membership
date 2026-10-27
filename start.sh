#!/usr/bin/env bash
set -uo pipefail

# Fail immediately with a clear log message if Railway is missing the bot token.
if [[ -z "${DISCORD_BOT_TOKEN:-}" ]]; then
  echo "[startup] ERROR: DISCORD_BOT_TOKEN is not set in Railway Variables." >&2
  exit 1
fi

# Run the bot with automatic restart so a transient Discord/network error does
# not permanently leave the website online while the bot is offline.
run_bot() {
  while true; do
    echo "[startup] Starting Discord bot..."
    python -u bot.py
    status=$?
    echo "[startup] Discord bot exited with status ${status}; restarting in 5 seconds..."
    sleep 5
  done
}

run_bot &
BOT_PID=$!

echo "[startup] Starting website with Gunicorn on port ${PORT:-8080}..."
gunicorn app:app --bind "0.0.0.0:${PORT:-8080}" --workers 1 --threads 4 --timeout 120 &
WEB_PID=$!

cleanup() {
  echo "[startup] Stopping website and Discord bot..."
  kill "$WEB_PID" "$BOT_PID" 2>/dev/null || true
  wait "$WEB_PID" 2>/dev/null || true
  wait "$BOT_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Keep the service alive as long as the website process is running.
wait "$WEB_PID"
WEB_STATUS=$?
exit "$WEB_STATUS"
