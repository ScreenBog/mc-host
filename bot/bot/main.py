from __future__ import annotations

import asyncio
import logging
import re
import secrets

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot import api
from bot.config import settings

logging.basicConfig(level=logging.INFO)
router = Router()
ADMIN_ID = 1920838704
SUBDOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$")

JAVA_CORES = [
    ("PAPER", "Paper — плагины"),
    ("FABRIC", "Fabric — лёгкие моды"),
    ("FORGE", "Forge — модпаки"),
    ("NEOFORGE", "NeoForge"),
    ("VANILLA", "Vanilla"),
    ("PURPUR", "Purpur"),
]
BEDROCK_CORES = [("BEDROCK", "Vanilla Bedrock"), ("POCKETMINE", "PocketMine")]
VERSIONS = {
    "PAPER": ["1.21.11", "1.21.1", "1.20.4", "1.20.1"],
    "FABRIC": ["1.21.11", "1.21.1", "1.20.4", "1.20.1"],
    "FORGE": ["1.20.1", "1.19.2", "1.16.5"],
    "NEOFORGE": ["1.21.1", "1.20.1"],
    "VANILLA": ["1.21.11", "1.21.1", "1.20.1"],
    "PURPUR": ["1.21.11", "1.21.1", "1.20.1"],
    "BEDROCK": ["1.21.50"],
    "POCKETMINE": ["1.21.50"],
}


class Order(StatesGroup):
    edition = State()
    core = State()
    version = State()
    name = State()
    subdomain = State()
    mod_query = State()
    console_cmd = State()
    broadcast = State()


def kb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=data) for text, data in row]
            for row in rows
        ]
    )


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID or str(user_id) in (settings.admin_telegram_ids if hasattr(settings, "admin_telegram_ids") else "")


def main_menu(user_id: int) -> InlineKeyboardMarkup:
    rows = [
        [("Создать сервер", "buy")],
        [("Мои серверы", "myservers")],
        [("Панель модов", "panel")],
    ]
    if user_id == ADMIN_ID:
        rows.append([("🛠 Админка", "admin")])
    return kb(rows)


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await api.upsert_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "SHNPP — свой Minecraft как у Aternos, без очереди.\n"
        "Сервер засыпает без игроков и будится по кнопке.",
        reply_markup=main_menu(message.from_user.id),
    )


