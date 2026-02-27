"""Scheduler job definitions for automated data collection."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger

from app.config import settings

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from app.scheduler.scheduler import SchedulerManager

logger = logging.getLogger(__name__)


def _today_jst() -> date:
    """Return today's date in the scheduler timezone (JST)."""
    tz = ZoneInfo(settings.SCHEDULER_TIMEZONE)
    return datetime.now(tz).date()


def _auto_detect_miss_reason(race, finish_pos: int | None) -> str:
    """Auto-detect miss reason from race data (no user input needed)."""
    parts = []
    if race.surface:
        parts.append(race.surface)
    if race.distance_m:
        parts.append(f"{race.distance_m}m")
    if finish_pos and finish_pos > 10:
        return f"{' '.join(parts)} 大敗({finish_pos}着)"
    if finish_pos and finish_pos > 5:
        return f"{' '.join(parts)} 中団以下({finish_pos}着)"
    if finish_pos and finish_pos > 3:
        return f"{' '.join(parts)} 惜敗({finish_pos}着)"
    return f"{' '.join(parts)} 着外" if parts else "着外"


def register_jobs(
    scheduler: AsyncIOScheduler, manager: SchedulerManager
) -> None:
    """Register all scheduled jobs."""
    tz = settings.SCHEDULER_TIMEZONE

    # 1. Calendar scan: daily at 6:00 JST
    scheduler.add_job(
        job_calendar,
        CronTrigger(hour=settings.SCHED_CALENDAR_HOUR, minute=settings.SCHED_CALENDAR_MINUTE, timezone=tz),
        id="calendar",
        name="カレンダースキャン",
        kwargs={"manager": manager},
        replace_existing=True,
    )

    # 2a. Shutuba fetch (morning): daily at 9:00 JST
    scheduler.add_job(
        job_shutuba,
        CronTrigger(hour=settings.SCHED_SHUTUBA_MORNING_HOUR, minute=settings.SCHED_SHUTUBA_MORNING_MINUTE, timezone=tz),
        id="shutuba_morning",
        name="出馬表取得(朝)",
        kwargs={"manager": manager},
        replace_existing=True,
    )

    # 2b. Shutuba fetch (evening): daily at 18:00 JST (fallback)
    scheduler.add_job(
        job_shutuba,
        CronTrigger(hour=settings.SCHED_SHUTUBA_HOUR, minute=settings.SCHED_SHUTUBA_MINUTE, timezone=tz),
        id="shutuba",
        name="出馬表取得(夕方)",
        kwargs={"manager": manager},
        replace_existing=True,
    )

    # 3. Odds fetch: every 30 min from 8:00-16:30 JST
    scheduler.add_job(
        job_odds,
        CronTrigger(
            hour=f"{settings.SCHED_ODDS_START_HOUR}-{settings.SCHED_ODDS_END_HOUR}",
            minute=f"*/{settings.SCHED_ODDS_INTERVAL_MINUTES}",
            timezone=tz,
        ),
        id="odds",
        name="オッズ取得",
        kwargs={"manager": manager},
        replace_existing=True,
    )

    # 4. Results fetch: at 17:00 and 19:00 JST
    scheduler.add_job(
        job_results,
        CronTrigger(hour=settings.SCHED_RESULTS_HOURS, minute=0, timezone=tz),
        id="results",
        name="レース結果取得",
        kwargs={"manager": manager},
        replace_existing=True,
    )

    # 5a. Prediction (morning): daily at 9:30 JST (after morning shutuba at 9:00)
    scheduler.add_job(
        job_predict,
        CronTrigger(
            hour=settings.SCHED_PREDICT_MORNING_HOUR,
            minute=settings.SCHED_PREDICT_MORNING_MINUTE,
            timezone=tz,
        ),
        id="predict_morning",
        name="AI予想実行(朝)",
        kwargs={"manager": manager},
        replace_existing=True,
    )

    # 5b. Prediction (evening): daily at 18:30 JST (after evening shutuba at 18:00)
    scheduler.add_job(
        job_predict,
        CronTrigger(hour=settings.SCHED_PREDICT_HOUR, minute=settings.SCHED_PREDICT_MINUTE, timezone=tz),
        id="predict",
        name="AI予想実行(夕方)",
        kwargs={"manager": manager},
        replace_existing=True,
    )

    # 6. Notify prediction: daily at 19:00 JST (after predict at 18:30)
    scheduler.add_job(
        job_notify_prediction,
        CronTrigger(
            hour=settings.SCHED_NOTIFY_PREDICTION_HOUR,
            minute=settings.SCHED_NOTIFY_PREDICTION_MINUTE,
            timezone=tz,
        ),
        id="notify_prediction",
        name="予想通知送信",
        kwargs={"manager": manager},
        replace_existing=True,
    )

    # 7. Notify results: daily at 20:00 JST (after results at 19:00)
    scheduler.add_job(
        job_notify_results,
        CronTrigger(
            hour=settings.SCHED_NOTIFY_RESULTS_HOUR,
            minute=settings.SCHED_NOTIFY_RESULTS_MINUTE,
            timezone=tz,
        ),
        id="notify_results",
        name="結果通知送信",
        kwargs={"manager": manager},
        replace_existing=True,
    )

    # 8. Weekly report: Monday at 8:00 JST
    scheduler.add_job(
        job_weekly_report,
        CronTrigger(
            day_of_week=settings.SCHED_WEEKLY_REPORT_DAY_OF_WEEK,
            hour=settings.SCHED_WEEKLY_REPORT_HOUR,
            minute=settings.SCHED_WEEKLY_REPORT_MINUTE,
            timezone=tz,
        ),
        id="weekly_report",
        name="週次レポート送信",
        kwargs={"manager": manager},
        replace_existing=True,
    )

    # 9. Monthly proposal: 1st of each month at 8:00 JST
    scheduler.add_job(
        job_monthly_proposal,
        CronTrigger(
            day=settings.SCHED_MONTHLY_PROPOSAL_DAY,
            hour=settings.SCHED_MONTHLY_PROPOSAL_HOUR,
            minute=settings.SCHED_MONTHLY_PROPOSAL_MINUTE,
            timezone=tz,
        ),
        id="monthly_proposal",
        name="月次改善提案送信",
        kwargs={"manager": manager},
        replace_existing=True,
    )

    # TODO: 3-month summary job (enable via SCHED_QUARTERLY_SUMMARY_ENABLED)
    # TODO: JRA-VAN reminder (trigger at JRAVAN_REMINDER_MONTH)

    logger.info("Registered 10 scheduler jobs")


