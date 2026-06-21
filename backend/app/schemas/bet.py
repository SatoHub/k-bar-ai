import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


# --- 予算指定の買い目提案 ---


class BetSuggestionRequest(BaseModel):
    budget: int  # 予算(円)
    alloc_mode: str = "gami_avoid"  # gami_avoid | odds_weighted | flat
    bet_types: list[str] | None = None  # 券種手動指定(None=荒れ度でおまかせ)
    type_budgets: dict[str, int] | None = None  # 券種別予算


class BetSuggestionItem(BaseModel):
    bet_type: str
    method: str
    axis: list[int] | None = None
    horses: list[int] = []
    points: int
    dropped_points: int = 0
    stake_min: int
    stake_max: int
    cost: int
    hit_rate: float
    ev_ratio: float
    payout_min: int
    payout_max: int
    gami_free: bool
    odds_estimated: bool
    rationale: str
    recommended: bool


class BetSuggestionResponse(BaseModel):
    race_id: str
    race_name: str | None = None
    budget: int
    upset_level: str
    alloc_mode: str
    odds_live: bool
    total_allocated: int
    names: dict[str, str] = {}  # 馬番 -> 馬名
    suggestions: list[BetSuggestionItem] = []
    message: str | None = None


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
