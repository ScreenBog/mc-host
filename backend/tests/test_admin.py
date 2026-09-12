from app.security import admin_telegram_ids, is_platform_admin
from app.services.software import get_software, list_software, versions_for


def test_hardcoded_owner_is_admin() -> None:
    assert 1920838704 in admin_telegram_ids()
    assert is_platform_admin(1920838704)
    assert not is_platform_admin(1)


def test_software_catalog_has_fabric_and_paper() -> None:
    ids = {s["id"] for s in list_software("JAVA")}
    assert "FABRIC" in ids
    assert "PAPER" in ids
    fabric = versions_for("FABRIC")
    assert "1.21.1" in fabric["versions"]
    assert get_software("pocketmine")["edition"] == "BEDROCK"
