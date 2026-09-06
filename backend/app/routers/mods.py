from fastapi import APIRouter, Query

from app.schemas import ModHit
from app.services.mods_discovery import search_mods

router = APIRouter(prefix="/api/v1/mods", tags=["mods"])


@router.get("/search", response_model=list[ModHit])
async def search(
    query: str = Query(..., min_length=1),
    loader: str = Query(..., pattern="^(fabric|forge|neoforge|paper)$"),
    game_version: str = Query(..., min_length=3),
) -> list[ModHit]:
    hits = await search_mods(query, loader, game_version)
    return [ModHit.model_validate(h) for h in hits]
