from fastapi import APIRouter, HTTPException, Query

from app.services.software import get_software, list_software, search_modpacks, versions_for

router = APIRouter(prefix="/api/v1", tags=["software"])


@router.get("/software")
async def software(edition: str | None = Query(default=None)) -> list[dict]:
    return list_software(edition)


@router.get("/software/{software_id}/versions")
async def software_versions(software_id: str) -> dict:
    item = get_software(software_id)
    if item is None:
        raise HTTPException(404, "Unknown software")
    return versions_for(software_id)


@router.get("/modpacks/search")
async def modpacks(query: str = "", game_version: str = "") -> list[dict]:
    return search_modpacks(query, game_version)


@router.get("/subdomain-available")
async def subdomain_available(subdomain: str) -> dict:
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Server

    async with SessionLocal() as db:
        taken = (
            await db.execute(select(Server).where(Server.subdomain == subdomain.lower()))
        ).scalar_one_or_none()
    return {"available": taken is None, "subdomain": subdomain.lower()}
