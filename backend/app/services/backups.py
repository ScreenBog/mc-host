from __future__ import annotations

import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from app.models import Backup, Server
from app.services.docker_orchestrator import server_dir


def backups_dir(server_id: str) -> Path:
    path = server_dir(server_id) / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_backup(server: Server, kind: str = "manual") -> tuple[Path, int]:
    root = server_dir(str(server.id))
    world = root / "world"
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    dest = backups_dir(str(server.id)) / f"{kind}-{stamp}.zip"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder in ("world", "world_nether", "world_the_end"):
            src = root / folder
            if not src.exists():
                continue
            for file in src.rglob("*"):
                if file.is_file():
                    zf.write(file, file.relative_to(root).as_posix())
        props = root / "server.properties"
        if props.exists():
            zf.write(props, "server.properties")
    size = dest.stat().st_size
    return dest, size


def restore_backup(server: Server, zip_path: Path) -> None:
    root = server_dir(str(server.id))
    for folder in ("world", "world_nether", "world_the_end"):
        target = root / folder
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(root)


def prune(server: Server, keep: int) -> None:
    files = sorted(backups_dir(str(server.id)).glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    for extra in files[keep:]:
        extra.unlink(missing_ok=True)


def world_zip(server: Server) -> Path:
    dest, _ = create_backup(server, kind="world")
    return dest
