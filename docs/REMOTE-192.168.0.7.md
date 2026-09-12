# Хост screen@192.168.0.7

Проект: `/home/screen/mc-hosting`

| Сервис | Адрес |
| --- | --- |
| Сайт / API | http://192.168.0.7:8000 |
| Minecraft | `192.168.0.7:25565` |
| Telegram | [@mchost_robot](https://t.me/mchost_robot) |

## Управление

```bash
ssh screen@192.168.0.7
/bin/bash /home/screen/mc-hosting/scripts/remote_status.sh
/bin/bash /home/screen/mc-hosting/scripts/remote_restart_api.sh
/bin/bash /home/screen/mc-hosting/scripts/remote_bot_start.sh
```

Логи: `logs/api.log`, `logs/bot.log`, `data/servers/*/process.log`

Клиент Minecraft: **26.2 / 1.21.11**, `online-mode=false`.
