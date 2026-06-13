"""API endpoints for AI prediction results and hit-rate analysis."""

from __future__ import annotations

import datetime
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.services.results_service import (
    get_latest_result_date,
    get_race_results,
    get_racecourses_for_date,
    get_results_calendar,
    get_results_summary,
)

router = APIRouter(prefix="/results", tags=["results"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ResultTop3Entry(BaseModel):
    finish_position: int
    horse_name: str
    win_odds: float | None = None
    win_favorite: int | None = None


class PredictedTop3Entry(BaseModel):
    rank: int
    horse_name: str


class AIHitResult(BaseModel):
    predicted_top3: list[PredictedTop3Entry]
    tansho_hit: bool
    fukusho_hit: bool
    umaren_hit: bool
    umatan_hit: bool
    wide_hit: bool
    sanrenpuku_hit: bool
    sanrentan_hit: bool


class RaceResultItem(BaseModel):
    race_id_str: str
    race_date: str | None
    racecourse_name: str | None
    race_number: int | None
    race_name: str | None
    surface: str | None
    distance_m: int | None
    result_top3: list[ResultTop3Entry]
    ai_prediction: AIHitResult | None


class RaceResultsResponse(BaseModel):
    items: list[RaceResultItem]


class HitRateEntry(BaseModel):
    hits: int
    total: int
    rate: float


class AiRoiEntry(BaseModel):
    strategy: str
    races: int
    hits: int
    hit_rate: float
    invested: int
    returned: int
    roi: float


class ResultsSummaryResponse(BaseModel):
    total_races: int
    period: str
    hit_rates: dict[str, HitRateEntry]
    ai_roi: AiRoiEntry


class LatestDateResponse(BaseModel):
    latest_date: str | None


class CalendarDayEntry(BaseModel):
    date: str
    race_count: int


class ResultsCalendarResponse(BaseModel):
    days: list[CalendarDayEntry]


class RacecoursesResponse(BaseModel):
    racecourses: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_YM_RE = re.compile(r"^\d{4}-\d{2}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_year_month(ym: str) -> tuple[int, int]:
    if not _YM_RE.match(ym):
        raise HTTPException(status_code=400, detail="year_month must be YYYY-MM")
    year, month = ym.split("-")
    return int(year), int(month)


def _parse_date(ds: str) -> datetime.date:
    if not _DATE_RE.match(ds):
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    try:
        return datetime.date.fromisoformat(ds)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date: {ds}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/latest-date", response_model=LatestDateResponse)
async def latest_date(session: AsyncSession = Depends(get_session)):
    """Return the latest date with confirmed results."""
    d = await get_latest_result_date(session)
    return LatestDateResponse(latest_date=d)


@router.get("/calendar", response_model=ResultsCalendarResponse)
async def results_calendar(
    year_month: str = Query(..., description="YYYY-MM"),
    session: AsyncSession = Depends(get_session),
):
    """Return days with confirmed results in a month."""
    year, month = _parse_year_month(year_month)
    days = await get_results_calendar(session, year, month)
    return ResultsCalendarResponse(days=days)


@router.get("/racecourses", response_model=RacecoursesResponse)
async def racecourses(
    date: str = Query(..., description="YYYY-MM-DD"),
    session: AsyncSession = Depends(get_session),
):
    """Return racecourse names available on a given date."""
    d = _parse_date(date)
    names = await get_racecourses_for_date(session, d)
    return RacecoursesResponse(racecourses=names)


@router.get("", response_model=RaceResultsResponse)
async def list_results(
    date: str = Query(..., description="YYYY-MM-DD"),
    racecourse: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """List race results for a date with AI prediction hit analysis."""
    d = _parse_date(date)
    items = await get_race_results(session, date=d, racecourse=racecourse)
    return RaceResultsResponse(items=items)


@router.get("/summary", response_model=ResultsSummaryResponse)
async def results_summary(
    year_month: str | None = Query(None, description="YYYY-MM (optional, omit for all-time)"),
    racecourse: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Get AI hit rates per bet type."""
    year, month = None, None
    if year_month:
        year, month = _parse_year_month(year_month)
    data = await get_results_summary(session, year=year, month=month, racecourse=racecourse)
    return data
