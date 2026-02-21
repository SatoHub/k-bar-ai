import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class BetRecordCreate(BaseModel):
    race_id: uuid.UUID | None = None
    bet_date: datetime.date
    bet_type: str
    horse_names: str
    amount_yen: int
    odds_at_bet: Decimal | None = None
    note: str | None = None


class BetRecordUpdate(BaseModel):
    actual_payout: int | None = None
    is_hit: bool | None = None
    note: str | None = None


class BetRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    race_id: uuid.UUID | None = None
    bet_date: datetime.date
    bet_type: str
    horse_names: str
    amount_yen: int
    odds_at_bet: Decimal | None = None
    actual_payout: int | None = None
    is_hit: bool | None = None
    note: str | None = None
    created_at: datetime.datetime


class BetListResponse(BaseModel):
    items: list[BetRecordResponse]
    total: int
    page: int
    per_page: int


class BetSummaryResponse(BaseModel):
    total_bets: int
    total_amount: int
    total_payout: int
    recovery_rate: float
    hit_count: int
    hit_rate: float
