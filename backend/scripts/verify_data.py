"""
Data verification script for K-Bar AI.

Checks:
  - Row counts for each table
  - FK integrity (orphan entries)
  - Duplicate checks
  - Date range
  - Value range checks
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import settings


def run_verify() -> None:
    engine = create_engine(settings.database_url_sync, echo=False)
    ok = True

    with Session(engine) as session:
        print("=" * 60)
        print("K-Bar AI Data Verification")
        print("=" * 60)

        # 1. Row counts
        print("\n[1] Row counts")
        tables = [
            "races",
            "horses",
            "jockeys",
            "trainers",
            "race_entries",
            "prediction_logs",
            "model_versions",
        ]
        for t in tables:
            count = session.scalar(text(f"SELECT count(*) FROM {t}"))
            print(f"  {t:20s}: {count:>10,}")

        # 2. Date range
        print("\n[2] Date range")
        min_date = session.scalar(text("SELECT min(race_date) FROM races"))
        max_date = session.scalar(text("SELECT max(race_date) FROM races"))
        print(f"  Earliest race: {min_date}")
        print(f"  Latest race  : {max_date}")

        # 3. FK integrity - orphan entries
        print("\n[3] FK integrity checks")
        checks = [
            (
                "race_entries with missing race",
                "SELECT count(*) FROM race_entries re LEFT JOIN races r ON re.race_id = r.id WHERE r.id IS NULL",
            ),
            (
                "race_entries with missing horse",
                "SELECT count(*) FROM race_entries re LEFT JOIN horses h ON re.horse_id = h.id WHERE h.id IS NULL",
            ),
            (
                "race_entries with missing jockey (where jockey_id is set)",
                "SELECT count(*) FROM race_entries re LEFT JOIN jockeys j ON re.jockey_id = j.id WHERE re.jockey_id IS NOT NULL AND j.id IS NULL",
            ),
            (
                "race_entries with missing trainer (where trainer_id is set)",
                "SELECT count(*) FROM race_entries re LEFT JOIN trainers t ON re.trainer_id = t.id WHERE re.trainer_id IS NOT NULL AND t.id IS NULL",
            ),
        ]
        for label, query in checks:
            count = session.scalar(text(query))
            status = "OK" if count == 0 else f"FAIL ({count:,} orphans)"
            if count > 0:
                ok = False
            print(f"  {label}: {status}")

        # 4. Duplicate checks
        print("\n[4] Duplicate checks")
        dup_races = session.scalar(
            text(
                "SELECT count(*) FROM (SELECT race_id FROM races GROUP BY race_id HAVING count(*) > 1) t"
            )
        )
        dup_entries = session.scalar(
            text(
                "SELECT count(*) FROM (SELECT race_id, horse_id FROM race_entries "
                "GROUP BY race_id, horse_id HAVING count(*) > 1) t"
            )
        )
        for label, count in [
            ("Duplicate race_id in races", dup_races),
            ("Duplicate (race, horse_id) in entries", dup_entries),
        ]:
            status = "OK" if count == 0 else f"FAIL ({count:,} duplicates)"
            if count > 0:
                ok = False
            print(f"  {label}: {status}")

        # 5. Value range checks
        print("\n[5] Value range checks")
        range_checks = [
            (
                "distance_m (800-4000)",
                "SELECT count(*) FROM races WHERE distance_m IS NOT NULL AND (distance_m < 800 OR distance_m > 4000)",
            ),
            (
                "bracket_number (1-8)",
                "SELECT count(*) FROM race_entries WHERE bracket_number IS NOT NULL AND (bracket_number < 1 OR bracket_number > 8)",
            ),
            (
                "finish_position (1-30)",
                "SELECT count(*) FROM race_entries WHERE finish_position IS NOT NULL AND (finish_position < 1 OR finish_position > 30)",
            ),
            (
                "horse_age (2-15)",
                "SELECT count(*) FROM race_entries WHERE horse_age IS NOT NULL AND (horse_age < 2 OR horse_age > 15)",
            ),
        ]
        for label, query in range_checks:
            count = session.scalar(text(query))
            status = "OK" if count == 0 else f"WARNING ({count:,} out of range)"
            print(f"  {label}: {status}")

        # 6. Racecourse list
        print("\n[6] Racecourses in data")
        result = session.execute(
            text(
                "SELECT racecourse_name, count(*) FROM races "
                "WHERE racecourse_name IS NOT NULL "
                "GROUP BY racecourse_name ORDER BY count(*) DESC"
            )
        )
        for name, count in result:
            print(f"  {name:10s}: {count:>8,} races")

        print("\n" + "=" * 60)
        print(f"Overall: {'ALL CHECKS PASSED' if ok else 'SOME CHECKS FAILED'}")
        print("=" * 60)


if __name__ == "__main__":
    run_verify()
