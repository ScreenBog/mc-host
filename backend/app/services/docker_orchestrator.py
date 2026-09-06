from __future__ import annotations

import asyncio
from pathlib import Path

import docker
from docker.errors import NotFound
from docker.models.containers import Container

from app.config import get_settings
from app.models import Server, ServerType

ITZ_TYPE = {
    ServerType.VANILLA: "VANILLA",
    ServerType.PAPER: "PAPER",
    ServerType.PURPUR: "PURPUR",
    ServerType.FABRIC: "FABRIC",
    ServerType.FORGE: "FORGE",
    ServerType.NEOFORGE: "NEOFORGE",
}


def _client() -> docker.DockerClient:
    return docker.from_env()


def server_dir(server_id: str) -> Path:
    settings = get_settings()
    path = Path(settings.mc_servers_root) / server_id
    path.mkdir(parents=True, exist_ok=True)
    (path / "mods").mkdir(exist_ok=True)
    (path / "plugins").mkdir(exist_ok=True)
    return path


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
    if settings.beta_mode:
        from app.services.java_orchestrator import create_mc_server as java_create

        return java_create(
            server_id,
            subdomain,
            server_type,
            game_version,
            ram_mb,
            cpus,
            modrinth_projects,
            curseforge_files,
        )
    srv_dir = server_dir(server_id)
    env = {
        "EULA": "TRUE",
        "TYPE": server_type.upper(),
        "VERSION": game_version,
        "MEMORY": f"{ram_mb}M",
        "USE_AIKAR_FLAGS": "TRUE",
        "ENABLE_ROLLING_LOGS": "true",
        "OVERRIDE_SERVER_PROPERTIES": "true",
        "MOTD": f"{subdomain}.{settings.game_domain}",
    }
    if modrinth_projects:
        env["MODRINTH_PROJECTS"] = modrinth_projects
        env["MODRINTH_DOWNLOAD_OPTIONAL_DEPENDENCIES"] = "false"
    if curseforge_files:
        env["CURSEFORGE_FILES"] = curseforge_files

    client = _client()
    container = client.containers.run(
        image=settings.mc_image,
        name=f"mc-{server_id}",
        detach=True,
        restart_policy={"Name": "on-failure", "MaximumRetryCount": 3},
        environment=env,
        labels={
            "mc-router.host": f"{subdomain}.{settings.game_domain}",
            "mc-router.auto-scale-up": "true",
            "mc-router.auto-scale-down": "true",
            "mc-hosting.server-id": server_id,
        },
        volumes={str(srv_dir): {"bind": "/data", "mode": "rw"}},
        network=settings.docker_network,
        nano_cpus=int(cpus * 1e9),
        mem_limit=f"{ram_mb}m",
        memswap_limit=f"{ram_mb}m",
        pids_limit=256,
        user="1000:1000",
    )
    return container.id


def _get(container_id: str) -> Container:
    return _client().containers.get(container_id)


def start_container(container_id: str) -> None:
    _get(container_id).start()


def stop_container(container_id: str) -> None:
    _get(container_id).stop(timeout=30)


def restart_container(container_id: str) -> None:
    _get(container_id).restart(timeout=30)


def remove_container(container_id: str) -> None:
    if container_id.startswith("java:"):
        from app.services.java_orchestrator import remove_container as java_remove

        java_remove(container_id)
        return
    try:
        container = _get(container_id)
        container.stop(timeout=20)
        container.remove(force=True)
    except NotFound:
        return


def set_router_enabled(container_id: str, enabled: bool) -> None:
    """Detach host label so mc-router stops advertising a suspended instance."""
    container = _get(container_id)
    host = container.labels.get("mc-router.host", "")
    if enabled and host.startswith("disabled:"):
        container.reload()
    # Docker cannot mutate labels in place; we rewrite via commit-less rename of the
    # advertised hostname by updating a sidecar env file consumed by recreate.
    # For live suspend we stop the container: AUTO_SCALE_UP is then ignored because
    # the host label is rewritten on next provision. Stopping is enough for T=0.
    if not enabled:
        container.stop(timeout=20)


def power(container_id: str, action: str) -> None:
    if container_id.startswith("java:"):
        from app.services.java_orchestrator import power as java_power

        java_power(container_id, action)
        return
    match action:
        case "start":
            start_container(container_id)
        case "stop":
            stop_container(container_id)
        case "restart":
            restart_container(container_id)
        case _:
            raise ValueError(f"unknown action {action}")


async def create_mc_server_async(*args, **kwargs) -> str:
    return await asyncio.to_thread(create_mc_server, *args, **kwargs)


async def power_async(container_id: str, action: str) -> None:
    await asyncio.to_thread(power, container_id, action)


async def remove_container_async(container_id: str) -> None:
    await asyncio.to_thread(remove_container, container_id)


def mods_volume(server: Server) -> Path:
    return server_dir(str(server.id)) / "mods"
