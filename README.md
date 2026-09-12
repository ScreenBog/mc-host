# SHNPP — хостинг Minecraft

Свой Aternos: кнопка «Старт» → игра. Один порт **25565**, сервер **спит без игроков**.

## Как зайти в панель

1. Telegram-бот [@mchost_robot](https://t.me/mchost_robot) → **Панель модов** (Magic Link).
2. Сайт: `PUBLIC_WEB_ORIGIN` из `.env` (бета: http://192.168.0.7:8000).
3. Мастер из 4 шагов: издание → ядро → версия → имя/поддомен.
4. Вкладка **Дополнения**: поиск Lithium / ViaVersion → Установить (зависимости подтягиваются).
5. **Старт** → копировать адрес `поддомен.game_domain` или `IP:25565`.

## Админ (только Telegram ID 1920838704)

- Бот: `/admin` или скрытая кнопка в меню.
- Сайт: `/admin` — в обычной навигации не показывается, пускает JWT с этим telegram_id.
- Env: `ADMIN_TELEGRAM_IDS=1920838704`

## Моды

`GET /api/v1/mods/search?query=&loader=&game_version=&source=both&project_type=mod`  
CurseForge `allowModDistribution=false` → не 500, а «нужна ручная загрузка».

## Бета Windows / Linux без Docker

`scripts/start_beta.ps1` (Windows) или `scripts/remote_start.sh` (Linux).  
Оркестратор: `java_orchestrator` + локальный mc-router.  
Linux+Docker: `docker compose up -d`.

`.env`, база и jar в git не кладутся.
