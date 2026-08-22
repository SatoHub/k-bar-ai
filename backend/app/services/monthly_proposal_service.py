"""Monthly improvement proposal generation service.

Analyzes the previous month's data and produces rule-based improvement proposals.
"""

from __future__ import annotations

import datetime
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prediction import PredictionLog
from app.models.entry import RaceEntry
from app.models.race import Race

logger = logging.getLogger(__name__)


async def generate_monthly_proposals(session: AsyncSession) -> list[dict]:
    """Analyze last month's data and return a list of improvement proposals.

    Each proposal: {proposal_type: str, description: str, priority: int}
    """
    from zoneinfo import ZoneInfo
    from app.config import settings

    tz = ZoneInfo(settings.SCHEDULER_TIMEZONE)
    today = datetime.datetime.now(tz).date()
    # Previous month range
    first_of_this_month = today.replace(day=1)
    last_month_end = first_of_this_month - datetime.timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    # Two months ago range (for comparison)
    two_months_start = (last_month_start - datetime.timedelta(days=1)).replace(day=1)
    two_months_end = last_month_start - datetime.timedelta(days=1)

    proposals: list[dict] = []

    # --- 1. Check prediction log growth ---
    last_month_count = (
        await session.scalar(
            select(func.count(PredictionLog.id)).where(
                PredictionLog.created_at
                >= datetime.datetime.combine(last_month_start, datetime.time.min),
                PredictionLog.created_at
                < datetime.datetime.combine(first_of_this_month, datetime.time.min),
            )
        )
        or 0
    )

    prev_month_count = (
        await session.scalar(
            select(func.count(PredictionLog.id)).where(
                PredictionLog.created_at
                >= datetime.datetime.combine(two_months_start, datetime.time.min),
                PredictionLog.created_at
                < datetime.datetime.combine(last_month_start, datetime.time.min),
            )
        )
        or 0
    )

    if last_month_count > 500 and last_month_count > prev_month_count * 1.2:
        proposals.append(
            {
                "proposal_type": "retrain",
                "description": (
                    f"先月の予想ログが{last_month_count}件に達しました"
                    f"（前月比+{last_month_count - prev_month_count}件）。"
                    "データ量が増えたのでモデル再学習を推奨します。"
                ),
                "priority": 1,
            }
        )

    # --- 2. Surface-specific hit rate analysis ---
    from app.services.results_service import _compute_hits

    for surface_name in ["芝", "ダート"]:
        race_ids_q = select(Race.id).where(
            Race.race_date >= last_month_start,
            Race.race_date <= last_month_end,
            Race.surface == surface_name,
        )
        race_ids_result = await session.execute(race_ids_q)
        race_ids = [r[0] for r in race_ids_result.all()]

        if not race_ids:
            continue

        # Predictions for these races
        pred_q = (
            select(PredictionLog)
            .where(PredictionLog.race_id.in_(race_ids))
            .order_by(PredictionLog.race_id, PredictionLog.predicted_score.desc())
        )
        pred_result = await session.execute(pred_q)
        preds_by_race: dict[str, list[dict]] = {}
        for pred in pred_result.scalars().all():
            rid = str(pred.race_id)
            preds_by_race.setdefault(rid, []).append({"horse_id": str(pred.horse_id)})

        # Finish positions
        entries_q = select(RaceEntry).where(
            RaceEntry.race_id.in_(race_ids),
            RaceEntry.finish_position.isnot(None),
        )
        entries_result = await session.execute(entries_q)
        finish_by_race: dict[str, dict[str, int]] = {}
        for entry in entries_result.scalars().all():
            rid = str(entry.race_id)
            finish_by_race.setdefault(rid, {})[str(entry.horse_id)] = (
                entry.finish_position
            )

        # Compute fukusho (複勝) hit rate for this surface
        fukusho_hits = 0
        total_races = 0
        for rid_str in set(list(preds_by_race.keys()) + list(finish_by_race.keys())):
            preds = preds_by_race.get(rid_str, [])
            finishes = finish_by_race.get(rid_str, {})
            if not preds or not finishes:
                continue
            total_races += 1
            hits = _compute_hits(preds, finishes)
            if hits["fukusho_hit"]:
                fukusho_hits += 1

        if total_races >= 10:
            rate = round(fukusho_hits / total_races * 100, 1)
            if rate < 30:
                proposals.append(
                    {
                        "proposal_type": "feature_engineering",
                        "description": (
                            f"{surface_name}の複勝的中率が{rate}%と低い状態です"
                            f"（{total_races}レース中{fukusho_hits}的中）。"
                            f"{surface_name}向けの特徴量追加を検討してください。"
                        ),
                        "priority": 2,
                    }
                )

    # --- 3. Bet type trend analysis (compare with two months ago) ---
    # This is simplified - check if any bet type improved significantly
    for bt_label, bt_key in [
        ("単勝", "tansho_hit"),
        ("複勝", "fukusho_hit"),
        ("ワイド", "wide_hit"),
    ]:
        last_rate = await _compute_monthly_hit_rate(
            session, bt_key, last_month_start, last_month_end
        )
        prev_rate = await _compute_monthly_hit_rate(
            session, bt_key, two_months_start, two_months_end
        )
        if last_rate is not None and prev_rate is not None:
            if last_rate > prev_rate + 5:
                proposals.append(
                    {
                        "proposal_type": "positive_trend",
                        "description": (
                            f"{bt_label}の的中率が{prev_rate:.1f}% → {last_rate:.1f}%に改善しました。"
                            "この馬券種の推奨度を上げることを検討してください。"
                        ),
                        "priority": 3,
                    }
                )

    # Sort by priority
    proposals.sort(key=lambda p: p["priority"])
    return proposals


async def _compute_monthly_hit_rate(
    session: AsyncSession,
    hit_key: str,
    start_date: datetime.date,
    end_date: datetime.date,
) -> float | None:
    """Compute hit rate for a specific bet type within a date range."""
    from app.services.results_service import _compute_hits

    race_q = select(Race.id).where(
        Race.race_date >= start_date, Race.race_date <= end_date
    )
    race_result = await session.execute(race_q)
    race_ids = [r[0] for r in race_result.all()]

    if not race_ids:
        return None

    pred_q = (
        select(PredictionLog)
        .where(PredictionLog.race_id.in_(race_ids))
        .order_by(PredictionLog.race_id, PredictionLog.predicted_score.desc())
    )
    pred_result = await session.execute(pred_q)
    preds_by_race: dict[str, list[dict]] = {}
    for pred in pred_result.scalars().all():
        rid = str(pred.race_id)
        preds_by_race.setdefault(rid, []).append({"horse_id": str(pred.horse_id)})

    entries_q = select(RaceEntry).where(
        RaceEntry.race_id.in_(race_ids),
        RaceEntry.finish_position.isnot(None),
    )
    entries_result = await session.execute(entries_q)
    finish_by_race: dict[str, dict[str, int]] = {}
    for entry in entries_result.scalars().all():
        rid = str(entry.race_id)
        finish_by_race.setdefault(rid, {})[str(entry.horse_id)] = entry.finish_position

    hits = 0
    total = 0
    for rid_str in preds_by_race:
        preds = preds_by_race.get(rid_str, [])
        finishes = finish_by_race.get(rid_str, {})
        if not preds or not finishes:
            continue
        total += 1
        computed = _compute_hits(preds, finishes)
        if computed.get(hit_key):
            hits += 1

    if total == 0:
        return None
    return round(hits / total * 100, 1)
