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


# --- Combo odds schemas ---


class ComboOddsRequest(BaseModel):
    bet_type: str
    selections: list[int]


class ComboOddsResponse(BaseModel):
    race_id: str
    bet_type: str
    selections: list[int]
    odds: float | None = None


class OddsComboEntry(BaseModel):
    combo: str  # netkeiba key, e.g. "01-02-03"
    odds: float | None = None
    odds_low: float | None = None
    odds_high: float | None = None
    favorite: int | None = None


class OddsTableResponse(BaseModel):
    """Full odds table for a single bet type (all combinations)."""

    race_id: str
    bet_type: str
    status: str | None = None  # result | middle | yoso
    official_datetime: str | None = None
    combos: list[OddsComboEntry] = []


# --- Past performance (馬柱) schemas ---


class PastRaceRecord(BaseModel):
    """A single past race for a horse (one column of the 馬柱)."""

    race_id: str
    race_date: datetime.date
    racecourse_name: str | None = None
    race_number: int | None = None
    race_name: str | None = None
    graded_race: str | None = None
    surface: str | None = None
    distance_m: int | None = None
    track_condition: str | None = None
    field_size: int | None = None  # 頭数
    bracket_number: int | None = None
    post_position: int | None = None
    finish_position: int | None = None
    finish_note: str | None = None
    total_time_tenths: int | None = None
    last_3f_time: Decimal | None = None
    margin: str | None = None
    corner_passing: str | None = None  # 通過順 "5-5-3-2"
    win_odds: Decimal | None = None
    win_favorite: int | None = None
    weight_carried_kg: Decimal | None = None
    horse_weight_kg: int | None = None
    horse_weight_diff: int | None = None
    jockey_name: str | None = None


class HorsePastPerformances(BaseModel):
    horse_id: uuid.UUID
    post_position: int | None = None
    records: list[PastRaceRecord] = []


class PastPerformancesResponse(BaseModel):
    race_id: str
    horses: list[HorsePastPerformances] = []


# --- Pedigree (血統) schemas ---


class HorsePedigree(BaseModel):
    horse_id: uuid.UUID
    post_position: int | None = None
    sire: str | None = None  # 父
    dam: str | None = None  # 母
    broodmare_sire: str | None = None  # 母父
    paternal_grandsire: str | None = None  # 父父


class RacePedigreeResponse(BaseModel):
    race_id: str
    horses: list[HorsePedigree] = []


# --- Confirmed (JV-Data) odds & payouts schemas ---


class ConfirmedWinOdds(BaseModel):
    umaban: int  # 馬番
    win_odds: float | None = None  # 確定単勝オッズ
    win_favorite: int | None = None  # 確定単勝人気


class ConfirmedPayouts(BaseModel):
    runners: int | None = None
    tan_umaban: str | None = None
    tan_pay: int | None = None
    tan_ninki: int | None = None
    fuku_umaban: str | None = None
    fuku_pay: int | None = None
    fuku_ninki: int | None = None
    umaren_kumi: str | None = None
    umaren_pay: int | None = None
    wide_kumi: str | None = None
    wide_pay: int | None = None
    umatan_kumi: str | None = None
    umatan_pay: int | None = None
    sanrenfuku_kumi: str | None = None
    sanrenfuku_pay: int | None = None
    sanrentan_kumi: str | None = None
    sanrentan_pay: int | None = None


class ConfirmedDataResponse(BaseModel):
    race_id: str
    win_odds: list[ConfirmedWinOdds] = []  # 確定単勝オッズ（馬番順）
    payouts: ConfirmedPayouts | None = None  # 確定払戻（無ければnull）


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
