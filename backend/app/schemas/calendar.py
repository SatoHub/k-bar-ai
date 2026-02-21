import datetime

from pydantic import BaseModel


class CalendarDay(BaseModel):
    date: datetime.date
    race_count: int
    has_entries: bool = False


class CalendarResponse(BaseModel):
    year_month: str
    days: list[CalendarDay]
