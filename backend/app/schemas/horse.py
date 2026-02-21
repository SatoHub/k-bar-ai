import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class HorseRaceRecord(BaseModel):
    race_id: str
    race_date: datetime.date
    racecourse_name: str | None = None
    race_name: str | None = None
    surface: str | None = None
    distance_m: int | None = None
    track_condition: str | None = None
    finish_position: int | None = None
    finish_note: str | None = None
    total_time_tenths: int | None = None
    win_odds: float | None = None
    jockey_name: str | None = None


class SurfaceStats(BaseModel):
    runs: int
    wins: int
    place: int


class HorseDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    sex: str | None = None
    netkeiba_id: str | None = None
    image_url: str | None = None
    total_runs: int
    wins: int
    place_count: int
    win_rate: float
    place_rate: float
    surface_stats: dict[str, SurfaceStats]
    records: list[HorseRaceRecord]
