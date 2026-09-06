import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import InstalledMod, Plan, Server, ServerStatus, User
from app.schemas import (
    InstalledModOut,
    ModInstallRequest,
    PowerAction,
    ServerCreate,
    ServerOut,
)
from app.security import require_bot_token, require_user
from app.services import docker_orchestrator
from app.services.mods_discovery import download_and_install

router = APIRouter(prefix="/api/v1", tags=["servers"])


def _to_out(server: Server) -> ServerOut:
    settings = get_settings()
    data = ServerOut.model_validate(server)
    data.address = f"{server.subdomain}.{settings.game_domain}"
    return data


async def _get_server(session: AsyncSession, server_id: uuid.UUID) -> Server:
    server = await session.get(Server, server_id)
    if server is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Server not found")
    return server


@router.post(
    "/servers",
    status_code=status.HTTP_201_CREATED,
    response_model=ServerOut,
    dependencies=[Depends(require_bot_token)],
)
async def enqueue_create(
    body: ServerCreate,
    session: AsyncSession = Depends(get_session),
) -> ServerOut:
    """Used by the bot after a pending payment is stored; actual Docker create happens on webhook."""
    plan = await session.get(Plan, body.plan_id)
    if plan is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown plan")
    exists = (
        await session.execute(select(Server).where(Server.subdomain == body.subdomain))
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Subdomain taken")
    user = await session.get(User, body.user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    from datetime import UTC, datetime, timedelta

    server = Server(
        user_id=body.user_id,
        plan_id=body.plan_id,
        name=body.name,
        subdomain=body.subdomain,
        server_type=body.server_type,
        game_version=body.game_version,
        status=ServerStatus.PROVISIONING,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    session.add(server)
    await session.commit()
    await session.refresh(server)
    return _to_out(server)


@router.get("/servers", response_model=list[ServerOut])
async def list_servers(
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> list[ServerOut]:
    rows = (
        await session.execute(select(Server).where(Server.user_id == int(claims["sub"])))
    ).scalars().all()
    return [_to_out(s) for s in rows]


@router.get("/servers/{server_id}", response_model=ServerOut)
async def get_server(
    server_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> ServerOut:
    server = await _owned(session, server_id, int(claims["sub"]))
    return _to_out(server)


@router.post("/servers/{server_id}/power")
async def power(
    server_id: uuid.UUID,
    body: PowerAction,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> dict:
    server = await _owned(session, server_id, int(claims["sub"]))
    if server.status in {ServerStatus.SUSPENDED, ServerStatus.TERMINATED, ServerStatus.PROVISIONING}:
        raise HTTPException(status.HTTP_409_CONFLICT, "Server is not controllable")
    if not server.container_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Container is not ready")
    await docker_orchestrator.power_async(server.container_id, body.action)
    if body.action == "stop":
        server.status = ServerStatus.STOPPED
    else:
        server.status = ServerStatus.RUNNING
    await session.commit()
    return {"ok": True, "status": server.status.value}


@router.get("/servers/{server_id}/mods", response_model=list[InstalledModOut])
async def list_mods(
    server_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> list[InstalledModOut]:
    server = await _owned(session, server_id, int(claims["sub"]))
    rows = (
        await session.execute(select(InstalledMod).where(InstalledMod.server_id == server.id))
    ).scalars().all()
    return [InstalledModOut.model_validate(r) for r in rows]


@router.post("/servers/{server_id}/mods", response_model=list[InstalledModOut])
async def install_mod(
    server_id: uuid.UUID,
    body: ModInstallRequest,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> list[InstalledModOut]:
    server = await _owned(session, server_id, int(claims["sub"]))
    loader = server.server_type.value.lower()
    installed = await download_and_install(
        server, body.source, body.external_id, body.version_id, loader
    )
    out: list[InstalledModOut] = []
    for item in installed:
        existing = (
            await session.execute(
                select(InstalledMod).where(
                    InstalledMod.server_id == server.id,
                    InstalledMod.source == item["source"],
                    InstalledMod.external_id == item["external_id"],
                )
            )
        ).scalar_one_or_none()
        if existing:
            existing.file_id = item["file_id"]
            existing.file_name = item["file_name"]
            existing.name = item["name"]
            row = existing
        else:
            row = InstalledMod(server_id=server.id, **item)
            session.add(row)
        await session.flush()
        out.append(InstalledModOut.model_validate(row))
    await session.commit()
    return out


@router.delete("/servers/{server_id}/mods/{mod_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mod(
    server_id: uuid.UUID,
    mod_id: int,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> None:
    server = await _owned(session, server_id, int(claims["sub"]))
    mod = await session.get(InstalledMod, mod_id)
    if mod is None or mod.server_id != server.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mod not found")
    jar = docker_orchestrator.mods_volume(server) / mod.file_name
    if jar.exists():
        jar.unlink()
    await session.delete(mod)
    await session.commit()


@router.get("/internal/servers/{telegram_id}", dependencies=[Depends(require_bot_token)])
async def servers_for_telegram(
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[ServerOut]:
    user = (
        await session.execute(select(User).where(User.telegram_id == telegram_id))
    ).scalar_one_or_none()
    if user is None:
        return []
    rows = (await session.execute(select(Server).where(Server.user_id == user.id))).scalars().all()
    return [_to_out(s) for s in rows]


async def _owned(session: AsyncSession, server_id: uuid.UUID, user_id: int) -> Server:
    server = await _get_server(session, server_id)
    if server.user_id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your server")
    return server
