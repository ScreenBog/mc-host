from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import (
    POWERABLE,
    can_backups,
    can_console,
    can_manage,
    can_power,
    get_user_by_claims,
    require_role,
    visible_servers,
)
from app.config import get_settings
from app.db import get_session
from app.models import (
    AclRole,
    Backup,
    InstalledMod,
    ModSource,
    Plan,
    Server,
    ServerAcl,
    ServerStatus,
    ServerType,
    User,
)
from app.schemas import (
    AclIn,
    ConsoleCommand,
    InstalledModOut,
    ModInstallRequest,
    PowerAction,
    ServerCreate,
    ServerOut,
    ServerSettingsIn,
)
from app.security import is_platform_admin, require_bot_token, require_user
from app.services import audit, backups, docker_orchestrator, settings_file
from app.services.mods_discovery import download_and_install

router = APIRouter(prefix="/api/v1", tags=["servers"])


def _to_out(server: Server) -> ServerOut:
    settings = get_settings()
    data = ServerOut.model_validate(server)
    data.address = f"{server.subdomain}.{settings.game_domain}"
    data.ip_address = f"{settings.lan_ip or settings.public_ip}:25565"
    return data


async def _get_server(session: AsyncSession, server_id: uuid.UUID) -> Server:
    server = await session.get(Server, server_id)
    if server is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Server not found")
    return server


async def _provision(session: AsyncSession, user: User, body: ServerCreate) -> Server:
    settings = get_settings()
    if settings.disable_create and not is_platform_admin(user.telegram_id):
        raise HTTPException(403, "Creating servers is disabled")
    if user.is_banned:
        raise HTTPException(403, "Account banned")
    plan_id = body.plan_id
    if is_platform_admin(user.telegram_id):
        plan_id = "unlimited" if (await session.get(Plan, "unlimited")) else plan_id
    plan = await session.get(Plan, plan_id) or await session.get(Plan, "starter")
    if plan is None:
        raise HTTPException(400, "Unknown plan")
    taken = (
        await session.execute(select(Server).where(Server.subdomain == body.subdomain.lower()))
    ).scalar_one_or_none()
    if taken:
        raise HTTPException(409, "Subdomain taken")
    existing = (
        await session.execute(
            select(Server).where(
                Server.user_id == user.id,
                Server.status != ServerStatus.TERMINATED,
            )
        )
    ).scalars().all()
    if existing and settings.beta_mode and not is_platform_admin(user.telegram_id):
        return existing[0]
    days = 3650 if is_platform_admin(user.telegram_id) else 30
    server = Server(
        user_id=user.id,
        plan_id=plan.id,
        name=body.name,
        subdomain=body.subdomain.lower(),
        server_type=body.server_type,
        game_version=body.game_version,
        edition=body.edition,
        loader_version=body.loader_version,
        max_players=body.max_players,
        gamemode=body.gamemode,
        difficulty=body.difficulty,
        online_mode=body.online_mode,
        status=ServerStatus.PROVISIONING,
        expires_at=datetime.now(UTC) + timedelta(days=days),
        settings={},
    )
    session.add(server)
    await session.flush()
    try:
        container_id = await docker_orchestrator.create_mc_server_async(
            server_id=str(server.id),
            subdomain=server.subdomain,
            server_type=server.server_type.value,
            game_version=server.game_version,
            ram_mb=plan.ram_mb,
            cpus=float(plan.cpu_cores),
        )
        server.container_id = container_id
        server.status = ServerStatus.STARTING
        settings_file.write_properties(
            server,
            {
                "max_players": body.max_players,
                "gamemode": body.gamemode,
                "difficulty": body.difficulty,
                "online_mode": body.online_mode,
                "motd": f"{server.subdomain}.{get_settings().game_domain}",
            },
        )
        server.status = ServerStatus.RUNNING
    except Exception as exc:
        server.status = ServerStatus.ERROR
        server.last_error = str(exc)[:500]
    session.add(
        ServerAcl(
            server_id=server.id,
            telegram_id=user.telegram_id,
            username=user.username,
            role=AclRole.OWNER,
        )
    )
    await session.commit()
    await session.refresh(server)
    return server