# ---------------------------------------------------------------------------
# Job: Calendar scan
# ---------------------------------------------------------------------------

async def job_calendar(manager: SchedulerManager) -> None:
    """Scan the next N days for races and create stub records."""
    logger.info("=== Job: Calendar scan starting ===")
    try:
        from app.scheduler.http_fetcher import fetch_race_lists_multi
        from app.scraper.store import store_race_stubs

        today = _today_jst()
        days_ahead = settings.SCHED_CALENDAR_DAYS_AHEAD
        date_strings = [
            (today + timedelta(days=i)).strftime("%Y%m%d")
            for i in range(days_ahead)
        ]

        results = await fetch_race_lists_multi(date_strings)

        total_stubs = 0
        for date_str, races in results.items():
            if not races:
                continue
            race_date = date(
                int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8])
            )
            count = store_race_stubs(races, race_date)
            total_stubs += count

        detail = f"{total_stubs} stubs created across {days_ahead} days"
        logger.info("Calendar scan complete: %s", detail)
        manager.record_job_run("calendar", status="success", detail=detail)

    except Exception as e:
        logger.error("Calendar scan failed: %s", e, exc_info=True)
        manager.record_job_run("calendar", status="error", detail=str(e))


# ---------------------------------------------------------------------------
# Job: Shutuba (出馬表)
# ---------------------------------------------------------------------------

