import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.calendar import CalendarDay, CalendarResponse
from app.services.calendar_service import get_calendar

router = APIRouter(prefix="/races", tags=["races"])


@router.get("/calendar", response_model=CalendarResponse)
async def race_calendar(
    year_month: str = Query(
        ..., description="YYYY-MM format", pattern=r"^\d{4}-\d{2}$"
    ),
    session: AsyncSession = Depends(get_session),
):
    match = re.match(r"^(\d{4})-(\d{2})$", year_month)
    if not match:
        raise HTTPException(status_code=400, detail="year_month must be YYYY-MM")
    year, month = int(match.group(1)), int(match.group(2))
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Invalid month")

    days_raw = await get_calendar(session, year, month)
    days = [CalendarDay(**d) for d in days_raw]
    return CalendarResponse(year_month=year_month, days=days)
