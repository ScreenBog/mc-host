from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import User
from app.schemas import MagicLinkOut, MagicLinkRequest, TokenOut
from app.security import create_token, decode_token, require_bot_token

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/magic-link", response_model=MagicLinkOut, dependencies=[Depends(require_bot_token)])
async def issue_magic_link(
    body: MagicLinkRequest,
    session: AsyncSession = Depends(get_session),
) -> MagicLinkOut:
    user = (
        await session.execute(select(User).where(User.telegram_id == body.telegram_id))
    ).scalar_one_or_none()
    if user is None:
        user = User(telegram_id=body.telegram_id, username=body.username)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    elif body.username and user.username != body.username:
        user.username = body.username
        await session.commit()

    token = create_token(
        subject=str(user.id),
        ttl=timedelta(minutes=10),
        token_type="magic",
        extra={"tg": user.telegram_id},
    )
    settings = get_settings()
    return MagicLinkOut(url=f"{settings.public_web_origin}/auth/callback?token={token}")


@router.get("/callback", response_model=TokenOut)
async def consume_magic_link(token: str = Query(...)) -> TokenOut:
    payload = decode_token(token, "magic")
    access = create_token(
        subject=payload["sub"],
        ttl=timedelta(days=7),
        token_type="access",
        extra={"tg": payload.get("tg")},
    )
    return TokenOut(access_token=access)
