#!/bin/bash
set -euo pipefail
ROOT=/home/screen/mc-hosting
cd "$ROOT/backend"
export PYTHONPATH="$ROOT/backend"

# Kill only uvicorn, keep Java Paper
if [[ -f "$ROOT/logs/api.pid" ]]; then
  kill "$(cat "$ROOT/logs/api.pid")" 2>/dev/null || true
fi
pkill -f "uvicorn app.main:app" 2>/dev/null || true
fuser -k 8000/tcp 2>/dev/null || true
# Do NOT kill 25566 (Paper). Router is in uvicorn so 25565 will restart.
fuser -k 25565/tcp 2>/dev/null || true
sleep 1

mkdir -p "$ROOT/logs"
nohup "$ROOT/.venv/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  >"$ROOT/logs/api.log" 2>&1 &
echo $! >"$ROOT/logs/api.pid"

for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/healthz >/dev/null 2>&1; then
    echo "API up pid=$(cat "$ROOT/logs/api.pid")"
    break
  fi
  sleep 1
done

# Re-bind mc-router hosts to existing Paper
curl -fsS -X POST http://127.0.0.1:8000/api/v1/dev/bootstrap \
  -H 'Content-Type: application/json' -d '{}' >/dev/null
echo bootstrap_ok
curl -fsS http://127.0.0.1:8000/healthz; echo
