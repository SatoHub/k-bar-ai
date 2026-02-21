"""APScheduler lifecycle management and status tracking."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings

logger = logging.getLogger(__name__)


class SchedulerManager:
    """Singleton-style scheduler wrapper with status tracking."""

    def __init__(self) -> None:
        self._scheduler: AsyncIOScheduler | None = None
        self._job_history: dict[str, dict[str, Any]] = {}
        self._paused: bool = False

    @property
    def is_running(self) -> bool:
        return self._scheduler is not None and self._scheduler.running

    @property
    def is_paused(self) -> bool:
        return self._paused

    def record_job_run(
        self, job_name: str, *, status: str = "success", detail: str = ""
    ) -> None:
        self._job_history[job_name] = {
            "last_run": datetime.utcnow().isoformat(),
            "status": status,
            "detail": detail,
        }

    def get_status(self) -> dict[str, Any]:
        jobs_info = []
        if self._scheduler:
            for job in self._scheduler.get_jobs():
                next_run = job.next_run_time
                jobs_info.append(
                    {
                        "id": job.id,
                        "name": job.name or job.id,
                        "next_run": next_run.isoformat() if next_run else None,
                        "last_run": self._job_history.get(job.id, {}).get(
                            "last_run"
                        ),
                        "last_status": self._job_history.get(job.id, {}).get(
                            "status"
                        ),
                        "last_detail": self._job_history.get(job.id, {}).get(
                            "detail"
                        ),
                    }
                )

        return {
            "running": self.is_running,
            "paused": self._paused,
            "timezone": settings.SCHEDULER_TIMEZONE,
            "jobs": jobs_info,
        }

    async def start(self) -> None:
        if self._scheduler and self._scheduler.running:
            logger.warning("Scheduler already running")
            return

        from app.scheduler.jobs import register_jobs

        self._scheduler = AsyncIOScheduler(
            timezone=settings.SCHEDULER_TIMEZONE,
        )

        register_jobs(self._scheduler, self)
        self._scheduler.start()
        self._paused = False
        logger.info("Scheduler started with timezone=%s", settings.SCHEDULER_TIMEZONE)

    async def shutdown(self) -> None:
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler shut down")
        self._scheduler = None

    def pause(self) -> None:
        if self._scheduler:
            self._scheduler.pause()
            self._paused = True
            logger.info("Scheduler paused")

    def resume(self) -> None:
        if self._scheduler:
            self._scheduler.resume()
            self._paused = False
            logger.info("Scheduler resumed")

    async def trigger_job(self, job_id: str) -> bool:
        if not self._scheduler:
            return False
        job = self._scheduler.get_job(job_id)
        if not job:
            return False
        job.modify(next_run_time=datetime.now())
        logger.info("Manually triggered job: %s", job_id)
        return True


# Global singleton
scheduler_manager = SchedulerManager()
