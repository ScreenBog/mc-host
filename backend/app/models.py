import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ServerStatus(str, enum.Enum):
    PROVISIONING = "PROVISIONING"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    SLEEPING = "SLEEPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"


class ServerType(str, enum.Enum):
    VANILLA = "VANILLA"
    SNAPSHOT = "SNAPSHOT"
    PAPER = "PAPER"
    PURPUR = "PURPUR"
    SPIGOT = "SPIGOT"
    FORGE = "FORGE"
    NEOFORGE = "NEOFORGE"
    FABRIC = "FABRIC"
    QUILT = "QUILT"
    ARCLIGHT = "ARCLIGHT"
    MODPACK = "MODPACK"
    BEDROCK = "BEDROCK"
    POCKETMINE = "POCKETMINE"


class InvoiceStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    CANCELED = "CANCELED"


class ModSource(str, enum.Enum):
    MODRINTH = "MODRINTH"
    CURSEFORGE = "CURSEFORGE"
    CUSTOM = "CUSTOM"


class AclRole(str, enum.Enum):
    OWNER = "OWNER"
    OPERATOR = "OPERATOR"
    START_CONSOLE = "START_CONSOLE"
    BACKUPS = "BACKUPS"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64))
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    banned_reason: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    servers: Mapped[list["Server"]] = relationship(back_populates="user")


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    cpu_cores: Mapped[Decimal] = mapped_column(Numeric(3, 1), nullable=False)
    ram_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    disk_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    price_monthly: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    subdomain: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    container_id: Mapped[str | None] = mapped_column(String(128))
    server_type: Mapped[ServerType] = mapped_column(
        Enum(ServerType, name="server_type", native_enum=False),
        default=ServerType.PAPER,
        nullable=False,
    )
    game_version: Mapped[str] = mapped_column(String(32), default="1.20.4", nullable=False)
    status: Mapped[ServerStatus] = mapped_column(
        Enum(ServerStatus, name="server_status", native_enum=False),
        default=ServerStatus.PROVISIONING,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    dns_record_id: Mapped[str | None] = mapped_column(String(64))
    renewal_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    edition: Mapped[str] = mapped_column(String(16), default="JAVA", nullable=False)
    loader_version: Mapped[str | None] = mapped_column(String(32))
    max_players: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    gamemode: Mapped[str] = mapped_column(String(16), default="survival", nullable=False)
    difficulty: Mapped[str] = mapped_column(String(16), default="normal", nullable=False)
    online_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    players_online: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    backup_on_stop: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    backup_keep: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    restart_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[User] = relationship(back_populates="servers")
    plan: Mapped[Plan] = relationship()
    mods: Mapped[list["InstalledMod"]] = relationship(back_populates="server")
    acl: Mapped[list["ServerAcl"]] = relationship(back_populates="server")
    backups: Mapped[list["Backup"]] = relationship(back_populates="server")


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    server_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("servers.id", ondelete="SET NULL")
    )
    yookassa_payment_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status", native_enum=False),
        default=InvoiceStatus.PENDING,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), default="CREATE", nullable=False)


class InstalledMod(Base):
    __tablename__ = "installed_mods"
    __table_args__ = (UniqueConstraint("server_id", "source", "external_id", name="uq_server_mod"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[ModSource] = mapped_column(
        Enum(ModSource, name="mod_source", native_enum=False), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    file_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    addon_type: Mapped[str] = mapped_column(String(32), default="mod", nullable=False)
    install_error: Mapped[str | None] = mapped_column(String(512))

    server: Mapped[Server] = relationship(back_populates="mods")


class ServerAcl(Base):
    __tablename__ = "server_acl"
    __table_args__ = (UniqueConstraint("server_id", "telegram_id", name="uq_acl"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False
    )
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64))
    role: Mapped[AclRole] = mapped_column(
        Enum(AclRole, name="acl_role", native_enum=False),
        default=AclRole.START_CONSOLE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    server: Mapped[Server] = relationship(back_populates="acl")


class Backup(Base):
    __tablename__ = "backups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False
    )
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    server: Mapped[Server] = relationship(back_populates="backups")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str | None] = mapped_column(String(128))
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class HiddenAddon(Base):
    __tablename__ = "hidden_addons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(256))
