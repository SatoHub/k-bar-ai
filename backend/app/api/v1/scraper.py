"""Scraper API endpoints — trigger scraping from the frontend."""

from __future__ import annotations

import datetime as dt
import logging
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scraper", tags=["scraper"])

# Simple in-memory lock to prevent duplicate scrapes
_running: dict[str, bool] = {}


def _today_jst() -> dt.date:
    return dt.datetime.now(ZoneInfo("Asia/Tokyo")).date()


class ScrapeRequest(BaseModel):
    date: str | None = None  # YYYY-MM-DD, default: today JST


class ScrapeResponse(BaseModel):
    success: bool
    message: str


class ScrapeStatusResponse(BaseModel):
    date: str
    running: bool
    last_status: str | None = None
    last_entries: int | None = None
    last_finished: str | None = None


async def _run_shutuba_scrape(target_date: dt.date) -> None:
    """Background task: scrape shutuba for a given date."""
    key = f"shutuba:{target_date.isoformat()}"
    try:
        from app.scraper.netkeiba import NetkeibaScraper
        from app.scraper.store import store_shutuba

        date_compact = target_date.strftime("%Y%m%d")

        async with NetkeibaScraper(headless=True) as nk:
            race_list = await nk.scrape_race_list(date_compact)
            logger.info(
                "Scraper API: Found %d races for %s", len(race_list), target_date
            )

            if not race_list:
                logger.info("Scraper API: No races found for %s", target_date)
                return

            total = 0
            for race_info in race_list:
                race_id = race_info["race_id"]
                try:
                    shutuba = await nk.scrape_shutuba(race_id)
                    if race_info.get("post_time"):
                        shutuba["post_time"] = race_info["post_time"]
                    if race_info.get("race_name") and not shutuba.get("race_name"):
                        shutuba["race_name"] = race_info["race_name"]
                    count = store_shutuba(shutuba, target_date)
                    total += count
                except Exception as e:
                    logger.warning("Failed shutuba for %s: %s", race_id, e)

        logger.info(
            "Scraper API: Stored %d entries for %s", total, target_date
        )

    except Exception as e:
        logger.error(
            "Scraper API: Failed for %s: %s", target_date, e, exc_info=True
        )
    finally:
        _running.pop(key, None)


@router.post("/shutuba", response_model=ScrapeResponse)
async def scrape_shutuba(
    req: ScrapeRequest, background_tasks: BackgroundTasks
):
    """Start shutuba scraping for a given date (runs in background)."""
    if req.date:
        try:
            target_date = dt.date.fromisoformat(req.date)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="日付の形式が不正です (YYYY-MM-DD)"
            )
    else:
        target_date = _today_jst()

    key = f"shutuba:{target_date.isoformat()}"
    if _running.get(key):
        return ScrapeResponse(
            success=False,
            message=f"{target_date} の出走馬データは現在取得中です。",
        )

    _running[key] = True
    background_tasks.add_task(_run_shutuba_scrape, target_date)

    return ScrapeResponse(
        success=True,
        message=f"{target_date} の出走馬データを取得開始しました。完了まで数分かかります。",
    )


@router.get("/shutuba/status", response_model=ScrapeStatusResponse)
async def scrape_shutuba_status(
    target_date: str | None = Query(None, alias="date"),
):
    """Check scraping status for a given date."""
    if target_date:
        try:
            date_obj = dt.date.fromisoformat(target_date)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="日付の形式が不正です (YYYY-MM-DD)"
            )
    else:
        date_obj = _today_jst()

    key = f"shutuba:{date_obj.isoformat()}"
    is_running = _running.get(key, False)

    # Check last scrape result from DB
    last_status = None
    last_entries = None
    last_finished = None
    try:
        from sqlalchemy import create_engine, select
        from sqlalchemy.orm import Session

        from app.models.scrape_log import ScrapeLog

        engine = create_engine(settings.database_url_sync, echo=False)
        with Session(engine) as session:
            stmt = (
                select(ScrapeLog)
                .where(ScrapeLog.task_type == "shutuba")
                .where(ScrapeLog.target_date == date_obj)
                .order_by(ScrapeLog.started_at.desc())
                .limit(1)
            )
            log = session.execute(stmt).scalar_one_or_none()
            if log:
                last_status = log.status
                last_entries = log.records_affected
                if log.finished_at:
                    last_finished = log.finished_at.isoformat()
        engine.dispose()
    except Exception as e:
        logger.warning("Failed to check scrape status: %s", e)

    return ScrapeStatusResponse(
        date=date_obj.isoformat(),
        running=is_running,
        last_status=last_status,
        last_entries=last_entries,
        last_finished=last_finished,
    )
