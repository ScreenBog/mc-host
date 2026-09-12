from __future__ import annotations

from pathlib import Path

from app.models import Server
from app.services.docker_orchestrator import server_dir

EDITABLE = {
    "max-players": "max_players",
    "gamemode": "gamemode",
    "difficulty": "difficulty",
    "online-mode": "online_mode",
    "pvp": "pvp",
    "white-list": "whitelist",
    "enable-command-block": "command_blocks",
    "spawn-animals": "spawn_animals",
    "spawn-monsters": "spawn_monsters",
    "allow-nether": "nether",
    "view-distance": "view_distance",
    "simulation-distance": "simulation_distance",
    "motd": "motd",
    "resource-pack": "resource_pack",
}

DEFAULTS = {
    "pvp": True,
    "whitelist": False,
    "command_blocks": False,
    "spawn_animals": True,
    "spawn_monsters": True,
    "nether": True,
    "view_distance": 10,
    "simulation_distance": 8,
    "motd": "",
    "resource_pack": "",
}


def _props_path(server: Server) -> Path:
    return server_dir(str(server.id)) / "server.properties"


def read_properties(server: Server) -> dict[str, str]:
    path = _props_path(server)
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        data[k.strip()] = v
    return data


def write_properties(server: Server, patch: dict) -> dict:
    data = read_properties(server)
    mapping_rev = {v: k for k, v in EDITABLE.items()}
    for key, value in patch.items():
        prop = mapping_rev.get(key, key.replace("_", "-"))
        if isinstance(value, bool):
            data[prop] = "true" if value else "false"
        else:
            data[prop] = str(value)
    path = _props_path(server)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"{k}={v}" for k, v in data.items()) + "\n"
    path.write_text(body, encoding="utf-8")
    return to_settings(server, data)


def to_settings(server: Server, props: dict[str, str] | None = None) -> dict:
    props = props if props is not None else read_properties(server)
    out = {
        "max_players": server.max_players,
        "gamemode": server.gamemode,
        "difficulty": server.difficulty,
        "online_mode": server.online_mode,
        **DEFAULTS,
        "motd": f"{server.subdomain}",
    }
    if server.settings:
        out.update(server.settings)
    for prop, field in EDITABLE.items():
        if prop in props:
            raw = props[prop]
            if raw.lower() in {"true", "false"}:
                out[field] = raw.lower() == "true"
            elif raw.isdigit():
                out[field] = int(raw)
            else:
                out[field] = raw
    return out
