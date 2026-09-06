from __future__ import annotations

import asyncio
import logging
import os
import socket
import subprocess
import time
from pathlib import Path

from app.config import get_settings
from app.services import mc_router
from app.services.docker_orchestrator import server_dir

log = logging.getLogger("java-orch")

_procs: dict[str, subprocess.Popen] = {}
_ports: dict[str, int] = {}
_next_port = 0


def _alloc_port() -> int:
    global _next_port
    settings = get_settings()
    if _next_port == 0:
        _next_port = settings.backend_bind_start
    for candidate in range(_next_port, _next_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", candidate))
            except OSError:
                continue
            _next_port = candidate + 1
            return candidate
    raise RuntimeError("No free backend ports")


def _paper_jar() -> Path:
    settings = get_settings()
    if settings.paper_jar:
        path = Path(settings.paper_jar)
        if path.exists():
            return path
    root = Path(settings.mc_servers_root).resolve().parent
    matches = sorted((root / "runtime").glob("paper-*.jar"))
    if matches:
        return matches[-1]
    raise FileNotFoundError("Paper jar is missing. Run scripts/download_paper.py")


def _write_files(srv: Path, port: int, motd: str) -> None:
    (srv / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    props = srv / "server.properties"
    existing = props.read_text(encoding="utf-8") if props.exists() else ""
    lines = {
        "server-port": str(port),
        "server-ip": "127.0.0.1",
        "online-mode": "false",
        "motd": motd.replace("\n", " "),
        "max-players": "10",
        "spawn-protection": "0",
        "enable-status": "true",
        "sync-chunk-writes": "true",
    }
    data = {}
    for line in existing.splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            data[k] = v
    data.update(lines)
    props.write_text("\n".join(f"{k}={v}" for k, v in data.items()) + "\n", encoding="utf-8")


def create_mc_server(
    server_id: str,
    subdomain: str,
    server_type: str,
    game_version: str,
    ram_mb: int,
    cpus: float,
    modrinth_projects: str | None = None,
    curseforge_files: str | None = None,
) -> str:
    settings = get_settings()
    srv = server_dir(server_id)
    port = _alloc_port()
    motd = f"{subdomain}.{settings.game_domain}"
    _write_files(srv, port, motd)
    jar = _paper_jar()
    ram = max(1024, min(int(ram_mb), 2048))
    cmd = [
        settings.java_bin,
        f"-Xms{ram}M",
        f"-Xmx{ram}M",
        "-jar",
        str(jar),
        "nogui",
    ]
    log.info("starting %s on :%s cmd=%s", server_id, port, cmd)
    proc = subprocess.Popen(
        cmd,
        cwd=str(srv),
        stdout=open(srv / "process.log", "ab"),
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    _procs[server_id] = proc
    _ports[server_id] = port
    hostname = f"{subdomain}.{settings.game_domain}"

    async def wake() -> None:
        start_container(f"java:{port}:{server_id}")

    try:
        loop = asyncio.get_running_loop()
        loop.call_soon(lambda: mc_router.register(hostname, port, wake=wake))
    except RuntimeError:
        mc_router.register(hostname, port)
    mc_router.register(hostname, port)
    time.sleep(2)
    if proc.poll() is not None:
        raise RuntimeError(f"Java process exited with {proc.returncode}. See {srv / 'process.log'}")
    return f"java:{port}:{server_id}"


def _parse(container_id: str) -> tuple[int, str]:
    _, port, server_id = container_id.split(":", 2)
    return int(port), server_id


def start_container(container_id: str) -> None:
    port, server_id = _parse(container_id)
    proc = _procs.get(server_id)
    if proc and proc.poll() is None:
        return
    settings = get_settings()
    srv = server_dir(server_id)
    jar = _paper_jar()
    ram = 2048
    cmd = [settings.java_bin, f"-Xms{ram}M", f"-Xmx{ram}M", "-jar", str(jar), "nogui"]
    proc = subprocess.Popen(
        cmd,
        cwd=str(srv),
        stdout=open(srv / "process.log", "ab"),
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    _procs[server_id] = proc
    _ports[server_id] = port


def stop_container(container_id: str) -> None:
    _, server_id = _parse(container_id)
    proc = _procs.get(server_id)
    if not proc or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()


def restart_container(container_id: str) -> None:
    stop_container(container_id)
    time.sleep(1)
    start_container(container_id)


def remove_container(container_id: str) -> None:
    stop_container(container_id)
    try:
        _, server_id = _parse(container_id)
        _procs.pop(server_id, None)
    except ValueError:
        pass


def power(container_id: str, action: str) -> None:
    match action:
        case "start":
            start_container(container_id)
        case "stop":
            stop_container(container_id)
        case "restart":
            restart_container(container_id)
        case _:
            raise ValueError(action)
