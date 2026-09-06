from collections.abc import AsyncIterator

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


async def init_db() -> None:
    from sqlalchemy import select

    from app.models import Plan

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        existing = (await session.execute(select(Plan))).scalars().first()
        if existing is None:
            session.add_all(
                [
                    Plan(id="starter", name="Starter", cpu_cores=1, ram_mb=2048, disk_mb=10240, price_monthly=199),
                    Plan(id="plus", name="Plus", cpu_cores=2, ram_mb=4096, disk_mb=20480, price_monthly=399),
                    Plan(id="pro", name="Pro", cpu_cores=2, ram_mb=6144, disk_mb=40960, price_monthly=699),
                ]
            )
            await session.commit()
