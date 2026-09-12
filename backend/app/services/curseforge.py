from __future__ import annotations

import httpx

from app.config import get_settings

BASE = "https://api.curseforge.com/v1"
GAME_ID = 432
CLASS_MODS = 6
CLASS_MODPACKS = 4471

LOADER_IDS = {
    "forge": 1,
    "fabric": 4,
    "neoforge": 6,
    "paper": None,
    "quilt": 5,
}


class DistributionBlocked(RuntimeError):
    def __init__(self, name: str):
        super().__init__(name)
        self.name = name


def _headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "Accept": "application/json",
        "x-api-key": settings.curseforge_api_key,
        "User-Agent": settings.modrinth_user_agent,
    }


async def search(query: str, loader: str, game_version: str, page_size: int = 20) -> list[dict]:
    settings = get_settings()
    if not settings.curseforge_api_key:
        return []
    params = {
        "gameId": GAME_ID,
        "classId": CLASS_MODS,
        "searchFilter": query,
        "gameVersion": game_version,
        "pageSize": page_size,
        "sortField": 2,
        "sortOrder": "desc",
    }
    loader_id = LOADER_IDS.get(loader.lower())
    if loader_id:
        params["modLoaderType"] = loader_id
    async with httpx.AsyncClient(timeout=20, headers=_headers()) as client:
        response = await client.get(f"{BASE}/mods/search", params=params)
        response.raise_for_status()
        mods = response.json().get("data", [])
    results = []
    for mod in mods:
        blocked = mod.get("allowModDistribution") is False
        results.append(
            {
                "source": "CURSEFORGE",
                "external_id": str(mod["id"]),
                "slug": mod.get("slug", str(mod["id"])),
                "name": mod.get("name", ""),
                "description": mod.get("summary", ""),
                "icon_url": (mod.get("logo") or {}).get("thumbnailUrl"),
                "downloads": int(mod.get("downloadCount") or 0),
                "distribution_blocked": blocked,
                "author": (mod.get("authors") or [{}])[0].get("name") if mod.get("authors") else "",
                "date_modified": str(mod.get("dateModified") or ""),
                "loaders": [],
                "game_versions": [],
                "project_type": "mod",
            }
        )
    return results


async def latest_file(mod_id: str, loader: str, game_version: str) -> dict:
    params: dict = {"gameVersion": game_version, "pageSize": 20}
    loader_id = LOADER_IDS.get(loader.lower())
    if loader_id:
        params["modLoaderType"] = loader_id
    async with httpx.AsyncClient(timeout=20, headers=_headers()) as client:
        response = await client.get(f"{BASE}/mods/{mod_id}/files", params=params)
        response.raise_for_status()
        files = response.json().get("data", [])
    if not files:
        raise RuntimeError("No matching CurseForge file")
    return files[0]


async def file_download_url(mod_id: str, file_id: str) -> str:
    async with httpx.AsyncClient(timeout=20, headers=_headers()) as client:
        response = await client.get(f"{BASE}/mods/{mod_id}/files/{file_id}/download-url")
        if response.status_code == 403:
            raise DistributionBlocked(mod_id)
        response.raise_for_status()
        url = response.json().get("data")
        if not url:
            raise DistributionBlocked(mod_id)
        return url
