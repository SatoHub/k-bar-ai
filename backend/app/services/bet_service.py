import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.bet_record import BetRecord
from app.models.entry import RaceEntry
from app.models.horse import Horse
from app.schemas.bet import BetRaceInfo, RaceResultEntry


async def create_bet(session: AsyncSession, data: dict) -> BetRecord:
    bet = BetRecord(**data)
    session.add(bet)
    await session.commit()
    await session.refresh(bet)
    return bet


async def _build_race_info(
    session: AsyncSession, bets: list[BetRecord]
) -> dict[uuid.UUID, BetRaceInfo]:
    """Build race info (including top 3 results) for a list of bets."""
    race_ids = [b.race_id for b in bets if b.race_id is not None]
    if not race_ids:
        return {}

    # Unique race UUIDs
    unique_race_ids = list(set(race_ids))

    # Query top 3 finishers for each race
    result_query = (
        select(
            RaceEntry.race_id,
            RaceEntry.finish_position,
            Horse.name.label("horse_name"),
        )
        .join(Horse, RaceEntry.horse_id == Horse.id)
        .where(
            RaceEntry.race_id.in_(unique_race_ids),
            RaceEntry.finish_position.is_not(None),
            RaceEntry.finish_position <= 3,
        )
        .order_by(RaceEntry.race_id, RaceEntry.finish_position)
    )
    result = await session.execute(result_query)
    rows = result.all()

    # Group by race_id
    top3_map: dict[uuid.UUID, list[RaceResultEntry]] = {}
    for row in rows:
        rid = row.race_id
        if rid not in top3_map:
            top3_map[rid] = []
        top3_map[rid].append(
            RaceResultEntry(finish_position=row.finish_position, horse_name=row.horse_name)
        )

    # Build race info from the bet's eagerly loaded race relationship
    info_map: dict[uuid.UUID, BetRaceInfo] = {}
    for bet in bets:
        if bet.race_id is None or bet.race is None:
            continue
        if bet.race_id in info_map:
            continue
        race = bet.race
        info_map[bet.race_id] = BetRaceInfo(
            race_number=race.race_number,
            racecourse_name=race.racecourse_name,
            race_name=race.race_name,
            race_id_str=race.race_id,
            result_top3=top3_map.get(bet.race_id, []),
        )

    return info_map


async def get_bets(
    session: AsyncSession, page: int = 1, per_page: int = 20
) -> tuple[list[dict], int]:
    total = await session.scalar(select(func.count(BetRecord.id)))
    query = (
        select(BetRecord)
        .options(joinedload(BetRecord.race))
        .order_by(BetRecord.bet_date.desc(), BetRecord.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await session.execute(query)
    bets = list(result.scalars().unique().all())

    # Build race info with top 3 results
    race_info_map = await _build_race_info(session, bets)

    # Convert to response dicts
    items = []
    for bet in bets:
        item = {
            "id": bet.id,
            "race_id": bet.race_id,
            "bet_date": bet.bet_date,
            "bet_type": bet.bet_type,
            "horse_names": bet.horse_names,
            "amount_yen": bet.amount_yen,
            "odds_at_bet": bet.odds_at_bet,
            "actual_payout": bet.actual_payout,
            "is_hit": bet.is_hit,
            "note": bet.note,
            "created_at": bet.created_at,
            "race_info": race_info_map.get(bet.race_id) if bet.race_id else None,
        }
        items.append(item)

    return items, total or 0


async def update_bet(
    session: AsyncSession, bet_id: uuid.UUID, data: dict
) -> BetRecord | None:
    result = await session.execute(select(BetRecord).where(BetRecord.id == bet_id))
    bet = result.scalar_one_or_none()
    if not bet:
        return None

    for key, value in data.items():
        setattr(bet, key, value)
    await session.commit()
    await session.refresh(bet)
    return bet


async def delete_bet(session: AsyncSession, bet_id: uuid.UUID) -> bool:
    result = await session.execute(select(BetRecord).where(BetRecord.id == bet_id))
    bet = result.scalar_one_or_none()
    if not bet:
        return False
    await session.delete(bet)
    await session.commit()
    return True


async def get_bet_summary(session: AsyncSession) -> dict:
    total_bets = await session.scalar(select(func.count(BetRecord.id))) or 0
    total_amount = await session.scalar(select(func.sum(BetRecord.amount_yen))) or 0
    total_payout = await session.scalar(select(func.sum(BetRecord.actual_payout))) or 0
    hit_count = (
        await session.scalar(
            select(func.count(BetRecord.id)).where(BetRecord.is_hit.is_(True))
        )
        or 0
    )

    return {
        "total_bets": total_bets,
        "total_amount": total_amount,
        "total_payout": total_payout,
        "recovery_rate": (total_payout / total_amount * 100)
        if total_amount > 0
        else 0.0,
        "hit_count": hit_count,
        "hit_rate": (hit_count / total_bets * 100) if total_bets > 0 else 0.0,
    }
