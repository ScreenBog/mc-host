# SHNPP — хостинг Minecraft

Кастомный оркестратор: **Docker Engine API + itzg/mc-router**, без Pterodactyl/Pelican.

- Один порт **25565** на все инстансы (hostname из Handshake).
- Scale-to-Zero: контейнер гасится без игроков и будится при входе (MOTD ожидания).
- Зоны: `shnpp.online` — веб (Cloudflare Proxy), `*.shnpp.ru` — игра (DNS only).
- Биллинг: Telegram-бот → ЮKassa → webhook → контейнер + CNAME.
- Моды: Modrinth API v2 + CurseForge Core, кэш Redis 15 минут.

## Состав репозитория

```
backend/   FastAPI + Docker SDK + Taskiq
bot/        aiogram 3
web/        Nuxt 3 панель модов
sql/        PostgreSQL DDL + тарифы
nginx/      Origin CA, reverse proxy
scripts/    iptables изоляция LAN
```

## Быстрый старт (Linux-хост с белым IP)

1. Скопируйте `.env.example` → `.env` и заполните секреты.
2. Origin CA: `nginx/certs/origin.crt` и `origin.key`, в Cloudflare SSL = **Full (strict)**.
3. DNS:
   - `shnpp.online`, `api.shnpp.online` — A, proxy **on**
   - `node1.shnpp.ru` — A на белый IP, proxy **off**
4. Каталог данных: `sudo mkdir -p /var/mc_hosting/servers && sudo chown 1000:1000 /var/mc_hosting/servers`
5. Файрвол: `sudo bash scripts/firewall.sh`
6. `cp scripts/sysctl-mc.conf /etc/sysctl.d/99-mc-hosting.conf && sudo sysctl --system`
7. `docker compose up -d --build`

Webhook ЮKassa: `https://api.shnpp.online/api/v1/payments/webhook`.  
Проверка IP: диапазоны из [документации ЮKassa](https://yookassa.ru/developers/using-api/webhooks). Для локального теста `YOOKASSA_IP_CHECK=false`.

## Поток оплаты

1. Бот собирает тариф / ядро / версию / поддомен.
2. `Payment.create` с Idempotence-Key UUIDv4.
3. `payment.succeeded` → сверка IP → `Payment.find_one` → Taskiq `provision_invoice`.
4. Docker: `itzg/minecraft-server`, labels `mc-router.host=<sub>.shnpp.ru`.
5. Cloudflare: CNAME `<sub>.shnpp.ru` → `node1.shnpp.ru`, **proxied=false**.
6. За 24 часа до `expires_at` — кнопка «Продлить». В ноль — `SUSPENDED`. Через 7 дней — том и DNS удаляются.

## Моды

`GET /api/v1/mods/search?query=&loader=&game_version=`  
User-Agent Modrinth обязателен. CurseForge `allowModDistribution=false` → HTTP 403 и ручная загрузка в `downloads/`.

На уже запущенном сервере jar пишется в `/var/mc_hosting/servers/<id>/mods`.

## Тесты бэкенда

```
cd backend
python -m pip install -r requirements.txt
python -m pytest
```

## Что нужно с вашей стороны

- Токен Telegram-бота, магазин ЮKassa, Cloudflare API token (DNS Write на зону `shnpp.ru`), ключ CurseForge.
- Linux-хост 32–64 ГБ RAM, Docker Engine, белый IP (или VPS-туннель GRE/WireGuard, как в спецификации).
