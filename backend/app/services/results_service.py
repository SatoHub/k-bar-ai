"""Service layer for AI prediction results and hit-rate analysis."""

from __future__ import annotations

import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Horse, PredictionLog, Race, RaceEntry


async def get_latest_result_date(session: AsyncSession) -> str | None:
    """Return the latest YYYY-MM-DD that has confirmed race results, or None."""
    has_result = (
        select(RaceEntry.race_id)
        .where(RaceEntry.finish_position.isnot(None))
        .distinct()
        .subquery()
    )
    max_date = await session.scalar(
        select(func.max(Race.race_date)).where(
            Race.id.in_(select(has_result.c.race_id))
        )
    )
    if max_date is None:
        return None
    return max_date.isoformat()


async def get_results_calendar(
    session: AsyncSession, year: int, month: int
) -> list[dict]:
    """Return race counts per day for confirmed-result races in a month."""
    has_result = (
        select(RaceEntry.race_id)
        .where(RaceEntry.finish_position.isnot(None))
        .distinct()
        .subquery()
    )
    q = (
        select(
            Race.race_date,
            func.count(Race.id).label("race_count"),
        )
        .where(
            Race.id.in_(select(has_result.c.race_id)),
            func.extract("year", Race.race_date) == year,
            func.extract("month", Race.race_date) == month,
        )
        .group_by(Race.race_date)
        .order_by(Race.race_date)
    )
    result = await session.execute(q)
    return [
        {"date": row.race_date.isoformat(), "race_count": row.race_count}
        for row in result.all()
    ]


async def get_racecourses_for_date(
    session: AsyncSession, date: datetime.date
) -> list[str]:
    """Return distinct racecourse names that have confirmed results on a date."""
    has_result = (
        select(RaceEntry.race_id)
        .where(RaceEntry.finish_position.isnot(None))
        .distinct()
        .subquery()
    )
    q = (
        select(Race.racecourse_name)
        .where(
            Race.id.in_(select(has_result.c.race_id)),
            Race.race_date == date,
            Race.racecourse_name.isnot(None),
        )
        .distinct()
        .order_by(Race.racecourse_name)
    )
    result = await session.execute(q)
    return [row[0] for row in result.all()]


async def get_race_results(
    session: AsyncSession,
    date: datetime.date,
    racecourse: str | None = None,
) -> list[dict]:
    """
    Return races with confirmed results + AI prediction hit analysis for a date.

    Only races that have at least one entry with finish_position are included.
    """
    # Subquery: race IDs with at least one confirmed result
    has_result = (
        select(RaceEntry.race_id)
        .where(RaceEntry.finish_position.isnot(None))
        .distinct()
        .subquery()
    )

    base_filter = [
        Race.id.in_(select(has_result.c.race_id)),
        Race.race_date == date,
    ]
    if racecourse:
        base_filter.append(Race.racecourse_name == racecourse)

    # Race list (no pagination — one day is at most ~36 races)
    races_q = (
        select(Race)
        .where(*base_filter)
        .order_by(Race.race_number)
    )
    result = await session.execute(races_q)
    races = list(result.scalars().all())

    if not races:
        return []

    race_ids = [r.id for r in races]

    # Bulk-load top-3 finishers per race
    top3_q = (
        select(RaceEntry, Horse.name.label("horse_name"))
        .join(Horse, RaceEntry.horse_id == Horse.id)
        .where(
            RaceEntry.race_id.in_(race_ids),
            RaceEntry.finish_position.isnot(None),
            RaceEntry.finish_position <= 3,
        )
        .order_by(RaceEntry.race_id, RaceEntry.finish_position)
    )
    top3_result = await session.execute(top3_q)
    top3_by_race: dict[str, list[dict]] = {}
    for entry, horse_name in top3_result.all():
        rid = str(entry.race_id)
        top3_by_race.setdefault(rid, []).append(
            {
                "finish_position": entry.finish_position,
                "horse_name": horse_name,
                "win_odds": float(entry.win_odds) if entry.win_odds is not None else None,
                "win_favorite": entry.win_favorite,
            }
        )

    # Bulk-load AI predictions (all predictions for these races)
    pred_q = (
        select(PredictionLog, Horse.name.label("horse_name"))
        .join(Horse, PredictionLog.horse_id == Horse.id)
        .where(PredictionLog.race_id.in_(race_ids))
        .order_by(PredictionLog.race_id, PredictionLog.predicted_score.desc())
    )
    pred_result = await session.execute(pred_q)
    preds_by_race: dict[str, list[dict]] = {}
    for pred, horse_name in pred_result.all():
        rid = str(pred.race_id)
        preds_by_race.setdefault(rid, []).append(
            {
                "horse_id": str(pred.horse_id),
                "horse_name": horse_name,
                "predicted_score": pred.predicted_score,
            }
        )

    # Bulk-load actual finish positions (all entries for hit computation)
    entries_q = (
        select(RaceEntry)
        .where(
            RaceEntry.race_id.in_(race_ids),
            RaceEntry.finish_position.isnot(None),
        )
    )
    entries_result = await session.execute(entries_q)
    finish_by_race: dict[str, dict[str, int]] = {}
    for entry in entries_result.scalars().all():
        rid = str(entry.race_id)
        finish_by_race.setdefault(rid, {})[str(entry.horse_id)] = entry.finish_position

    # Build response
    items = []
    for race in races:
        rid = str(race.id)
        top3 = top3_by_race.get(rid, [])
        preds = preds_by_race.get(rid, [])
        finishes = finish_by_race.get(rid, {})

        ai_prediction = None
        if preds:
            predicted_top3 = [
                {"rank": i + 1, "horse_name": p["horse_name"]}
                for i, p in enumerate(preds[:3])
            ]
            hits = _compute_hits(preds, finishes)
            ai_prediction = {
                "predicted_top3": predicted_top3,
                **hits,
            }

        items.append(
            {
                "race_id_str": race.race_id,
                "race_date": race.race_date.isoformat() if race.race_date else None,
                "racecourse_name": race.racecourse_name,
                "race_number": race.race_number,
                "race_name": race.race_name,
                "surface": race.surface,
                "distance_m": race.distance_m,
                "result_top3": top3,
                "ai_prediction": ai_prediction,
            }
        )

    return items


