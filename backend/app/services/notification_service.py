"""LINE notification service stub.

Full implementation deferred to Step C.
"""


class NotificationService:
    """LINE Messaging API integration (stub)."""

    def __init__(self, channel_secret: str = "", channel_access_token: str = ""):
        self.channel_secret = channel_secret
        self.channel_access_token = channel_access_token
        self._configured = bool(channel_secret and channel_access_token)

    @property
    def is_configured(self) -> bool:
        return self._configured

    async def send_text(self, user_id: str, message: str) -> bool:
        """Send a text message to a LINE user. (stub)"""
        if not self._configured:
            return False
        # TODO: Implement with LINE Messaging API in Step C
        return False

    async def send_race_notification(
        self, user_id: str, race_name: str, predictions_summary: str
    ) -> bool:
        """Send race prediction notification. (stub)"""
        return await self.send_text(
            user_id,
            f"【K-Bar AI】{race_name}\n{predictions_summary}",
        )
