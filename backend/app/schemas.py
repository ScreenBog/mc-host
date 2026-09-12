import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models import InvoiceStatus, ModSource, ServerStatus, ServerType


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    cpu_cores: Decimal
    ram_mb: int
    disk_mb: int
    price_monthly: Decimal


class ServerCreate(BaseModel):
    user_id: int | None = None
    plan_id: str = "starter"
    name: str = Field(min_length=2, max_length=64)
    subdomain: str = Field(pattern=r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
    server_type: ServerType
    game_version: str
    edition: str = "JAVA"
    loader_version: str | None = None
    max_players: int = 10
    gamemode: str = "survival"
    difficulty: str = "normal"
    online_mode: bool = False


class ServerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: int
    plan_id: str
    name: str
    subdomain: str
    container_id: str | None
    server_type: ServerType
    game_version: str
    status: ServerStatus
    expires_at: datetime
    created_at: datetime
    address: str | None = None
    edition: str | None = None
    loader_version: str | None = None
    max_players: int | None = None
    gamemode: str | None = None
    difficulty: str | None = None
    online_mode: bool | None = None
    last_error: str | None = None
    players_online: int | None = None
    restart_required: bool | None = None
    ip_address: str | None = None


class PowerAction(BaseModel):
    action: str = Field(pattern=r"^(start|stop|restart)$")


class ModSearchQuery(BaseModel):
    query: str
    loader: str
    game_version: str


class ModHit(BaseModel):
    source: ModSource
    external_id: str
    slug: str
    name: str
    description: str
    icon_url: str | None = None
    downloads: int = 0
    distribution_blocked: bool = False
    author: str | None = None
    date_modified: str | None = None
    loaders: list[str] = []
    game_versions: list[str] = []
    project_type: str | None = None


class ModInstallRequest(BaseModel):
    source: ModSource
    external_id: str
    version_id: str | None = None


class InstalledModOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: ModSource
    external_id: str
    file_id: str
    name: str
    file_name: str
    installed_at: datetime
    enabled: bool = True
    addon_type: str = "mod"
    install_error: str | None = None


class PaymentCreate(BaseModel):
    user_id: int
    plan_id: str
    name: str
    subdomain: str
    server_type: ServerType
    game_version: str
    purpose: str = "CREATE"
    server_id: uuid.UUID | None = None


class PaymentOut(BaseModel):
    invoice_id: uuid.UUID
    confirmation_url: str
    amount: Decimal
    status: InvoiceStatus


class MagicLinkRequest(BaseModel):
    telegram_id: int
    username: str | None = None


class MagicLinkOut(BaseModel):
    url: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_admin: bool = False


class ServerSettingsIn(BaseModel):
    max_players: int | None = None
    gamemode: str | None = None
    difficulty: str | None = None
    online_mode: bool | None = None
    pvp: bool | None = None
    whitelist: bool | None = None
    command_blocks: bool | None = None
    spawn_animals: bool | None = None
    spawn_monsters: bool | None = None
    nether: bool | None = None
    view_distance: int | None = None
    simulation_distance: int | None = None
    motd: str | None = None
    resource_pack: str | None = None


class AclIn(BaseModel):
    telegram_id: int | None = None
    username: str | None = None
    role: str = "START_CONSOLE"


class ConsoleCommand(BaseModel):
    command: str = Field(min_length=1, max_length=256)
