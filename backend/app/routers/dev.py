from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import Plan, Server, ServerStatus, ServerType, User
from app.schemas import ServerOut
from app.security import create_token
from app.services import provisioning

router = APIRouter(prefix="/api/v1/dev", tags=["dev"])


class BootstrapIn(BaseModel):
    telegram_id: int = 1
    username: str = "beta"
    name: str = "Beta SMP"
    subdomain: str = Field(default="beta", pattern=r"^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$")
    plan_id: str = "starter"
    server_type: ServerType = ServerType.PAPER
    game_version: str = "1.21.11"


def _require_beta() -> None:
    if not get_settings().beta_mode:
        raise HTTPException(404, "Beta endpoint disabled")


@router.post("/bootstrap")
async def bootstrap(body: BootstrapIn, session: AsyncSession = Depends(get_session)) -> dict:
    _require_beta()
    user = (
        await session.execute(select(User).where(User.telegram_id == body.telegram_id))
    ).scalar_one_or_none()
    if user is None:
        user = User(telegram_id=body.telegram_id, username=body.username)
        session.add(user)
        await session.flush()
    plan = await session.get(Plan, body.plan_id)
    if plan is None:
        raise HTTPException(400, "Unknown plan")
    server = (
        await session.execute(select(Server).where(Server.subdomain == body.subdomain))
    ).scalar_one_or_none()
    if server is None:
        server = Server(
            user_id=user.id,
            plan_id=plan.id,
            name=body.name,
            subdomain=body.subdomain,
            server_type=body.server_type,
            game_version=body.game_version,
            status=ServerStatus.PROVISIONING,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        session.add(server)
        await session.flush()
        from app.models import Invoice, InvoiceStatus

        invoice = Invoice(
            user_id=user.id,
            server_id=server.id,
            amount=0,
            status=InvoiceStatus.PENDING,
            purpose="CREATE",
            yookassa_payment_id=f"beta-{server.id}",
            metadata_={
                "plan_id": plan.id,
                "name": body.name,
                "subdomain": body.subdomain,
                "server_type": body.server_type.value,
                "game_version": body.game_version,
            },
        )
        session.add(invoice)
        await session.flush()
        server = await provisioning.provision_paid_invoice(session, invoice)
    elif server.container_id:
        from app.services.java_orchestrator import ensure_running
        from app.services.docker_orchestrator import power_async
        import asyncio

        await asyncio.to_thread(ensure_running, server.container_id, server.subdomain)
        try:
            await power_async(server.container_id, "start")
        except Exception:
            pass
        server.status = ServerStatus.RUNNING
        await session.commit()
    else:
        from app.models import Invoice, InvoiceStatus

        invoice = Invoice(
            user_id=user.id,
            server_id=server.id,
            amount=0,
            status=InvoiceStatus.PENDING,
            purpose="CREATE",
            yookassa_payment_id=f"beta-retry-{server.id}",
            metadata_={
                "plan_id": plan.id,
                "name": body.name,
                "subdomain": body.subdomain,
                "server_type": body.server_type.value,
                "game_version": body.game_version,
            },
        )
        session.add(invoice)
        await session.flush()
        server = await provisioning.provision_paid_invoice(session, invoice)
    settings = get_settings()
    token = create_token(
        subject=str(user.id),
        ttl=timedelta(days=7),
        token_type="access",
        extra={"tg": user.telegram_id},
    )
    magic = create_token(
        subject=str(user.id),
        ttl=timedelta(minutes=30),
        token_type="magic",
        extra={"tg": user.telegram_id},
    )
    return {
        "access_token": token,
        "panel": f"{settings.public_web_origin}/auth/callback?token={magic}",
        "address": f"{server.subdomain}.{settings.game_domain}",
        "server_id": str(server.id),
        "status": server.status.value,
        "connect": f"{server.subdomain}.{settings.game_domain}:25565",
    }


@router.get("/health")
async def health() -> dict:
    _require_beta()
    return {"beta": True, "ip": get_settings().public_ip}
