"""
Core data ingestion pipeline for the Kaggle JRA horse racing dataset.

Reads CSV in chunks, upserts master tables (horses, jockeys, trainers),
builds race records with JSONB race_symbols, and bulk-inserts race entries.
Uses sync SQLAlchemy with psycopg2.
"""

from __future__ import annotations

import time
import uuid
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Horse, Jockey, Race, RaceEntry, Trainer
from app.pipeline.column_mapping import COLUMN_MAP, RACE_SYMBOL_COLUMNS

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
CHUNK_SIZE = 10_000
BATCH_SIZE = 1_000


# ---------------------------------------------------------------------------
# Safe type conversion helpers
# ---------------------------------------------------------------------------


def _safe_int(val) -> int | None:
    """Convert value to int, returning None on failure."""
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> float | None:
    """Convert value to float, returning None on failure."""
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_str(val) -> str | None:
    """Convert to stripped string, returning None for NaN / empty."""
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    s = str(val).strip()
    return s if s and s.lower() != "nan" else None


def _parse_race_date(val) -> date | None:
    """Parse date value to a date object.

    Handles: pandas Timestamp, datetime.date, YYYY-MM-DD string,
    YYYYMMDD int/string.
    """
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    # pandas Timestamp or datetime.date
    if isinstance(val, (date, pd.Timestamp)):
        d = val if isinstance(val, date) else val.date()
        return d
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return None
    # Try YYYY-MM-DD format first (pandas auto-parsed)
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        pass
    # Try YYYYMMDD integer format
    try:
        return datetime.strptime(str(int(float(s))), "%Y%m%d").date()
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# CSV discovery & reading
# ---------------------------------------------------------------------------


def _find_csv(csv_path: str | Path | None) -> Path:
    """Find the CSV file to ingest."""
    if csv_path:
        p = Path(csv_path)
        if not p.exists():
            raise FileNotFoundError(f"CSV file not found: {p}")
        return p

    candidates = sorted(DATA_DIR.glob("*.csv"))
    if not candidates:
        raise FileNotFoundError(
            f"No CSV files found in {DATA_DIR}\n"
            "Please place the Kaggle dataset CSV in the data/ directory."
        )
    return candidates[0]


def _read_csv_chunks(csv_path: Path, chunk_size: int = CHUNK_SIZE):
    """Yield DataFrames in chunks, trying UTF-8 first then cp932."""
    for encoding in ("utf-8-sig", "cp932"):
        try:
            reader = pd.read_csv(
                csv_path,
                encoding=encoding,
                chunksize=chunk_size,
                low_memory=False,
            )
            # Peek at first chunk to validate encoding
            first = next(reader)
            print(f"[ingest] Encoding: {encoding}, columns: {len(first.columns)}")
            yield first
            yield from reader
            return
        except UnicodeDecodeError:
            print(f"[ingest] {encoding} failed, trying next encoding...")
            continue
        except StopIteration:
            print("[ingest] CSV file is empty.")
            return

    raise RuntimeError(f"Could not read {csv_path} with UTF-8 or cp932 encoding.")


# ---------------------------------------------------------------------------
# Column mapping & cleaning for a chunk
# ---------------------------------------------------------------------------


