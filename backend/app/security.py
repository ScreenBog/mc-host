from datetime import UTC, datetime, timedelta
from ipaddress import ip_address, ip_network

from fastapi import Header, HTTPException, Request, status
from jose import JWTError, jwt

from app.config import get_settings

YOOKASSA_NETWORKS = [
    ip_network("185.71.76.0/27"),
    ip_network("185.71.77.0/27"),
    ip_network("77.75.153.0/25"),
    ip_network("77.75.154.128/25"),
    ip_network("77.75.156.11/32"),
    ip_network("77.75.156.35/32"),
    ip_network("2a02:5180::/32"),
]

CLOUDFLARE_CONNECTING_IP = "cf-connecting-ip"


def create_token(subject: str, ttl: timedelta, token_type: str, extra: dict | None = None) -> str:
    settings = get_settings()
    payload = {
        "sub": subject,
        "typ": token_type,
        "exp": datetime.now(UTC) + ttl,
        **(extra or {}),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str, expected_type: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    if payload.get("typ") != expected_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")
    return payload


def client_ip(request: Request) -> str:
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


def is_yookassa_ip(ip: str) -> bool:
    try:
        parsed = ip_address(ip)
    except ValueError:
        return False
    return any(parsed in network for network in YOOKASSA_NETWORKS)


async def require_bot_token(x_internal_token: str = Header(...)) -> None:
    settings = get_settings()
    if x_internal_token != settings.internal_bot_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad internal token")


async def require_user(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return decode_token(authorization.removeprefix("Bearer ").strip(), "access")