@router.post("/servers", status_code=status.HTTP_201_CREATED, response_model=ServerOut)
async def create_server(
    body: ServerCreate,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> ServerOut:
    user = await get_user_by_claims(session, claims)
    server = await _provision(session, user, body)
    await audit.log(session, "server.create", user.telegram_id, str(server.id), server.subdomain)
    await session.commit()
    return _to_out(server)


@router.post(
    "/internal/servers",
    status_code=status.HTTP_201_CREATED,
    response_model=ServerOut,
    dependencies=[Depends(require_bot_token)],
)
async def bot_create(
    body: ServerCreate,
    session: AsyncSession = Depends(get_session),
) -> ServerOut:
    if body.user_id is None:
        raise HTTPException(400, "user_id required")
    user = await session.get(User, body.user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return _to_out(await _provision(session, user, body))


@router.get("/servers", response_model=list[ServerOut])
async def list_servers(
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> list[ServerOut]:
    user = await get_user_by_claims(session, claims)
    rows = await visible_servers(session, user)
    return [_to_out(s) for s in rows]


@router.get("/servers/{server_id}", response_model=ServerOut)
async def get_server(
    server_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> ServerOut:
    server, _, _ = await require_role(session, server_id, claims, lambda r: True)
    return _to_out(server)


@router.post("/servers/{server_id}/power")
async def power(
    server_id: uuid.UUID,
    body: PowerAction,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> dict:
    server, user, role = await require_role(session, server_id, claims, can_power)
    if server.status not in POWERABLE and server.status != ServerStatus.PROVISIONING:
        raise HTTPException(409, "Server is not controllable")
    if not server.container_id:
        raise HTTPException(409, "Container is not ready")
    if body.action == "start":
        server.status = ServerStatus.STARTING
        await session.commit()
        from app.services.java_orchestrator import ensure_running

        if server.container_id.startswith("java:"):
            await __import__("asyncio").to_thread(ensure_running, server.container_id, server.subdomain)
        else:
            await docker_orchestrator.power_async(server.container_id, "start")
        server.status = ServerStatus.RUNNING
    else:
        if body.action == "stop" and server.backup_on_stop:
            try:
                path, size = backups.create_backup(server, kind="autostop")
                session.add(Backup(server_id=server.id, path=str(path), size_bytes=size, kind="autostop"))
                backups.prune(server, server.backup_keep)
            except Exception:
                pass
        await docker_orchestrator.power_async(server.container_id, body.action)
        server.status = ServerStatus.SLEEPING if body.action == "stop" else ServerStatus.RUNNING
    await audit.log(session, f"server.{body.action}", user.telegram_id, str(server.id))
    await session.commit()
    return {"ok": True, "status": server.status.value}


@router.get("/servers/{server_id}/mods", response_model=list[InstalledModOut])
async def list_mods(
    server_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> list[InstalledModOut]:
    server, _, _ = await require_role(session, server_id, claims, lambda r: True)
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
    server, user, _ = await require_role(session, server_id, claims, can_manage)
    loader = server.server_type.value.lower()
    if loader in {"purpur", "spigot"}:
        loader = "paper"
    try:
        installed = await download_and_install(
            server, body.source, body.external_id, body.version_id, loader
        )
    except HTTPException:
        raise
    out: list[InstalledModOut] = []
    for item in installed:
        item.setdefault("enabled", True)
        item.setdefault("addon_type", "plugin" if loader == "paper" else "mod")
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
            for k, v in item.items():
                setattr(existing, k, v)
            row = existing
        else:
            allowed = {
                "source",
                "external_id",
                "file_id",
                "name",
                "file_name",
                "enabled",
                "addon_type",
                "install_error",
            }
            row = InstalledMod(
                server_id=server.id,
                **{k: v for k, v in item.items() if k in allowed},
            )
            session.add(row)
        await session.flush()
        out.append(InstalledModOut.model_validate(row))
    server.restart_required = True
    await audit.log(session, "mod.install", user.telegram_id, str(server.id), body.external_id)
    await session.commit()
    return out


@router.post("/servers/{server_id}/mods/search-install", response_model=list[InstalledModOut])
async def search_install(
    server_id: uuid.UUID,
    query: str,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> list[InstalledModOut]:
    from app.services.mods_discovery import search_mods

    server, _, _ = await require_role(session, server_id, claims, can_manage)
    loader = server.server_type.value.lower()
    if loader in {"purpur", "spigot"}:
        loader = "paper"
    hits = await search_mods(query, loader, server.game_version)
    if not hits:
        raise HTTPException(404, "Nothing found")
    body = ModInstallRequest(source=ModSource(hits[0]["source"]), external_id=hits[0]["external_id"])
    return await install_mod(server_id, body, session, claims)


@router.post("/servers/{server_id}/mods/{mod_id}/toggle")
async def toggle_mod(
    server_id: uuid.UUID,
    mod_id: int,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> dict:
    server, user, _ = await require_role(session, server_id, claims, can_manage)
    mod = await session.get(InstalledMod, mod_id)
    if mod is None or mod.server_id != server.id:
        raise HTTPException(404, "Mod not found")
    folder = docker_orchestrator.mods_volume(server)
    if server.server_type.value in {"PAPER", "PURPUR", "SPIGOT"}:
        folder = docker_orchestrator.plugins_volume(server)
    src = folder / mod.file_name
    disabled = folder / (mod.file_name + ".disabled")
    if mod.enabled:
        if src.exists():
            src.rename(disabled)
        mod.enabled = False
    else:
        if disabled.exists():
            disabled.rename(src)
        mod.enabled = True
    server.restart_required = True
    await audit.log(session, "mod.toggle", user.telegram_id, str(server.id), mod.file_name)
    await session.commit()
    return {"ok": True, "enabled": mod.enabled}


@router.delete("/servers/{server_id}/mods/{mod_id}")
async def delete_mod(
    server_id: uuid.UUID,
    mod_id: int,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> dict:
    server, user, _ = await require_role(session, server_id, claims, can_manage)
    mod = await session.get(InstalledMod, mod_id)
    if mod is None or mod.server_id != server.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mod not found")
    jar = docker_orchestrator.mods_volume(server) / mod.file_name
    if jar.exists():
        jar.unlink()
    disabled = docker_orchestrator.mods_volume(server) / (mod.file_name + ".disabled")
    if disabled.exists():
        disabled.unlink()
    await session.delete(mod)
    await audit.log(session, "mod.delete", user.telegram_id, str(server.id), mod.file_name)
    await session.commit()
    return {"ok": True}


@router.get("/servers/{server_id}/settings")
async def get_settings_ep(
    server_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> dict:
    server, _, _ = await require_role(session, server_id, claims, lambda r: True)
    return settings_file.to_settings(server)


@router.put("/servers/{server_id}/settings")
async def put_settings(
    server_id: uuid.UUID,
    body: ServerSettingsIn,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> dict:
    server, user, _ = await require_role(session, server_id, claims, can_manage)
    patch = body.model_dump(exclude_none=True)
    if "max_players" in patch:
        server.max_players = patch["max_players"]
    if "gamemode" in patch:
        server.gamemode = patch["gamemode"]
    if "difficulty" in patch:
        server.difficulty = patch["difficulty"]
    if "online_mode" in patch:
        server.online_mode = patch["online_mode"]
    merged = {**(server.settings or {}), **patch}
    server.settings = merged
    settings_file.write_properties(server, patch)
    server.restart_required = True
    await audit.log(session, "server.settings", user.telegram_id, str(server.id))
    await session.commit()
    return settings_file.to_settings(server)


@router.get("/servers/{server_id}/console")
async def console_tail(
    server_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
    lines: int = 80,
) -> dict:
    server, _, _ = await require_role(session, server_id, claims, can_console)
    return {"lines": docker_orchestrator.tail_log(str(server.id), lines)}


@router.post("/servers/{server_id}/console")
async def console_cmd(
    server_id: uuid.UUID,
    body: ConsoleCommand,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> dict:
    server, user, _ = await require_role(session, server_id, claims, can_console)
    if not server.container_id:
        raise HTTPException(409, "No process")
    try:
        docker_orchestrator.send_command(server.container_id, body.command)
    except Exception as exc:
        raise HTTPException(409, str(exc)) from exc
    await audit.log(session, "server.command", user.telegram_id, str(server.id), body.command[:80])
    await session.commit()
    return {"ok": True}


@router.websocket("/servers/{server_id}/console/ws")
async def console_ws(websocket: WebSocket, server_id: uuid.UUID) -> None:
    await websocket.accept()
    token = websocket.query_params.get("token") or websocket.headers.get("authorization", "")
    if token.startswith("Bearer "):
        token = token[7:]
    try:
        from app.security import decode_token

        claims = decode_token(token, "access")
    except Exception:
        await websocket.close(code=4401)
        return
    from app.db import SessionLocal

    async with SessionLocal() as session:
        try:
            await require_role(session, server_id, claims, can_console)
        except HTTPException:
            await websocket.close(code=4403)
            return
    try:
        while True:
            text = docker_orchestrator.tail_log(str(server_id), 40)
            await websocket.send_text(text)
            await __import__("asyncio").sleep(2)
    except WebSocketDisconnect:
        return


@router.get("/servers/{server_id}/backups")
async def list_backups(
    server_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> list[dict]:
    server, _, _ = await require_role(session, server_id, claims, can_backups)
    rows = (
        await session.execute(select(Backup).where(Backup.server_id == server.id).order_by(Backup.id.desc()))
    ).scalars().all()
    return [
        {"id": r.id, "kind": r.kind, "size_bytes": r.size_bytes, "created_at": r.created_at.isoformat(), "path": r.path}
        for r in rows
    ]


@router.post("/servers/{server_id}/backups")
async def make_backup(
    server_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> dict:
    server, user, _ = await require_role(session, server_id, claims, can_backups)
    path, size = backups.create_backup(server, kind="manual")
    row = Backup(server_id=server.id, path=str(path), size_bytes=size, kind="manual")
    session.add(row)
    backups.prune(server, server.backup_keep)
    await audit.log(session, "backup.create", user.telegram_id, str(server.id))
    await session.commit()
    return {"id": row.id, "size_bytes": size}


@router.get("/servers/{server_id}/backups/{backup_id}/download")
async def download_backup(
    server_id: uuid.UUID,
    backup_id: int,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
):
    await require_role(session, server_id, claims, can_backups)
    row = await session.get(Backup, backup_id)
    if row is None or row.server_id != server_id:
        raise HTTPException(404)
    return FileResponse(row.path, filename=Path(row.path).name)


@router.post("/servers/{server_id}/backups/{backup_id}/restore")
async def restore(
    server_id: uuid.UUID,
    backup_id: int,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> dict:
    server, user, _ = await require_role(session, server_id, claims, can_backups)
    row = await session.get(Backup, backup_id)
    if row is None:
        raise HTTPException(404)
    if server.container_id:
        await docker_orchestrator.power_async(server.container_id, "stop")
        server.status = ServerStatus.STOPPED
    backups.restore_backup(server, Path(row.path))
    await audit.log(session, "backup.restore", user.telegram_id, str(server.id), str(backup_id))
    await session.commit()
    return {"ok": True}


@router.post("/servers/{server_id}/world")
async def upload_world(
    server_id: uuid.UUID,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> dict:
    server, user, _ = await require_role(session, server_id, claims, can_backups)
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(400, "Need a .zip world")
    backups.create_backup(server, kind="pre-upload")
    dest = docker_orchestrator.server_dir(str(server.id)) / "upload-world.zip"
    dest.write_bytes(await file.read())
    if server.container_id:
        await docker_orchestrator.power_async(server.container_id, "stop")
        server.status = ServerStatus.STOPPED
    backups.restore_backup(server, dest)
    await audit.log(session, "world.upload", user.telegram_id, str(server.id), file.filename)
    await session.commit()
    return {"ok": True}


@router.get("/servers/{server_id}/world")
async def download_world(
    server_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
):
    server, _, _ = await require_role(session, server_id, claims, can_backups)
    path = backups.world_zip(server)
    return FileResponse(path, filename=f"{server.subdomain}-world.zip")


@router.get("/servers/{server_id}/gdrive")
async def gdrive_placeholder(
    server_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> dict:
    await require_role(session, server_id, claims, can_backups)
    return {"connected": False, "todo": "Google Drive OAuth will land here"}


@router.get("/servers/{server_id}/acl")
async def list_acl(
    server_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> list[dict]:
    server, _, _ = await require_role(session, server_id, claims, can_manage)
    rows = (await session.execute(select(ServerAcl).where(ServerAcl.server_id == server.id))).scalars().all()
    return [
        {"id": r.id, "telegram_id": r.telegram_id, "username": r.username, "role": r.role.value}
        for r in rows
    ]


@router.post("/servers/{server_id}/acl")
async def add_acl(
    server_id: uuid.UUID,
    body: AclIn,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> dict:
    server, user, _ = await require_role(session, server_id, claims, lambda r: r == AclRole.OWNER)
    if not body.telegram_id:
        raise HTTPException(400, "telegram_id required")
    role = AclRole(body.role)
    row = ServerAcl(
        server_id=server.id,
        telegram_id=body.telegram_id,
        username=body.username,
        role=role,
    )
    session.add(row)
    await audit.log(session, "acl.add", user.telegram_id, str(server.id), str(body.telegram_id))
    await session.commit()
    return {"ok": True, "id": row.id}


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
    rows = await visible_servers(session, user)
    return [_to_out(s) for s in rows]


@router.post(
    "/internal/servers/{server_id}/power",
    dependencies=[Depends(require_bot_token)],
)
async def bot_power(
    server_id: uuid.UUID,
    body: PowerAction,
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = (
        await session.execute(select(User).where(User.telegram_id == telegram_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    fake = {"sub": str(user.id), "tg": user.telegram_id}
    return await power(server_id, body, session, fake)


@router.get("/internal/console/{server_id}", dependencies=[Depends(require_bot_token)])
async def bot_console(server_id: uuid.UUID, telegram_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    user = (await session.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(404)
    fake = {"sub": str(user.id), "tg": user.telegram_id}
    return await console_tail(server_id, session, fake)


@router.post("/internal/console/{server_id}", dependencies=[Depends(require_bot_token)])
async def bot_console_cmd(
    server_id: uuid.UUID,
    body: ConsoleCommand,
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = (await session.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(404)
    fake = {"sub": str(user.id), "tg": user.telegram_id}
    return await console_cmd(server_id, body, session, fake)


@router.post("/internal/mods/{server_id}", dependencies=[Depends(require_bot_token)])
async def bot_install_mod(
    server_id: uuid.UUID,
    body: ModInstallRequest,
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
):
    user = (await session.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(404)
    fake = {"sub": str(user.id), "tg": user.telegram_id}
    return await install_mod(server_id, body, session, fake)


@router.get("/internal/admin/servers", dependencies=[Depends(require_bot_token)])
async def bot_admin_servers(session: AsyncSession = Depends(get_session)) -> list[dict]:
    from app.routers.admin import servers as admin_servers

    return await admin_servers(session=session)


@router.get("/internal/admin/overview", dependencies=[Depends(require_bot_token)])
async def bot_admin_overview(session: AsyncSession = Depends(get_session)) -> dict:
    from app.routers.admin import overview

    return await overview(session=session, claims={"tg": 1920838704})


@router.post("/internal/admin/servers/{server_id}/power", dependencies=[Depends(require_bot_token)])
async def bot_admin_power(
    server_id: uuid.UUID,
    action: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.routers.admin import admin_power

    return await admin_power(server_id, action, session, {"tg": 1920838704})


@router.get("/me")
async def me(
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> dict:
    user = await get_user_by_claims(session, claims)
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "is_admin": is_platform_admin(user.telegram_id),
    }