def _map_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename Japanese CSV columns to internal names using COLUMN_MAP."""
    present = {c: COLUMN_MAP[c] for c in COLUMN_MAP if c in df.columns}
    return df.rename(columns=present)


def _extract_race_symbols(row: pd.Series) -> dict:
    """Pack race symbol flag columns into a dict for JSONB storage."""
    symbols: dict[str, object] = {}
    for jp_name in RACE_SYMBOL_COLUMNS:
        internal = COLUMN_MAP[jp_name]
        val = row.get(internal)
        if val is not None and not (isinstance(val, float) and pd.isna(val)):
            # Store truthy values (1, non-empty string, etc.)
            cleaned = _safe_str(val)
            if cleaned is not None and cleaned not in ("0", "0.0"):
                symbols[internal] = cleaned
    return symbols


# ---------------------------------------------------------------------------
# Master table upsert helpers
# ---------------------------------------------------------------------------


def _upsert_horses(
    session: Session,
    df: pd.DataFrame,
    cache: dict[tuple[str, str | None], uuid.UUID],
) -> dict[tuple[str, str | None], uuid.UUID]:
    """Upsert unique horses from this chunk. Returns updated cache."""
    pairs = df[["horse_name", "sex"]].dropna(subset=["horse_name"]).drop_duplicates()
    new_values = []

    for _, row in pairs.iterrows():
        name = _safe_str(row["horse_name"])
        sex = _safe_str(row.get("sex"))
        if name is None:
            continue
        key = (name, sex)
        if key not in cache:
            new_values.append({"id": uuid.uuid4(), "name": name, "sex": sex})

    if new_values:
        for i in range(0, len(new_values), BATCH_SIZE):
            batch = new_values[i : i + BATCH_SIZE]
            stmt = pg_insert(Horse).values(batch)
            stmt = stmt.on_conflict_do_nothing(constraint="uq_horses_name_sex")
            session.execute(stmt)
        session.flush()

        # Refresh cache with DB-assigned IDs (in case of conflict, our uuid was ignored)
        result = session.execute(select(Horse.name, Horse.sex, Horse.id))
        for name, sex, id_ in result:
            cache[(name, sex)] = id_

    return cache


def _upsert_jockeys(
    session: Session,
    df: pd.DataFrame,
    cache: dict[str, uuid.UUID],
) -> dict[str, uuid.UUID]:
    """Upsert unique jockeys from this chunk. Returns updated cache."""
    names = df["jockey_name"].dropna().unique().tolist()
    new_values = []

    for n in names:
        name = _safe_str(n)
        if name and name not in cache:
            new_values.append({"id": uuid.uuid4(), "name": name})

    if new_values:
        for i in range(0, len(new_values), BATCH_SIZE):
            batch = new_values[i : i + BATCH_SIZE]
            stmt = pg_insert(Jockey).values(batch)
            stmt = stmt.on_conflict_do_nothing(index_elements=["name"])
            session.execute(stmt)
        session.flush()

        result = session.execute(select(Jockey.name, Jockey.id))
        for name, id_ in result:
            cache[name] = id_

    return cache


def _upsert_trainers(
    session: Session,
    df: pd.DataFrame,
    cache: dict[str, uuid.UUID],
) -> dict[str, uuid.UUID]:
    """Upsert unique trainers from this chunk. Returns updated cache."""
    names = df["trainer_name"].dropna().unique().tolist()
    new_values = []

    for n in names:
        name = _safe_str(n)
        if name and name not in cache:
            new_values.append({"id": uuid.uuid4(), "name": name})

    if new_values:
        for i in range(0, len(new_values), BATCH_SIZE):
            batch = new_values[i : i + BATCH_SIZE]
            stmt = pg_insert(Trainer).values(batch)
            stmt = stmt.on_conflict_do_nothing(index_elements=["name"])
            session.execute(stmt)
        session.flush()

        result = session.execute(select(Trainer.name, Trainer.id))
        for name, id_ in result:
            cache[name] = id_

    return cache


# ---------------------------------------------------------------------------
# Race & RaceEntry builders
# ---------------------------------------------------------------------------


def _build_and_upsert_races(
    session: Session,
    df: pd.DataFrame,
    race_cache: dict[str, uuid.UUID],
) -> dict[str, uuid.UUID]:
    """Build race records from chunk, upsert, and return updated cache."""
    races_df = df.drop_duplicates(subset=["race_id"])
    new_values = []

    for _, row in races_df.iterrows():
        rid = _safe_str(row.get("race_id"))
        if rid is None or rid in race_cache:
            continue

        symbols = _extract_race_symbols(row)

        new_values.append(
            {
                "id": uuid.uuid4(),
                "race_id": rid,
                "race_date": _parse_race_date(row.get("race_date")),
                "racecourse_code": _safe_str(row.get("racecourse_code")),
                "racecourse_name": _safe_str(row.get("racecourse_name")),
                "race_number": _safe_int(row.get("race_number")),
                "race_name": _safe_str(row.get("race_name")),
                "surface": _safe_str(row.get("surface")),
                "distance_m": _safe_int(row.get("distance_m")),
                "weather": _safe_str(row.get("weather")),
                "track_condition": _safe_str(row.get("track_condition")),
                "direction": _safe_str(row.get("direction")),
                "graded_race": _safe_str(row.get("graded_race")),
                "race_symbols": symbols if symbols else None,
            }
        )

    if new_values:
        for i in range(0, len(new_values), BATCH_SIZE):
            batch = new_values[i : i + BATCH_SIZE]
            stmt = pg_insert(Race).values(batch)
            stmt = stmt.on_conflict_do_nothing(index_elements=["race_id"])
            session.execute(stmt)
        session.flush()

        # Refresh the race cache
        result = session.execute(select(Race.race_id, Race.id))
        for race_id_str, id_ in result:
            race_cache[race_id_str] = id_

    return race_cache


def _build_entries(
    df: pd.DataFrame,
    race_cache: dict[str, uuid.UUID],
    horse_cache: dict[tuple[str, str | None], uuid.UUID],
    jockey_cache: dict[str, uuid.UUID],
    trainer_cache: dict[str, uuid.UUID],
) -> list[dict]:
    """Build race_entry dicts from a chunk DataFrame."""
    entries = []

    for _, row in df.iterrows():
        rid_str = _safe_str(row.get("race_id"))
        if rid_str is None:
            continue
        race_uuid = race_cache.get(rid_str)
        if race_uuid is None:
            continue

        horse_name = _safe_str(row.get("horse_name"))
        sex = _safe_str(row.get("sex"))
        if horse_name is None:
            continue
        horse_uuid = horse_cache.get((horse_name, sex))
        if horse_uuid is None:
            continue

        jockey_name = _safe_str(row.get("jockey_name"))
        jockey_uuid = jockey_cache.get(jockey_name) if jockey_name else None

        trainer_name = _safe_str(row.get("trainer_name"))
        trainer_uuid = trainer_cache.get(trainer_name) if trainer_name else None

        # finish_position: try int, if fails keep finish_note
        fp_raw = row.get("finish_position")
        finish_position = _safe_int(fp_raw)
        finish_note = _safe_str(row.get("finish_note"))

        entries.append(
            {
                "id": uuid.uuid4(),
                "race_id": race_uuid,
                "horse_id": horse_uuid,
                "jockey_id": jockey_uuid,
                "trainer_id": trainer_uuid,
                "bracket_number": _safe_int(row.get("bracket_number")),
                "post_position": _safe_int(row.get("post_position")),
                "horse_age": _safe_int(row.get("age")),
                "weight_carried_kg": _safe_float(row.get("weight_carried_kg")),
                "finish_position": finish_position,
                "finish_note": finish_note,
                "total_time_tenths": _safe_int(row.get("total_time_tenths")),
                "margin": _safe_str(row.get("margin")),
                "corner_pos_1": _safe_str(row.get("corner_pos_1")),
                "corner_pos_2": _safe_str(row.get("corner_pos_2")),
                "corner_pos_3": _safe_str(row.get("corner_pos_3")),
                "corner_pos_4": _safe_str(row.get("corner_pos_4")),
                "last_3f_time": _safe_float(row.get("last_3f_time")),
                "win_odds": _safe_float(row.get("win_odds")),
                "win_favorite": _safe_int(row.get("win_favorite")),
                "horse_weight_kg": _safe_int(row.get("horse_weight_kg")),
                "horse_weight_diff": _safe_int(row.get("horse_weight_diff")),
                "owner": _safe_str(row.get("owner")),
                "prize_money_10k_yen": _safe_float(row.get("prize_money_10k_yen")),
            }
        )

    return entries


def _insert_entries(session: Session, entries: list[dict]) -> int:
    """Bulk insert race entries. Returns count of inserted rows."""
    if not entries:
        return 0

    inserted = 0
    for i in range(0, len(entries), BATCH_SIZE):
        batch = entries[i : i + BATCH_SIZE]
        stmt = pg_insert(RaceEntry).values(batch)
        stmt = stmt.on_conflict_do_nothing(index_elements=["race_id", "horse_id"])
        session.execute(stmt)
        inserted += len(batch)

    return inserted


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_ingest(csv_path: str | Path | None = None) -> None:
    """
    Run the full ingestion pipeline.

    Reads the CSV in chunks, upserts master tables, builds races with
    JSONB race_symbols, and bulk-inserts race entries. Idempotent via
    ON CONFLICT DO NOTHING.
    """
    t_start = time.time()

    resolved_path = _find_csv(csv_path)
    print(f"[ingest] CSV: {resolved_path}")

    engine = create_engine(settings.database_url_sync, echo=False)

    # In-memory caches for master table lookups (avoid repeated DB queries)
    horse_cache: dict[tuple[str, str | None], uuid.UUID] = {}
    jockey_cache: dict[str, uuid.UUID] = {}
    trainer_cache: dict[str, uuid.UUID] = {}
    race_cache: dict[str, uuid.UUID] = {}

    total_rows = 0
    total_entries_inserted = 0
    chunk_num = 0

    with Session(engine) as session:
        # Pre-load existing master data into caches
        print("[ingest] Loading existing master data into cache...")
        for name, sex, id_ in session.execute(select(Horse.name, Horse.sex, Horse.id)):
            horse_cache[(name, sex)] = id_
        for name, id_ in session.execute(select(Jockey.name, Jockey.id)):
            jockey_cache[name] = id_
        for name, id_ in session.execute(select(Trainer.name, Trainer.id)):
            trainer_cache[name] = id_
        for race_id_str, id_ in session.execute(select(Race.race_id, Race.id)):
            race_cache[race_id_str] = id_

        print(
            f"[ingest] Cache loaded: "
            f"{len(horse_cache)} horses, "
            f"{len(jockey_cache)} jockeys, "
            f"{len(trainer_cache)} trainers, "
            f"{len(race_cache)} races"
        )

        for chunk_df in _read_csv_chunks(resolved_path):
            chunk_num += 1
            chunk_start = time.time()
            rows_in_chunk = len(chunk_df)
            total_rows += rows_in_chunk

            # 1. Map columns
            chunk_df = _map_columns(chunk_df)

            # 2. Upsert master tables
            horse_cache = _upsert_horses(session, chunk_df, horse_cache)
            jockey_cache = _upsert_jockeys(session, chunk_df, jockey_cache)
            trainer_cache = _upsert_trainers(session, chunk_df, trainer_cache)

            # 3. Build & upsert races (with race_symbols JSONB)
            race_cache = _build_and_upsert_races(session, chunk_df, race_cache)

            # 4. Build & insert race entries
            entries = _build_entries(
                chunk_df, race_cache, horse_cache, jockey_cache, trainer_cache
            )
            inserted = _insert_entries(session, entries)
            total_entries_inserted += inserted

            # Commit each chunk
            session.commit()

            elapsed_chunk = time.time() - chunk_start
            elapsed_total = time.time() - t_start
            print(
                f"[ingest] Chunk {chunk_num}: "
                f"{rows_in_chunk:,} rows processed, "
                f"{inserted:,} entries inserted, "
                f"chunk time {elapsed_chunk:.1f}s, "
                f"total time {elapsed_total:.1f}s"
            )

    elapsed = time.time() - t_start
    print("\n" + "=" * 60)
    print("INGESTION SUMMARY")
    print("=" * 60)
    print(f"  Total CSV rows processed : {total_rows:,}")
    print(f"  Total entries inserted    : {total_entries_inserted:,}")
    print(f"  Unique horses (cache)     : {len(horse_cache):,}")
    print(f"  Unique jockeys (cache)    : {len(jockey_cache):,}")
    print(f"  Unique trainers (cache)   : {len(trainer_cache):,}")
    print(f"  Unique races (cache)      : {len(race_cache):,}")
    print(f"  Elapsed time              : {elapsed:.1f}s")
    print("=" * 60)