async def job_shutuba(manager: SchedulerManager) -> None:
    """Fetch shutuba for tomorrow and the day after (stub races only)."""
    logger.info("=== Job: Shutuba fetch starting ===")
    try:
        from app.scraper.netkeiba import NetkeibaScraper
        from app.scraper.store import (
            get_races_with_incomplete_entries,
            get_races_without_entries,
            store_shutuba,
        )

        today = _today_jst()
        target_dates = [today, today + timedelta(days=1), today + timedelta(days=2)]

        total_entries = 0
        total_races = 0
        failed_races = 0
        total_attempted = 0

        for target_date in target_dates:
            stub_ids = get_races_without_entries(target_date)
            incomplete_ids = get_races_with_incomplete_entries(target_date)
            race_ids = list(dict.fromkeys(stub_ids + incomplete_ids))  # dedupe, keep order
            if not race_ids:
                logger.info("No stub/incomplete races for %s, skipping", target_date)
                continue
            if incomplete_ids:
                logger.info(
                    "Found %d incomplete races for %s: %s",
                    len(incomplete_ids),
                    target_date,
                    incomplete_ids,
                )

            logger.info(
                "Fetching shutuba for %d races on %s",
                len(race_ids),
                target_date,
            )
            total_attempted += len(race_ids)

            async with NetkeibaScraper(headless=True) as nk:
                # Get race_list for post_time merging
                date_compact = target_date.strftime("%Y%m%d")
                race_list = await nk.scrape_race_list(date_compact)
                race_list_map = {r["race_id"]: r for r in race_list}

                for race_id in race_ids:
                    try:
                        shutuba = await nk.scrape_shutuba(race_id)
                        # Merge post_time from race_list
                        rl = race_list_map.get(race_id, {})
                        if rl.get("post_time"):
                            shutuba["post_time"] = rl["post_time"]
                        if rl.get("race_name") and not shutuba.get("race_name"):
                            shutuba["race_name"] = rl["race_name"]
                        count = store_shutuba(shutuba, target_date)
                        total_entries += count
                        total_races += 1
                    except Exception as e:
                        failed_races += 1
                        logger.warning(
                            "Failed shutuba for %s: %s", race_id, e,
                            exc_info=True,
                        )

        # Determine status based on success/failure ratio
        detail = f"{total_entries} entries across {total_races}/{total_attempted} races"
        if failed_races > 0:
            detail += f" ({failed_races} failed)"

        if total_attempted == 0:
            status = "skipped"
            detail = "No races to fetch"
        elif failed_races == total_attempted:
            status = "error"
        elif failed_races > 0:
            status = "partial"
        else:
            status = "success"

        logger.info("Shutuba fetch complete [%s]: %s", status, detail)
        manager.record_job_run("shutuba", status=status, detail=detail)

        # Verification: check for remaining races without entries
        remaining_ids = []
        for target_date in target_dates:
            remaining_ids.extend(get_races_without_entries(target_date))
        if remaining_ids:
            logger.warning(
                "Shutuba verification: %d races still without entries: %s",
                len(remaining_ids),
                remaining_ids[:10],  # Log first 10 to avoid huge output
            )
        else:
            logger.info("Shutuba verification: all target races have entries")

    except Exception as e:
        logger.error("Shutuba fetch failed: %s", e, exc_info=True)
        manager.record_job_run("shutuba", status="error", detail=str(e))


# ---------------------------------------------------------------------------
# Job: Odds
# ---------------------------------------------------------------------------

async def job_odds(manager: SchedulerManager) -> None:
    """Fetch odds for today's races (skip if no races today)."""
    logger.info("=== Job: Odds fetch starting ===")
    try:
        from app.scraper.netkeiba import NetkeibaScraper
        from app.scraper.store import get_race_ids_for_date, store_odds

        today = _today_jst()
        race_ids = get_race_ids_for_date(today)

        if not race_ids:
            logger.info("No races today, skipping odds")
            manager.record_job_run(
                "odds", status="skipped", detail="No races today"
            )
            return

        total_odds = 0
        failed_count = 0
        async with NetkeibaScraper(headless=True) as nk:
            for race_id in race_ids:
                try:
                    odds = await nk.scrape_odds(race_id)
                    count = store_odds(odds, race_id)
                    total_odds += count
                except Exception as e:
                    failed_count += 1
                    logger.warning("Failed odds for %s: %s", race_id, e, exc_info=True)

        detail = f"{total_odds} odds for {len(race_ids)} races"
        if failed_count > 0:
            detail += f" ({failed_count} failed)"

        if failed_count == len(race_ids):
            status = "error"
        elif failed_count > 0:
            status = "partial"
        else:
            status = "success"

        logger.info("Odds fetch complete [%s]: %s", status, detail)
        manager.record_job_run("odds", status=status, detail=detail)

    except Exception as e:
        logger.error("Odds fetch failed: %s", e, exc_info=True)
        manager.record_job_run("odds", status="error", detail=str(e))


