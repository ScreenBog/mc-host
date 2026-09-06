# SHNPP Minecraft Hosting

Кастомный оркестратор на Docker Engine API + itzg/mc-router вместо Pterodactyl/Pelican.

## Стек

| Слой | Выбор |
| --- | --- |
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| Bot | aiogram 3.x |
| DB / cache | PostgreSQL 16, Redis 7, Taskiq |
| Game | itzg/minecraft-server + itzg/mc-router |
| Web | Nuxt 3, Vue 3, Tailwind, Pinia |
| Edge | Nginx + Cloudflare Origin CA (Full Strict) |

## DNS

| Имя | Тип | Proxy |
| --- | --- | --- |
| shnpp.online | A сайт | on |
| api.shnpp.online | A API / ЮKassa | on |
| node1.shnpp.ru | A белый IP | off |
| `<server>.shnpp.ru` | CNAME → node1.shnpp.ru | off |

Minecraft handshake читается mc-router на :25565, контейнеры без проброса портов в `mc-router-net`.

## Scale-to-Zero

`AUTO_SCALE_UP` / `AUTO_SCALE_DOWN` / `AUTO_SCALE_DOWN_AFTER=15m`. Игрок видит asleep MOTD, пока контейнер поднимается.

## Биллинг

Бот → Payment.create (Idempotence-Key UUIDv4) → webhook `payment.succeeded` → проверка IP ЮKassa + GET Payment → Docker SDK + Cloudflare CNAME.

T=0: STOPPED/SUSPENDED. T+7d: том и DNS удаляются.

## Изоляция

cgroups: memory=plan RAM, swap=RAM, cpus=plan, pids=256, user 1000:1000.
`scripts/firewall.sh` режет Docker → RFC1918 кроме docker-to-docker.
