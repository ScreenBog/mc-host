from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AclRole, Server, ServerAcl, ServerStatus, User
from app.security import is_platform_admin


async def get_user_by_claims(session: AsyncSession, claims: dict) -> User:
    user = await session.get(User, int(claims["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    if user.is_banned:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account banned")
    return user


async def load_server(session: AsyncSession, server_id: uuid.UUID) -> Server:
    server = await session.get(Server, server_id)
    if server is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Server not found")
    return server


async def role_on(session: AsyncSession, server: Server, user: User) -> AclRole | None:
    if is_platform_admin(user.telegram_id):
        return AclRole.OWNER
    if server.user_id == user.id:
        return AclRole.OWNER
    row = (
        await session.execute(
            select(ServerAcl).where(
                ServerAcl.server_id == server.id,
                ServerAcl.telegram_id == user.telegram_id,
            )
        )
    ).scalar_one_or_none()
    return row.role if row else None


def can_power(role: AclRole | None) -> bool:
    return role in {AclRole.OWNER, AclRole.OPERATOR, AclRole.START_CONSOLE}


def can_console(role: AclRole | None) -> bool:
    return role in {AclRole.OWNER, AclRole.OPERATOR, AclRole.START_CONSOLE}


def can_backups(role: AclRole | None) -> bool:
    return role in {AclRole.OWNER, AclRole.OPERATOR, AclRole.BACKUPS}


def can_manage(role: AclRole | None) -> bool:
    return role in {AclRole.OWNER, AclRole.OPERATOR}


async def require_role(
    session: AsyncSession, server_id: uuid.UUID, claims: dict, predicate
) -> tuple[Server, User, AclRole]:
    user = await get_user_by_claims(session, claims)
    server = await load_server(session, server_id)
    role = await role_on(session, server, user)
    if role is None or not predicate(role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not enough rights")
    return server, user, role


async def visible_servers(session: AsyncSession, user: User) -> list[Server]:
    if is_platform_admin(user.telegram_id):
        return (await session.execute(select(Server))).scalars().all()
    own = (await session.execute(select(Server).where(Server.user_id == user.id))).scalars().all()
    shared_ids = (
        await session.execute(select(ServerAcl.server_id).where(ServerAcl.telegram_id == user.telegram_id))
    ).scalars().all()
    extra = []
    if shared_ids:
        extra = (
            await session.execute(select(Server).where(Server.id.in_(shared_ids)))
        ).scalars().all()
    seen = {s.id for s in own}
    return list(own) + [s for s in extra if s.id not in seen]


POWERABLE = {ServerStatus.RUNNING, ServerStatus.STOPPED, ServerStatus.SLEEPING, ServerStatus.ERROR, ServerStatus.STARTING}
