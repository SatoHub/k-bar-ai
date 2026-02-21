from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import router as v1_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if settings.SCHEDULER_ENABLED:
        from app.scheduler.scheduler import scheduler_manager

        await scheduler_manager.start()

    yield

    # Shutdown
    if settings.SCHEDULER_ENABLED:
        from app.scheduler.scheduler import scheduler_manager

        await scheduler_manager.shutdown()


app = FastAPI(
    title="K-Bar AI",
    description="競馬AI予想アプリ API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.ALLOWED_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)
