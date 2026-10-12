"""Compare the original telemetry dataset with PostgreSQL measurements."""

import os
from datetime import timezone
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def main():
    expected = pd.read_csv(ROOT / "data" / "telemetry_sample.csv")
    expected_times = set(
        pd.to_datetime(expected["timestamp_utc"], utc=True).dt.to_pydatetime()
    )

    with psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        connect_timeout=5,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT measurement_timestamp FROM telemetry WHERE device_id = %s",
                ("inverter_01",),
            )
            actual_times = {row[0].astimezone(timezone.utc) for row in cursor.fetchall()}

    missing = expected_times - actual_times
    unexpected = actual_times - expected_times

    print(f"Expected measurements: {len(expected_times)}")
    print(f"Stored measurements: {len(actual_times)}")
    print(f"Missing measurements: {len(missing)}")
    print(f"Unexpected measurements: {len(unexpected)}")
    print(f"Data complete: {not missing and not unexpected}")
    if missing:
        print("First missing UTC timestamps:")
        for timestamp in sorted(missing)[:5]:
            print(timestamp.isoformat())


if __name__ == "__main__":
    main()
