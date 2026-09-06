# Бета SHNENEPEPE на Windows

Белый IP хоста: **178.47.143.15**  
Локальный IP этой машины: **192.168.0.148**

Docker на ПК нет — бета крутится нативно: FastAPI + Nuxt + Paper (Java) + Python mc-router на порту 25565.

## DNS (Cloudflare)

Зона **shnenepepe.online** (веб, proxy ON):

| Имя | Тип | Значение | Proxy |
| --- | --- | --- | --- |
| `@` | A | `178.47.143.15` | ON (оранжевое облако) |
| `api` | A | `178.47.143.15` | ON |

Зона **shnenepepe.ru** (игра, proxy OFF — Cloudflare не проксирует TCP Minecraft):

| Имя | Тип | Значение | Proxy |
| --- | --- | --- | --- |
| `node1` | A | `178.47.143.15` | OFF (серое облако) |
| `beta` | CNAME | `node1.shnenepepe.ru` | OFF |
| `*` | CNAME | `node1.shnenepepe.ru` | OFF |

Игрок вводит `beta.shnenepepe.ru` без порта (25565).

## Проброс портов на роутере

На роутере WAN → `192.168.0.148`:

- TCP **8000** — панель и API (бета)
- TCP **25565** — Minecraft
- позже: TCP **80** и **443** (Nginx + Origin CA)

Windows Firewall: правила `SHNENEPEPE-API` (8000) и `SHNENEPEPE-MC` (25565).

## Как зайти в бету

1. Панель: http://192.168.0.148:8000 (из дома) или http://178.47.143.15:8000 (с интернета, после проброса).
2. Ссылка входа печатается скриптом запуска (`panel`).
3. Minecraft: `beta.shnenepepe.ru` или `192.168.0.148:25565` (пока DNS не прописан).
4. `online-mode=false` — можно зайти без лицензии.

Первый старт Paper качает vanilla-jar 1–3 минуты. Смотрите `data/servers/<id>/process.log`.

## Что ещё не в бете

Telegram-бот, ЮKassa, Cloudflare API, Docker Scale-to-Zero. Это Linux-прод (`docker compose`).
