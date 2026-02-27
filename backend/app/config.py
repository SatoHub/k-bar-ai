from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"
    ALLOWED_ORIGINS: str = "http://localhost:3000"  # comma-separated for multiple

    POSTGRES_USER: str = "kbar"
    POSTGRES_PASSWORD: str = "kbar_dev_password"
    POSTGRES_DB: str = "kbar"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    KAGGLE_USERNAME: str = ""
    KAGGLE_KEY: str = ""

    LINE_CHANNEL_SECRET: str = ""
    LINE_CHANNEL_ACCESS_TOKEN: str = ""
    LINE_USER_ID: str = ""

    # Scheduler settings (cron expressions, JST)
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_TIMEZONE: str = "Asia/Tokyo"
    # Calendar scan: daily at 6:00 JST
    SCHED_CALENDAR_HOUR: int = 6
    SCHED_CALENDAR_MINUTE: int = 0
    # Shutuba fetch: morning at 9:00 JST + evening at 18:00 JST
    SCHED_SHUTUBA_MORNING_HOUR: int = 9
    SCHED_SHUTUBA_MORNING_MINUTE: int = 0
    SCHED_SHUTUBA_HOUR: int = 18
    SCHED_SHUTUBA_MINUTE: int = 0
    # Odds fetch: every 30 min from 8:00-16:30 JST
    SCHED_ODDS_START_HOUR: int = 8
    SCHED_ODDS_END_HOUR: int = 16
    SCHED_ODDS_INTERVAL_MINUTES: int = 30
    # Results fetch: at 17:00 and 19:00 JST
    SCHED_RESULTS_HOURS: str = "17,19"
    # Prediction: morning at 9:30 JST (after morning shutuba) + evening at 18:30 JST
    SCHED_PREDICT_MORNING_HOUR: int = 9
    SCHED_PREDICT_MORNING_MINUTE: int = 30
    SCHED_PREDICT_HOUR: int = 18
    SCHED_PREDICT_MINUTE: int = 30
    SCHED_PREDICT_MODEL_VERSION: str = "v1.0.0"
    # Calendar scan: how many days ahead
    SCHED_CALENDAR_DAYS_AHEAD: int = 14
    # Notification: prediction at 19:00, results at 20:00 JST
    SCHED_NOTIFY_PREDICTION_HOUR: int = 19
    SCHED_NOTIFY_PREDICTION_MINUTE: int = 0
    SCHED_NOTIFY_RESULTS_HOUR: int = 20
    SCHED_NOTIFY_RESULTS_MINUTE: int = 0
    # Weekly report: Monday at 8:00 JST
    SCHED_WEEKLY_REPORT_HOUR: int = 8
    SCHED_WEEKLY_REPORT_MINUTE: int = 0
    SCHED_WEEKLY_REPORT_DAY_OF_WEEK: str = "mon"
    # Monthly proposal: 1st of each month at 8:00 JST
    SCHED_MONTHLY_PROPOSAL_DAY: int = 1
    SCHED_MONTHLY_PROPOSAL_HOUR: int = 8
    SCHED_MONTHLY_PROPOSAL_MINUTE: int = 0
    # Future: quarterly summary (enabled after 3 months of operation)
    SCHED_QUARTERLY_SUMMARY_ENABLED: bool = False
    # Future: JRA-VAN reminder month (adjust based on operation start)
    JRAVAN_REMINDER_MONTH: int = 5

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