def _compute_hits(
    preds: list[dict],
    finishes: dict[str, int],
) -> dict[str, bool]:
    """
    Compute hit flags for each bet type.

    preds: list of predictions sorted by predicted_score DESC
    finishes: {horse_id_str: finish_position}
    """
    if len(preds) < 1 or not finishes:
        return {
            "tansho_hit": False,
            "fukusho_hit": False,
            "umaren_hit": False,
            "umatan_hit": False,
            "wide_hit": False,
            "sanrenpuku_hit": False,
            "sanrentan_hit": False,
        }

    # AI predicted top 3 horse_ids
    ai_top = [p["horse_id"] for p in preds[:3]]
    # Actual finish positions for AI predicted horses
    ai_finishes = [finishes.get(hid) for hid in ai_top]

    # Actual top-3 horse_ids
    actual_top3_ids = {hid for hid, pos in finishes.items() if pos <= 3}
    actual_1st = {hid for hid, pos in finishes.items() if pos == 1}
    actual_2nd = {hid for hid, pos in finishes.items() if pos == 2}
    actual_3rd = {hid for hid, pos in finishes.items() if pos == 3}
    actual_top2_ids = actual_1st | actual_2nd

    has3 = len(ai_top) >= 3
    has2 = len(ai_top) >= 2

    # 単勝: AI1位馬 == 実1着
    tansho_hit = ai_top[0] in actual_1st

    # 複勝: AI1位馬が実3着以内
    fukusho_hit = ai_top[0] in actual_top3_ids

    # 馬連: AI上位2頭が実上位2着に含まれる（順不同）
    umaren_hit = (
        has2
        and ai_top[0] in actual_top2_ids
        and ai_top[1] in actual_top2_ids
    )

    # 馬単: AI1位=実1着 かつ AI2位=実2着
    umatan_hit = (
        has2 and ai_top[0] in actual_1st and ai_top[1] in actual_2nd
    )

    # ワイド: AI上位3頭のうち2頭以上が実3着以内
    if has3:
        in_top3_count = sum(1 for hid in ai_top[:3] if hid in actual_top3_ids)
        wide_hit = in_top3_count >= 2
    else:
        wide_hit = False

    # 3連複: AI上位3頭 == 実上位3着（順不同）
    sanrenpuku_hit = has3 and set(ai_top[:3]) == actual_top3_ids

    # 3連単: AI1位=実1着, AI2位=実2着, AI3位=実3着
    sanrentan_hit = (
        has3
        and ai_top[0] in actual_1st
        and ai_top[1] in actual_2nd
        and ai_top[2] in actual_3rd
    )

    return {
        "tansho_hit": tansho_hit,
        "fukusho_hit": fukusho_hit,
        "umaren_hit": umaren_hit,
        "umatan_hit": umatan_hit,
        "wide_hit": wide_hit,
        "sanrenpuku_hit": sanrenpuku_hit,
        "sanrentan_hit": sanrentan_hit,
    }


