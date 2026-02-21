"""Notification API endpoints (stub).

Full implementation deferred to Step C.
"""

from fastapi import APIRouter

from app.config import settings
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/test")
async def test_notification():
    """Test endpoint to verify notification service configuration."""
    svc = NotificationService(
        channel_secret=settings.LINE_CHANNEL_SECRET,
        channel_access_token=settings.LINE_CHANNEL_ACCESS_TOKEN,
    )
    return {
        "configured": svc.is_configured,
        "message": "LINE通知は Step C で実装予定です"
        if not svc.is_configured
        else "LINE設定が検出されました",
    }
