from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse


from app.config import get_settings
from app.db import init_db
from app.routers import admin, auth, dev, mods, payments, servers, software, users
from app.services import mc_router

settings = get_settings()

app = FastAPI(
    title="Minecraft Hosting Core API",
    version="1.0.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
)

origins = settings.cors_origin_list
if settings.beta_mode:
    origins = list(
        {
            *origins,
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000",
            f"http://{settings.public_ip}:8000",
            f"http://{settings.public_ip}:3000",
            "http://192.168.0.148:8000",
            "http://192.168.0.148:3000",
            "http://shnenepepe.online:8000",
            "https://shnenepepe.online",
        }
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(servers.router)
app.include_router(mods.router)
app.include_router(payments.router)
app.include_router(dev.router)
app.include_router(software.router)
app.include_router(admin.router)


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True, "beta": settings.beta_mode}


@app.on_event("startup")
async def startup() -> None:
    await init_db()
    if settings.beta_mode:
        await mc_router.start(settings.mc_router_port)


@app.on_event("shutdown")
async def shutdown() -> None:
    if settings.beta_mode:
        await mc_router.stop()


WEB_DIST = Path(__file__).resolve().parents[2] / "web" / ".output" / "public"


@app.get("/{full_path:path}")
async def spa(full_path: str):
    from fastapi import HTTPException

    if full_path.startswith("api/") or full_path in {"healthz", "docs"}:
        raise HTTPException(404)
    if not WEB_DIST.exists():
        raise HTTPException(404, "Frontend is not built yet")
    candidate = WEB_DIST / full_path
    if candidate.is_file():
        return FileResponse(candidate)
    nuxt_asset = WEB_DIST / "_nuxt" / full_path.removeprefix("_nuxt/")
    if full_path.startswith("_nuxt/") and nuxt_asset.is_file():
        return FileResponse(nuxt_asset)
    index = WEB_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(404)
