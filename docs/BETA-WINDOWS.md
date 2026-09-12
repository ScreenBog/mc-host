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

Панель (актуальный нод): http://192.168.0.7:8000  
Бот: [@mchost_robot](https://t.me/mchost_robot) → Панель модов.

Админ 1920838704: в боте `/admin`, на сайте скрытый URL `/admin`.

Поставить мод: сервер → Дополнения → lithium → Установить → Рестарт → копировать адрес.

Minecraft, клиент **26.2 / 1.21.11** (не 1.16.5):

- из дома: `192.168.0.148:25565`
- после DNS: `beta.shnenepepe.ru`
- с интернета (после проброса 25565): `178.47.143.15:25565`

`online-mode=false` — заход без лицензии.

Перезапуск API (Paper не гасить): `powershell -File C:\Users\1\mc-hosting\scripts\start_beta.ps1`

## Что ещё не в бете

Telegram-бот, ЮKassa, Cloudflare API, Docker Scale-to-Zero. Это Linux-прод (`docker compose`).
