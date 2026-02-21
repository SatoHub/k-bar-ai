import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Horse, Jockey, OddsSnapshot, Race, RaceEntry, Trainer


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
    year_month: tuple[int, int] | None = None,
    week: int | None = None,
    racecourse: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Race], int]:
    """Get paginated race list with optional filters."""
    from app.services.calendar_service import compute_week_date_range

    query = select(Race)
    count_query = select(func.count(Race.id))

    if date:
        query = query.where(Race.race_date == date)
        count_query = count_query.where(Race.race_date == date)
    elif year_month:
        year, month = year_month
        query = query.where(
            func.extract("year", Race.race_date) == year,
            func.extract("month", Race.race_date) == month,
        )
        count_query = count_query.where(
            func.extract("year", Race.race_date) == year,
            func.extract("month", Race.race_date) == month,
        )
        if week:
            start, end = compute_week_date_range(year, month, week)
            query = query.where(Race.race_date >= start, Race.race_date <= end)
            count_query = count_query.where(
                Race.race_date >= start, Race.race_date <= end
            )

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


async def get_latest_odds(session: AsyncSession, race_id_str: str) -> dict | None:
    """Get the latest odds snapshot for a race."""
    result = await session.execute(select(Race).where(Race.race_id == race_id_str))
    race = result.scalar_one_or_none()
    if not race:
        return None

    # Get latest snapshot per post_position
    subq = (
        select(
            OddsSnapshot.post_position,
            func.max(OddsSnapshot.fetched_at).label("latest"),
        )
        .where(OddsSnapshot.race_id == race.id)
        .group_by(OddsSnapshot.post_position)
        .subquery()
    )

    query = (
        select(OddsSnapshot)
        .join(
            subq,
            (OddsSnapshot.post_position == subq.c.post_position)
            & (OddsSnapshot.fetched_at == subq.c.latest),
        )
        .where(OddsSnapshot.race_id == race.id)
        .order_by(OddsSnapshot.post_position)
    )
    result = await session.execute(query)
    snapshots = result.scalars().all()

    # Get horse names via entries
    entries_result = await session.execute(
        select(RaceEntry, Horse)
        .join(Horse, RaceEntry.horse_id == Horse.id)
        .where(RaceEntry.race_id == race.id)
    )
    horse_by_post: dict[int, str] = {}
    for entry, horse in entries_result.all():
        if entry.post_position is not None:
            horse_by_post[entry.post_position] = horse.name

    fetched_at = None
    entries = []
    for s in snapshots:
        entries.append(
            {
                "post_position": s.post_position,
                "horse_name": horse_by_post.get(s.post_position),
                "win_odds": float(s.win_odds) if s.win_odds is not None else None,
                "win_favorite": s.win_favorite,
                "fetched_at": s.fetched_at.isoformat() if s.fetched_at else None,
            }
        )
        if s.fetched_at and (fetched_at is None or s.fetched_at > fetched_at):
            fetched_at = s.fetched_at

    return {
        "race_id": race_id_str,
        "entries": entries,
        "fetched_at": fetched_at.isoformat() if fetched_at else None,
    }


async def get_odds_history(session: AsyncSession, race_id_str: str) -> dict | None:
    """Get full odds history for a race."""
    result = await session.execute(select(Race).where(Race.race_id == race_id_str))
    race = result.scalar_one_or_none()
    if not race:
        return None

    query = (
        select(OddsSnapshot)
        .where(OddsSnapshot.race_id == race.id)
        .order_by(OddsSnapshot.fetched_at, OddsSnapshot.post_position)
    )
    result = await session.execute(query)
    snapshots = result.scalars().all()

    # Horse names
    entries_result = await session.execute(
        select(RaceEntry, Horse)
        .join(Horse, RaceEntry.horse_id == Horse.id)
        .where(RaceEntry.race_id == race.id)
    )
    horse_by_post: dict[int, str] = {}
    for entry, horse in entries_result.all():
        if entry.post_position is not None:
            horse_by_post[entry.post_position] = horse.name

    history = []
    for s in snapshots:
        if s.win_odds is not None:
            history.append(
                {
                    "post_position": s.post_position,
                    "horse_name": horse_by_post.get(s.post_position),
                    "win_odds": float(s.win_odds),
                    "fetched_at": s.fetched_at.isoformat() if s.fetched_at else None,
                }
            )

    return {"race_id": race_id_str, "history": history}
