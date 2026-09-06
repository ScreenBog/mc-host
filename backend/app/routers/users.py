from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.security import require_bot_token

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.post("/upsert", dependencies=[Depends(require_bot_token)])
async def upsert_user(
    telegram_id: int,
    username: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = (
        await session.execute(select(User).where(User.telegram_id == telegram_id))
    ).scalar_one_or_none()
    if user is None:
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    elif username and user.username != username:
        user.username = username
        await session.commit()
    return {"id": user.id, "telegram_id": user.telegram_id, "username": user.username}
