import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class NotificationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    direction: str
    message_type: str
    category: str
    status: str
    payload: dict | None = None
    error_detail: str | None = None
    created_at: datetime.datetime


class NotificationLogListResponse(BaseModel):
    items: list[NotificationLogResponse]
    total: int
    page: int
    per_page: int


class NotificationTestResponse(BaseModel):
    configured: bool
    sent: bool
    message: str