# ---------------------------------------------------------------------------
# Job: Results
# ---------------------------------------------------------------------------

def _find_predict_target_date() -> date | None:
    """Find the best date for prediction.

    Priority:
      1. Nearest future date (today or later) with entries (stub_only=False)
      2. Most recent past date with entries but no predictions yet

    Returns None if no suitable date is found.
    """
    from sqlalchemy import and_, create_engine, func, select
    from sqlalchemy.orm import Session as SyncSession

    from app.models import PredictionLog, Race

    today = _today_jst()
    engine = create_engine(settings.database_url_sync)
    try:
        with SyncSession(engine) as session:
            # 1. Nearest upcoming date with entries
            upcoming = session.execute(
                select(Race.race_date)
                .where(
                    and_(
                        Race.race_date >= today,
                        Race.stub_only == False,  # noqa: E712
                    )
                )
                .order_by(Race.race_date)
                .limit(1)
            ).scalar_one_or_none()

            if upcoming:
                return upcoming

            # 2. Most recent past date with entries but no predictions
            pred_subq = (
                select(func.count(PredictionLog.id))
                .where(PredictionLog.race_id == Race.id)
                .correlate(Race)
                .scalar_subquery()
            )
            past_unpredicted = session.execute(
                select(Race.race_date)
                .where(
                    and_(
                        Race.stub_only == False,  # noqa: E712
                        pred_subq == 0,
                    )
                )
                .order_by(Race.race_date.desc())
                .limit(1)
            ).scalar_one_or_none()

            return past_unpredicted
    finally:
        engine.dispose()


async def job_predict(manager: SchedulerManager) -> None:
    """Generate AI predictions for upcoming races.

    Auto-detects the nearest race date (today or later) that has entries.
    Falls back to tomorrow if no upcoming race date is found in the DB.
    """
    logger.info("=== Job: Prediction starting ===")
    try:
        from app.ml.predictor import predict_race

        target_date = _find_predict_target_date()
        if target_date is None:
            logger.info("No races with entries found for prediction")
            manager.record_job_run(
                "predict", status="skipped", detail="No races with entries found"
            )
            return

        logger.info("Prediction target date: %s", target_date)
        model_version = settings.SCHED_PREDICT_MODEL_VERSION

        results = await asyncio.to_thread(
            predict_race,
            version=model_version,
            target_date=target_date,
            save_to_db=True,
        )

        if not results:
            manager.record_job_run(
                "predict", status="skipped", detail=f"No races on {target_date}"
            )
            return

        unique_races = len({r["race_id_str"] for r in results})
        detail = f"{len(results)} predictions across {unique_races} races ({target_date})"
        logger.info("Prediction complete: %s", detail)
        manager.record_job_run("predict", status="success", detail=detail)

    except Exception as e:
        logger.error("Prediction failed: %s", e, exc_info=True)
        manager.record_job_run("predict", status="error", detail=str(e))


# ---------------------------------------------------------------------------
# Job: Results
# ---------------------------------------------------------------------------

async def job_results(manager: SchedulerManager) -> None:
    """Fetch results for today's and recent past races that don't have results yet.

    Checks today and the past 3 days to catch results that were missed
    (e.g., due to delayed posting on netkeiba or server downtime).
    """
    logger.info("=== Job: Results fetch starting ===")
    try:
        from app.scraper.netkeiba import NetkeibaScraper
        from app.scraper.store import get_races_needing_results, store_result

        today = _today_jst()
        # Check today + past 3 days for uncollected results
        target_dates = [today - timedelta(days=i) for i in range(4)]

        all_race_ids: list[str] = []
        for d in target_dates:
            ids = get_races_needing_results(d)
            all_race_ids.extend(ids)

        # Deduplicate while preserving order
        race_ids = list(dict.fromkeys(all_race_ids))

        if not race_ids:
            logger.info("No races needing results, skipping")
            manager.record_job_run(
                "results", status="skipped", detail="No races needing results"
            )
            return

        total_results = 0
        failed_count = 0
        async with NetkeibaScraper(headless=True) as nk:
            for race_id in race_ids:
                try:
                    result = await nk.scrape_result(race_id)
                    count = store_result(result)
                    total_results += count
                except Exception as e:
                    failed_count += 1
                    logger.warning("Failed result for %s: %s", race_id, e, exc_info=True)

        detail = f"{total_results} results for {len(race_ids)} races"
        if failed_count > 0:
            detail += f" ({failed_count} failed)"

        if failed_count == len(race_ids):
            status = "error"
        elif failed_count > 0:
            status = "partial"
        else:
            status = "success"

        logger.info("Results fetch complete [%s]: %s", status, detail)
        manager.record_job_run("results", status=status, detail=detail)

    except Exception as e:
        logger.error("Results fetch failed: %s", e, exc_info=True)
        manager.record_job_run("results", status="error", detail=str(e))


