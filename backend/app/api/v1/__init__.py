from fastapi import APIRouter

from app.api.v1.data_status import router as data_status_router
from app.api.v1.health import router as health_router
from app.api.v1.predictions import router as predictions_router
from app.api.v1.races import router as races_router

router = APIRouter(prefix="/api/v1")
router.include_router(health_router)
router.include_router(races_router)
router.include_router(data_status_router)
router.include_router(predictions_router)
