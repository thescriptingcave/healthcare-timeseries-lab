"""Stream simulated vitals through Kafka (Avro + Schema Registry) into the
Iceberg lakehouse, then read back a summary via Trino (Milestone 4).

Pipeline::

    simulate -> produce Avro -> consume Avro -> INSERT lake.vitals

Run with::

    uv run python scripts/run_kafka_streaming.py
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from random import Random
from uuid import UUID, uuid4

from healthcare_timeseries_lab.lakehouse import (
    ANALYTICS_AGG_QUERY,
    LAKEHOUSE_SCHEMA,
    VITALS_TABLE,
)
from healthcare_timeseries_lab.lakehouse.catalog import run_trino_ddl, trino_query
from healthcare_timeseries_lab.patients.models import PatientProfile
from healthcare_timeseries_lab.physiology.engine import PhysiologyEngine
from healthcare_timeseries_lab.physiology.models import PhysiologicalState
from healthcare_timeseries_lab.runtime.clock import SimulationClock
from healthcare_timeseries_lab.streaming import (
    TOPIC_DEFAULT,
    consume_vitals,
    event_time_to_trino_timestamp,
    produce_vitals,
)
from healthcare_timeseries_lab.telemetry.events import VitalsTelemetryEvent

SEED = 42
STEP_SECONDS = 5
TICKS = 12
PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
DEVICE_ID = UUID("22222222-2222-2222-2222-222222222222")
SIMULATION_ID = UUID("33333333-3333-3333-3333-333333333333")
START = datetime(2026, 1, 1, tzinfo=UTC)


def _simulate() -> list[VitalsTelemetryEvent]:
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

    clock = SimulationClock(start_time=START, step=timedelta(seconds=STEP_SECONDS))
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

    events: list[VitalsTelemetryEvent] = []
    for seq in range(1, TICKS + 1):
        timestamp = clock.advance()
        state = engine.next_state(
            patient=profile,
            previous_state=state,
            timestamp=timestamp,
        )
        events.append(
            VitalsTelemetryEvent.from_physiological_state(
                event_id=uuid4(),
                simulation_id=SIMULATION_ID,
                patient_id=PATIENT_ID,
                device_id=DEVICE_ID,
                sequence_number=seq,
                state=state,
            )
        )
    return events


def _insert_records(records: list[dict]) -> None:
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
    for record in records:
        placeholders: list[str] = []
        for col in col_list.split(","):
            col = col.strip()
            if col == "event_time":
                placeholders.append(f"TIMESTAMP '{event_time_to_trino_timestamp(record)}'")
            elif col == "patient_id":
                placeholders.append(f"'{record[col]}'")
            else:
                placeholders.append(str(record[col]))
        value_placeholders.append(f"({', '.join(placeholders)})")

    sql = (
        f"INSERT INTO lake.{LAKEHOUSE_SCHEMA}.{VITALS_TABLE}"
        f" ({col_list}) VALUES {', '.join(value_placeholders)}"
    )
    run_trino_ddl([sql])


def run() -> None:
    print("== Milestone 4: Kafka vitals streaming pipeline ==")

    print(f"  1. Simulating {TICKS} vitals ticks ...")
    events = _simulate()
    print(f"     {len(events)} events ready")

    print(f"  2. Producing to Kafka topic '{TOPIC_DEFAULT}' (Avro + Schema Registry) ...")
    sent = produce_vitals(events)
    print(f"     produced {sent} messages")

    print("  3. Consuming Avro messages back ...")
    all_records = consume_vitals(topic=TOPIC_DEFAULT, max_messages=TICKS * 10)
    records = all_records[-TICKS:]
    print(f"     consumed {len(records)} messages (newest {TICKS} of {len(all_records)})")
    if len(records) != TICKS:
        print(f"     FAIL: expected {TICKS}, got {len(records)}")
        raise SystemExit(1)

    print("  4. Inserting consumed records into lake.lakehouse.vitals ...")
    _insert_records(records)
    print(f"     INSERT complete ({len(records)} rows)")

    print("  5. Analytics aggregation (Trino):")
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
    print("MILESTONE 4 KAFKA STREAMING OK")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)