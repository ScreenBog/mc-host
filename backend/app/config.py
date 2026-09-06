from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), extra="ignore"
    )

    app_env: str = "production"
    beta_mode: bool = False
    public_ip: str = "178.47.143.15"
    public_web_origin: str = "https://shnenepepe.online"
    public_api_origin: str = "https://api.shnenepepe.online"
    game_domain: str = "shnenepepe.ru"
    node_hostname: str = "node1.shnenepepe.ru"

    database_url: str = "postgresql+asyncpg://orchestrator:dev@localhost:5432/mc_platform"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-secret-change-me"
    internal_bot_token: str = "dev-internal-token"

    cors_origins: str = "https://shnenepepe.online"

    telegram_bot_token: str = ""

    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""
    yookassa_return_url: str = "https://shnenepepe.online/payments/return"
    yookassa_ip_check: bool = True

    cloudflare_api_token: str = ""
    cloudflare_zone_id: str = ""

    curseforge_api_key: str = ""
    modrinth_user_agent: str = "shnenepepe-hosting/1.0.0 (https://shnenepepe.online)"

    mc_servers_root: str = "/var/mc_hosting/servers"
    docker_network: str = "mc-router-net"
    mc_image: str = "itzg/minecraft-server:latest"
    java_bin: str = "java"
    paper_jar: str = ""
    mc_router_port: int = 25565
    backend_bind_start: int = 25566

    @field_validator("database_url")
    @classmethod
    def require_async_pg(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
