from __future__ import annotations

import json

import httpx

from app.config import get_settings

BASE = "https://api.modrinth.com/v2"


def _headers() -> dict[str, str]:
    return {"User-Agent": get_settings().modrinth_user_agent}


async def search(query: str, loader: str, game_version: str, limit: int = 20) -> list[dict]:
    facets = json.dumps(
        [
            ["project_type:mod"],
            [f"versions:{game_version}"],
            [f"categories:{loader}"],
        ]
    )
    params = {"query": query, "facets": facets, "limit": limit}
    async with httpx.AsyncClient(timeout=20, headers=_headers()) as client:
        response = await client.get(f"{BASE}/search", params=params)
        response.raise_for_status()
        hits = response.json().get("hits", [])
    return [
        {
            "source": "MODRINTH",
            "external_id": hit["project_id"],
            "slug": hit.get("slug", hit["project_id"]),
            "name": hit.get("title", ""),
            "description": hit.get("description", ""),
            "icon_url": hit.get("icon_url"),
            "downloads": hit.get("downloads", 0),
            "distribution_blocked": False,
        }
        for hit in hits
    ]


async def version(version_id: str) -> dict:
    async with httpx.AsyncClient(timeout=20, headers=_headers()) as client:
        response = await client.get(f"{BASE}/version/{version_id}")
        response.raise_for_status()
        return response.json()


async def latest_version(project_id: str, loader: str, game_version: str) -> dict | None:
    params = {
        "loaders": json.dumps([loader]),
        "game_versions": json.dumps([game_version]),
    }
    async with httpx.AsyncClient(timeout=20, headers=_headers()) as client:
        response = await client.get(f"{BASE}/project/{project_id}/version", params=params)
        response.raise_for_status()
        versions = response.json()
    return versions[0] if versions else None


async def resolve_dependencies(version_payload: dict, loader: str, game_version: str) -> list[dict]:
    """Recursively walk required dependencies from GET /v2/version/{id}."""
    seen: set[str] = set()
    ordered: list[dict] = []

    async def walk(payload: dict) -> None:
        vid = payload.get("id")
        if not vid or vid in seen:
            return
        seen.add(vid)
        ordered.append(payload)
        for dep in payload.get("dependencies") or []:
            if dep.get("dependency_type") not in {"required", "embedded"}:
                continue
            if dep.get("version_id"):
                child = await version(dep["version_id"])
            elif dep.get("project_id"):
                child = await latest_version(dep["project_id"], loader, game_version)
            else:
                continue
            if child:
                await walk(child)

    await walk(version_payload)
    return ordered
