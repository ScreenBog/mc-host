from __future__ import annotations

import httpx

from app.config import get_settings


class CloudflareError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.cloudflare_api_token}",
        "Content-Type": "application/json",
    }


async def create_cname(subdomain: str) -> str:
    settings = get_settings()
    if settings.beta_mode or not settings.cloudflare_api_token or not settings.cloudflare_zone_id:
        return "beta-dns-skipped"

    payload = {
        "type": "CNAME",
        "name": f"{subdomain}.{settings.game_domain}",
        "content": settings.node_hostname,
        "ttl": 1,
        "proxied": False,
        "comment": "mc-hosting auto",
    }
    url = f"https://api.cloudflare.com/client/v4/zones/{settings.cloudflare_zone_id}/dns_records"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, headers=_headers(), json=payload)
        data = response.json()
        if not data.get("success"):
            raise CloudflareError(str(data.get("errors")))
        return data["result"]["id"]


async def create_srv(subdomain: str, service: str, port: int) -> str:
    """SRV for Voice Chat / Geyser: _minecraft._udp.<sub>.shnpp.ru or custom service."""
    settings = get_settings()
    payload = {
        "type": "SRV",
        "name": f"{service}.{subdomain}.{settings.game_domain}",
        "data": {
            "priority": 0,
            "weight": 5,
            "port": port,
            "target": settings.node_hostname,
        },
        "ttl": 1,
        "proxied": False,
    }
    url = f"https://api.cloudflare.com/client/v4/zones/{settings.cloudflare_zone_id}/dns_records"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, headers=_headers(), json=payload)
        data = response.json()
        if not data.get("success"):
            raise CloudflareError(str(data.get("errors")))
        return data["result"]["id"]


async def delete_record(record_id: str) -> None:
    settings = get_settings()
    if not record_id:
        return
    url = (
        f"https://api.cloudflare.com/client/v4/zones/"
        f"{settings.cloudflare_zone_id}/dns_records/{record_id}"
    )
    async with httpx.AsyncClient(timeout=20) as client:
        await client.delete(url, headers=_headers())
