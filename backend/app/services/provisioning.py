from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Invoice, InvoiceStatus, Plan, Server, ServerStatus, User
from app.services import cloudflare, docker_orchestrator, telegram


async def provision_paid_invoice(session: AsyncSession, invoice: Invoice) -> Server:
    meta = invoice.metadata_ or {}
    plan = await session.get(Plan, meta["plan_id"])
    if plan is None:
        raise RuntimeError("Unknown plan")

    server = await session.get(Server, invoice.server_id) if invoice.server_id else None
    if invoice.purpose == "RENEW" and server:
        server.expires_at = max(server.expires_at, datetime.now(UTC)) + timedelta(days=30)
        server.status = ServerStatus.RUNNING
        server.suspended_at = None
        server.renewal_notified_at = None
        if server.container_id:
            await docker_orchestrator.power_async(server.container_id, "start")
        invoice.status = InvoiceStatus.SUCCEEDED
        await session.commit()
        await _notify(
            session,
            server,
            f"Аренда <b>{server.name}</b> продлена до {server.expires_at:%d.%m.%Y}.",
        )
        return server

    if server is not None and server.container_id and server.status == ServerStatus.RUNNING:
        invoice.status = InvoiceStatus.SUCCEEDED
        await session.commit()
        return server

    if server is None:
        user_id = invoice.user_id
        server = Server(
            user_id=user_id,
            plan_id=plan.id,
            name=meta["name"],
            subdomain=meta["subdomain"],
            server_type=meta["server_type"],
            game_version=meta["game_version"],
            status=ServerStatus.PROVISIONING,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        session.add(server)
        await session.flush()
        invoice.server_id = server.id

    settings = get_settings()
    container_id = await docker_orchestrator.create_mc_server_async(
        server_id=str(server.id),
        subdomain=server.subdomain,
        server_type=server.server_type.value,
        game_version=server.game_version,
        ram_mb=plan.ram_mb,
        cpus=float(plan.cpu_cores),
    )
    dns_id = await cloudflare.create_cname(server.subdomain)
    server.container_id = container_id
    server.dns_record_id = dns_id
    server.status = ServerStatus.RUNNING
    invoice.status = InvoiceStatus.SUCCEEDED
    await session.commit()

    address = f"{server.subdomain}.{settings.game_domain}"
    await _notify(
        session,
        server,
        (
            f"Сервер <b>{server.name}</b> готов.\n"
            f"Адрес: <code>{address}</code> (порт 25565)\n"
            f"Панель модов: {settings.public_web_origin}"
        ),
        with_panel=True,
    )
    return server


async def suspend_server(session: AsyncSession, server: Server) -> None:
    if server.container_id:
        await docker_orchestrator.power_async(server.container_id, "stop")
    server.status = ServerStatus.SUSPENDED
    server.suspended_at = datetime.now(UTC)
    await session.commit()
    await _notify(
        session,
        server,
        f"Сервер <b>{server.name}</b> остановлен: срок аренды истёк. Данные хранятся 7 дней.",
    )


async def terminate_server(session: AsyncSession, server: Server) -> None:
    if server.container_id:
        await docker_orchestrator.remove_container_async(server.container_id)
    if server.dns_record_id:
        await cloudflare.delete_record(server.dns_record_id)
    root = docker_orchestrator.server_dir(str(server.id))
    shutil.rmtree(root, ignore_errors=True)
    server.status = ServerStatus.TERMINATED
    server.container_id = None
    server.dns_record_id = None
    await session.commit()
    await _notify(session, server, f"Сервер <b>{server.name}</b> удалён вместе с миром и DNS-записью.")


async def _notify(
    session: AsyncSession, server: Server, text: str, with_panel: bool = False
) -> None:
    user = await session.get(User, server.user_id)
    if not user:
        return
    markup = None
    if with_panel:
        settings = get_settings()
        markup = {
            "inline_keyboard": [
                [{"text": "Открыть панель", "url": settings.public_web_origin}]
            ]
        }
    await telegram.send_message(user.telegram_id, text, markup)
