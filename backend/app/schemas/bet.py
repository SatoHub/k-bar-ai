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


class RaceResultEntry(BaseModel):
    finish_position: int
    horse_name: str


class BetRaceInfo(BaseModel):
    race_number: int | None = None
    racecourse_name: str | None = None
    race_name: str | None = None
    race_id_str: str | None = None
    result_top3: list[RaceResultEntry] = []


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
    race_info: BetRaceInfo | None = None


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