# ---------------------------------------------------------------------------
# Job: Notify prediction
# ---------------------------------------------------------------------------

def _find_latest_predicted_date() -> date | None:
    """Find the most recent date that has predictions in the DB.

    Priority:
      1. Nearest future date (today or later) with predictions
      2. Most recent past date with predictions
    """
    from sqlalchemy import and_, create_engine, select

    from app.models import PredictionLog, Race

    today = _today_jst()
    engine = create_engine(settings.database_url_sync)
    try:
        from sqlalchemy.orm import Session as SyncSession

        with SyncSession(engine) as session:
            # 1. Nearest upcoming date with predictions
            upcoming = session.execute(
                select(Race.race_date)
                .join(PredictionLog, PredictionLog.race_id == Race.id)
                .where(Race.race_date >= today)
                .order_by(Race.race_date)
                .limit(1)
            ).scalar_one_or_none()

            if upcoming:
                return upcoming

            # 2. Most recent past date with predictions
            past = session.execute(
                select(Race.race_date)
                .join(PredictionLog, PredictionLog.race_id == Race.id)
                .order_by(Race.race_date.desc())
                .limit(1)
            ).scalar_one_or_none()

            return past
    finally:
        engine.dispose()


async def job_notify_prediction(manager: SchedulerManager) -> None:
    """Send LINE notification with the latest AI prediction summary.

    Finds the nearest date that has predictions (generated by job_predict).
    """
    logger.info("=== Job: Notify prediction starting ===")
    try:
        from sqlalchemy import and_, select
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

        from app.models.entry import RaceEntry
        from app.models.horse import Horse
        from app.models.prediction import PredictionLog
        from app.models.race import Race
        from app.services.notification_service import get_notification_service

        svc = get_notification_service()
        if not svc.is_configured:
            logger.info("LINE not configured, skipping notify_prediction")
            manager.record_job_run(
                "notify_prediction", status="skipped", detail="LINE not configured"
            )
            return

        # Find the nearest date that has predictions
        target_date = await asyncio.to_thread(_find_latest_predicted_date)
        if target_date is None:
            logger.info("No predictions found in database")
            manager.record_job_run(
                "notify_prediction", status="skipped",
                detail="No predictions found",
            )
            return

        logger.info("Notify prediction target date: %s", target_date)

        engine = create_async_engine(settings.database_url)
        async with AsyncSession(engine) as session:
            # Get prediction logs joined with horse info via race_id + horse_id
            stmt = (
                select(PredictionLog, Race, RaceEntry, Horse)
                .join(Race, PredictionLog.race_id == Race.id)
                .join(
                    RaceEntry,
                    and_(
                        RaceEntry.race_id == PredictionLog.race_id,
                        RaceEntry.horse_id == PredictionLog.horse_id,
                    ),
                )
                .join(Horse, PredictionLog.horse_id == Horse.id)
                .where(Race.race_date == target_date)
                .order_by(Race.race_id, PredictionLog.predicted_score.desc())
            )
            rows = (await session.execute(stmt)).all()
        await engine.dispose()

        if not rows:
            logger.info("No predictions for %s", target_date)
            manager.record_job_run(
                "notify_prediction", status="skipped",
                detail=f"No predictions for {target_date}",
            )
            return

        # Group by race
        races_map: dict[str, dict] = {}
        for pred, race, entry, horse in rows:
            rid = race.race_id
            if rid not in races_map:
                races_map[rid] = {
                    "race_name": race.race_name or "",
                    "racecourse_name": race.racecourse_name or "",
                    "race_number": race.race_number or 0,
                    "top_horses": [],
                }
            if len(races_map[rid]["top_horses"]) < 3:
                races_map[rid]["top_horses"].append({
                    "name": horse.name,
                    "score": float(pred.predicted_score or 0),
                    "odds": str(entry.win_odds or "-"),
                })

        predictions = list(races_map.values())
        sent = await svc.push_prediction_notification(predictions)

        detail = f"Sent prediction for {len(predictions)} races ({target_date})" if sent else "Send failed"
        status = "success" if sent else "error"
        logger.info("Notify prediction: %s", detail)
        manager.record_job_run("notify_prediction", status=status, detail=detail)

    except Exception as e:
        logger.error("Notify prediction failed: %s", e, exc_info=True)
        manager.record_job_run("notify_prediction", status="error", detail=str(e))


