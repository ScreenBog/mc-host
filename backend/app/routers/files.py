from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import can_manage, require_role
from app.db import get_session
from app.security import require_user
from app.services.filesafe import MAX_TEXT, is_text, rel_of, root_of, safe_join

router = APIRouter(prefix="/api/v1/servers", tags=["files"])


class MkdirIn(BaseModel):
    path: str


class RenameIn(BaseModel):
    path: str
    new_name: str


class ContentIn(BaseModel):
    content: str


def _stat(server_id: str, path) -> dict:
    st = path.stat()
    return {
        "name": path.name or "/",
        "path": rel_of(server_id, path) if path != root_of(server_id) else "",
        "dir": path.is_dir(),
        "size": 0 if path.is_dir() else st.st_size,
        "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
        "text": (not path.is_dir()) and is_text(path),
    }


@router.get("/{server_id}/files")
async def list_files(
    server_id: uuid.UUID,
    path: str = Query(default=""),
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> dict:
    await require_role(session, server_id, claims, can_manage)
    folder = safe_join(str(server_id), path)
    if not folder.exists():
        raise HTTPException(404, "Not found")
    if not folder.is_dir():
        raise HTTPException(400, "Not a directory")
    entries = sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    crumbs = []
    acc = []
    for part in (path or "").replace("\\", "/").split("/"):
        if not part:
            continue
        acc.append(part)
        crumbs.append({"name": part, "path": "/".join(acc)})
    return {
        "path": path,
        "crumbs": crumbs,
        "entries": [_stat(str(server_id), p) for p in entries],
    }


@router.get("/{server_id}/files/content")
async def read_content(
    server_id: uuid.UUID,
    path: str = Query(...),
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> dict:
    await require_role(session, server_id, claims, can_manage)
    target = safe_join(str(server_id), path)
    if not target.is_file():
        raise HTTPException(404, "Not found")
    if not is_text(target):
        raise HTTPException(400, "Binary file — download instead")
    if target.stat().st_size > MAX_TEXT:
        raise HTTPException(400, "File too large to edit")
    return {"path": path, "content": target.read_text(encoding="utf-8", errors="replace")}


@router.put("/{server_id}/files/content")
async def write_content(
    server_id: uuid.UUID,
    body: ContentIn,
    path: str = Query(...),
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> dict:
    await require_role(session, server_id, claims, can_manage)
    target = safe_join(str(server_id), path)
    if not is_text(target) and target.exists():
        raise HTTPException(400, "Not a text file")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body.content, encoding="utf-8")
    return {"ok": True}


@router.get("/{server_id}/files/download")
async def download_file(
    server_id: uuid.UUID,
    path: str = Query(...),
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
):
    await require_role(session, server_id, claims, can_manage)
    target = safe_join(str(server_id), path)
    if not target.is_file():
        raise HTTPException(404, "Not found")
    return FileResponse(target, filename=target.name)


@router.post("/{server_id}/files/upload")
async def upload_file(
    server_id: uuid.UUID,
    path: str = Query(default=""),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> dict:
    await require_role(session, server_id, claims, can_manage)
    folder = safe_join(str(server_id), path)
    folder.mkdir(parents=True, exist_ok=True)
    name = (file.filename or "upload").replace("\\", "/").split("/")[-1]
    dest = safe_join(str(server_id), f"{path.rstrip('/')}/{name}" if path else name)
    with dest.open("wb") as fh:
        while True:
            chunk = await file.read(64 * 1024)
            if not chunk:
                break
            fh.write(chunk)
    return {"ok": True, "path": rel_of(str(server_id), dest)}


@router.post("/{server_id}/files/mkdir")
async def mkdir(
    server_id: uuid.UUID,
    body: MkdirIn,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> dict:
    await require_role(session, server_id, claims, can_manage)
    target = safe_join(str(server_id), body.path)
    target.mkdir(parents=True, exist_ok=True)
    return {"ok": True}


@router.post("/{server_id}/files/rename")
async def rename(
    server_id: uuid.UUID,
    body: RenameIn,
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> dict:
    await require_role(session, server_id, claims, can_manage)
    src = safe_join(str(server_id), body.path)
    dest = src.with_name(body.new_name.replace("/", "").replace("\\", ""))
    dest = safe_join(str(server_id), rel_of(str(server_id), dest))
    if not src.exists():
        raise HTTPException(404)
    src.rename(dest)
    return {"ok": True, "path": rel_of(str(server_id), dest)}


@router.delete("/{server_id}/files")
async def delete_file(
    server_id: uuid.UUID,
    path: str = Query(...),
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_user),
) -> dict:
    await require_role(session, server_id, claims, can_manage)
    target = safe_join(str(server_id), path)
    if target == root_of(str(server_id)):
        raise HTTPException(400, "Cannot delete root")
    if not target.exists():
        raise HTTPException(404)
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    return {"ok": True}
