"""Scraper API endpoints — trigger scraping from the frontend."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import time
from datetime import timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scraper", tags=["scraper"])

# In-memory lock with timestamp to auto-expire stale locks (15 min timeout)
_running: dict[str, float] = {}  # key -> start timestamp
_LOCK_TIMEOUT_SECONDS = 15 * 60  # 15 minutes


def _today_jst() -> dt.date:
    return dt.datetime.now(ZoneInfo("Asia/Tokyo")).date()


def _parse_date(date_str: str | None) -> dt.date:
    if date_str:
        try:
            return dt.date.fromisoformat(date_str)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="日付の形式が不正です (YYYY-MM-DD)"
            )
    return _today_jst()


def _is_running(key: str) -> bool:
    """Check if a task is running, auto-expiring stale locks."""
    started = _running.get(key)
    if started is None:
        return False
    if time.monotonic() - started > _LOCK_TIMEOUT_SECONDS:
        logger.warning("Lock expired for %s (started %.0fs ago), releasing", key, time.monotonic() - started)
        _running.pop(key, None)
        return False
    return True


def _try_start(key: str, label: str) -> ScrapeResponse | None:
    """Return a 'already running' response if key is active, else mark it."""
    if _is_running(key):
        return ScrapeResponse(success=False, message=f"{label}は現在実行中です。")
    _running[key] = time.monotonic()
    return None


class ScrapeRequest(BaseModel):
    date: str | None = None  # YYYY-MM-DD, default: today JST


class ScrapeResponse(BaseModel):
    success: bool
    message: str


class TaskStatusResponse(BaseModel):
    date: str
    running: bool
    last_status: str | None = None
    last_entries: int | None = None
    last_finished: str | None = None


def _query_scrape_log(task_type: str, date_obj: dt.date) -> dict:
    """Query ScrapeLog for the latest entry of a given type+date."""
    try:
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        from app.models.scrape_log import ScrapeLog
        from app.scraper.store import _get_engine

        engine = _get_engine()
        with Session(engine) as session:
            stmt = (
                select(ScrapeLog)
                .where(ScrapeLog.task_type == task_type)
                .where(ScrapeLog.target_date == date_obj)
                .order_by(ScrapeLog.started_at.desc())
                .limit(1)
            )
            log = session.execute(stmt).scalar_one_or_none()
            if log:
                return {
                    "last_status": log.status,
                    "last_entries": log.records_affected,
                    "last_finished": log.finished_at.isoformat()
                    if log.finished_at
                    else None,
                }
    except Exception as e:
        logger.warning("Failed to check scrape log: %s", e)
    return {"last_status": None, "last_entries": None, "last_finished": None}


# =========================================================================
# 1. Shutuba (出馬表)
# =========================================================================


async def _run_shutuba(target_date: dt.date) -> None:
    key = f"shutuba:{target_date.isoformat()}"
    try:
        from app.scraper.netkeiba import NetkeibaScraper
        from app.scraper.store import store_shutuba

        date_compact = target_date.strftime("%Y%m%d")
        async with NetkeibaScraper(headless=True) as nk:
            race_list = await nk.scrape_race_list(date_compact)
            logger.info("Scraper[shutuba]: %d races for %s", len(race_list), target_date)
            if not race_list:
                return
            total = 0
            failed = 0
            for ri in race_list:
                try:
                    shutuba = await nk.scrape_shutuba(ri["race_id"])
                    if ri.get("post_time"):
                        shutuba["post_time"] = ri["post_time"]
                    if ri.get("race_name") and not shutuba.get("race_name"):
                        shutuba["race_name"] = ri["race_name"]
                    total += store_shutuba(shutuba, target_date)
                except Exception as e:
                    failed += 1
                    logger.warning("shutuba %s: %s", ri["race_id"], e, exc_info=True)
        if failed > 0:
            logger.error(
                "Scraper[shutuba]: stored %d entries for %s (%d/%d races FAILED)",
                total, target_date, failed, len(race_list),
            )
        else:
            logger.info("Scraper[shutuba]: stored %d entries for %s (all %d races OK)", total, target_date, len(race_list))
    except Exception as e:
        logger.error("Scraper[shutuba] failed: %s", e, exc_info=True)
    finally:
        _running.pop(key, None)


@router.post("/shutuba", response_model=ScrapeResponse)
async def scrape_shutuba(req: ScrapeRequest, bg: BackgroundTasks):
    """出馬表を取得（バックグラウンド実行）"""
    target = _parse_date(req.date)
    key = f"shutuba:{target.isoformat()}"
    if dup := _try_start(key, f"{target} の出馬表取得"):
        return dup
    bg.add_task(_run_shutuba, target)
    return ScrapeResponse(
        success=True,
        message=f"{target} の出馬表を取得開始しました。完了まで数分かかります。",
    )


@router.get("/shutuba/status", response_model=TaskStatusResponse)
async def shutuba_status(target_date: str | None = Query(None, alias="date")):
    date_obj = _parse_date(target_date)
    key = f"shutuba:{date_obj.isoformat()}"
    info = _query_scrape_log("shutuba", date_obj)
    return TaskStatusResponse(date=date_obj.isoformat(), running=_is_running(key), **info)


# =========================================================================
# 2. Odds (オッズ)
# =========================================================================


async def _run_odds(target_date: dt.date) -> None:
    key = f"odds:{target_date.isoformat()}"
    try:
        from app.scraper.netkeiba import NetkeibaScraper
        from app.scraper.store import get_race_ids_for_date, store_odds

        race_ids = get_race_ids_for_date(target_date)
        if not race_ids:
            logger.info("Scraper[odds]: no races for %s", target_date)
            return

        total = 0
        async with NetkeibaScraper(headless=True) as nk:
            for race_id in race_ids:
                try:
                    odds = await nk.scrape_odds(race_id)
                    total += store_odds(odds, race_id)
                except Exception as e:
                    logger.warning("odds %s: %s", race_id, e)
        logger.info("Scraper[odds]: stored %d odds for %s", total, target_date)
    except Exception as e:
        logger.error("Scraper[odds] failed: %s", e, exc_info=True)
    finally:
        _running.pop(key, None)


@router.post("/odds", response_model=ScrapeResponse)
async def scrape_odds(req: ScrapeRequest, bg: BackgroundTasks):
    """オッズを取得（バックグラウンド実行）"""
    target = _parse_date(req.date)
    key = f"odds:{target.isoformat()}"
    if dup := _try_start(key, f"{target} のオッズ取得"):
        return dup
    bg.add_task(_run_odds, target)
    return ScrapeResponse(
        success=True,
        message=f"{target} のオッズを取得開始しました。",
    )


@router.get("/odds/status", response_model=TaskStatusResponse)
async def odds_status(target_date: str | None = Query(None, alias="date")):
    date_obj = _parse_date(target_date)
    key = f"odds:{date_obj.isoformat()}"
    info = _query_scrape_log("odds", date_obj)
    return TaskStatusResponse(date=date_obj.isoformat(), running=_is_running(key), **info)


# =========================================================================
# 3. Results (レース結果)
# =========================================================================


async def _run_results(target_date: dt.date) -> None:
    key = f"results:{target_date.isoformat()}"
    try:
        from app.scraper.netkeiba import NetkeibaScraper
        from app.scraper.store import get_race_ids_for_date, store_result

        race_ids = get_race_ids_for_date(target_date)
        if not race_ids:
            logger.info("Scraper[results]: no races for %s", target_date)
            return

        total = 0
        async with NetkeibaScraper(headless=True) as nk:
            for race_id in race_ids:
                try:
                    result = await nk.scrape_result(race_id)
                    total += store_result(result)
                except Exception as e:
                    logger.warning("result %s: %s", race_id, e)
        logger.info("Scraper[results]: stored %d results for %s", total, target_date)
    except Exception as e:
        logger.error("Scraper[results] failed: %s", e, exc_info=True)
    finally:
        _running.pop(key, None)


@router.post("/results", response_model=ScrapeResponse)
async def scrape_results(req: ScrapeRequest, bg: BackgroundTasks):
    """レース結果を取得（バックグラウンド実行）"""
    target = _parse_date(req.date)
    key = f"results:{target.isoformat()}"
    if dup := _try_start(key, f"{target} の結果取得"):
        return dup
    bg.add_task(_run_results, target)
    return ScrapeResponse(
        success=True,
        message=f"{target} のレース結果を取得開始しました。",
    )


@router.get("/results/status", response_model=TaskStatusResponse)
async def results_status(target_date: str | None = Query(None, alias="date")):
    date_obj = _parse_date(target_date)
    key = f"results:{date_obj.isoformat()}"
    info = _query_scrape_log("result", date_obj)
    return TaskStatusResponse(date=date_obj.isoformat(), running=_is_running(key), **info)


# =========================================================================
# 4. Predict (AI予想)
# =========================================================================


async def _run_predict(target_date: dt.date) -> None:
    key = f"predict:{target_date.isoformat()}"
    try:
        from app.ml.predictor import predict_race

        model_version = settings.SCHED_PREDICT_MODEL_VERSION
        results = await asyncio.to_thread(
            predict_race,
            version=model_version,
            target_date=target_date,
            save_to_db=True,
        )
        if results:
            unique_races = len({r["race_id_str"] for r in results})
            logger.info(
                "Scraper[predict]: %d predictions across %d races for %s",
                len(results), unique_races, target_date,
            )
        else:
            logger.info("Scraper[predict]: no races to predict for %s", target_date)
    except Exception as e:
        logger.error("Scraper[predict] failed: %s", e, exc_info=True)
    finally:
        _running.pop(key, None)


@router.post("/predict", response_model=ScrapeResponse)
async def run_predict(req: ScrapeRequest, bg: BackgroundTasks):
    """AI予想を実行（バックグラウンド実行）"""
    target = _parse_date(req.date)
    key = f"predict:{target.isoformat()}"
    if dup := _try_start(key, f"{target} のAI予想"):
        return dup
    bg.add_task(_run_predict, target)
    return ScrapeResponse(
        success=True,
        message=f"{target} のAI予想を実行開始しました。",
    )


@router.get("/predict/status", response_model=TaskStatusResponse)
async def predict_status(target_date: str | None = Query(None, alias="date")):
    date_obj = _parse_date(target_date)
    key = f"predict:{date_obj.isoformat()}"
    # Predictions don't use ScrapeLog — just check running flag
    return TaskStatusResponse(
        date=date_obj.isoformat(),
        running=_is_running(key),
    )


# =========================================================================
# 5. Calendar (カレンダースキャン)
# =========================================================================


async def _run_calendar() -> None:
    key = "calendar"
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
        total = 0
        for date_str, races in results.items():
            if not races:
                continue
            race_date = dt.date(
                int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8])
            )
            total += store_race_stubs(races, race_date)
        logger.info("Scraper[calendar]: %d stubs across %d days", total, days_ahead)
    except Exception as e:
        logger.error("Scraper[calendar] failed: %s", e, exc_info=True)
    finally:
        _running.pop(key, None)


@router.post("/calendar", response_model=ScrapeResponse)
async def scan_calendar(bg: BackgroundTasks):
    """カレンダースキャン（今後14日分のレース予定を取得）"""
    key = "calendar"
    if dup := _try_start(key, "カレンダースキャン"):
        return dup
    bg.add_task(_run_calendar)
    return ScrapeResponse(
        success=True,
        message=f"今後{settings.SCHED_CALENDAR_DAYS_AHEAD}日分のカレンダースキャンを開始しました。",
    )


@router.get("/calendar/status", response_model=TaskStatusResponse)
async def calendar_status():
    key = "calendar"
    return TaskStatusResponse(
        date=_today_jst().isoformat(),
        running=_is_running(key),
    )


# =========================================================================
# 6. Run All (一括実行)
# =========================================================================


async def _run_all(target_date: dt.date) -> None:
    """Run calendar → shutuba → odds → predict sequentially."""
    key = "all"
    try:
        # 1. Calendar scan
        logger.info("RunAll: starting calendar scan")
        from app.scheduler.http_fetcher import fetch_race_lists_multi
        from app.scraper.store import store_race_stubs

        date_compact = target_date.strftime("%Y%m%d")
        results = await fetch_race_lists_multi([date_compact])
        for ds, races in results.items():
            if races:
                race_date = dt.date(int(ds[:4]), int(ds[4:6]), int(ds[6:8]))
                store_race_stubs(races, race_date)
        logger.info("RunAll: calendar done")

        # 2. Shutuba
        logger.info("RunAll: starting shutuba")
        from app.scraper.netkeiba import NetkeibaScraper
        from app.scraper.store import store_shutuba, get_race_ids_for_date, store_odds

        async with NetkeibaScraper(headless=True) as nk:
            race_list = await nk.scrape_race_list(date_compact)
            for ri in race_list:
                try:
                    shutuba = await nk.scrape_shutuba(ri["race_id"])
                    if ri.get("post_time"):
                        shutuba["post_time"] = ri["post_time"]
                    if ri.get("race_name") and not shutuba.get("race_name"):
                        shutuba["race_name"] = ri["race_name"]
                    store_shutuba(shutuba, target_date)
                except Exception as e:
                    logger.warning("RunAll shutuba %s: %s", ri["race_id"], e)
            logger.info("RunAll: shutuba done")

            # 3. Odds
            logger.info("RunAll: starting odds")
            race_ids = get_race_ids_for_date(target_date)
            for race_id in race_ids:
                try:
                    odds = await nk.scrape_odds(race_id)
                    store_odds(odds, race_id)
                except Exception as e:
                    logger.warning("RunAll odds %s: %s", race_id, e)
            logger.info("RunAll: odds done")

        # 4. Predict
        logger.info("RunAll: starting predict")
        from app.ml.predictor import predict_race

        await asyncio.to_thread(
            predict_race,
            version=settings.SCHED_PREDICT_MODEL_VERSION,
            target_date=target_date,
            save_to_db=True,
        )
        logger.info("RunAll: predict done")

        logger.info("RunAll: all tasks completed for %s", target_date)
    except Exception as e:
        logger.error("RunAll failed: %s", e, exc_info=True)
    finally:
        _running.pop(key, None)


@router.post("/all", response_model=ScrapeResponse)
async def run_all(req: ScrapeRequest, bg: BackgroundTasks):
    """全データ取得を一括実行（カレンダー→出馬表→オッズ→AI予想）"""
    target = _parse_date(req.date)
    key = "all"
    if dup := _try_start(key, "一括実行"):
        return dup
    bg.add_task(_run_all, target)
    return ScrapeResponse(
        success=True,
        message=f"{target} の全データ取得を開始しました。完了まで10分程度かかります。",
    )


@router.get("/all/status", response_model=TaskStatusResponse)
async def all_status():
    key = "all"
    return TaskStatusResponse(
        date=_today_jst().isoformat(),
        running=_is_running(key),
    )
