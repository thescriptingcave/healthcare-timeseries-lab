"""Iceberg vitals INSERT helper shared by the pipelines (M7)."""

from __future__ import annotations

from healthcare_timeseries_lab.lakehouse import (
    LAKEHOUSE_SCHEMA,
    VITALS_TABLE,
)
from healthcare_timeseries_lab.lakehouse.catalog import run_trino_ddl
from healthcare_timeseries_lab.streaming.consumer import (
    event_time_to_trino_timestamp,
)

_VITALS_COLUMNS = (
    "event_time,"
    "patient_id,"
    "heart_rate_bpm,"
    "spo2_pct,"
    "respiration_rate_bpm,"
    "temperature_c,"
    "systolic_bp_mmhg,"
    "diastolic_bp_mmhg"
)

_COLUMN_LIST: list[str] = [
    col.strip()
    for col in _VITALS_COLUMNS.split(",")
]


def build_vitals_insert_sql(
    records: list[dict],
    *,
    catalog: str = "lake",
) -> str:
    """Build a single Trino INSERT into ``lake.lakehouse.vitals``.

    ``records`` are decoded Kafka vitals rows (datetime already serialised
    as an ISO string; everything else is a scalar).
    """
    value_placeholders: list[str] = []
    for record in records:
        placeholders: list[str] = []
        for col in _COLUMN_LIST:
            if col == "event_time":
                placeholders.append(
                    f"TIMESTAMP '{event_time_to_trino_timestamp(record)}'"
                )
            elif col == "patient_id":
                placeholders.append(f"'{record[col]}'")
            else:
                placeholders.append(str(record[col]))
        value_placeholders.append(f"({', '.join(placeholders)})")

    return (
        f"INSERT INTO {catalog}.{LAKEHOUSE_SCHEMA}.{VITALS_TABLE}"
        f" ({_VITALS_COLUMNS}) VALUES {', '.join(value_placeholders)}"
    )


def insert_vitals(
    records: list[dict],
    *,
    catalog: str = "lake",
) -> int:
    """Insert decoded vitals records into the Iceberg table via Trino."""
    run_trino_ddl([build_vitals_insert_sql(records, catalog=catalog)])
    return len(records)


__all__ = [
    "build_vitals_insert_sql",
    "insert_vitals",
]