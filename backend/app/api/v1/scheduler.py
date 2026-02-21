"""Scheduler API endpoints for status, manual trigger, pause/resume."""

from fastapi import APIRouter, HTTPException

from app.scheduler.scheduler import scheduler_manager
from app.schemas.scheduler import SchedulerStatusResponse, TriggerResponse

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.get("/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status():
    """Get current scheduler status and job info."""
    return scheduler_manager.get_status()


@router.post("/jobs/{job_id}/trigger", response_model=TriggerResponse)
async def trigger_job(job_id: str):
    """Manually trigger a specific job."""
    success = await scheduler_manager.trigger_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return TriggerResponse(success=True, message=f"Job '{job_id}' triggered")


@router.post("/pause", response_model=TriggerResponse)
async def pause_scheduler():
    """Pause all scheduled jobs."""
    scheduler_manager.pause()
    return TriggerResponse(success=True, message="Scheduler paused")


@router.post("/resume", response_model=TriggerResponse)
async def resume_scheduler():
    """Resume all scheduled jobs."""
    scheduler_manager.resume()
    return TriggerResponse(success=True, message="Scheduler resumed")
