import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Horse, Jockey, Race, RaceEntry, Trainer


async def get_data_status(session: AsyncSession) -> dict:
    """Get overall data statistics."""
    total_races = await session.scalar(select(func.count(Race.id)))
    total_entries = await session.scalar(select(func.count(RaceEntry.id)))
    total_horses = await session.scalar(select(func.count(Horse.id)))
    total_jockeys = await session.scalar(select(func.count(Jockey.id)))
    total_trainers = await session.scalar(select(func.count(Trainer.id)))
    date_min = await session.scalar(select(func.min(Race.race_date)))
    date_max = await session.scalar(select(func.max(Race.race_date)))

    result = await session.execute(
        select(Race.racecourse_name)
        .where(Race.racecourse_name.isnot(None))
        .distinct()
        .order_by(Race.racecourse_name)
    )
    racecourses = [row[0] for row in result.all()]

    return {
        "total_races": total_races or 0,
        "total_entries": total_entries or 0,
        "total_horses": total_horses or 0,
        "total_jockeys": total_jockeys or 0,
        "total_trainers": total_trainers or 0,
        "date_min": date_min,
        "date_max": date_max,
        "racecourses": racecourses,
    }


async def get_races(
    session: AsyncSession,
    date: datetime.date | None = None,
    racecourse: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Race], int]:
    """Get paginated race list with optional filters."""
    query = select(Race)
    count_query = select(func.count(Race.id))

    if date:
        query = query.where(Race.race_date == date)
        count_query = count_query.where(Race.race_date == date)
    if racecourse:
        query = query.where(Race.racecourse_name == racecourse)
        count_query = count_query.where(Race.racecourse_name == racecourse)

    total = await session.scalar(count_query)

    query = (
        query.order_by(Race.race_date.desc(), Race.race_number)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )

    result = await session.execute(query)
    return result.scalars().all(), total or 0


async def get_race_detail(session: AsyncSession, race_id: str) -> Race | None:
    """Get race with all entries eagerly loaded."""
    query = (
        select(Race)
        .where(Race.race_id == race_id)
        .options(
            selectinload(Race.entries).selectinload(RaceEntry.horse),
            selectinload(Race.entries).selectinload(RaceEntry.jockey),
            selectinload(Race.entries).selectinload(RaceEntry.trainer),
        )
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()
