import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.race import RaceDetail, RaceListResponse
from app.services.race_service import get_race_detail, get_races

router = APIRouter(prefix="/races", tags=["races"])


@router.get("", response_model=RaceListResponse)
async def list_races(
    date: datetime.date | None = Query(
        None, description="Filter by race date (YYYY-MM-DD)"
    ),
    racecourse: str | None = Query(None, description="Filter by racecourse name"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    session: AsyncSession = Depends(get_session),
):
    items, total = await get_races(
        session, date=date, racecourse=racecourse, page=page, per_page=per_page
    )
    return RaceListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/{race_id}", response_model=RaceDetail)
async def get_race(race_id: str, session: AsyncSession = Depends(get_session)):
    race = await get_race_detail(session, race_id)
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")
    return race
