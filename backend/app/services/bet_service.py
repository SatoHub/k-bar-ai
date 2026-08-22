import math
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.bet_record import BetRecord
from app.models.entry import RaceEntry
from app.models.horse import Horse
from app.schemas.bet import BetEntryInfo, BetRaceInfo, RaceResultEntry


async def create_bet(session: AsyncSession, data: dict) -> BetRecord:
    bet = BetRecord(**data)
    session.add(bet)
    await session.commit()
    await session.refresh(bet)
    return bet


# ──────────────────────────────────────────────────────────────────────────
# 自動判定（当落・払戻のセトルメント）
#
# レース結果(race_entries.finish_position)と、ベット時オッズ(odds_at_bet)から
# 各馬券の当落と払戻を自動計算する。シミュレーターの「推定払戻」と同じ
# floor(掛け金×オッズ/100)×100 で算出するためJV-Data同期の有無に依存しない。
# ──────────────────────────────────────────────────────────────────────────


def _parse_waku(token: str) -> int | None:
    t = token.replace("枠", "").strip()
    return int(t) if t.isdigit() else None


def _place_cutoff(num_runners: int) -> int:
    """複勝・ワイドの対象着順（JRA: 8頭以上=3着まで / 5-7頭=2着まで / 4頭以下=1着）。"""
    if num_runners >= 8:
        return 3
    if num_runners >= 5:
        return 2
    return 1


def _evaluate_hit(bet_type: str, horse_names: str, ctx: dict) -> bool:
    """1点の馬券（=1組み合わせ）が的中したかを判定する。"""
    names = [s.strip() for s in horse_names.split(",") if s.strip()]
    if not names:
        return False

    finish: dict[str, int] = ctx["finish_by_name"]
    at_pos: dict[int, str] = ctx["name_at_pos"]
    first, second, third = at_pos.get(1), at_pos.get(2), at_pos.get(3)
    cutoff = _place_cutoff(ctx["num_runners"])

    if bet_type == "tansho":
        return finish.get(names[0]) == 1
    if bet_type == "fukusho":
        fp = finish.get(names[0])
        return fp is not None and fp <= cutoff
    if bet_type == "umaren":
        if len(names) < 2 or None in (first, second):
            return False
        return {names[0], names[1]} == {first, second}
    if bet_type == "umatan":
        if len(names) < 2:
            return False
        return names[0] == first and names[1] == second
    if bet_type == "wide":
        if len(names) < 2 or names[0] == names[1]:
            return False
        fa, fb = finish.get(names[0]), finish.get(names[1])
        return fa is not None and fb is not None and fa <= cutoff and fb <= cutoff
    if bet_type == "sanrenpuku":
        if len(names) < 3 or None in (first, second, third):
            return False
        return {names[0], names[1], names[2]} == {first, second, third}
    if bet_type == "sanrentan":
        if len(names) < 3:
            return False
        return names[0] == first and names[1] == second and names[2] == third
    if bet_type == "wakuren":
        if len(names) < 2:
            return False
        bks = [_parse_waku(n) for n in names[:2]]
        if any(b is None for b in bks):
            return False
        at_bracket: dict[int, int | None] = ctx["bracket_at_pos"]
        w1, w2 = at_bracket.get(1), at_bracket.get(2)
        if w1 is None or w2 is None:
            return False
        return sorted(bks) == sorted([w1, w2])
    return False


async def settle_bets(session: AsyncSession) -> int:
    """未判定(is_hit IS NULL)で結果が出ているレースの馬券を一括判定する。

    結果未確定のレースの馬券は据え置く（次回結果が入ったときに判定される）。
    判定済みの件数を返す。
    """
    bets = list(
        (
            await session.execute(
                select(BetRecord).where(
                    BetRecord.is_hit.is_(None),
                    BetRecord.race_id.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    if not bets:
        return 0

    race_ids = list({b.race_id for b in bets})
    rows = (
        await session.execute(
            select(
                RaceEntry.race_id,
                RaceEntry.finish_position,
                RaceEntry.bracket_number,
                Horse.name.label("horse_name"),
            )
            .join(Horse, RaceEntry.horse_id == Horse.id)
            .where(RaceEntry.race_id.in_(race_ids))
        )
    ).all()

    # レースごとの結果コンテキストを構築
    race_ctx: dict[uuid.UUID, dict] = {}
    for row in rows:
        ctx = race_ctx.setdefault(
            row.race_id,
            {
                "finish_by_name": {},
                "name_at_pos": {},
                "bracket_at_pos": {},
                "num_runners": 0,
                "has_result": False,
            },
        )
        ctx["num_runners"] += 1
        if row.finish_position is not None:
            ctx["finish_by_name"][row.horse_name] = row.finish_position
            ctx["name_at_pos"][row.finish_position] = row.horse_name
            ctx["bracket_at_pos"][row.finish_position] = row.bracket_number
            if row.finish_position == 1:
                ctx["has_result"] = True

    settled = 0
    for bet in bets:
        ctx = race_ctx.get(bet.race_id)
        if not ctx or not ctx["has_result"]:
            continue  # 結果未確定 → 据え置き
        hit = _evaluate_hit(bet.bet_type, bet.horse_names, ctx)
        bet.is_hit = hit
        if not hit:
            bet.actual_payout = 0
        elif bet.odds_at_bet is not None:
            bet.actual_payout = (
                math.floor(bet.amount_yen * float(bet.odds_at_bet) / 100) * 100
            )
        else:
            bet.actual_payout = None  # 的中だがオッズ未記録 → 払戻不明
        settled += 1

    if settled:
        await session.commit()
    return settled


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
            RaceResultEntry(
                finish_position=row.finish_position, horse_name=row.horse_name
            )
        )

    # All entries (post / bracket / name) so the client can map names -> 馬番/枠
    entry_query = (
        select(
            RaceEntry.race_id,
            RaceEntry.post_position,
            RaceEntry.bracket_number,
            Horse.name.label("horse_name"),
        )
        .join(Horse, RaceEntry.horse_id == Horse.id)
        .where(RaceEntry.race_id.in_(unique_race_ids))
        .order_by(RaceEntry.race_id, RaceEntry.post_position)
    )
    entry_rows = (await session.execute(entry_query)).all()
    entries_map: dict[uuid.UUID, list[BetEntryInfo]] = {}
    for row in entry_rows:
        entries_map.setdefault(row.race_id, []).append(
            BetEntryInfo(
                post_position=row.post_position,
                bracket_number=row.bracket_number,
                horse_name=row.horse_name,
            )
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
            entries=entries_map.get(bet.race_id, []),
        )

    return info_map


async def get_bets(
    session: AsyncSession, page: int = 1, per_page: int = 20
) -> tuple[list[dict], int]:
    # 結果が出ている未判定の馬券を自動判定してから一覧を返す
    await settle_bets(session)

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
    # サマリー集計の前に未判定の馬券を自動判定（TOP画面で自動反映される）
    await settle_bets(session)

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
