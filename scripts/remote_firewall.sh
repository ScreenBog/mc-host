#!/bin/bash
set -euo pipefail
# CachyOS / firewalld or nftables / ufw — try common options
if command -v firewall-cmd >/dev/null 2>&1; then
  sudo firewall-cmd --permanent --add-port=8000/tcp || true
  sudo firewall-cmd --permanent --add-port=25565/tcp || true
  sudo firewall-cmd --reload || true
  echo "firewalld updated"
elif command -v ufw >/dev/null 2>&1; then
  sudo ufw allow 8000/tcp || true
  sudo ufw allow 25565/tcp || true
  echo "ufw updated"
else
  # nftables direct accept on input for LAN
  if command -v nft >/dev/null 2>&1; then
    sudo nft list ruleset >/tmp/nft-before.txt 2>/dev/null || true
    sudo nft add table inet filter 2>/dev/null || true
    sudo nft add chain inet filter input '{ type filter hook input priority 0; policy accept; }' 2>/dev/null || true
    echo "nft present; policy likely accept already"
  fi
fi
# Also ensure services listen on 0.0.0.0 (already do)
ss -tlnp | grep -E ':8000|:25565|:25566' || true
# Test local
curl -fsS http://127.0.0.1:8000/healthz; echo
# iptables ACCEPT if iptables-nft
if command -v iptables >/dev/null 2>&1; then
  sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT 2>/dev/null || true
  sudo iptables -I INPUT -p tcp --dport 25565 -j ACCEPT 2>/dev/null || true
  echo "iptables rules inserted"
fi
echo DONE
