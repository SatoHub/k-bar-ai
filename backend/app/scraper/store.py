"""Store scraped data into the database (upsert logic).

Follows the same pattern as pipeline/ingest.py:
- Uses sync SQLAlchemy with psycopg2
- PostgreSQL INSERT ... ON CONFLICT for idempotency
"""

from __future__ import annotations

import datetime
import logging
import uuid

from sqlalchemy import create_engine, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Horse, Jockey, OddsSnapshot, Race, RaceEntry, ScrapeLog, Trainer

logger = logging.getLogger(__name__)


def _get_engine():
    return create_engine(settings.database_url_sync, echo=False)


# ---------------------------------------------------------------------------
# ScrapeLog helpers
# ---------------------------------------------------------------------------


def _log_start(
    session: Session, task_type: str, target_date, target_race_id=None
) -> uuid.UUID:
    log_id = uuid.uuid4()
    session.execute(
        pg_insert(ScrapeLog).values(
            id=log_id,
            task_type=task_type,
            target_date=target_date,
            target_race_id=target_race_id,
            status="running",
            started_at=datetime.datetime.utcnow(),
        )
    )
    session.flush()
    return log_id


def _log_finish(
    session: Session,
    log_id: uuid.UUID,
    status: str,
    records: int,
    error: str | None = None,
):
    session.execute(
        update(ScrapeLog)
        .where(ScrapeLog.id == log_id)
        .values(
            status=status,
            records_affected=records,
            error_message=error,
            finished_at=datetime.datetime.utcnow(),
        )
    )


# ---------------------------------------------------------------------------
# Master table upsert helpers
# ---------------------------------------------------------------------------


def _upsert_horse(
    session: Session, name: str, sex: str | None, netkeiba_id: str | None
) -> uuid.UUID:
    """Upsert a horse and return its UUID."""
    # Try to find by netkeiba_id first (more reliable)
    if netkeiba_id:
        row = session.execute(
            select(Horse.id).where(Horse.netkeiba_id == netkeiba_id)
        ).first()
        if row:
            return row[0]

    # Try to find by name + sex
    row = session.execute(
        select(Horse.id).where(Horse.name == name, Horse.sex == sex)
    ).first()
    if row:
        # Update netkeiba_id if we have it now
        if netkeiba_id:
            session.execute(
                update(Horse).where(Horse.id == row[0]).values(netkeiba_id=netkeiba_id)
            )
        return row[0]

    # Insert new
    horse_id = uuid.uuid4()
    stmt = pg_insert(Horse).values(
        id=horse_id, name=name, sex=sex, netkeiba_id=netkeiba_id
    )
    stmt = stmt.on_conflict_do_nothing(constraint="uq_horses_name_sex")
    session.execute(stmt)
    session.flush()

    # Re-fetch in case of conflict
    row = session.execute(
        select(Horse.id).where(Horse.name == name, Horse.sex == sex)
    ).first()
    return row[0] if row else horse_id


def _upsert_jockey(session: Session, name: str) -> uuid.UUID:
    row = session.execute(select(Jockey.id).where(Jockey.name == name)).first()
    if row:
        return row[0]
    jockey_id = uuid.uuid4()
    stmt = pg_insert(Jockey).values(id=jockey_id, name=name)
    stmt = stmt.on_conflict_do_nothing(index_elements=["name"])
    session.execute(stmt)
    session.flush()
    row = session.execute(select(Jockey.id).where(Jockey.name == name)).first()
    return row[0] if row else jockey_id


def _upsert_trainer(session: Session, name: str) -> uuid.UUID:
    row = session.execute(select(Trainer.id).where(Trainer.name == name)).first()
    if row:
        return row[0]
    trainer_id = uuid.uuid4()
    stmt = pg_insert(Trainer).values(id=trainer_id, name=name)
    stmt = stmt.on_conflict_do_nothing(index_elements=["name"])
    session.execute(stmt)
    session.flush()
    row = session.execute(select(Trainer.id).where(Trainer.name == name)).first()
    return row[0] if row else trainer_id


# ---------------------------------------------------------------------------
# store_shutuba
# ---------------------------------------------------------------------------


