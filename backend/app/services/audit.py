from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def log(
    session: AsyncSession,
    action: str,
    actor_telegram_id: int | None = None,
    target: str | None = None,
    detail: str | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_telegram_id=actor_telegram_id,
            action=action,
            target=target,
            detail=detail,
        )
    )
    await session.flush()