# ---------------------------------------------------------------------------
# Job: Notify results
# ---------------------------------------------------------------------------

async def job_notify_results(manager: SchedulerManager) -> None:
    """Send LINE notification with today's race results summary + miss confirmations."""
    logger.info("=== Job: Notify results starting ===")
    try:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

        from app.models.entry import RaceEntry
        from app.models.horse import Horse
        from app.models.prediction import PredictionLog
        from app.models.race import Race
        from app.services.notification_service import get_notification_service

        svc = get_notification_service()
        if not svc.is_configured:
            logger.info("LINE not configured, skipping notify_results")
            manager.record_job_run(
                "notify_results", status="skipped", detail="LINE not configured"
            )
            return

        today = _today_jst()

        engine = create_async_engine(settings.database_url)
        async with AsyncSession(engine) as session:
            # Get races with results for today
            stmt = (
                select(Race)
                .where(Race.race_date == today)
                .where(Race.stub_only == False)  # noqa: E712
                .order_by(Race.race_id)
            )
            races = (await session.execute(stmt)).scalars().all()

            if not races:
                logger.info("No race results for %s", today)
                await engine.dispose()
                manager.record_job_run(
                    "notify_results", status="skipped",
                    detail=f"No results for {today}",
                )
                return

            results_data = []
            miss_candidates = []  # Races where AI top-1 missed fukusho

            for race in races:
                race_id_int = race.id
                # Get top 3 finishers
                entry_stmt = (
                    select(RaceEntry, Horse)
                    .join(Horse, RaceEntry.horse_id == Horse.id)
                    .where(RaceEntry.race_id == race_id_int)
                    .where(RaceEntry.finish_position.isnot(None))
                    .order_by(RaceEntry.finish_position)
                    .limit(3)
                )
                top3_rows = (await session.execute(entry_stmt)).all()

                results_data.append({
                    "race_name": race.race_name or "",
                    "racecourse_name": race.racecourse_name or "",
                    "race_number": race.race_number or 0,
                    "bet_result": "none",
                    "top3": [
                        {"position": e.finish_position, "name": h.name}
                        for e, h in top3_rows
                    ],
                })

                # Check if AI top-1 missed fukusho (not in top 3)
                pred_stmt = (
                    select(PredictionLog, Horse)
                    .join(Horse, PredictionLog.horse_id == Horse.id)
                    .where(PredictionLog.race_id == race_id_int)
                    .order_by(PredictionLog.predicted_score.desc())
                    .limit(3)
                )
                pred_rows = (await session.execute(pred_stmt)).all()

                if pred_rows:
                    ai_top1_horse_id = pred_rows[0][0].horse_id
                    finish_stmt = (
                        select(RaceEntry.finish_position)
                        .where(
                            RaceEntry.race_id == race_id_int,
                            RaceEntry.horse_id == ai_top1_horse_id,
                        )
                    )
                    finish_pos = (await session.execute(finish_stmt)).scalar()

                    if finish_pos is None or finish_pos > 3:
                        actual_top3_names = [h.name for _, h in top3_rows[:3]]
                        ai_top3_names = [h.name for _, h in pred_rows[:3]]
                        # Auto-detect reason from race data
                        auto_reason = _auto_detect_miss_reason(race, finish_pos)
                        miss_candidates.append({
                            "race_name": f"{race.racecourse_name or ''} {race.race_number or ''}R {race.race_name or ''}",
                            "race_id": race.race_id,
                            "ai_top3": ai_top3_names,
                            "actual_top3": actual_top3_names,
                            "auto_reason": auto_reason,
                        })

                        # Auto-save to miss_reason_logs
                        from app.models.miss_reason import MissReasonLog
                        log = MissReasonLog(
                            race_id=race.id,
                            bet_type="fukusho",
                            reason=auto_reason,
                        )
                        session.add(log)

            await session.commit()
        await engine.dispose()

        # Send results notification
        sent = await svc.push_results_notification(results_data)

        # Send miss summary (single message, max 5 races)
        miss_sent = False
        if miss_candidates:
            try:
                miss_sent = await svc.push_miss_summary(miss_candidates[:5])
            except Exception as e:
                logger.warning("Failed to send miss summary: %s", e)

        detail = f"Sent results for {len(results_data)} races"
        if miss_candidates:
            detail += f", {len(miss_candidates)} misses"
            if miss_sent:
                detail += " (summary sent)"
        status = "success" if sent else "error"
        logger.info("Notify results: %s", detail)
        manager.record_job_run("notify_results", status=status, detail=detail)

    except Exception as e:
        logger.error("Notify results failed: %s", e, exc_info=True)
        manager.record_job_run("notify_results", status="error", detail=str(e))


