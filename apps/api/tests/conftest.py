import asyncio
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from loom_api.chat.lock import GenerationLock
from loom_api.chat.repository import ChatRepository
from loom_api.chat.schemas import ConcreteGenerationSettings
from loom_api.chat.service import ChatService
from loom_api.config import settings
from loom_api.db import create_session_factory
from loom_api.deps import get_chat_service
from loom_api.llm.base import LLMProvider
from loom_api.main import app
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

ALEMBIC_INI = Path(__file__).parents[1] / "alembic.ini"

UseProvider = Callable[[LLMProvider], ChatService]


async def _create_database_if_missing(url: str) -> None:
    target = make_url(url)
    admin = create_async_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            found = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": target.database}
            )
            if not found:
                await conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    finally:
        await admin.dispose()


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Build the test schema from scratch with the real migrations, once per run."""
    url = settings.test_database_url
    assert url != settings.database_url, "refusing to run destructive tests on the dev database"
    asyncio.run(_create_database_if_missing(url))
    config = Config(str(ALEMBIC_INI))
    config.attributes["url"] = url
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    return url


@pytest.fixture
async def engine(test_database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(test_database_url)
    # Truncate instead of rolling back a wrapping transaction: the chat flow commits the user
    # message in its own transaction on purpose, and a rollback fixture would hide that.
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE conversations, messages"))
    yield engine
    await engine.dispose()


@pytest.fixture
async def redis() -> AsyncIterator[Redis]:
    assert settings.test_redis_url != settings.redis_url, "refusing to flush the dev Redis"
    client = Redis.from_url(settings.test_redis_url)
    await client.flushdb()
    yield client
    await client.aclose()


@pytest.fixture
def repo(engine: AsyncEngine) -> ChatRepository:
    return ChatRepository(create_session_factory(engine))


@pytest.fixture
def lock(redis: Redis) -> GenerationLock:
    return GenerationLock(redis, ttl_s=settings.generation_lock_ttl_s)


@pytest.fixture
def use_provider(repo: ChatRepository, lock: GenerationLock) -> Iterator[UseProvider]:
    """Build a ChatService around `provider` and serve it from the app."""

    def _use(provider: LLMProvider) -> ChatService:
        service = ChatService(
            repo, lock, provider, ConcreteGenerationSettings(model="fake", max_tokens=100)
        )
        app.dependency_overrides[get_chat_service] = lambda: service
        return service

    yield _use
    app.dependency_overrides.clear()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
