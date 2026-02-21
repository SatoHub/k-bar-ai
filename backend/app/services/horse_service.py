import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Horse, Jockey, Race, RaceEntry


async def get_horse_detail(session: AsyncSession, horse_id: uuid.UUID) -> dict | None:
    """Get horse detail with race history and stats."""
    result = await session.execute(select(Horse).where(Horse.id == horse_id))
    horse = result.scalar_one_or_none()
    if not horse:
        return None

    # Fetch all entries for this horse with race + jockey info
    query = (
        select(RaceEntry, Race, Jockey)
        .join(Race, RaceEntry.race_id == Race.id)
        .outerjoin(Jockey, RaceEntry.jockey_id == Jockey.id)
        .where(RaceEntry.horse_id == horse_id)
        .order_by(Race.race_date.desc())
    )
    result = await session.execute(query)
    rows = result.all()

    records = []
    total_runs = 0
    wins = 0
    place_count = 0
    surface_stats: dict[str, dict] = {}

    for entry, race, jockey in rows:
        total_runs += 1
        fp = entry.finish_position

        if fp is not None and fp == 1:
            wins += 1
        if fp is not None and fp <= 3:
            place_count += 1

        # Surface stats
        surface_key = race.surface or "不明"
        if surface_key not in surface_stats:
            surface_stats[surface_key] = {"runs": 0, "wins": 0, "place": 0}
        surface_stats[surface_key]["runs"] += 1
        if fp is not None and fp == 1:
            surface_stats[surface_key]["wins"] += 1
        if fp is not None and fp <= 3:
            surface_stats[surface_key]["place"] += 1

        records.append(
            {
                "race_id": race.race_id,
                "race_date": race.race_date,
                "racecourse_name": race.racecourse_name,
                "race_name": race.race_name,
                "surface": race.surface,
                "distance_m": race.distance_m,
                "track_condition": race.track_condition,
                "finish_position": entry.finish_position,
                "finish_note": entry.finish_note,
                "total_time_tenths": entry.total_time_tenths,
                "win_odds": float(entry.win_odds)
                if entry.win_odds is not None
                else None,
                "jockey_name": jockey.name if jockey else None,
            }
        )

    # Build image URL from netkeiba_id if available
    image_url = horse.image_url
    if not image_url and horse.netkeiba_id:
        image_url = (
            f"https://cdn.netkeiba.com/img/horse/240_320/{horse.netkeiba_id}.jpg"
        )

    return {
        "id": horse.id,
        "name": horse.name,
        "sex": horse.sex,
        "netkeiba_id": horse.netkeiba_id,
        "image_url": image_url,
        "total_runs": total_runs,
        "wins": wins,
        "place_count": place_count,
        "win_rate": wins / total_runs if total_runs > 0 else 0.0,
        "place_rate": place_count / total_runs if total_runs > 0 else 0.0,
        "surface_stats": surface_stats,
        "records": records,
    }


async def get_course_aptitude_bulk(
    session: AsyncSession,
    race_id: uuid.UUID,
    surface: str | None,
    distance_m: int | None,
) -> list[dict]:
    """Get course aptitude for all horses in a race."""
    # Get all horse IDs in this race
    result = await session.execute(
        select(RaceEntry.horse_id).where(RaceEntry.race_id == race_id)
    )
    horse_ids = [row[0] for row in result.all()]
    if not horse_ids:
        return []

    # Build filters for "similar course": same surface, distance ±200m
    filters = [
        RaceEntry.horse_id.in_(horse_ids),
        RaceEntry.race_id != race_id,
    ]
    if surface:
        filters.append(Race.surface == surface)
    if distance_m:
        filters.append(Race.distance_m >= distance_m - 200)
        filters.append(Race.distance_m <= distance_m + 200)

    # Query past results on similar courses
    apt_map: dict[uuid.UUID, dict] = {}
    for horse_id in horse_ids:
        apt_map[horse_id] = {
            "horse_id": horse_id,
            "runs": 0,
            "wins": 0,
            "place_count": 0,
        }

    # Re-query with individual counts for accuracy
    for hid in horse_ids:
        hfilters = [
            RaceEntry.horse_id == hid,
            RaceEntry.race_id != race_id,
        ]
        if surface:
            hfilters.append(Race.surface == surface)
        if distance_m:
            hfilters.append(Race.distance_m >= distance_m - 200)
            hfilters.append(Race.distance_m <= distance_m + 200)

        result = await session.execute(
            select(RaceEntry.finish_position)
            .join(Race, RaceEntry.race_id == Race.id)
            .where(*hfilters)
            .where(RaceEntry.finish_position.isnot(None))
        )
        positions = [r[0] for r in result.all()]
        runs = len(positions)
        wins = sum(1 for p in positions if p is not None and p == 1)
        place = sum(1 for p in positions if p is not None and p <= 3)
        apt_map[hid] = {
            "horse_id": hid,
            "runs": runs,
            "wins": wins,
            "place_count": place,
        }

    # Calculate score (1-3 stars)
    entries = []
    for hid, data in apt_map.items():
        runs = data["runs"]
        if runs == 0:
            score = 0
        elif runs >= 3 and data["place_count"] / runs >= 0.5:
            score = 3
        elif runs >= 2 and data["place_count"] / runs >= 0.3:
            score = 2
        elif runs >= 1 and data["wins"] > 0:
            score = 2
        elif runs >= 1:
            score = 1
        else:
            score = 0
        entries.append({**data, "score": score})

    return entries
