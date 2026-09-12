from __future__ import annotations

import httpx

from bot.config import settings


def _headers() -> dict[str, str]:
    return {"X-Internal-Token": settings.internal_bot_token}


class ApiError(RuntimeError):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


async def request(method: str, path: str, **kwargs):
    headers = {**_headers(), **(kwargs.pop("headers", {}) or {})}
    async with httpx.AsyncClient(base_url=settings.api_base_url, timeout=60) as client:
        response = await client.request(method, path, headers=headers, **kwargs)
        if response.status_code >= 400:
            raise ApiError(response.status_code, response.text)
        if response.status_code == 204:
            return None
        return response.json()


async def upsert_user(telegram_id: int, username: str | None) -> dict:
    return await request(
        "POST",
        "/api/v1/users/upsert",
        params={"telegram_id": telegram_id, "username": username},
    )


async def plans() -> list[dict]:
    return await request("GET", "/api/v1/plans")


async def create_payment(payload: dict) -> dict:
    return await request("POST", "/api/v1/payments", json=payload)


async def create_server(payload: dict) -> dict:
    return await request("POST", "/api/v1/internal/servers", json=payload)


async def servers(telegram_id: int) -> list[dict]:
    return await request("GET", f"/api/v1/internal/servers/{telegram_id}")


async def magic_link(telegram_id: int, username: str | None) -> dict:
    return await request(
        "POST",
        "/api/v1/auth/magic-link",
        json={"telegram_id": telegram_id, "username": username},
    )


async def power(server_id: str, action: str, telegram_id: int) -> dict:
    return await request(
        "POST",
        f"/api/v1/internal/servers/{server_id}/power",
        params={"telegram_id": telegram_id},
        json={"action": action},
    )


async def console(server_id: str, telegram_id: int) -> dict:
    return await request(
        "GET",
        f"/api/v1/internal/console/{server_id}",
        params={"telegram_id": telegram_id},
    )


async def console_cmd(server_id: str, telegram_id: int, command: str) -> dict:
    return await request(
        "POST",
        f"/api/v1/internal/console/{server_id}",
        params={"telegram_id": telegram_id},
        json={"command": command},
    )


async def search_mods(query: str, loader: str, game_version: str) -> list[dict]:
    return await request(
        "GET",
        "/api/v1/mods/search",
        params={"query": query, "loader": loader, "game_version": game_version},
    )


async def install_mod(server_id: str, telegram_id: int, source: str, external_id: str) -> dict:
    return await request(
        "POST",
        f"/api/v1/internal/mods/{server_id}",
        params={"telegram_id": telegram_id},
        json={"source": source, "external_id": external_id},
    )


async def admin_servers() -> list[dict]:
    return await request("GET", "/api/v1/internal/admin/servers")


async def admin_overview() -> dict:
    return await request("GET", "/api/v1/internal/admin/overview")


async def admin_power(server_id: str, action: str) -> dict:
    return await request(
        "POST",
        f"/api/v1/internal/admin/servers/{server_id}/power",
        params={"action": action},
    )
