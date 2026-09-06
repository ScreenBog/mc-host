#!/usr/bin/env bash
# Isolate Docker networks from the home LAN (RFC1918) while allowing
# container-to-container traffic on Docker bridges.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "run as root" >&2
  exit 1
fi

iptables -N DOCKER-USER 2>/dev/null || true

# Allow established/related
iptables -C DOCKER-USER -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN 2>/dev/null \
  || iptables -I DOCKER-USER 1 -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN

# Allow traffic between Docker bridges (compose networks live in 172.16/12)
iptables -C DOCKER-USER -s 172.16.0.0/12 -d 172.16.0.0/12 -j RETURN 2>/dev/null \
  || iptables -I DOCKER-USER 2 -s 172.16.0.0/12 -d 172.16.0.0/12 -j RETURN

# Drop any remaining traffic from Docker toward private LAN ranges
for dest in 192.168.0.0/16 10.0.0.0/8 172.16.0.0/12 169.254.0.0/16; do
  iptables -C DOCKER-USER -d "$dest" -j DROP 2>/dev/null \
    || iptables -A DOCKER-USER -d "$dest" -j DROP
done

# Kernel hardening from the spec
sysctl -w net.ipv4.tcp_syncookies=1
sysctl -w net.ipv4.conf.all.rp_filter=1
sysctl -w net.ipv4.conf.default.rp_filter=1

echo "DOCKER-USER isolation applied."
iptables -L DOCKER-USER -n -v
