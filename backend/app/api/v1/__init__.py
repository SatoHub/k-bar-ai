from fastapi import APIRouter

from app.api.v1.bets import router as bets_router
from app.api.v1.calendar import router as calendar_router
from app.api.v1.data_status import router as data_status_router
from app.api.v1.health import router as health_router
from app.api.v1.horses import router as horses_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.predictions import router as predictions_router
from app.api.v1.races import router as races_router
from app.api.v1.results import router as results_router
from app.api.v1.scheduler import router as scheduler_router

router = APIRouter(prefix="/api/v1")
router.include_router(health_router)
router.include_router(calendar_router)
router.include_router(races_router)
router.include_router(horses_router)
router.include_router(bets_router)
router.include_router(notifications_router)
router.include_router(data_status_router)
router.include_router(predictions_router)
router.include_router(results_router)
router.include_router(scheduler_router)
