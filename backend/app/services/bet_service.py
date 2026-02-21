import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bet_record import BetRecord


async def create_bet(session: AsyncSession, data: dict) -> BetRecord:
    bet = BetRecord(**data)
    session.add(bet)
    await session.commit()
    await session.refresh(bet)
    return bet


async def get_bets(
    session: AsyncSession, page: int = 1, per_page: int = 20
) -> tuple[list[BetRecord], int]:
    total = await session.scalar(select(func.count(BetRecord.id)))
    query = (
        select(BetRecord)
        .order_by(BetRecord.bet_date.desc(), BetRecord.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await session.execute(query)
    return list(result.scalars().all()), total or 0


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
