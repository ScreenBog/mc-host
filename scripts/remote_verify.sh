#!/bin/bash
set -euo pipefail
echo "== ports =="
ss -tlnp | grep -E ':8000|:25565|:25566' || true
echo "== health =="
curl -fsS http://127.0.0.1:8000/healthz; echo
echo "== site =="
curl -fsS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/
echo "== plans =="
curl -fsS http://127.0.0.1:8000/api/v1/plans | head -c 200; echo
echo "== mc status ping =="
python3.12 - <<'PY'
import socket, struct
def varint(n):
    out=b''
    while True:
        b=n & 0x7f; n >>= 7
        out += bytes([b | (0x80 if n else 0)])
        if not n: return out
def pack_str(s):
    b=s.encode(); return varint(len(b))+b
def ping(host):
    s=socket.create_connection(('127.0.0.1',25565),5)
    payload=varint(770)+pack_str(host)+struct.pack('>H',25565)+varint(1)
    s.sendall(varint(len(payload)+1)+b'\x00'+payload)
    s.sendall(varint(1)+b'\x00')
    s.settimeout(5)
    data=s.recv(4096); s.close(); return data
for h in ('beta.shnenepepe.ru','192.168.0.7','127.0.0.1'):
    try:
        d=ping(h)
        print(h, 'OK', d[2:70])
    except Exception as e:
        print(h, 'FAIL', e)
PY
echo DONE
