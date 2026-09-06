import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import Invoice, InvoiceStatus, Plan, Server, User
from app.schemas import PaymentCreate, PaymentOut, PlanOut
from app.security import client_ip, is_yookassa_ip, require_bot_token
from app.services import provisioning, yookassa_client

router = APIRouter(prefix="/api/v1", tags=["payments"])


@router.get("/plans", response_model=list[PlanOut])
async def list_plans(session: AsyncSession = Depends(get_session)) -> list[PlanOut]:
    rows = (await session.execute(select(Plan).order_by(Plan.price_monthly))).scalars().all()
    return [PlanOut.model_validate(p) for p in rows]


@router.post("/payments", response_model=PaymentOut, dependencies=[Depends(require_bot_token)])
async def create_invoice(
    body: PaymentCreate,
    session: AsyncSession = Depends(get_session),
) -> PaymentOut:
    settings = get_settings()
    plan = await session.get(Plan, body.plan_id)
    if plan is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown plan")
    user = await session.get(User, body.user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if body.purpose == "CREATE":
        taken = (
            await session.execute(select(Server).where(Server.subdomain == body.subdomain))
        ).scalar_one_or_none()
        if taken:
            raise HTTPException(status.HTTP_409_CONFLICT, "Subdomain taken")

    invoice = Invoice(
        user_id=body.user_id,
        server_id=body.server_id,
        amount=plan.price_monthly,
        status=InvoiceStatus.PENDING,
        purpose=body.purpose,
        metadata_={
            "plan_id": body.plan_id,
            "name": body.name,
            "subdomain": body.subdomain,
            "server_type": body.server_type.value,
            "game_version": body.game_version,
        },
    )
    session.add(invoice)
    await session.flush()

    if settings.beta_mode:
        invoice.yookassa_payment_id = f"beta-{invoice.id}"
        await session.commit()
        await session.refresh(invoice)
        await provisioning.provision_paid_invoice(session, invoice)
        return PaymentOut(
            invoice_id=invoice.id,
            confirmation_url=f"{settings.public_web_origin}/",
            amount=invoice.amount,
            status=InvoiceStatus.SUCCEEDED,
        )

    payment_id, confirmation_url = yookassa_client.create_payment(
        amount=plan.price_monthly,
        description=f"Minecraft {plan.name}: {body.subdomain}",
        metadata={"invoice_id": str(invoice.id), "user_id": str(body.user_id)},
        idempotence_key=str(uuid.uuid4()),
    )
    invoice.yookassa_payment_id = payment_id
    await session.commit()
    return PaymentOut(
        invoice_id=invoice.id,
        confirmation_url=confirmation_url,
        amount=invoice.amount,
        status=invoice.status,
    )


@router.post("/payments/webhook")
async def yookassa_webhook(request: Request, session: AsyncSession = Depends(get_session)) -> dict:
    settings = get_settings()
    ip = client_ip(request)
    if settings.yookassa_ip_check and not is_yookassa_ip(ip):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "IP is not in YooKassa ranges")

    payload = await request.json()
    event = payload.get("event")
    obj = payload.get("object") or {}
    payment_id = obj.get("id")
    if not payment_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Malformed notification")

    remote = yookassa_client.fetch_payment(payment_id)
    invoice = (
        await session.execute(select(Invoice).where(Invoice.yookassa_payment_id == payment_id))
    ).scalar_one_or_none()
    if invoice is None:
        return {"ok": True, "ignored": True}

    if event == "payment.canceled" or getattr(remote, "status", None) == "canceled":
        invoice.status = InvoiceStatus.CANCELED
        await session.commit()
        return {"ok": True}

    if event != "payment.succeeded" and getattr(remote, "status", None) != "succeeded":
        return {"ok": True, "ignored": True}

    if invoice.status == InvoiceStatus.SUCCEEDED:
        return {"ok": True, "duplicate": True}

    await provisioning.provision_paid_invoice(session, invoice)
    return {"ok": True}
