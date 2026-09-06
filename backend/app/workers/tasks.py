import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Invoice, InvoiceStatus, Server, ServerStatus, User
from app.services import provisioning, telegram
from app.workers.broker import broker


@broker.task
async def provision_invoice(invoice_id: str) -> None:
    async with SessionLocal() as session:
        invoice = (
            await session.execute(
                select(Invoice)
                .where(Invoice.id == uuid.UUID(invoice_id))
                .with_for_update()
            )
        ).scalar_one_or_none()
        if invoice is None or invoice.status == InvoiceStatus.SUCCEEDED:
            return
        await provisioning.provision_paid_invoice(session, invoice)


@broker.task(schedule=[{"cron": "0 * * * *"}])
async def lease_lifecycle() -> None:
    now = datetime.now(UTC)
    warn_after = now + timedelta(hours=24)
    terminate_before = now - timedelta(days=7)

    async with SessionLocal() as session:
        expiring = (
            await session.execute(
                select(Server).where(
                    Server.status.in_([ServerStatus.RUNNING, ServerStatus.STOPPED]),
                    Server.expires_at <= warn_after,
                    Server.expires_at > now,
                    Server.renewal_notified_at.is_(None),
                )
            )
        ).scalars().all()
        for server in expiring:
            user = await session.get(User, server.user_id)
            if user:
                await telegram.send_message(
                    user.telegram_id,
                    (
                        f"Аренда <b>{server.name}</b> истекает "
                        f"{server.expires_at:%d.%m.%Y %H:%M} UTC.\n"
                        "Нажмите «Продлить» в боте, чтобы не потерять мир."
                    ),
                    {
                        "inline_keyboard": [
                            [{"text": "Продлить", "callback_data": f"renew:{server.id}"}]
                        ]
                    },
                )
            server.renewal_notified_at = now
        await session.commit()

        overdue = (
            await session.execute(
                select(Server).where(
                    Server.status.in_([ServerStatus.RUNNING, ServerStatus.STOPPED]),
                    Server.expires_at <= now,
                )
            )
        ).scalars().all()
        for server in overdue:
            await provisioning.suspend_server(session, server)

        stale = (
            await session.execute(
                select(Server).where(
                    Server.status == ServerStatus.SUSPENDED,
                    Server.suspended_at.is_not(None),
                    Server.suspended_at <= terminate_before,
                )
            )
        ).scalars().all()
        for server in stale:
            await provisioning.terminate_server(session, server)
