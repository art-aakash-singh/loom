from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from loom_api.chat import router as chat
from loom_api.chat.schemas import ConcreteGenerationSettings
from loom_api.config import settings
from loom_api.deps import build_provider
from loom_api.routers import health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.provider = build_provider(settings)
    app.state.generation_settings = ConcreteGenerationSettings(
        model=settings.llm_model, max_tokens=settings.llm_max_tokens
    )
    yield


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
