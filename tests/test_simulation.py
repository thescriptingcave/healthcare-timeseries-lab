from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from healthcare_timeseries_lab.patients.models import PatientProfile
from healthcare_timeseries_lab.simulation.models import SimulationStatus
from healthcare_timeseries_lab.simulation.runner import (
    BaselineSimulationConfig,
    run_baseline_simulation,
)

PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
SIMULATION_ID = UUID("22222222-2222-2222-2222-222222222222")
DEVICE_ID = UUID("33333333-3333-3333-3333-333333333333")


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


def make_config(seed: int = 42) -> BaselineSimulationConfig:
    return BaselineSimulationConfig(
        simulation_id=SIMULATION_ID,
        device_id=DEVICE_ID,
        start_time=datetime(2026, 1, 1, tzinfo=UTC),
        duration=timedelta(hours=1),
        step=timedelta(seconds=5),
        seed=seed,
    )


def test_one_hour_simulation_produces_720_events() -> None:
    result = run_baseline_simulation(
        patient=make_patient(),
        config=make_config(),
    )

    assert len(result.events) == 720


def test_simulation_produces_run_metadata() -> None:
    result = run_baseline_simulation(
        patient=make_patient(),
        config=make_config(),
    )

    run = result.run

    assert run.simulation_id == SIMULATION_ID
    assert run.scenario_name == "baseline"
    assert run.scenario_version == "1.0"
    assert run.seed == 42
    assert run.status == SimulationStatus.COMPLETED

    assert run.start_time == datetime(
        2026,
        1,
        1,
        0,
        0,
        0,
        tzinfo=UTC,
    )

    assert run.end_time == datetime(
        2026,
        1,
        1,
        1,
        0,
        0,
        tzinfo=UTC,
    )

    assert run.duration == timedelta(hours=1)


def test_simulation_uses_correct_event_timestamps() -> None:
    result = run_baseline_simulation(
        patient=make_patient(),
        config=make_config(),
    )

    events = result.events

    assert events[0].event_time == datetime(
        2026,
        1,
        1,
        0,
        0,
        5,
        tzinfo=UTC,
    )

    assert events[-1].event_time == datetime(
        2026,
        1,
        1,
        1,
        0,
        0,
        tzinfo=UTC,
    )


def test_sequence_numbers_are_monotonic() -> None:
    result = run_baseline_simulation(
        patient=make_patient(),
        config=make_config(),
    )

    sequence_numbers = [
        event.sequence_number
        for event in result.events
    ]

    assert sequence_numbers == list(range(1, 721))


def test_all_events_reference_simulation_run() -> None:
    result = run_baseline_simulation(
        patient=make_patient(),
        config=make_config(),
    )

    assert all(
        event.simulation_id == result.run.simulation_id
        for event in result.events
    )


def test_same_seed_produces_identical_simulation() -> None:
    first_run = run_baseline_simulation(
        patient=make_patient(),
        config=make_config(seed=42),
    )

    second_run = run_baseline_simulation(
        patient=make_patient(),
        config=make_config(seed=42),
    )

    assert first_run == second_run


def test_different_seed_changes_physiology() -> None:
    first_run = run_baseline_simulation(
        patient=make_patient(),
        config=make_config(seed=42),
    )

    second_run = run_baseline_simulation(
        patient=make_patient(),
        config=make_config(seed=99),
    )

    assert (
        first_run.events[0].heart_rate_bpm
        != second_run.events[0].heart_rate_bpm
    )


def test_event_ids_are_unique() -> None:
    result = run_baseline_simulation(
        patient=make_patient(),
        config=make_config(),
    )

    event_ids = {
        event.event_id
        for event in result.events
    }

    assert len(event_ids) == len(result.events)


def test_invalid_duration_is_rejected() -> None:
    config = BaselineSimulationConfig(
        simulation_id=SIMULATION_ID,
        device_id=DEVICE_ID,
        start_time=datetime(2026, 1, 1, tzinfo=UTC),
        duration=timedelta(0),
        step=timedelta(seconds=5),
        seed=42,
    )

    with pytest.raises(ValueError, match="duration"):
        run_baseline_simulation(
            patient=make_patient(),
            config=config,
        )