import datetime

from sqlalchemy import case, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Race


async def get_calendar(
    session: AsyncSession,
    year: int,
    month: int,
) -> list[dict]:
    """Get race counts per day for a given year-month.

    Returns list of dicts with date, race_count, and has_entries.
    has_entries is True if at least one race on that day has stub_only=False.
    """
    query = (
        select(
            Race.race_date,
            func.count(Race.id).label("race_count"),
            func.count(
                case((Race.stub_only == False, Race.id))  # noqa: E712
            ).label("entries_count"),
        )
        .where(
            extract("year", Race.race_date) == year,
            extract("month", Race.race_date) == month,
        )
        .group_by(Race.race_date)
        .order_by(Race.race_date)
    )
    result = await session.execute(query)
    return [
        {
            "date": row.race_date,
            "race_count": row.race_count,
            "has_entries": (row.entries_count or 0) > 0,
        }
        for row in result.all()
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
