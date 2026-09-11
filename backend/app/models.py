import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ServerStatus(str, enum.Enum):
    PROVISIONING = "PROVISIONING"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"


class ServerType(str, enum.Enum):
    VANILLA = "VANILLA"
    PAPER = "PAPER"
    PURPUR = "PURPUR"
    FABRIC = "FABRIC"
    FORGE = "FORGE"
    NEOFORGE = "NEOFORGE"


class InvoiceStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    CANCELED = "CANCELED"


class ModSource(str, enum.Enum):
    MODRINTH = "MODRINTH"
    CURSEFORGE = "CURSEFORGE"
    CUSTOM = "CUSTOM"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64))
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

    user: Mapped[User] = relationship(back_populates="servers")
    plan: Mapped[Plan] = relationship()
    mods: Mapped[list["InstalledMod"]] = relationship(back_populates="server")


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

    server: Mapped[Server] = relationship(back_populates="mods")
