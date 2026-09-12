#!/bin/bash
set -euo pipefail
ROOT=/home/screen/mc-hosting
cd "$ROOT/bot"
export PYTHONPATH="$ROOT/bot"

pkill -f "python -m bot.main" 2>/dev/null || true
pkill -f "bot.main" 2>/dev/null || true
sleep 1

# Ensure aiogram present
"$ROOT/.venv/bin/pip" install -q "aiogram>=3.17" httpx pydantic-settings

nohup "$ROOT/.venv/bin/python" -m bot.main >"$ROOT/logs/bot.log" 2>&1 &
echo $! >"$ROOT/logs/bot.pid"
sleep 2
echo "bot pid=$(cat "$ROOT/logs/bot.pid")"
tail -20 "$ROOT/logs/bot.log"
