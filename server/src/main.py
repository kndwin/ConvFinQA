from contextlib import asynccontextmanager

from dishka import make_async_container
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI
from scalar_fastapi import get_scalar_api_reference

from src.module.chat_sessions.chat_sessions_router import router as chat_sessions_router
from src.module.dataset_conversations.dataset_conversations_router import (
    router as dataset_conversations_router,
)
from src.platform.database import database_lifespan, engine
from src.platform.dependency_injection import ApplicationProvider
from src.platform.observability import configure_observability, observability_lifespan


def create_app() -> FastAPI:
    container = make_async_container(ApplicationProvider())

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        async with database_lifespan(), observability_lifespan(), container:
            yield

    app = FastAPI(
        title="OpenAI Deploy API",
        description="API for exploring ConvFinQA dataset conversations.",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    configure_observability(app, engine)

    @app.get("/docs", include_in_schema=False)
    async def scalar_docs():
        return get_scalar_api_reference(
            openapi_url=app.openapi_url,
            title=app.title,
        )

    app.include_router(dataset_conversations_router)
    app.include_router(chat_sessions_router)
    setup_dishka(container, app)
    return app


app = create_app()