def store_shutuba(shutuba_data: dict, race_date: datetime.date) -> int:
    """Store shutuba data into DB.

    Upserts: races, horses, jockeys, trainers, race_entries.
    Returns number of entries stored.
    """
    engine = _get_engine()
    race_id_str = shutuba_data["race_id"]
    entries = shutuba_data.get("entries", [])

    with Session(engine) as session:
        log_id = _log_start(session, "shutuba", race_date, race_id_str)

        try:
            # Upsert race
            race_uuid = _upsert_race(session, shutuba_data, race_date)

            # Upsert entries
            count = 0
            for entry in entries:
                horse_name = entry.get("horse_name")
                if not horse_name:
                    continue

                sex = entry.get("sex")
                horse_uuid = _upsert_horse(
                    session, horse_name, sex, entry.get("horse_netkeiba_id")
                )

                jockey_uuid = None
                if entry.get("jockey_name"):
                    jockey_uuid = _upsert_jockey(session, entry["jockey_name"])

                trainer_uuid = None
                if entry.get("trainer_name"):
                    trainer_uuid = _upsert_trainer(session, entry["trainer_name"])

                entry_values = {
                    "id": uuid.uuid4(),
                    "race_id": race_uuid,
                    "horse_id": horse_uuid,
                    "jockey_id": jockey_uuid,
                    "trainer_id": trainer_uuid,
                    "bracket_number": entry.get("bracket_number"),
                    "post_position": entry.get("post_position"),
                    "horse_age": entry.get("age"),
                    "weight_carried_kg": entry.get("weight_carried_kg"),
                    "horse_weight_kg": entry.get("horse_weight_kg"),
                    "horse_weight_diff": entry.get("horse_weight_diff"),
                    "data_source": "scrape",
                }

                stmt = pg_insert(RaceEntry).values(entry_values)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["race_id", "post_position"],
                    set_={
                        "horse_id": horse_uuid,
                        "jockey_id": jockey_uuid,
                        "trainer_id": trainer_uuid,
                        "weight_carried_kg": entry.get("weight_carried_kg"),
                        "horse_weight_kg": entry.get("horse_weight_kg"),
                        "horse_weight_diff": entry.get("horse_weight_diff"),
                        "data_source": "scrape",
                    },
                )
                session.execute(stmt)
                count += 1

            _log_finish(session, log_id, "success", count)
            session.commit()
            logger.info("Stored shutuba %s: %d entries", race_id_str, count)
            return count

        except Exception as e:
            _log_finish(session, log_id, "error", 0, str(e))
            session.commit()
            raise


def _upsert_race(
    session: Session, shutuba_data: dict, race_date: datetime.date
) -> uuid.UUID:
    """Upsert race record and return its UUID."""
    race_id_str = shutuba_data["race_id"]
    race_info = shutuba_data.get("race_info", {})

    row = session.execute(select(Race.id).where(Race.race_id == race_id_str)).first()
    if row:
        # Update race info if we have new data
        session.execute(
            update(Race)
            .where(Race.id == row[0])
            .values(
                race_name=shutuba_data.get("race_name"),
                surface=race_info.get("surface"),
                distance_m=race_info.get("distance_m"),
                direction=race_info.get("direction"),
                weather=race_info.get("weather"),
                track_condition=race_info.get("track_condition"),
                racecourse_name=race_info.get("racecourse_name"),
                data_source="scrape",
            )
        )
        return row[0]

    # Parse race_number from race_id (last 2 digits)
    race_number = None
    if len(race_id_str) >= 12:
        try:
            race_number = int(race_id_str[-2:])
        except ValueError:
            pass

    race_uuid = uuid.uuid4()
    stmt = pg_insert(Race).values(
        id=race_uuid,
        race_id=race_id_str,
        race_date=race_date,
        race_number=race_number,
        race_name=shutuba_data.get("race_name"),
        surface=race_info.get("surface"),
        distance_m=race_info.get("distance_m"),
        direction=race_info.get("direction"),
        weather=race_info.get("weather"),
        track_condition=race_info.get("track_condition"),
        racecourse_name=race_info.get("racecourse_name"),
        data_source="scrape",
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=["race_id"])
    session.execute(stmt)
    session.flush()

    row = session.execute(select(Race.id).where(Race.race_id == race_id_str)).first()
    return row[0] if row else race_uuid


# ---------------------------------------------------------------------------
# store_odds
# ---------------------------------------------------------------------------


