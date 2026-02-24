from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routes import router
from src.config.logging import configure_logging
from src.config.settings import get_settings
from src.models.session import init_db

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title='Intelligent Trade Reconciliation and Exception Management API',
    version='1.0.0',
    description='AI-powered platform for trade matching, break prediction, exception routing, and analytics.',
    lifespan=lifespan,
)


app.include_router(router)
