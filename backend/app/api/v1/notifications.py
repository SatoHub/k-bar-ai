"""Notification API endpoints — LINE Webhook, test, logs."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, Request, HTTPException

from app.config import settings
from app.schemas.notification import (
    NotificationLogListResponse,
    NotificationLogResponse,
    NotificationTestResponse,
)
from app.services.notification_service import get_notification_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ------------------------------------------------------------------
# POST /webhook — LINE Webhook receiver
# ------------------------------------------------------------------


@router.post("/webhook")
async def line_webhook(request: Request):
    """Receive LINE Webhook events (signature-verified)."""
    from linebot.v3.webhooks import MessageEvent, PostbackEvent, FollowEvent
    from linebot.v3.webhook import WebhookParser, InvalidSignatureError

    body = (await request.body()).decode("utf-8")
    signature = request.headers.get("X-Line-Signature", "")

    if not settings.LINE_CHANNEL_SECRET:
        raise HTTPException(status_code=503, detail="LINE not configured")

    parser = WebhookParser(settings.LINE_CHANNEL_SECRET)

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    svc = get_notification_service()

    for event in events:
        if isinstance(event, FollowEvent):
            logger.info("LINE FollowEvent: user_id=%s", event.source.user_id)
            # Log the follow for reference
            await svc._log(
                "incoming", "text", "webhook", "success",
                {"event": "follow", "user_id": event.source.user_id},
            )

        elif isinstance(event, PostbackEvent):
            data = event.postback.data
            logger.info("LINE PostbackEvent: data=%s", data)
            await svc._log(
                "incoming", "text", "webhook", "success",
                {"event": "postback", "data": data},
            )

        elif isinstance(event, MessageEvent):
            logger.info("LINE MessageEvent received")
            await svc._log(
                "incoming", "text", "webhook", "success",
                {"event": "message"},
            )

    return {"status": "ok"}


# ------------------------------------------------------------------
# POST /test — send a test notification
# ------------------------------------------------------------------


@router.post("/test", response_model=NotificationTestResponse)
async def test_notification():
    """Send a test notification to verify LINE configuration."""
    svc = get_notification_service()

    if not svc.is_configured:
        return NotificationTestResponse(
            configured=False,
            sent=False,
            message="LINE未設定です。.env に LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN, LINE_USER_ID を設定してください。",
        )

    sent = await svc.push_test_message()
    return NotificationTestResponse(
        configured=True,
        sent=sent,
        message="テスト通知を送信しました。" if sent else "送信に失敗しました。ログを確認してください。",
    )


# ------------------------------------------------------------------
# GET /logs — notification log list
# ------------------------------------------------------------------


@router.get("/logs", response_model=NotificationLogListResponse)
async def list_notification_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    category: str | None = Query(None),
):
    """List notification logs with pagination."""
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

    from app.models.notification_log import NotificationLog

    engine = create_async_engine(settings.database_url)
    async with AsyncSession(engine) as session:
        # Build query
        base_q = select(NotificationLog)
        count_q = select(func.count(NotificationLog.id))

        if category:
            base_q = base_q.where(NotificationLog.category == category)
            count_q = count_q.where(NotificationLog.category == category)

        # Total count
        total = (await session.execute(count_q)).scalar() or 0

        # Paginated results
        offset = (page - 1) * per_page
        rows = (
            await session.execute(
                base_q.order_by(NotificationLog.created_at.desc())
                .offset(offset)
                .limit(per_page)
            )
        ).scalars().all()

    await engine.dispose()

    return NotificationLogListResponse(
        items=[NotificationLogResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        per_page=per_page,
    )
