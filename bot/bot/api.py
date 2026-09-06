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
    async with httpx.AsyncClient(base_url=settings.api_base_url, timeout=30) as client:
        response = await client.request(method, path, headers=_headers(), **kwargs)
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


async def servers(telegram_id: int) -> list[dict]:
    return await request("GET", f"/api/v1/internal/servers/{telegram_id}")


async def magic_link(telegram_id: int, username: str | None) -> dict:
    return await request(
        "POST",
        "/api/v1/auth/magic-link",
        json={"telegram_id": telegram_id, "username": username},
    )
