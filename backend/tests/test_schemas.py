import pytest
from pydantic import ValidationError

from app.schemas import ServerCreate
from app.models import ServerType


def test_subdomain_accepts_dns_label() -> None:
    body = ServerCreate(
        user_id=1,
        plan_id="plus",
        name="My SMP",
        subdomain="friends-smp",
        server_type=ServerType.PAPER,
        game_version="1.20.4",
    )
    assert body.subdomain == "friends-smp"


def test_subdomain_rejects_dots() -> None:
    with pytest.raises(ValidationError):
        ServerCreate(
            user_id=1,
            plan_id="plus",
            name="bad",
            subdomain="a.shnpp",
            server_type=ServerType.PAPER,
            game_version="1.20.4",
        )
