from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

SessionFactory = async_sessionmaker[AsyncSession]


class Base(DeclarativeBase):
    pass


def create_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> SessionFactory:
    # expire_on_commit=False: repositories copy rows into plain records before the session closes.
    return async_sessionmaker(engine, expire_on_commit=False)
