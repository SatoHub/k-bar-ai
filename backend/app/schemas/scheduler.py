from pydantic import BaseModel


class JobInfo(BaseModel):
    id: str
    name: str
    next_run: str | None = None
    last_run: str | None = None
    last_status: str | None = None
    last_detail: str | None = None


class SchedulerStatusResponse(BaseModel):
    running: bool
    paused: bool
    timezone: str
    jobs: list[JobInfo]


class TriggerResponse(BaseModel):
    success: bool
    message: str
