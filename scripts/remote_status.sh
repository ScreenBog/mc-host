#!/bin/bash
echo "== bot log =="
tail -50 /home/screen/mc-hosting/logs/bot.log || true
echo "== api log =="
tail -20 /home/screen/mc-hosting/logs/api.log || true
echo "== procs =="
pgrep -af 'uvicorn|bot.main|paper-server' || true
echo "== ports =="
ss -tlnp | grep -E ':8000|:25565|:25566' || true
echo "== env token set =="
grep '^TELEGRAM_BOT_TOKEN=' /home/screen/mc-hosting/.env | sed 's/=.*/=***SET***/'
echo "== ufw =="
sudo -n ufw status || echo "ufw status failed"
echo "== health =="
curl -fsS http://127.0.0.1:8000/healthz || true
echo