# ---------------------------------------------------------------------------
# Job: Weekly report
# ---------------------------------------------------------------------------

async def job_weekly_report(manager: SchedulerManager) -> None:
    """Send weekly performance report via LINE."""
    logger.info("=== Job: Weekly report starting ===")
    try:
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

        from app.services.notification_service import get_notification_service
        from app.services.weekly_report_service import build_weekly_report_data

        svc = get_notification_service()
        if not svc.is_configured:
            logger.info("LINE not configured, skipping weekly_report")
            manager.record_job_run(
                "weekly_report", status="skipped", detail="LINE not configured"
            )
            return

        engine = create_async_engine(settings.database_url)
        async with AsyncSession(engine) as session:
            report = await build_weekly_report_data(session)
        await engine.dispose()

        sent = await svc.push_weekly_report(report)

        detail = f"Weekly report sent ({report.get('period', '')})" if sent else "Send failed"
        status = "success" if sent else "error"
        logger.info("Weekly report: %s", detail)
        manager.record_job_run("weekly_report", status=status, detail=detail)

    except Exception as e:
        logger.error("Weekly report failed: %s", e, exc_info=True)
        manager.record_job_run("weekly_report", status="error", detail=str(e))


# ---------------------------------------------------------------------------
# Job: Monthly proposal
# ---------------------------------------------------------------------------

async def job_monthly_proposal(manager: SchedulerManager) -> None:
    """Generate and send monthly improvement proposals via LINE."""
    logger.info("=== Job: Monthly proposal starting ===")
    try:
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

        from app.models.improvement_proposal import ImprovementProposal
        from app.services.monthly_proposal_service import generate_monthly_proposals
        from app.services.notification_service import get_notification_service

        svc = get_notification_service()
        if not svc.is_configured:
            logger.info("LINE not configured, skipping monthly_proposal")
            manager.record_job_run(
                "monthly_proposal", status="skipped", detail="LINE not configured"
            )
            return

        engine = create_async_engine(settings.database_url)
        async with AsyncSession(engine) as session:
            proposals = await generate_monthly_proposals(session)

            if not proposals:
                logger.info("No monthly proposals generated")
                await engine.dispose()
                manager.record_job_run(
                    "monthly_proposal", status="skipped", detail="No proposals"
                )
                return

            # Save proposals to DB
            import datetime
            today = _today_jst()
            last_month = (today.replace(day=1) - timedelta(days=1))
            month_date = last_month.replace(day=1)

            saved_proposals = []
            for p in proposals:
                db_proposal = ImprovementProposal(
                    month=month_date,
                    proposal_type=p["proposal_type"],
                    description=p["description"],
                    status="pending",
                )
                session.add(db_proposal)
                await session.flush()
                saved_proposals.append({
                    "id": str(db_proposal.id),
                    "proposal_type": p["proposal_type"],
                    "description": p["description"],
                    "priority": p.get("priority", 99),
                })
            await session.commit()
        await engine.dispose()

        sent = await svc.push_monthly_proposal(saved_proposals)

        detail = f"Sent {len(saved_proposals)} proposals" if sent else "Send failed"
        status = "success" if sent else "error"
        logger.info("Monthly proposal: %s", detail)
        manager.record_job_run("monthly_proposal", status=status, detail=detail)

    except Exception as e:
        logger.error("Monthly proposal failed: %s", e, exc_info=True)
        manager.record_job_run("monthly_proposal", status="error", detail=str(e))
