from collections.abc import AsyncIterator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


def SessionLocal() -> AsyncSession:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _session_factory()


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def _add_columns(sync_conn) -> None:
    insp = inspect(sync_conn)
    wanted = {
        "users": {
            "is_banned": "BOOLEAN DEFAULT 0 NOT NULL",
            "banned_reason": "VARCHAR(256)",
        },
        "servers": {
            "edition": "VARCHAR(16) DEFAULT 'JAVA' NOT NULL",
            "loader_version": "VARCHAR(32)",
            "max_players": "INTEGER DEFAULT 10 NOT NULL",
            "gamemode": "VARCHAR(16) DEFAULT 'survival' NOT NULL",
            "difficulty": "VARCHAR(16) DEFAULT 'normal' NOT NULL",
            "online_mode": "BOOLEAN DEFAULT 0 NOT NULL",
            "settings": "JSON",
            "last_error": "TEXT",
            "players_online": "INTEGER DEFAULT 0 NOT NULL",
            "backup_on_stop": "BOOLEAN DEFAULT 1 NOT NULL",
            "backup_keep": "INTEGER DEFAULT 5 NOT NULL",
            "restart_required": "BOOLEAN DEFAULT 0 NOT NULL",
        },
        "installed_mods": {
            "enabled": "BOOLEAN DEFAULT 1 NOT NULL",
            "addon_type": "VARCHAR(32) DEFAULT 'mod' NOT NULL",
            "install_error": "VARCHAR(512)",
        },
    }
    tables = set(insp.get_table_names())
    for table, cols in wanted.items():
        if table not in tables:
            continue
        existing = {c["name"] for c in insp.get_columns(table)}
        for name, ddl in cols.items():
            if name not in existing:
                sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


async def init_db() -> None:
    from sqlalchemy import select

    from app.models import Plan

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_columns)
    async with SessionLocal() as session:
        existing = (await session.execute(select(Plan))).scalars().first()
        if existing is None:
            session.add_all(
                [
                    Plan(id="starter", name="Starter", cpu_cores=1, ram_mb=2048, disk_mb=10240, price_monthly=0),
                    Plan(id="plus", name="Plus", cpu_cores=2, ram_mb=4096, disk_mb=20480, price_monthly=399),
                    Plan(id="pro", name="Pro", cpu_cores=2, ram_mb=6144, disk_mb=40960, price_monthly=699),
                    Plan(id="unlimited", name="Unlimited", cpu_cores=4, ram_mb=8192, disk_mb=81920, price_monthly=0),
                ]
            )
            await session.commit()
        else:
            unlimited = await session.get(Plan, "unlimited")
            if unlimited is None:
                session.add(
                    Plan(id="unlimited", name="Unlimited", cpu_cores=4, ram_mb=8192, disk_mb=81920, price_monthly=0)
                )
                await session.commit()
