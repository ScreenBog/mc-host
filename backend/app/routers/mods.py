from fastapi import APIRouter, Query

from app.schemas import ModHit
from app.services.mods_discovery import search_mods

router = APIRouter(prefix="/api/v1/mods", tags=["mods"])


@router.get("/search", response_model=list[ModHit])
async def search(
    query: str = Query(..., min_length=1),
    loader: str = Query(default="fabric"),
    game_version: str = Query(..., min_length=3),
    source: str = Query(default="both"),
    project_type: str = Query(default="mod"),
    index: str = Query(default="relevance"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=40),
) -> list[ModHit]:
    hits = await search_mods(
        query,
        loader,
        game_version,
        source=source,
        project_type=project_type,
        index=index,
        offset=offset,
        limit=limit,
    )
    return [ModHit.model_validate(h) for h in hits]
