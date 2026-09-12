from __future__ import annotations

import json
from pathlib import Path

import httpx
import redis.asyncio as redis
from fastapi import HTTPException, status

from app.config import get_settings
from app.models import ModSource, Server
from app.services import curseforge, modrinth
from app.services.docker_orchestrator import mods_volume

CACHE_TTL = 15 * 60
_mem: dict[str, tuple[float, list[dict]]] = {}


def _redis() -> redis.Redis:
    return redis.from_url(get_settings().redis_url, decode_responses=True)


async def search_mods(
    query: str,
    loader: str,
    game_version: str,
    source: str = "both",
    project_type: str = "mod",
    index: str = "relevance",
) -> list[dict]:
    import time

    cache_key = f"mods:search:{source}:{project_type}:{loader}:{game_version}:{index}:{query.lower()}"
    if get_settings().beta_mode:
        hit = _mem.get(cache_key)
        if hit and hit[0] > time.time():
            return hit[1]
        merged = await _gather(query, loader, game_version, source, project_type, index)
        _mem[cache_key] = (time.time() + CACHE_TTL, merged)
        return merged
    client = _redis()
    try:
        cached = await client.get(cache_key)
        if cached:
            return json.loads(cached)
        merged = await _gather(query, loader, game_version, source, project_type, index)
        await client.setex(cache_key, CACHE_TTL, json.dumps(merged))
        return merged
    finally:
        await client.aclose()


async def _gather(
    query: str,
    loader: str,
    game_version: str,
    source: str,
    project_type: str,
    index: str,
) -> list[dict]:
    mr: list[dict] = []
    cf: list[dict] = []
    if source in {"both", "modrinth", "MODRINTH"}:
        try:
            mr = await modrinth.search(query, loader, game_version, project_type=project_type, index=index)
        except httpx.HTTPError:
            mr = []
    if source in {"both", "curseforge", "CURSEFORGE"} and project_type in {"mod", "modpack"}:
        try:
            cf = await curseforge.search(query, loader, game_version)
        except httpx.HTTPError:
            cf = []
    return _dedupe(mr + cf)


def _dedupe(hits: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for hit in hits:
        key = (hit["source"], hit["external_id"])
        if key in seen:
            continue
        seen.add(key)
        out.append(hit)
    return out


async def download_and_install(
    server: Server,
    source: ModSource,
    external_id: str,
    version_id: str | None,
    loader: str,
) -> list[dict]:
    if source == ModSource.MODRINTH:
        payload = (
            await modrinth.version(version_id)
            if version_id
            else await modrinth.latest_version(external_id, loader, server.game_version)
        )
        if not payload:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No matching Modrinth version")
        versions = await modrinth.resolve_dependencies(payload, loader, server.game_version)
        installed = []
        for item in versions:
            primary = next((f for f in item.get("files", []) if f.get("primary")), None) or (
                item.get("files") or [None]
            )[0]
            if not primary:
                continue
            dest_name = primary["filename"]
            await _save_url(mods_volume(server) / dest_name, primary["url"])
            installed.append(
                {
                    "source": ModSource.MODRINTH,
                    "external_id": item.get("project_id", external_id),
                    "file_id": item["id"],
                    "name": dest_name,
                    "file_name": dest_name,
                }
            )
        return installed

    if source == ModSource.CURSEFORGE:
        file_info = (
            {"id": version_id}
            if version_id
            else await curseforge.latest_file(external_id, loader, server.game_version)
        )
        file_id = str(file_info["id"] if isinstance(file_info, dict) and "id" in file_info else version_id)
        try:
            url = await curseforge.file_download_url(external_id, file_id)
        except curseforge.DistributionBlocked as exc:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                {
                    "code": "distribution_blocked",
                    "message": (
                        "Автор запретил распространение через API "
                        "(allowModDistribution=false). Загрузите .jar вручную в /downloads."
                    ),
                    "mod_id": str(exc),
                },
            ) from exc
        dest_name = file_info.get("fileName") if isinstance(file_info, dict) else f"{external_id}.jar"
        dest_name = dest_name or f"{external_id}-{file_id}.jar"
        await _save_url(mods_volume(server) / dest_name, url)
        return [
            {
                "source": ModSource.CURSEFORGE,
                "external_id": external_id,
                "file_id": file_id,
                "name": dest_name,
                "file_name": dest_name,
            }
        ]

    raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported source")


async def _save_url(dest: Path, url: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            with dest.open("wb") as fh:
                async for chunk in response.aiter_bytes():
                    fh.write(chunk)