def store_odds(odds_data: list[dict], race_id_str: str) -> int:
    """Store odds data into DB.

    Inserts into odds_snapshots and updates race_entries.win_odds.
    Returns number of odds records stored.
    """
    if not odds_data:
        return 0

    engine = _get_engine()

    with Session(engine) as session:
        log_id = _log_start(session, "odds", None, race_id_str)

        try:
            # Find race UUID
            row = session.execute(
                select(Race.id).where(Race.race_id == race_id_str)
            ).first()
            if not row:
                logger.warning("Race %s not found, skipping odds", race_id_str)
                _log_finish(session, log_id, "error", 0, "Race not found")
                session.commit()
                return 0

            race_uuid = row[0]
            now = datetime.datetime.utcnow()
            count = 0

            for odds in odds_data:
                post_pos = odds["post_position"]

                # Insert odds snapshot
                session.execute(
                    pg_insert(OddsSnapshot).values(
                        id=uuid.uuid4(),
                        race_id=race_uuid,
                        post_position=post_pos,
                        win_odds=odds.get("win_odds"),
                        win_favorite=odds.get("win_favorite"),
                        fetched_at=now,
                    )
                )

                # Update race_entries
                session.execute(
                    update(RaceEntry)
                    .where(
                        RaceEntry.race_id == race_uuid,
                        RaceEntry.post_position == post_pos,
                    )
                    .values(
                        win_odds=odds.get("win_odds"),
                        win_favorite=odds.get("win_favorite"),
                    )
                )
                count += 1

            _log_finish(session, log_id, "success", count)
            session.commit()
            logger.info("Stored odds %s: %d entries", race_id_str, count)
            return count

        except Exception as e:
            _log_finish(session, log_id, "error", 0, str(e))
            session.commit()
            raise


# ---------------------------------------------------------------------------
# store_result
# ---------------------------------------------------------------------------


def store_result(result_data: dict) -> int:
    """Store race result data into DB.

    Updates race_entries with finish positions, times, etc.
    Returns number of entries updated.
    """
    engine = _get_engine()
    race_id_str = result_data["race_id"]
    entries = result_data.get("entries", [])
    race_info = result_data.get("race_info", {})

    with Session(engine) as session:
        log_id = _log_start(session, "result", None, race_id_str)

        try:
            # Find or create race
            row = session.execute(
                select(Race.id).where(Race.race_id == race_id_str)
            ).first()
            if not row:
                logger.warning("Race %s not found for result, skipping", race_id_str)
                _log_finish(session, log_id, "error", 0, "Race not found")
                session.commit()
                return 0

            race_uuid = row[0]

            # Update race with weather/condition from result page
            if race_info.get("weather") or race_info.get("track_condition"):
                session.execute(
                    update(Race)
                    .where(Race.id == race_uuid)
                    .values(
                        weather=race_info.get("weather"),
                        track_condition=race_info.get("track_condition"),
                    )
                )

            count = 0
            for entry in entries:
                post_pos = entry.get("post_position")
                if post_pos is None:
                    continue

                update_values = {
                    "finish_position": entry.get("finish_position"),
                    "finish_note": entry.get("finish_note"),
                    "total_time_tenths": entry.get("total_time_tenths"),
                    "margin": entry.get("margin"),
                    "win_odds": entry.get("win_odds"),
                    "win_favorite": entry.get("win_favorite"),
                    "last_3f_time": entry.get("last_3f_time"),
                    "corner_pos_1": entry.get("corner_pos_1"),
                    "corner_pos_2": entry.get("corner_pos_2"),
                    "corner_pos_3": entry.get("corner_pos_3"),
                    "corner_pos_4": entry.get("corner_pos_4"),
                    "horse_weight_kg": entry.get("horse_weight_kg"),
                    "horse_weight_diff": entry.get("horse_weight_diff"),
                }

                result = session.execute(
                    update(RaceEntry)
                    .where(
                        RaceEntry.race_id == race_uuid,
                        RaceEntry.post_position == post_pos,
                    )
                    .values(update_values)
                )
                if result.rowcount > 0:
                    count += 1

            _log_finish(session, log_id, "success", count)
            session.commit()
            logger.info("Stored result %s: %d entries updated", race_id_str, count)
            return count

        except Exception as e:
            _log_finish(session, log_id, "error", 0, str(e))
            session.commit()
            raise
