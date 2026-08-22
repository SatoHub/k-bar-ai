"""LINE Messaging API notification service.

Sends push notifications via LINE and logs all activity to the DB.
"""

from __future__ import annotations

import logging
from typing import Any

from linebot.v3.messaging import (
    AsyncApiClient,
    AsyncMessagingApi,
    Configuration,
    FlexContainer,
    FlexMessage,
    PushMessageRequest,
    TextMessage,
)

from app.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """LINE Messaging API integration."""

    def __init__(
        self,
        channel_secret: str = "",
        channel_access_token: str = "",
        user_id: str = "",
    ):
        self.channel_secret = channel_secret
        self.channel_access_token = channel_access_token
        self.user_id = user_id
        self._configured = bool(channel_secret and channel_access_token and user_id)

    @property
    def is_configured(self) -> bool:
        return self._configured

    # ------------------------------------------------------------------
    # Low-level send helpers
    # ------------------------------------------------------------------

    async def push_text(self, text: str) -> bool:
        """Send a plain text message to the configured user."""
        if not self._configured:
            logger.debug("LINE not configured, skipping push_text")
            return False

        try:
            config = Configuration(access_token=self.channel_access_token)
            async with AsyncApiClient(config) as api_client:
                api = AsyncMessagingApi(api_client)
                await api.push_message(
                    PushMessageRequest(
                        to=self.user_id,
                        messages=[TextMessage(text=text)],
                    )
                )
            await self._log(
                "outgoing", "text", "general", "success", {"text": text[:200]}
            )
            return True
        except Exception as e:
            logger.error("push_text failed: %s", e, exc_info=True)
            await self._log("outgoing", "text", "general", "error", error=str(e))
            return False

    async def push_flex(
        self, alt_text: str, flex_dict: dict, category: str = "general"
    ) -> bool:
        """Send a Flex Message to the configured user."""
        if not self._configured:
            logger.debug("LINE not configured, skipping push_flex")
            return False

        try:
            container = FlexContainer.from_dict(flex_dict)
            config = Configuration(access_token=self.channel_access_token)
            async with AsyncApiClient(config) as api_client:
                api = AsyncMessagingApi(api_client)
                await api.push_message(
                    PushMessageRequest(
                        to=self.user_id,
                        messages=[FlexMessage(alt_text=alt_text, contents=container)],
                    )
                )
            await self._log(
                "outgoing", "flex", category, "success", {"alt_text": alt_text}
            )
            return True
        except Exception as e:
            logger.error("push_flex failed: %s", e, exc_info=True)
            await self._log("outgoing", "flex", category, "error", error=str(e))
            return False

    # ------------------------------------------------------------------
    # High-level notification methods
    # ------------------------------------------------------------------

    async def push_prediction_notification(self, predictions: list[dict]) -> bool:
        """Send tomorrow's AI prediction summary."""
        from app.services.line_templates import build_prediction_flex

        if not predictions:
            logger.info("No predictions to notify")
            return False

        flex_dict = build_prediction_flex(predictions)
        return await self.push_flex("明日のAI予想", flex_dict, category="prediction")

    async def push_results_notification(self, results: list[dict]) -> bool:
        """Send today's race results summary."""
        from app.services.line_templates import build_results_flex

        if not results:
            logger.info("No results to notify")
            return False

        flex_dict = build_results_flex(results)
        return await self.push_flex("本日のレース結果", flex_dict, category="results")

    async def push_weekly_report(self, report: dict) -> bool:
        """Send weekly performance report."""
        from app.services.line_templates import build_weekly_report_flex

        flex_dict = build_weekly_report_flex(report)
        return await self.push_flex("週次レポート", flex_dict, category="weekly")

    async def push_miss_summary(self, misses: list[dict]) -> bool:
        """Send a summary of today's AI misses (informational, no buttons).

        Each item: {race_name, race_id, ai_top3, actual_top3, auto_reason}
        """
        from app.services.line_templates import build_miss_summary_flex

        if not misses:
            logger.info("No misses to notify")
            return False

        flex_dict = build_miss_summary_flex(misses)
        return await self.push_flex(
            f"本日のAIハズレまとめ ({len(misses)}件)",
            flex_dict,
            category="miss_summary",
        )

    async def push_monthly_proposal(self, proposals: list[dict]) -> bool:
        """Send monthly improvement proposals via Flex Message."""
        from app.services.line_templates import build_monthly_proposal_flex

        if not proposals:
            logger.info("No monthly proposals to notify")
            return False

        import datetime

        today = datetime.date.today()
        last_month = today.replace(day=1) - datetime.timedelta(days=1)
        month_str = f"{last_month.year}年{last_month.month}月"

        flex_dict = build_monthly_proposal_flex(month_str, proposals)
        return await self.push_flex(
            "月次改善提案", flex_dict, category="monthly_proposal"
        )

    async def push_test_message(self) -> bool:
        """Send a test message to verify configuration."""
        text = "K-Bar AI LINE通知テスト\n設定が正常に動作しています。"
        if not self._configured:
            return False

        try:
            config = Configuration(access_token=self.channel_access_token)
            async with AsyncApiClient(config) as api_client:
                api = AsyncMessagingApi(api_client)
                await api.push_message(
                    PushMessageRequest(
                        to=self.user_id,
                        messages=[TextMessage(text=text)],
                    )
                )
            await self._log("outgoing", "text", "test", "success", {"text": text})
            return True
        except Exception as e:
            logger.error("push_test_message failed: %s", e, exc_info=True)
            await self._log("outgoing", "text", "test", "error", error=str(e))
            return False

    # ------------------------------------------------------------------
    # Logging helper
    # ------------------------------------------------------------------

    async def _log(
        self,
        direction: str,
        message_type: str,
        category: str,
        status: str,
        payload: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Record a notification event to the DB."""
        try:
            from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
            from app.models.notification_log import NotificationLog

            engine = create_async_engine(settings.database_url)
            async with AsyncSession(engine) as session:
                log = NotificationLog(
                    direction=direction,
                    message_type=message_type,
                    category=category,
                    status=status,
                    payload=payload,
                    error_detail=error,
                )
                session.add(log)
                await session.commit()
            await engine.dispose()
        except Exception as e:
            logger.warning("Failed to write notification log: %s", e)


def get_notification_service() -> NotificationService:
    """Factory that creates a NotificationService from app settings."""
    return NotificationService(
        channel_secret=settings.LINE_CHANNEL_SECRET,
        channel_access_token=settings.LINE_CHANNEL_ACCESS_TOKEN,
        user_id=settings.LINE_USER_ID,
    )
