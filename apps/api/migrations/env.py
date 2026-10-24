import asyncio

import loom_api.chat.models  # noqa: F401  (registers tables on Base.metadata)
from alembic import context
from loom_api.config import settings
from loom_api.db import Base
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

target_metadata = Base.metadata


def _url() -> str:
    # Tests pass their own URL through config.attributes; everything else uses LOOM_DATABASE_URL.
    url = context.config.attributes.get("url")
    return url if isinstance(url, str) else settings.database_url


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_online() -> None:
    engine = create_async_engine(_url())
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(_run_online())
