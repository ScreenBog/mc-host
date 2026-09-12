from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path
from typing import Any, Callable

import httpx
from fastapi import HTTPException

from app.models import InstalledMod, ModSource, Server
from app.services import curseforge, modrinth
from app.services.docker_orchestrator import mods_volume, plugins_volume

ProgressFn = Callable[[int, int, str], None]

_jobs: dict[str, dict[str, Any]] = {}


def get_job(job_id: str) -> dict | None:
    return _jobs.get(job_id)


def jobs_for(server_id: str) -> list[dict]:
    return [j for j in _jobs.values() if j.get("server_id") == server_id]


def _addon_dir(server: Server) -> Path:
    if server.server_type.value in {"PAPER", "PURPUR", "SPIGOT"}:
        return plugins_volume(server)
    return mods_volume(server)


def create_job(server_id: str, source: str, external_id: str, name: str = "") -> str:
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id": job_id,
        "server_id": server_id,
        "source": source,
        "external_id": external_id,
        "name": name,
        "state": "queued",
        "bytes_done": 0,
        "bytes_total": 0,
        "filename": "",
        "error": None,
        "created_at": time.time(),
    }
    return job_id


def _update(job_id: str, **kwargs) -> None:
    job = _jobs.get(job_id)
    if job:
        job.update(kwargs)


async def save_url(dest: Path, url: str, progress: ProgressFn | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length") or 0)
            done = 0
            with dest.open("wb") as fh:
                async for chunk in response.aiter_bytes(64 * 1024):
                    fh.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total, dest.name)


async def run_install(
    job_id: str,
    server: Server,
    source: ModSource,
    external_id: str,
    version_id: str | None,
    loader: str,
    with_deps: bool,
) -> list[dict]:
    dest_dir = _addon_dir(server)

    def progress(done: int, total: int, filename: str) -> None:
        _update(
            job_id,
            state="downloading",
            bytes_done=done,
            bytes_total=total,
            filename=filename,
        )

    try:
        _update(job_id, state="downloading")
        installed: list[dict] = []
        if source == ModSource.MODRINTH:
            payload = (
                await modrinth.version(version_id)
                if version_id
                else await modrinth.latest_version(external_id, loader, server.game_version)
            )
            if not payload:
                raise HTTPException(404, "No matching Modrinth version")
            versions = (
                await modrinth.resolve_dependencies(payload, loader, server.game_version)
                if with_deps
                else [payload]
            )
            _update(job_id, state="installing")
            for item in versions:
                primary = next((f for f in item.get("files", []) if f.get("primary")), None) or (
                    item.get("files") or [None]
                )[0]
                if not primary:
                    continue
                dest_name = primary["filename"]
                await save_url(dest_dir / dest_name, primary["url"], progress)
                installed.append(
                    {
                        "source": ModSource.MODRINTH,
                        "external_id": item.get("project_id", external_id),
                        "file_id": item["id"],
                        "name": dest_name,
                        "file_name": dest_name,
                    }
                )
        elif source == ModSource.CURSEFORGE:
            file_info = (
                {"id": version_id}
                if version_id
                else await curseforge.latest_file(external_id, loader, server.game_version)
            )
            file_id = str(
                file_info["id"] if isinstance(file_info, dict) and "id" in file_info else version_id
            )
            try:
                url = await curseforge.file_download_url(external_id, file_id)
            except curseforge.DistributionBlocked:
                _update(
                    job_id,
                    state="manual",
                    error="allowModDistribution=false — загрузите jar вручную в Файлы",
                )
                return []
            dest_name = (file_info.get("fileName") if isinstance(file_info, dict) else None) or (
                f"{external_id}-{file_id}.jar"
            )
            _update(job_id, state="installing", filename=dest_name)
            await save_url(dest_dir / dest_name, url, progress)
            installed.append(
                {
                    "source": ModSource.CURSEFORGE,
                    "external_id": external_id,
                    "file_id": file_id,
                    "name": dest_name,
                    "file_name": dest_name,
                }
            )
        else:
            raise HTTPException(400, "Unsupported source")
        _update(job_id, state="done", filename=installed[-1]["file_name"] if installed else "")
        return installed
    except HTTPException as exc:
        _update(job_id, state="error", error=str(exc.detail))
        raise
    except Exception as exc:
        _update(job_id, state="error", error=str(exc)[:400])
        raise
