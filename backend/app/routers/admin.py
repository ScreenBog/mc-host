from __future__ import annotations

import os
import shutil
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import load_server
from app.config import get_settings
from app.db import get_session
from app.models import AuditLog, HiddenAddon, Invoice, Server, ServerStatus, User
from app.security import create_token, require_admin
from app.services import audit, docker_orchestrator

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class BanIn(BaseModel):
    reason: str | None = None
    banned: bool = True


class FlagIn(BaseModel):
    maintenance: bool | None = None
    disable_create: bool | None = None


class TransferIn(BaseModel):
    telegram_id: int


@router.get("/overview")
async def overview(session: AsyncSession = Depends(get_session), claims: dict = Depends(require_admin)) -> dict:
    counts = {}
    for status in ServerStatus:
        n = (
            await session.execute(select(func.count()).select_from(Server).where(Server.status == status))
        ).scalar_one()
        counts[status.value] = n
    users = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    vm = shutil.disk_usage("/")
    ram = None
    try:
        import psutil

        ram = psutil.virtual_memory()._asdict()
    except Exception:
        ram = {"available": None}
    settings = get_settings()
    return {
        "servers": counts,
        "users": users,
        "disk": {"total": vm.total, "used": vm.used, "free": vm.free},
        "ram": ram,
        "flags": {
            "maintenance": settings.maintenance,
            "disable_create": settings.disable_create,
        },
        "pid": os.getpid(),
    }


@router.get("/users")
async def users(session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = (await session.execute(select(User).order_by(User.id.desc()))).scalars().all()
    out = []
    for u in rows:
        n = (
            await session.execute(select(func.count()).select_from(Server).where(Server.user_id == u.id))
        ).scalar_one()
        out.append(
            {
                "id": u.id,
                "telegram_id": u.telegram_id,
                "username": u.username,
                "is_banned": u.is_banned,
                "created_at": u.created_at.isoformat(),
                "servers": n,
            }
        )
    return out


@router.post("/users/{telegram_id}/ban")
async def ban_user(
    telegram_id: int,
    body: BanIn,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_admin),
) -> dict:
    user = (await session.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(404, "User not found")
    user.is_banned = body.banned
    user.banned_reason = body.reason
    await audit.log(session, "user.ban" if body.banned else "user.unban", claims.get("tg"), str(telegram_id), body.reason)
    await session.commit()
    return {"ok": True}


@router.get("/servers")
async def servers(
    q: str = "",
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    stmt = select(Server)
    if status:
        stmt = stmt.where(Server.status == status)
    rows = (await session.execute(stmt.order_by(Server.created_at.desc()))).scalars().all()
    out = []
    for s in rows:
        if q and q.lower() not in f"{s.subdomain}{s.name}{s.id}".lower():
            continue
        user = await session.get(User, s.user_id)
        out.append(
            {
                "id": str(s.id),
                "name": s.name,
                "subdomain": s.subdomain,
                "status": s.status.value,
                "server_type": s.server_type.value,
                "game_version": s.game_version,
                "telegram_id": user.telegram_id if user else None,
                "username": user.username if user else None,
            }
        )
    return out


@router.post("/servers/{server_id}/power")
async def admin_power(
    server_id: uuid.UUID,
    action: str = Query(...),
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_admin),
) -> dict:
    server = await load_server(session, server_id)
    if not server.container_id:
        raise HTTPException(409, "No process")
    await docker_orchestrator.power_async(server.container_id, action)
    server.status = ServerStatus.STOPPED if action == "stop" else ServerStatus.RUNNING
    await audit.log(session, f"admin.power.{action}", claims.get("tg"), str(server_id))
    await session.commit()
    return {"ok": True, "status": server.status.value}


@router.post("/servers/{server_id}/transfer")
async def transfer(
    server_id: uuid.UUID,
    body: TransferIn,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_admin),
) -> dict:
    server = await load_server(session, server_id)
    user = (await session.execute(select(User).where(User.telegram_id == body.telegram_id))).scalar_one_or_none()
    if user is None:
        user = User(telegram_id=body.telegram_id)
        session.add(user)
        await session.flush()
    server.user_id = user.id
    await audit.log(session, "admin.transfer", claims.get("tg"), str(server_id), str(body.telegram_id))
    await session.commit()
    return {"ok": True}


@router.post("/impersonate/{telegram_id}")
async def impersonate(
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_admin),
) -> dict:
    user = (await session.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(404, "User not found")
    token = create_token(str(user.id), timedelta(minutes=30), "magic", extra={"tg": user.telegram_id})
    settings = get_settings()
    await audit.log(session, "admin.impersonate", claims.get("tg"), str(telegram_id))
    await session.commit()
    return {"url": f"{settings.public_web_origin}/auth/callback?token={token}"}


@router.get("/audit")
async def audit_list(session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = (await session.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(200))).scalars().all()
    return [
        {
            "id": r.id,
            "actor": r.actor_telegram_id,
            "action": r.action,
            "target": r.target,
            "detail": r.detail,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/invoices")
async def invoices(session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = (await session.execute(select(Invoice).order_by(Invoice.created_at.desc()).limit(100))).scalars().all()
    return [
        {
            "id": str(r.id),
            "amount": str(r.amount),
            "status": r.status.value,
            "yookassa": r.yookassa_payment_id,
            "purpose": r.purpose,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.post("/catalog/hide")
async def hide_addon(
    source: str,
    external_id: str,
    reason: str = "",
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_admin),
) -> dict:
    session.add(HiddenAddon(source=source, external_id=external_id, reason=reason))
    await audit.log(session, "catalog.hide", claims.get("tg"), f"{source}:{external_id}", reason)
    await session.commit()
    return {"ok": True}


@router.get("/me")
async def me(claims: dict = Depends(require_admin)) -> dict:
    return {"ok": True, "telegram_id": claims.get("tg")}
