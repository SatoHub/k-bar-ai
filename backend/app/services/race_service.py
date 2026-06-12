import datetime

from sqlalchemy import func, select, text
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


async def get_past_performances(
    session: AsyncSession, race_id: str, limit_per_horse: int = 5
) -> dict | None:
    """Return the most recent N past races for every horse in a race (馬柱).

    Uses a single windowed query (ROW_NUMBER partitioned by horse) to avoid
    N+1 queries across up to 18 horses.
    """
    race = (
        await session.execute(select(Race).where(Race.race_id == race_id))
    ).scalar_one_or_none()
    if not race:
        return None

    entry_rows = (
        await session.execute(
            select(RaceEntry.horse_id, RaceEntry.post_position).where(
                RaceEntry.race_id == race.id
            )
        )
    ).all()
    horse_ids = [r[0] for r in entry_rows]
    post_by_horse = {r[0]: r[1] for r in entry_rows}
    if not horse_ids:
        return {"race_id": race_id, "horses": []}

    rn = (
        func.row_number()
        .over(
            partition_by=RaceEntry.horse_id,
            order_by=(Race.race_date.desc(), Race.race_number.desc()),
        )
        .label("rn")
    )
    subq = (
        select(
            RaceEntry.horse_id.label("horse_id"),
            Race.race_id.label("p_race_id"),
            Race.race_date,
            Race.racecourse_name,
            Race.race_number,
            Race.race_name,
            Race.graded_race,
            Race.surface,
            Race.distance_m,
            Race.track_condition,
            Race.head_count,
            RaceEntry.bracket_number,
            RaceEntry.post_position,
            RaceEntry.finish_position,
            RaceEntry.finish_note,
            RaceEntry.total_time_tenths,
            RaceEntry.last_3f_time,
            RaceEntry.margin,
            RaceEntry.corner_pos_1,
            RaceEntry.corner_pos_2,
            RaceEntry.corner_pos_3,
            RaceEntry.corner_pos_4,
            RaceEntry.win_odds,
            RaceEntry.win_favorite,
            RaceEntry.weight_carried_kg,
            RaceEntry.horse_weight_kg,
            RaceEntry.horse_weight_diff,
            Jockey.name.label("jockey_name"),
            rn,
        )
        .join(Race, RaceEntry.race_id == Race.id)
        .outerjoin(Jockey, RaceEntry.jockey_id == Jockey.id)
        .where(RaceEntry.horse_id.in_(horse_ids))
        .where(Race.race_date < race.race_date)
        .subquery()
    )
    query = (
        select(subq)
        .where(subq.c.rn <= limit_per_horse)
        .order_by(subq.c.horse_id, subq.c.rn)
    )
    rows = (await session.execute(query)).all()

    by_horse: dict = {}
    for row in rows:
        m = row._mapping
        corners = []
        for key in ("corner_pos_1", "corner_pos_2", "corner_pos_3", "corner_pos_4"):
            c = (m[key] or "").strip()
            if c.endswith(".0"):
                c = c[:-2]
            if c:
                corners.append(c)
        corner_passing = "-".join(corners) or None
        record = {
            "race_id": m["p_race_id"],
            "race_date": m["race_date"],
            "racecourse_name": m["racecourse_name"],
            "race_number": m["race_number"],
            "race_name": m["race_name"],
            "graded_race": m["graded_race"],
            "surface": m["surface"],
            "distance_m": m["distance_m"],
            "track_condition": m["track_condition"],
            "field_size": m["head_count"],
            "bracket_number": m["bracket_number"],
            "post_position": m["post_position"],
            "finish_position": m["finish_position"],
            "finish_note": m["finish_note"],
            "total_time_tenths": m["total_time_tenths"],
            "last_3f_time": m["last_3f_time"],
            "margin": m["margin"],
            "corner_passing": corner_passing,
            "win_odds": m["win_odds"],
            "win_favorite": m["win_favorite"],
            "weight_carried_kg": m["weight_carried_kg"],
            "horse_weight_kg": m["horse_weight_kg"],
            "horse_weight_diff": m["horse_weight_diff"],
            "jockey_name": m["jockey_name"],
        }
        by_horse.setdefault(m["horse_id"], []).append(record)

    horses = [
        {
            "horse_id": hid,
            "post_position": post_by_horse.get(hid),
            "records": by_horse.get(hid, []),
        }
        for hid in horse_ids
    ]
    return {"race_id": race_id, "horses": horses}


async def get_race_pedigree(session: AsyncSession, race_id: str) -> dict | None:
    """Return sire / dam / broodmare-sire for every horse in a race (血統).

    Sourced from JRA-VAN (NL_UM) and stored in the self-contained
    ``horse_pedigree`` table (keyed by netkeiba_id = kettonum). The table is
    populated on the home PC from the jravan.v_pedigree FDW view and synced to
    VPS as data, so this endpoint works in production without any FDW link.
    Degrades gracefully: horses without pedigree return null fields.
    """
    race = (
        await session.execute(select(Race).where(Race.race_id == race_id))
    ).scalar_one_or_none()
    if not race:
        return None

    sql = text(
        """
        SELECT h.id AS horse_id, e.post_position,
               p.sire, p.dam, p.broodmare_sire, p.paternal_grandsire
        FROM race_entries e
        JOIN horses h ON h.id = e.horse_id
        LEFT JOIN horse_pedigree p ON p.netkeiba_id = h.netkeiba_id
        WHERE e.race_id = :rid
        ORDER BY e.post_position NULLS LAST
        """
    )
    rows = (await session.execute(sql, {"rid": race.id})).mappings().all()
    horses = [dict(r) for r in rows]
    return {"race_id": race_id, "horses": horses}


async def get_confirmed_data(session: AsyncSession, race_id: str) -> dict | None:
    """Return JV-Data confirmed win odds + payouts for a race (確定オッズ・払戻).

    Sourced from the self-contained confirmed_win_odds / confirmed_payouts
    tables (keyed by netkeiba race_id), populated on the home PC from JV-Data
    and synced to VPS. Works in production without any FDW link. Returns empty
    lists / null when JV-Data has no confirmed data for the race yet.
    """
    race = (
        await session.execute(select(Race).where(Race.race_id == race_id))
    ).scalar_one_or_none()
    if not race:
        return None

    odds_rows = (
        await session.execute(
            text(
                """
                SELECT umaban, win_odds, win_favorite
                FROM confirmed_win_odds
                WHERE race_id = :rid
                ORDER BY umaban
                """
            ),
            {"rid": race_id},
        )
    ).mappings().all()

    payout_row = (
        await session.execute(
            text("SELECT * FROM confirmed_payouts WHERE race_id = :rid"),
            {"rid": race_id},
        )
    ).mappings().first()

    payouts = None
    if payout_row is not None:
        payouts = {k: v for k, v in dict(payout_row).items() if k not in ("race_id", "updated_at")}

    win_odds = []
    for r in odds_rows:
        d = dict(r)
        # tanodds is stored as float32 (real); round to JV-Data's 1-decimal scale.
        if d.get("win_odds") is not None:
            d["win_odds"] = round(float(d["win_odds"]), 1)
        win_odds.append(d)

    return {
        "race_id": race_id,
        "win_odds": win_odds,
        "payouts": payouts,
    }


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
