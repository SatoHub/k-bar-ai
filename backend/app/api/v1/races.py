import datetime
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.race import (
    AptitudeResponse,
    ComboOddsRequest,
    ComboOddsResponse,
    OddsHistoryResponse,
    OddsResponse,
    RaceDetail,
    RaceListResponse,
)
from app.services.horse_service import get_course_aptitude_bulk
from app.services.race_service import (
    get_latest_odds,
    get_odds_history,
    get_race_detail,
    get_races,
)

router = APIRouter(prefix="/races", tags=["races"])


@router.get("", response_model=RaceListResponse)
async def list_races(
    date: datetime.date | None = Query(
        None, description="Filter by race date (YYYY-MM-DD)"
    ),
    year_month: str | None = Query(None, description="Filter by year-month (YYYY-MM)"),
    week: int | None = Query(None, ge=1, le=5, description="Week of month (1-5)"),
    racecourse: str | None = Query(None, description="Filter by racecourse name"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    session: AsyncSession = Depends(get_session),
):
    ym_year: int | None = None
    ym_month: int | None = None
    if year_month:
        m = re.match(r"^(\d{4})-(\d{2})$", year_month)
        if not m:
            raise HTTPException(status_code=400, detail="year_month must be YYYY-MM")
        ym_year, ym_month = int(m.group(1)), int(m.group(2))
        if not (1 <= ym_month <= 12):
            raise HTTPException(
                status_code=400, detail="month must be between 01 and 12"
            )

    items, total = await get_races(
        session,
        date=date,
        year_month=(ym_year, ym_month) if ym_year and ym_month else None,
        week=week,
        racecourse=racecourse,
        page=page,
        per_page=per_page,
    )
    return RaceListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/{race_id}", response_model=RaceDetail)
async def get_race(race_id: str, session: AsyncSession = Depends(get_session)):
    race = await get_race_detail(session, race_id)
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")
    return race


@router.get("/{race_id}/odds", response_model=OddsResponse)
async def get_odds(race_id: str, session: AsyncSession = Depends(get_session)):
    result = await get_latest_odds(session, race_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return result


@router.post("/{race_id}/odds/refresh", response_model=OddsResponse)
async def refresh_odds(race_id: str, session: AsyncSession = Depends(get_session)):
    # For now, just return latest odds (scraper integration later)
    result = await get_latest_odds(session, race_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return result


@router.get("/{race_id}/odds/history", response_model=OddsHistoryResponse)
async def get_odds_hist(race_id: str, session: AsyncSession = Depends(get_session)):
    result = await get_odds_history(session, race_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return result


@router.post("/{race_id}/odds/combo", response_model=ComboOddsResponse)
async def get_combo_odds(
    race_id: str,
    body: ComboOddsRequest,
    session: AsyncSession = Depends(get_session),
):
    """Fetch real-time odds for a specific bet type and horse combination."""
    from app.scraper.parsers.odds import NETKEIBA_ODDS_TYPE_MAP

    if body.bet_type not in NETKEIBA_ODDS_TYPE_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown bet_type: {body.bet_type}")
    if not body.selections:
        raise HTTPException(status_code=400, detail="selections must not be empty")

    # Resolve race_id string to DB race_id for validation
    from app.models import Race
    from sqlalchemy import select

    result = await session.execute(select(Race).where(Race.race_id == race_id))
    race = result.scalar_one_or_none()
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")

    # Fetch odds from netkeiba (lightweight: uses browser JSON fetch, no full page)
    from app.scraper.netkeiba import NetkeibaScraper

    try:
        async with NetkeibaScraper(headless=True) as nk:
            odds = await nk.scrape_combo_odds(race_id, body.bet_type, body.selections)
    except Exception:
        odds = None

    return ComboOddsResponse(
        race_id=race_id,
        bet_type=body.bet_type,
        selections=body.selections,
        odds=odds,
    )


@router.get("/{race_id}/aptitude", response_model=AptitudeResponse)
async def get_aptitude(race_id: str, session: AsyncSession = Depends(get_session)):
    race = await get_race_detail(session, race_id)
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")
    entries = await get_course_aptitude_bulk(
        session, race.id, race.surface, race.distance_m
    )
    return AptitudeResponse(race_id=race_id, entries=entries)
