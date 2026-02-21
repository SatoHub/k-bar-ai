import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class HorseBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    sex: str | None = None
    netkeiba_id: str | None = None


class JockeyBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str


class TrainerBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str


class RaceEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    bracket_number: int | None = None
    post_position: int | None = None
    horse_age: int | None = None
    weight_carried_kg: Decimal | None = None
    finish_position: int | None = None
    finish_note: str | None = None
    total_time_tenths: int | None = None
    margin: str | None = None
    corner_pos_1: str | None = None
    corner_pos_2: str | None = None
    corner_pos_3: str | None = None
    corner_pos_4: str | None = None
    last_3f_time: Decimal | None = None
    win_odds: Decimal | None = None
    win_favorite: int | None = None
    horse_weight_kg: int | None = None
    horse_weight_diff: int | None = None
    owner: str | None = None
    prize_money_10k_yen: Decimal | None = None
    horse: HorseBase
    jockey: JockeyBase | None = None
    trainer: TrainerBase | None = None


class RaceListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    race_id: str
    race_date: datetime.date
    racecourse_name: str | None = None
    race_number: int | None = None
    race_name: str | None = None
    post_time: datetime.time | None = None
    surface: str | None = None
    distance_m: int | None = None
    weather: str | None = None
    track_condition: str | None = None
    graded_race: str | None = None
    head_count: int | None = None
    stub_only: bool = False


class RaceDetail(RaceListItem):
    racecourse_code: str | None = None
    direction: str | None = None
    race_symbols: dict | None = None
    entries: list[RaceEntryResponse] = []


class RaceListResponse(BaseModel):
    items: list[RaceListItem]
    total: int
    page: int
    per_page: int


class DataStatusResponse(BaseModel):
    total_races: int
    total_entries: int
    total_horses: int
    total_jockeys: int
    total_trainers: int
    date_min: datetime.date | None = None
    date_max: datetime.date | None = None
    racecourses: list[str] = []


# --- Odds schemas ---


class OddsEntry(BaseModel):
    post_position: int
    horse_name: str | None = None
    win_odds: float | None = None
    win_favorite: int | None = None
    fetched_at: str | None = None


class OddsResponse(BaseModel):
    race_id: str
    entries: list[OddsEntry] = []
    fetched_at: str | None = None


class OddsHistoryPoint(BaseModel):
    post_position: int
    horse_name: str | None = None
    win_odds: float
    fetched_at: str | None = None


class OddsHistoryResponse(BaseModel):
    race_id: str
    history: list[OddsHistoryPoint] = []


# --- Aptitude schemas ---


class AptitudeEntry(BaseModel):
    horse_id: uuid.UUID
    runs: int
    wins: int
    place_count: int
    score: int


class AptitudeResponse(BaseModel):
    race_id: str
    entries: list[AptitudeEntry] = []
