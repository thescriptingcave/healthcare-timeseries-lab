"""Run a simulated vitals window, write into the Iceberg lakehouse,
and read back a summary via a Trino analytics query (Milestone 3).

The script reuses the same simulation as ``push_to_fhir.py`` (M2),
parses the resulting ``VitalsTelemetryEvent`` objects into vitals-row
dicts, inserts them into ``lake.lakehouse.vitals``, then runs an
aggregation query and prints the results.

Run with::

    uv run python scripts/run_lakehouse_analytics.py
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from random import Random
from uuid import UUID

from healthcare_timeseries_lab.lakehouse import (
    ANALYTICS_AGG_QUERY,
    LAKEHOUSE_SCHEMA,
    READ_BACK_QUERY,
    VITALS_TABLE,
)
from healthcare_timeseries_lab.lakehouse.catalog import run_trino_ddl, trino_query
from healthcare_timeseries_lab.patients.models import PatientProfile
from healthcare_timeseries_lab.physiology.engine import PhysiologyEngine
from healthcare_timeseries_lab.physiology.models import PhysiologicalState
from healthcare_timeseries_lab.runtime.clock import SimulationClock

SEED = 42
STEP_SECONDS = 5
TICKS = 12
PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
DEVICE_ID = UUID("22222222-2222-2222-2222-222222222222")
SIMULATION_ID = UUID("33333333-3333-3333-3333-333333333333")
START = datetime(2026, 1, 1, tzinfo=UTC)


def _simulate() -> list[dict]:
    """Run the physiology simulation and return vitals-row dicts."""
    profile = PatientProfile(
        patient_id=PATIENT_ID,
        age=45,
        sex="female",
        baseline_heart_rate_bpm=72.0,
        baseline_spo2_pct=98.0,
        baseline_respiration_rate_bpm=14.0,
        baseline_temperature_c=36.8,
        baseline_systolic_bp_mmhg=120.0,
        baseline_diastolic_bp_mmhg=76.0,
        variability_factor=1.0,
    )

    clock = SimulationClock(
        start_time=START,
        step=timedelta(seconds=STEP_SECONDS),
    )
    engine = PhysiologyEngine(Random(SEED))

    state = PhysiologicalState(
        timestamp=clock.now,
        heart_rate_bpm=profile.baseline_heart_rate_bpm,
        spo2_pct=profile.baseline_spo2_pct,
        respiration_rate_bpm=profile.baseline_respiration_rate_bpm,
        temperature_c=profile.baseline_temperature_c,
        systolic_bp_mmhg=profile.baseline_systolic_bp_mmhg,
        diastolic_bp_mmhg=profile.baseline_diastolic_bp_mmhg,
    )

    rows: list[dict] = []

    for _ in range(TICKS):
        timestamp = clock.advance()
        state = engine.next_state(
            patient=profile,
            previous_state=state,
            timestamp=timestamp,
        )
        rows.append(
            {
                "event_time": state.timestamp.isoformat(),
                "patient_id": str(PATIENT_ID),
                "heart_rate_bpm": state.heart_rate_bpm,
                "spo2_pct": state.spo2_pct,
                "respiration_rate_bpm": state.respiration_rate_bpm,
                "temperature_c": state.temperature_c,
                "systolic_bp_mmhg": state.systolic_bp_mmhg,
                "diastolic_bp_mmhg": state.diastolic_bp_mmhg,
            }
        )

    return rows


def _insert_rows(rows: list[dict]) -> None:
    """Insert rows into the Iceberg vitals table via Trino."""
    col_list = (
        "event_time,"
        "patient_id,"
        "heart_rate_bpm,"
        "spo2_pct,"
        "respiration_rate_bpm,"
        "temperature_c,"
        "systolic_bp_mmhg,"
        "diastolic_bp_mmhg"
    )

    value_placeholders: list[str] = []
    for row in rows:
        placeholders: list[str] = []
        for col in col_list.split(","):
            col = col.strip()
            if col == "event_time":
                literal = row[col].replace("T", " ")
                placeholders.append(f"TIMESTAMP '{literal}'")
            elif col == "patient_id":
                placeholders.append(f"'{row[col]}'")
            else:
                placeholders.append(str(row[col]))
        value_placeholders.append(f"({', '.join(placeholders)})")

    sql = (
        f"INSERT INTO lake.{LAKEHOUSE_SCHEMA}.{VITALS_TABLE}"
        f" ({col_list}) VALUES {', '.join(value_placeholders)}"
    )
    run_trino_ddl([sql])


def run() -> None:
    print("== Milestone 3: lakehouse analytics read-back ==")

    print(f"  1. Simulating {TICKS} vitals ticks ...")
    rows = _simulate()
    print(f"     {len(rows)} rows ready")

    print("  2. Inserting into lake.lakehouse.vitals ...")
    _insert_rows(rows)
    print(f"     INSERT complete ({len(rows)} rows)")

    print("  3. Read-back (raw rows):")
    raw = trino_query(READ_BACK_QUERY)
    print(f"     {len(raw)} rows returned")
    for r in raw:
        print("    ", r)

    print()
    print("  4. Analytics aggregation:")
    agg = trino_query(ANALYTICS_AGG_QUERY)
    for row in agg:
        patient, n, hr, spo2, rr, temp, sbp, dbp, wstart, wend = row
        print(
            f"    patient={patient}  n={n}  "
            f"avg_HR={hr:.2f}  avg_SpO2={spo2:.2f}  avg_RR={rr:.2f}  "
            f"avg_T={temp:.2f}  avg_SBP={sbp:.2f}  avg_DBP={dbp:.2f}  "
            f"window=[{wstart}, {wend}]"
        )

    print()
    print("MILESTONE 3 LAKEHOUSE READ-BACK OK")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
