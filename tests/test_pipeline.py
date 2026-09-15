"""Unit tests for the unified simulation pipeline orchestrator (M7).

The orchestrator is exercised with injected fakes for the Kafka / lakehouse /
FHIR stages so no live infrastructure is required.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from healthcare_timeseries_lab.patients.models import PatientProfile
from healthcare_timeseries_lab.simulation.pipeline import (
    PipelineConfig,
    run_pipeline,
    select_newest,
)
from healthcare_timeseries_lab.streaming.producer import event_to_record
from healthcare_timeseries_lab.telemetry.events import VitalsTelemetryEvent

PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
SIMULATION_ID = UUID("33333333-3333-3333-3333-333333333333")
DEVICE_ID = UUID("22222222-2222-2222-2222-222222222222")
START_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def make_patient() -> PatientProfile:
    return PatientProfile(
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


def make_config(
    *,
    scenario: str = "baseline",
    duration: timedelta = timedelta(minutes=2),
) -> PipelineConfig:
    return PipelineConfig(
        patient=make_patient(),
        simulation_id=SIMULATION_ID,
        device_id=DEVICE_ID,
        scenario_name=scenario,
        scenario_version="1.0",
        start_time=START_TIME,
        duration=duration,
        step=timedelta(seconds=5),
        seed=42,
    )


def records_for(events: list[VitalsTelemetryEvent]) -> list[dict]:
    return [event_to_record(event) for event in events]


def fake_stages():
    stale = {
        "patient_id": "88888888-8888-8888-8888-888888888888",
        "simulation_id": "99999999-9999-9999-9999-999999999999",
    }

    produced: dict[str, list[VitalsTelemetryEvent]] = {"events": []}

    def produce(evts):
        produced["events"] = list(evts)
        return len(evts)

    def consume(max_messages):
        return [stale] + records_for(produced["events"])

    def insert(records):
        return len(records)

    def push(evts):
        return "201", [], 2 + len(evts)

    return produce, consume, insert, push


def test_pipeline_baseline_streams_all_stages() -> None:
    config = make_config(duration=timedelta(minutes=2))
    produce, consume, insert, push = fake_stages()

    result = run_pipeline(
        config=config,
        produce=produce,
        consume=consume,
        insert=insert,
        push_fhir=push,
    )

    assert result.run.scenario_name == "baseline"
    assert len(result.events) == 24
    assert result.produced == 24
    assert result.consumed == 24
    assert result.lakehouse_inserted == 24
    assert result.fhir_transactions == 26
    assert result.fhir_status == "201"
    assert result.clinical_ground_truth == []


def test_pipeline_reads_past_large_stale_backlog() -> None:
    config = make_config(duration=timedelta(minutes=2))
    produced: dict[str, list[VitalsTelemetryEvent]] = {"events": []}

    def produce(evts):
        produced["events"] = list(evts)
        return len(evts)

    stale = [
        {
            "patient_id": "88888888-8888-8888-8888-888888888888",
            "simulation_id": "99999999-9999-9999-9999-999999999999",
        }
        for _ in range(4000)
    ]

    def consume(max_messages):
        combined = stale + records_for(produced["events"])
        return combined[:max_messages]

    def insert(records):
        return len(records)

    def push(evts):
        return "201", [], 2 + len(evts)

    result = run_pipeline(
        config=config,
        produce=produce,
        consume=consume,
        insert=insert,
        push_fhir=push,
    )

    assert result.produced == 24
    assert result.lakehouse_inserted == 24
    assert len(result.events) == 24


def test_pipeline_scenario_produces_ground_truth() -> None:
    config = make_config(
        scenario="progressive_hypoxemia",
        duration=timedelta(hours=6),
    )
    produce, consume, insert, push = fake_stages()

    result = run_pipeline(
        config=config,
        produce=produce,
        consume=consume,
        insert=insert,
        push_fhir=push,
    )

    assert result.run.scenario_name == "progressive_hypoxemia"
    assert len(result.clinical_ground_truth) > 0
    assert result.produced == len(result.events) == 4320


def test_pipeline_rejects_unknown_scenario() -> None:
    config = make_config(scenario="not-a-real-scenario")

    with pytest.raises(ValueError, match="unknown scenario"):
        run_pipeline(
            config=config,
            produce=lambda evts: len(evts),
            consume=lambda n: [],
            insert=lambda recs: len(recs),
            push_fhir=lambda evts: ("200", [], 0),
        )


def test_select_newest_keeps_only_current_simulation() -> None:
    stale_other_patient = {
        "patient_id": "8" * 36,
        "simulation_id": "9" * 36,
    }
    stale_other_sim = {
        "patient_id": str(PATIENT_ID),
        "simulation_id": "9" * 36,
    }
    current = [
        {"patient_id": str(PATIENT_ID), "simulation_id": str(SIMULATION_ID), "n": 1},
        {"patient_id": str(PATIENT_ID), "simulation_id": str(SIMULATION_ID), "n": 2},
    ]

    newest = select_newest(
        [stale_other_patient, stale_other_sim, *current],
        patient_id=PATIENT_ID,
        simulation_id=SIMULATION_ID,
        count=1,
    )

    assert newest == [current[-1]]


def test_select_newest_empty_when_nothing_matches() -> None:
    records = [
        {"patient_id": "8" * 36, "simulation_id": "9" * 36},
    ]
    newest = select_newest(
        records,
        patient_id=PATIENT_ID,
        simulation_id=SIMULATION_ID,
        count=3,
    )

    assert newest == []