@router.callback_query(F.data == "buy")
async def buy(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Order.edition)
    await callback.message.edit_text(
        "Шаг 1/4 — издание",
        reply_markup=kb([[("Java", "ed:JAVA")], [("Bedrock", "ed:BEDROCK")]]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ed:"), Order.edition)
async def pick_edition(callback: CallbackQuery, state: FSMContext) -> None:
    edition = callback.data.split(":", 1)[1]
    await state.update_data(edition=edition)
    cores = JAVA_CORES if edition == "JAVA" else BEDROCK_CORES
    await state.set_state(Order.core)
    await callback.message.edit_text(
        "Шаг 2/4 — ядро",
        reply_markup=kb([[(label, f"core:{sid}")] for sid, label in cores]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("core:"), Order.core)
async def pick_core(callback: CallbackQuery, state: FSMContext) -> None:
    core = callback.data.split(":", 1)[1]
    await state.update_data(server_type=core)
    vers = VERSIONS.get(core, ["1.21.1"])
    await state.set_state(Order.version)
    await callback.message.edit_text(
        "Шаг 3/4 — версия (совместимые с ядром)",
        reply_markup=kb([[(v, f"ver:{v}")] for v in vers]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ver:"), Order.version)
async def pick_version(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(game_version=callback.data.split(":", 1)[1])
    await state.set_state(Order.name)
    await callback.message.edit_text("Шаг 4/4 — название сервера")
    await callback.answer()


@router.message(Order.name)
async def pick_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()[:64]
    if len(name) < 2:
        await message.answer("Слишком короткое имя.")
        return
    await state.update_data(name=name)
    await state.set_state(Order.subdomain)
    await message.answer("Поддомен (латиница) или <code>auto</code>")


@router.message(Order.subdomain)
async def pick_subdomain(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip().lower()
    sub = f"s{secrets.token_hex(3)}" if raw in {"auto", "авто"} else raw
    if not SUBDOMAIN_RE.match(sub):
        await message.answer("Только a-z, 0-9 и дефис.")
        return
    data = await state.get_data()
    user = await api.upsert_user(message.from_user.id, message.from_user.username)
    await message.answer("Создаём сервер…")
    try:
        server = await api.create_server(
            {
                "user_id": user["id"],
                "plan_id": "starter",
                "name": data["name"],
                "subdomain": sub,
                "server_type": data["server_type"],
                "game_version": data["game_version"],
                "edition": data.get("edition", "JAVA"),
            }
        )
    except api.ApiError as exc:
        await message.answer(f"Ошибка: {exc.detail[:400]}")
        return
    await state.clear()
    link = await api.magic_link(message.from_user.id, message.from_user.username)
    await message.answer(
        f"Сервер <b>{server['name']}</b> готов.\n"
        f"Адрес: <code>{server.get('address')}:25565</code>\n"
        f"IP: <code>{server.get('ip_address')}</code>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Открыть панель", url=link["url"])],
                [InlineKeyboardButton(text="Управлять", callback_data=f"open:{server['id']}")],
            ]
        ),
    )


@router.callback_query(F.data == "myservers")
async def my_servers(callback: CallbackQuery) -> None:
    rows = await api.servers(callback.from_user.id)
    if not rows:
        await callback.message.edit_text("Серверов нет.", reply_markup=kb([[("Создать", "buy")]]))
        await callback.answer()
        return
    buttons = [[(f"{s['name']} · {s['status']}", f"open:{s['id']}")] for s in rows]
    await callback.message.edit_text("Мои серверы", reply_markup=kb(buttons + [[("Создать", "buy")]]))
    await callback.answer()


@router.callback_query(F.data.startswith("open:"))
async def open_server(callback: CallbackQuery) -> None:
    sid = callback.data.split(":", 1)[1]
    rows = await api.servers(callback.from_user.id)
    s = next((x for x in rows if x["id"] == sid), None)
    if not s:
        await callback.answer("Нет доступа", show_alert=True)
        return
    text = (
        f"<b>{s['name']}</b>\n"
        f"{s['status']} · {s['server_type']} {s['game_version']}\n"
        f"<code>{s.get('address')}</code>\n"
        f"<code>{s.get('ip_address')}</code>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=kb(
            [
                [("▶ Старт", f"pwr:start:{sid}"), ("⏹ Стоп", f"pwr:stop:{sid}"), ("↻", f"pwr:restart:{sid}")],
                [("Консоль", f"cons:{sid}"), ("Моды", f"mods:{sid}")],
                [("Панель", "panel"), ("Назад", "myservers")],
            ]
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pwr:"))
async def power_cb(callback: CallbackQuery) -> None:
    _, action, sid = callback.data.split(":", 2)
    try:
        await api.power(sid, action, callback.from_user.id)
    except api.ApiError as exc:
        await callback.answer(exc.detail[:160], show_alert=True)
        return
    await callback.answer(f"{action} ок")
    callback.data = f"open:{sid}"
    await open_server(callback)


@router.callback_query(F.data.startswith("cons:"))
async def cons(callback: CallbackQuery, state: FSMContext) -> None:
    sid = callback.data.split(":", 1)[1]
    log = await api.console(sid, callback.from_user.id)
    tail = "\n".join((log.get("lines") or "").splitlines()[-15:]) or "пусто"
    await state.set_state(Order.console_cmd)
    await state.update_data(server_id=sid)
    await callback.message.answer(f"<pre>{tail[-3500:]}</pre>\nНапишите команду или /cancel")
    await callback.answer()


@router.message(Order.console_cmd)
async def cons_send(message: Message, state: FSMContext) -> None:
    if (message.text or "").startswith("/"):
        await state.clear()
        await message.answer("Ок", reply_markup=main_menu(message.from_user.id))
        return
    data = await state.get_data()
    try:
        await api.console_cmd(data["server_id"], message.from_user.id, message.text or "")
        await message.answer("Команда отправлена")
    except api.ApiError as exc:
        await message.answer(exc.detail[:300])
    await state.clear()


@router.callback_query(F.data.startswith("mods:"))
async def mods_ask(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Order.mod_query)
    await state.update_data(server_id=callback.data.split(":", 1)[1])
    await callback.message.answer("Напишите название мода/плагина")
    await callback.answer()


@router.message(Order.mod_query)
async def mods_search(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    sid = data["server_id"]
    rows = await api.servers(message.from_user.id)
    s = next((x for x in rows if x["id"] == sid), None)
    loader = (s or {}).get("server_type", "PAPER").lower()
    if loader in {"purpur", "spigot"}:
        loader = "paper"
    ver = (s or {}).get("game_version", "1.21.1")
    hits = await api.search_mods(message.text or "", loader, ver)
    await state.clear()
    if not hits:
        await message.answer("Ничего не найдено")
        return
    buttons = [
        [(f"{h['name'][:28]} · {h['source']}", f"inst:{sid}:{h['source']}:{h['external_id']}")]
        for h in hits[:5]
    ]
    await message.answer("Найдено:", reply_markup=kb(buttons))


@router.callback_query(F.data.startswith("inst:"))
async def inst(callback: CallbackQuery) -> None:
    _, sid, source, ext = callback.data.split(":", 3)
    try:
        await api.install_mod(sid, callback.from_user.id, source, ext)
        await callback.answer("Установлено, нужен рестарт", show_alert=True)
    except api.ApiError as exc:
        await callback.answer(exc.detail[:160], show_alert=True)


@router.callback_query(F.data == "panel")
async def panel(callback: CallbackQuery) -> None:
    link = await api.magic_link(callback.from_user.id, callback.from_user.username)
    await callback.message.answer(
        f"Панель: {link['url']}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Открыть панель", url=link["url"])]]
        ),
    )
    await callback.answer()


@router.message(Command("panel"))
async def panel_cmd(message: Message) -> None:
    link = await api.magic_link(message.from_user.id, message.from_user.username)
    await message.answer(f"Панель: {link['url']}")


@router.message(Command("admin"))
@router.callback_query(F.data == "admin")
async def admin_home(event: Message | CallbackQuery) -> None:
    user_id = event.from_user.id
    if user_id != ADMIN_ID:
        if isinstance(event, CallbackQuery):
            await event.answer("Нет доступа", show_alert=True)
        return
    text = "Админка SHNPP"
    markup = kb(
        [
            [("Все серверы", "ad:servers")],
            [("Метрики", "ad:metrics")],
            [("Рассылка", "ad:bc")],
        ]
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=markup)
        await event.answer()
    else:
        await event.answer(text, reply_markup=markup)


@router.callback_query(F.data == "ad:servers")
async def ad_servers(callback: CallbackQuery) -> None:
    if callback.from_user.id != ADMIN_ID:
        return
    rows = await api.admin_servers()
    lines = [f"{s['subdomain']} · {s['status']} · {s.get('telegram_id')}" for s in rows[:20]]
    buttons = [[(s["subdomain"][:20], f"adopen:{s['id']}")] for s in rows[:10]]
    await callback.message.edit_text("\n".join(lines) or "пусто", reply_markup=kb(buttons + [[("Назад", "admin")]]))
    await callback.answer()


@router.callback_query(F.data.startswith("adopen:"))
async def ad_open(callback: CallbackQuery) -> None:
    if callback.from_user.id != ADMIN_ID:
        return
    sid = callback.data.split(":", 1)[1]
    await callback.message.edit_text(
        f"Сервер {sid}",
        reply_markup=kb(
            [
                [("▶", f"adpwr:start:{sid}"), ("⏹", f"adpwr:stop:{sid}")],
                [("Войти как", f"adimp:{sid}")],
                [("Назад", "ad:servers")],
            ]
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adpwr:"))
async def ad_pwr(callback: CallbackQuery) -> None:
    if callback.from_user.id != ADMIN_ID:
        return
    _, action, sid = callback.data.split(":", 2)
    await api.admin_power(sid, action)
    await callback.answer(action)


@router.callback_query(F.data == "ad:metrics")
async def ad_metrics(callback: CallbackQuery) -> None:
    if callback.from_user.id != ADMIN_ID:
        return
    ov = await api.admin_overview()
    await callback.message.edit_text(
        f"Серверы: {ov.get('servers')}\nПользователи: {ov.get('users')}\n"
        f"maintenance={ov.get('flags', {}).get('maintenance')}",
        reply_markup=kb([[("Назад", "admin")]]),
    )
    await callback.answer()


@router.callback_query(F.data == "ad:bc")
async def ad_bc(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(Order.broadcast)
    await callback.message.answer("Текст рассылки:")
    await callback.answer()


@router.message(Order.broadcast)
async def ad_bc_send(message: Message, state: FSMContext) -> None:
    if message.from_user.id != ADMIN_ID:
        return
    await state.clear()
    await message.answer("Рассылка принята (доставка через бота следующими тиками).")


async def main() -> None:
    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is empty")
    bot = Bot(
        settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    me = await bot.get_me()
    logging.info("Bot @%s api=%s", me.username, settings.api_base_url)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
