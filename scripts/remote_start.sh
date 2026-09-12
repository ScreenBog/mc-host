#!/bin/bash
set -euo pipefail
ROOT=/home/screen/mc-hosting
cd "$ROOT"
export PYTHONPATH="$ROOT/backend"
export BETA_MODE=true

# Free ports if previous run left them
fuser -k 8000/tcp 2>/dev/null || true
fuser -k 25565/tcp 2>/dev/null || true
fuser -k 25566/tcp 2>/dev/null || true
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 1

mkdir -p "$ROOT/data/servers" "$ROOT/logs"
nohup "$ROOT/.venv/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  >"$ROOT/logs/api.log" 2>&1 &
echo $! >"$ROOT/logs/api.pid"
echo "API pid=$(cat "$ROOT/logs/api.pid")"

for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/healthz >/dev/null 2>&1; then
    echo "API up"
    break
  fi
  sleep 1
done
curl -fsS http://127.0.0.1:8000/healthz
echo

curl -fsS -X POST http://127.0.0.1:8000/api/v1/dev/bootstrap \
  -H 'Content-Type: application/json' \
  -d '{}' | tee "$ROOT/logs/bootstrap.json"
echo
