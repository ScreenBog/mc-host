from __future__ import annotations

import uuid
from decimal import Decimal

from yookassa import Configuration, Payment

from app.config import get_settings


def configure() -> None:
    settings = get_settings()
    Configuration.account_id = settings.yookassa_shop_id
    Configuration.secret_key = settings.yookassa_secret_key


def create_payment(
    *,
    amount: Decimal,
    description: str,
    metadata: dict,
    idempotence_key: str | None = None,
) -> tuple[str, str]:
    settings = get_settings()
    configure()
    payment = Payment.create(
        {
            "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "return_url": settings.yookassa_return_url,
            },
            "capture": True,
            "description": description,
            "metadata": metadata,
        },
        idempotence_key or str(uuid.uuid4()),
    )
    return payment.id, payment.confirmation.confirmation_url


def fetch_payment(payment_id: str):
    configure()
    return Payment.find_one(payment_id)
