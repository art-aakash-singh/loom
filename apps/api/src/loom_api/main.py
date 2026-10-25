from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from loom_api.chat import router as chat
from loom_api.chat.lock import GenerationLock
from loom_api.chat.repository import ChatRepository
from loom_api.chat.service import ChatService
from loom_api.config import settings
from loom_api.context.types import GenerationSettings
from loom_api.db import create_engine, create_session_factory
from loom_api.deps import build_provider
from loom_api.routers import health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = create_engine(settings.database_url)
    redis = Redis.from_url(settings.redis_url)
    chat_service = ChatService(
        repo=ChatRepository(create_session_factory(engine)),
        lock=GenerationLock(redis, ttl_s=settings.generation_lock_ttl_s),
        provider=build_provider(settings),
        settings=GenerationSettings(
            model=settings.llm_model,
            max_output_tokens=settings.llm_max_tokens,
            context_window=settings.context_window,
        ),
    )
    await chat_service.sweep_interrupted_generations()
    app.state.chat_service = chat_service
    try:
        yield
    finally:
        await redis.aclose()
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="Loom API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(chat.router)
    return app


app = create_app()
