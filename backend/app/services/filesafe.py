from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from app.services.docker_orchestrator import server_dir

TEXT_SUFFIXES = {
    ".txt",
    ".log",
    ".yml",
    ".yaml",
    ".json",
    ".properties",
    ".toml",
    ".cfg",
    ".conf",
    ".snbt",
    ".md",
    ".xml",
    ".csv",
}
MAX_TEXT = 1_000_000


def root_of(server_id: str) -> Path:
    return server_dir(server_id).resolve()


def safe_join(server_id: str, rel: str) -> Path:
    root = root_of(server_id)
    cleaned = (rel or "").replace("\\", "/").lstrip("/")
    parts = [p for p in cleaned.split("/") if p and p != "."]
    if any(p == ".." for p in parts):
        raise HTTPException(400, "invalid path")
    target = root.joinpath(*parts).resolve()
    if not target.is_relative_to(root):
        raise HTTPException(400, "invalid path")
    return target


def rel_of(server_id: str, path: Path) -> str:
    root = root_of(server_id)
    return path.resolve().relative_to(root).as_posix()


def is_text(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES
