from __future__ import annotations

import asyncio
import logging
import re


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
SUBDOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$")
VERSIONS = ["1.21.1", "1.20.4", "1.20.1", "1.19.4", "1.16.5"]
TYPES = ["PAPER", "PURPUR", "FABRIC", "FORGE", "NEOFORGE", "VANILLA"]


class Order(StatesGroup):
    plan = State()
    server_type = State()
    game_version = State()
    name = State()
    subdomain = State()


def kb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=data) for text, data in row]
            for row in rows
        ]
    )


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await api.upsert_user(message.from_user.id, message.from_user.username)
    await state.update_data(db_user_id=user["id"])
    await message.answer(
        "Хостинг Minecraft на одном порту 25565.\n"
        "Серверы засыпают без игроков и просыпаются при входе.",
        reply_markup=kb(
            [
                [("Купить сервер", "buy")],
                [("Мои серверы", "myservers")],
                [("Панель модов", "panel")],
            ]
        ),
    )


@router.callback_query(F.data == "buy")
async def buy(callback: CallbackQuery, state: FSMContext) -> None:
    plans = await api.plans()
    await state.set_state(Order.plan)
    await callback.message.edit_text(
        "Выберите тариф:",
        reply_markup=kb(
            [
                [
                    (
                        f"{p['name']} — {p['ram_mb']} МБ / {p['price_monthly']} ₽",
                        f"plan:{p['id']}",
                    )
                ]
                for p in plans
            ]
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("plan:"), Order.plan)
async def pick_plan(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(plan_id=callback.data.split(":", 1)[1])
    await state.set_state(Order.server_type)
    await callback.message.edit_text(
        "Ядро:",
        reply_markup=kb([[(t, f"type:{t}")] for t in TYPES]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("type:"), Order.server_type)
async def pick_type(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(server_type=callback.data.split(":", 1)[1])
    await state.set_state(Order.game_version)
    await callback.message.edit_text(
        "Версия Minecraft:",
        reply_markup=kb([[(v, f"ver:{v}")] for v in VERSIONS]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ver:"), Order.game_version)
async def pick_version(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(game_version=callback.data.split(":", 1)[1])
    await state.set_state(Order.name)
    await callback.message.edit_text("Название сервера (как в панели):")
    await callback.answer()


@router.message(Order.name)
async def pick_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()[:64]
    if len(name) < 2:
        await message.answer("Слишком короткое имя.")
        return
    await state.update_data(name=name)
    await state.set_state(Order.subdomain)
    await message.answer("Поддомен (латиница, без точки). Адрес будет <code>имя.shnenepepe.ru</code>.")


@router.message(Order.subdomain)
async def pick_subdomain(message: Message, state: FSMContext) -> None:
    sub = (message.text or "").strip().lower()
    if not SUBDOMAIN_RE.match(sub):
        await message.answer("Только a-z, 0-9 и дефис.")
        return
    data = await state.get_data()
    user = await api.upsert_user(message.from_user.id, message.from_user.username)
    try:
        payment = await api.create_payment(
            {
                "user_id": user["id"],
                "plan_id": data["plan_id"],
                "name": data["name"],
                "subdomain": sub,
                "server_type": data["server_type"],
                "game_version": data["game_version"],
                "purpose": "CREATE",
            }
        )
    except api.ApiError as exc:
        await message.answer(f"Не удалось создать счёт: {exc.detail[:400]}")
        return
    await state.clear()
    await message.answer(
        "Оплатите счёт в ЮKassa. После webhook сервер поднимется автоматически.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Оплатить", url=payment["confirmation_url"])]
            ]
        ),
    )


@router.callback_query(F.data == "myservers")
async def my_servers(callback: CallbackQuery) -> None:
    rows = await api.servers(callback.from_user.id)
    if not rows:
        await callback.message.edit_text("Серверов пока нет.", reply_markup=kb([[("Купить", "buy")]]))
        await callback.answer()
        return
    lines = []
    buttons = []
    for s in rows:
        lines.append(
            f"• <b>{s['name']}</b> — <code>{s.get('address')}</code>\n"
            f"  {s['status']} / {s['server_type']} {s['game_version']}"
        )
        if s["status"] in {"RUNNING", "STOPPED", "SUSPENDED"}:
            buttons.append([("Продлить " + s["name"], f"renew:{s['id']}")])
    await callback.message.edit_text("\n\n".join(lines), reply_markup=kb(buttons + [[("Панель", "panel")]]))
    await callback.answer()


@router.callback_query(F.data.startswith("renew:"))
async def renew(callback: CallbackQuery) -> None:
    server_id = callback.data.split(":", 1)[1]
    rows = await api.servers(callback.from_user.id)
    server = next((s for s in rows if s["id"] == server_id), None)
    if not server:
        await callback.answer("Сервер не найден", show_alert=True)
        return
    user = await api.upsert_user(callback.from_user.id, callback.from_user.username)
    payment = await api.create_payment(
        {
            "user_id": user["id"],
            "plan_id": server["plan_id"],
            "name": server["name"],
            "subdomain": server["subdomain"],
            "server_type": server["server_type"],
            "game_version": server["game_version"],
            "purpose": "RENEW",
            "server_id": server["id"],
        }
    )
    await callback.message.answer(
        f"Продление {server['name']}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Оплатить", url=payment["confirmation_url"])]
            ]
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "panel")
async def panel(callback: CallbackQuery) -> None:
    link = await api.magic_link(callback.from_user.id, callback.from_user.username)
    await callback.message.answer(
        "Одноразовая ссылка в веб-панель (10 минут):",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Открыть панель", url=link["url"])]]
        ),
    )
    await callback.answer()


@router.message(Command("panel"))
async def panel_cmd(message: Message) -> None:
    link = await api.magic_link(message.from_user.id, message.from_user.username)
    await message.answer(
        "Ссылка в панель:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Открыть", url=link["url"])]]
        ),
    )


async def main() -> None:
    bot = Bot(
        settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
