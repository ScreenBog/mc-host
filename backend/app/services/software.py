from __future__ import annotations

SOFTWARE = [
    {
        "id": "VANILLA",
        "edition": "JAVA",
        "name": "Vanilla",
        "blurb": "Чистый Minecraft без плагинов и модов.",
        "recommended": False,
        "versions": ["1.21.11", "1.21.4", "1.21.1", "1.20.4", "1.20.1", "1.19.4", "1.16.5"],
        "loader": None,
        "addon_kind": None,
    },
    {
        "id": "SNAPSHOT",
        "edition": "JAVA",
        "name": "Snapshot",
        "blurb": "Тестовые сборки Mojang. Миры могут сломаться.",
        "recommended": False,
        "versions": ["25w14a", "1.21.11"],
        "loader": None,
        "addon_kind": None,
    },
    {
        "id": "PAPER",
        "edition": "JAVA",
        "name": "Paper",
        "blurb": "Плагины, производительность. Рекомендуем.",
        "recommended": True,
        "versions": ["1.21.11", "1.21.4", "1.21.1", "1.20.4", "1.20.1", "1.19.4", "1.16.5"],
        "loader": "paper",
        "addon_kind": "plugin",
    },
    {
        "id": "PURPUR",
        "edition": "JAVA",
        "name": "Purpur",
        "blurb": "Paper + больше настроек геймплея.",
        "recommended": False,
        "versions": ["1.21.11", "1.21.4", "1.21.1", "1.20.4", "1.20.1"],
        "loader": "purpur",
        "addon_kind": "plugin",
    },
    {
        "id": "SPIGOT",
        "edition": "JAVA",
        "name": "Spigot",
        "blurb": "Классические Bukkit-плагины.",
        "recommended": False,
        "versions": ["1.21.1", "1.20.4", "1.20.1", "1.16.5"],
        "loader": "spigot",
        "addon_kind": "plugin",
    },
    {
        "id": "FABRIC",
        "edition": "JAVA",
        "name": "Fabric",
        "blurb": "Лёгкие моды (Sodium, Lithium, Fabric API).",
        "recommended": False,
        "versions": ["1.21.11", "1.21.4", "1.21.1", "1.20.4", "1.20.1", "1.19.4"],
        "loader": "fabric",
        "addon_kind": "mod",
        "loader_versions": {"recommended": "0.16.9", "choices": ["0.16.9", "0.16.5", "0.15.11"]},
    },
    {
        "id": "FORGE",
        "edition": "JAVA",
        "name": "Forge",
        "blurb": "Крупные модпаки и техмоды.",
        "recommended": False,
        "versions": ["1.20.1", "1.19.2", "1.18.2", "1.16.5", "1.12.2"],
        "loader": "forge",
        "addon_kind": "mod",
        "loader_versions": {"recommended": "47.3.0", "choices": ["47.3.0", "47.2.0"]},
    },
    {
        "id": "NEOFORGE",
        "edition": "JAVA",
        "name": "NeoForge",
        "blurb": "Современный форк Forge для 1.20.1+.",
        "recommended": False,
        "versions": ["1.21.1", "1.21.4", "1.20.1"],
        "loader": "neoforge",
        "addon_kind": "mod",
        "loader_versions": {"recommended": "21.1.0", "choices": ["21.1.0", "20.4.0"]},
    },
    {
        "id": "QUILT",
        "edition": "JAVA",
        "name": "Quilt",
        "blurb": "Форк Fabric, многие моды совместимы.",
        "recommended": False,
        "versions": ["1.21.1", "1.20.4", "1.20.1"],
        "loader": "quilt",
        "addon_kind": "mod",
        "loader_versions": {"recommended": "0.26.0", "choices": ["0.26.0"]},
    },
    {
        "id": "ARCLIGHT",
        "edition": "JAVA",
        "name": "Arclight",
        "blurb": "Моды Forge/NeoForge и Bukkit-плагины вместе.",
        "recommended": False,
        "versions": ["1.20.1", "1.19.4"],
        "loader": "forge",
        "addon_kind": "mod",
    },
    {
        "id": "MODPACK",
        "edition": "JAVA",
        "name": "Модпак",
        "blurb": "Готовый набор модов (ATM, Better MC, RLCraft).",
        "recommended": False,
        "versions": ["1.20.1", "1.19.2", "1.16.5", "1.12.2"],
        "loader": None,
        "addon_kind": "modpack",
    },
    {
        "id": "BEDROCK",
        "edition": "BEDROCK",
        "name": "Vanilla Bedrock",
        "blurb": "Официальный dedicated Bedrock.",
        "recommended": False,
        "versions": ["1.21.50", "1.21.30"],
        "loader": None,
        "addon_kind": None,
    },
    {
        "id": "POCKETMINE",
        "edition": "BEDROCK",
        "name": "PocketMine",
        "blurb": "Плагины для Bedrock на PHP.",
        "recommended": False,
        "versions": ["1.21.50", "1.20.0"],
        "loader": "pocketmine",
        "addon_kind": "plugin",
    },
]

MODPACKS = [
    {"slug": "all-the-mods-9", "name": "All the Mods 9", "version": "1.20.1", "ram_hint_gb": 8, "loader": "forge"},
    {"slug": "better-mc-forge", "name": "Better MC", "version": "1.20.1", "ram_hint_gb": 6, "loader": "forge"},
    {"slug": "rlcraft", "name": "RLCraft", "version": "1.12.2", "ram_hint_gb": 6, "loader": "forge"},
    {"slug": "create-live", "name": "Create: Above and Beyond", "version": "1.16.5", "ram_hint_gb": 6, "loader": "forge"},
    {"slug": "prominence-2", "name": "Prominence II", "version": "1.20.1", "ram_hint_gb": 8, "loader": "fabric"},
]


def list_software(edition: str | None = None) -> list[dict]:
    rows = SOFTWARE
    if edition:
        rows = [s for s in rows if s["edition"] == edition.upper()]
    return rows


def get_software(sid: str) -> dict | None:
    sid = sid.upper()
    return next((s for s in SOFTWARE if s["id"] == sid), None)


def versions_for(sid: str) -> dict:
    item = get_software(sid)
    if not item:
        return {"id": sid, "versions": [], "groups": {}}
    versions = item["versions"]
    fresh = versions[:3]
    archive = versions[3:]
    return {
        "id": item["id"],
        "versions": versions,
        "loader": item.get("loader"),
        "loader_versions": item.get("loader_versions"),
        "groups": {"fresh": fresh, "lts": versions[1:4], "archive": archive},
    }


def search_modpacks(query: str = "", game_version: str = "") -> list[dict]:
    q = query.lower().strip()
    out = []
    for pack in MODPACKS:
        if q and q not in pack["name"].lower() and q not in pack["slug"]:
            continue
        if game_version and pack["version"] != game_version:
            continue
        out.append(pack)
    return out