async def get_results_summary(
    session: AsyncSession,
    year: int | None = None,
    month: int | None = None,
    racecourse: str | None = None,
) -> dict:
    """
    Compute hit rates per bet type for races with AI predictions.
    """
    # Races with predictions
    pred_race_ids_q = select(PredictionLog.race_id).distinct()

    base_filter = [Race.id.in_(pred_race_ids_q)]
    if year and month:
        base_filter.extend([
            func.extract("year", Race.race_date) == year,
            func.extract("month", Race.race_date) == month,
        ])

    if racecourse:
        base_filter.append(Race.racecourse_name == racecourse)

    # Also filter: must have confirmed results
    has_result = (
        select(RaceEntry.race_id)
        .where(RaceEntry.finish_position.isnot(None))
        .distinct()
        .subquery()
    )
    base_filter.append(Race.id.in_(select(has_result.c.race_id)))

    races_q = select(Race).where(*base_filter)
    result = await session.execute(races_q)
    races = list(result.scalars().all())

    if not races:
        period = f"{year}-{month:02d}" if year and month else "全期間"
        return {
            "total_races": 0,
            "period": period,
            "hit_rates": _empty_hit_rates(),
            "ai_roi": {
                "strategy": "単勝◎（AI1位に毎レース¥100）",
                "races": 0,
                "hits": 0,
                "hit_rate": 0.0,
                "invested": 0,
                "returned": 0,
                "roi": 0.0,
            },
        }

    race_ids = [r.id for r in races]

    # Predictions
    pred_q = (
        select(PredictionLog)
        .where(PredictionLog.race_id.in_(race_ids))
        .order_by(PredictionLog.race_id, PredictionLog.predicted_score.desc())
    )
    pred_result = await session.execute(pred_q)
    preds_by_race: dict[str, list[dict]] = {}
    for pred in pred_result.scalars().all():
        rid = str(pred.race_id)
        preds_by_race.setdefault(rid, []).append(
            {"horse_id": str(pred.horse_id)}
        )

    # Finish positions
    entries_q = (
        select(RaceEntry)
        .where(
            RaceEntry.race_id.in_(race_ids),
            RaceEntry.finish_position.isnot(None),
        )
    )
    entries_result = await session.execute(entries_q)
    finish_by_race: dict[str, dict[str, int]] = {}
    odds_by_race: dict[str, dict[str, float]] = {}
    for entry in entries_result.scalars().all():
        rid = str(entry.race_id)
        finish_by_race.setdefault(rid, {})[str(entry.horse_id)] = entry.finish_position
        if entry.win_odds is not None:
            odds_by_race.setdefault(rid, {})[str(entry.horse_id)] = float(entry.win_odds)

    # Aggregate hits
    bet_types = [
        "tansho_hit", "fukusho_hit", "umaren_hit", "umatan_hit",
        "wide_hit", "sanrenpuku_hit", "sanrentan_hit",
    ]
    counters = {bt: 0 for bt in bet_types}
    total_races = 0

    # AI回収率（単勝◎＝AI1位に毎レース¥100賭けた想定。結果＋確定単勝オッズから自動算出）
    BET_UNIT = 100.0
    roi_races = 0
    roi_hits = 0
    roi_invested = 0.0
    roi_returned = 0.0

    for race in races:
        rid = str(race.id)
        preds = preds_by_race.get(rid, [])
        finishes = finish_by_race.get(rid, {})
        if not preds or not finishes:
            continue
        total_races += 1
        hits = _compute_hits(preds, finishes)
        for bt in bet_types:
            if hits[bt]:
                counters[bt] += 1

        # 単勝◎: AI1位馬にオッズがあり着順が確定していれば1レースとして集計
        top_horse = preds[0]["horse_id"]
        top_odds = odds_by_race.get(rid, {}).get(top_horse)
        if top_odds is not None and top_horse in finishes:
            roi_races += 1
            roi_invested += BET_UNIT
            if finishes[top_horse] == 1:
                roi_hits += 1
                roi_returned += top_odds * BET_UNIT

    # Build hit_rates
    key_map = {
        "tansho_hit": "tansho",
        "fukusho_hit": "fukusho",
        "umaren_hit": "umaren",
        "umatan_hit": "umatan",
        "wide_hit": "wide",
        "sanrenpuku_hit": "sanrenpuku",
        "sanrentan_hit": "sanrentan",
    }
    hit_rates = {}
    for bt, label in key_map.items():
        hit_rates[label] = {
            "hits": counters[bt],
            "total": total_races,
            "rate": round(counters[bt] / total_races * 100, 1) if total_races > 0 else 0.0,
        }

    period = f"{year}-{month:02d}" if year and month else "全期間"

    ai_roi = {
        "strategy": "単勝◎（AI1位に毎レース¥100）",
        "races": roi_races,
        "hits": roi_hits,
        "hit_rate": round(roi_hits / roi_races * 100, 1) if roi_races > 0 else 0.0,
        "invested": int(roi_invested),
        "returned": int(roi_returned),
        "roi": round(roi_returned / roi_invested * 100, 1) if roi_invested > 0 else 0.0,
    }

    return {
        "total_races": total_races,
        "period": period,
        "hit_rates": hit_rates,
        "ai_roi": ai_roi,
    }


def _empty_hit_rates() -> dict:
    """Return zeroed hit rates structure."""
    return {
        key: {"hits": 0, "total": 0, "rate": 0.0}
        for key in [
            "tansho", "fukusho", "umaren", "umatan",
            "wide", "sanrenpuku", "sanrentan",
        ]
    }
