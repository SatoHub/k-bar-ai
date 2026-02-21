import datetime

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Race


async def get_calendar(
    session: AsyncSession,
    year: int,
    month: int,
) -> list[dict]:
    """Get race counts per day for a given year-month."""
    query = (
        select(Race.race_date, func.count(Race.id).label("race_count"))
        .where(
            extract("year", Race.race_date) == year,
            extract("month", Race.race_date) == month,
        )
        .group_by(Race.race_date)
        .order_by(Race.race_date)
    )
    result = await session.execute(query)
    return [
        {"date": row.race_date, "race_count": row.race_count} for row in result.all()
    ]


def compute_week_date_range(
    year: int, month: int, week: int
) -> tuple[datetime.date, datetime.date]:
    """Compute start/end dates for week N (1-5) of a given month."""
    first_day = datetime.date(year, month, 1)
    start = first_day + datetime.timedelta(days=(week - 1) * 7)
    end = start + datetime.timedelta(days=6)
    # Clamp to month boundaries
    if month == 12:
        last_day = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        last_day = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
    if end > last_day:
        end = last_day
    return start, end
