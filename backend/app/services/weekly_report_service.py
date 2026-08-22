"""Weekly report data aggregation service."""

from __future__ import annotations

import datetime
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bet_record import BetRecord
from app.models.prediction import PredictionLog
from app.models.entry import RaceEntry
from app.models.race import Race

logger = logging.getLogger(__name__)


async def build_weekly_report_data(session: AsyncSession) -> dict:
    """Aggregate past 7 days of betting and prediction data for the weekly report.

    Returns a dict compatible with build_weekly_report_flex().
    """
    from zoneinfo import ZoneInfo
    from app.config import settings

    tz = ZoneInfo(settings.SCHEDULER_TIMEZONE)
    today = datetime.datetime.now(tz).date()
    week_ago = today - datetime.timedelta(days=7)
    period = f"{week_ago.month}/{week_ago.day} - {today.month}/{today.day}"

    # --- Bet record aggregation ---
    bet_q = select(BetRecord).where(
        BetRecord.bet_date >= week_ago,
        BetRecord.bet_date <= today,
    )
    result = await session.execute(bet_q)
    bets = list(result.scalars().all())

    total_bets = len(bets)
    wins = sum(1 for b in bets if b.is_hit is True)
    total_invested = sum(b.amount_yen for b in bets)
    total_returned = sum(b.actual_payout or 0 for b in bets)
    roi = (total_returned / total_invested * 100) if total_invested > 0 else 0.0

    # --- Per bet_type hit rates from AI predictions ---
    from app.services.results_service import _compute_hits

    pred_race_ids_q = select(PredictionLog.race_id).distinct().subquery()
    races_q = select(Race).where(
        Race.id.in_(select(pred_race_ids_q.c.race_id)),
        Race.race_date >= week_ago,
        Race.race_date <= today,
    )
    races_result = await session.execute(races_q)
    races = list(races_result.scalars().all())
    race_ids = [r.id for r in races]

    hit_rates: dict[str, dict] = {}

    if race_ids:
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

        # Aggregate
        bet_types_map = {
            "tansho_hit": "tansho",
            "fukusho_hit": "fukusho",
            "umaren_hit": "umaren",
            "umatan_hit": "umatan",
            "wide_hit": "wide",
            "sanrenpuku_hit": "sanrenpuku",
            "sanrentan_hit": "sanrentan",
        }
        counters = {bt: 0 for bt in bet_types_map}
        total_pred_races = 0

        for race in races:
            rid = str(race.id)
            preds = preds_by_race.get(rid, [])
            finishes = finish_by_race.get(rid, {})
            if not preds or not finishes:
                continue
            total_pred_races += 1
            hits = _compute_hits(preds, finishes)
            for bt in counters:
                if hits[bt]:
                    counters[bt] += 1

        for bt, label in bet_types_map.items():
            hit_rates[label] = {
                "hits": counters[bt],
                "total": total_pred_races,
                "rate": round(counters[bt] / total_pred_races * 100, 1)
                if total_pred_races > 0
                else 0.0,
            }

    return {
        "period": period,
        "total_bets": total_bets,
        "wins": wins,
        "total_invested": total_invested,
        "total_returned": total_returned,
        "roi": roi,
        "hit_rates": hit_rates,
    }
