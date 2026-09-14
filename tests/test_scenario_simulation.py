from datetime import UTC, datetime, timedelta
from statistics import mean
from uuid import UUID

from healthcare_timeseries_lab.patients.models import PatientProfile
from healthcare_timeseries_lab.scenarios.library import progressive_hypoxemia
from healthcare_timeseries_lab.simulation.scenario_runner import (
    ScenarioSimulationConfig,
    run_scenario_simulation,
)

PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
SIMULATION_ID = UUID("44444444-4444-4444-4444-444444444444")
DEVICE_ID = UUID("33333333-3333-3333-3333-333333333333")

START_TIME = datetime(
    2026,
    1,
    1,
    tzinfo=UTC,
)


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


def make_config() -> ScenarioSimulationConfig:
    return ScenarioSimulationConfig(
        simulation_id=SIMULATION_ID,
        device_id=DEVICE_ID,
        scenario_name="progressive_hypoxemia",
        scenario_version="1.0",
        start_time=START_TIME,
        duration=timedelta(hours=6),
        step=timedelta(seconds=5),
        seed=42,
    )


def events_between(result, start: timedelta, end: timedelta):
    start_time = START_TIME + start
    end_time = START_TIME + end

    return [
        event
        for event in result.events
        if start_time <= event.event_time < end_time
    ]


def test_six_hour_scenario_produces_expected_event_count() -> None:
    result = run_scenario_simulation(
        patient=make_patient(),
        config=make_config(),
        conditions=progressive_hypoxemia(),
    )

    assert len(result.events) == 4320


def test_hypoxemia_reduces_spo2_during_plateau() -> None:
    result = run_scenario_simulation(
        patient=make_patient(),
        config=make_config(),
        conditions=progressive_hypoxemia(),
    )

    baseline = events_between(
        result,
        timedelta(hours=1),
        timedelta(hours=2),
    )

    plateau = events_between(
        result,
        timedelta(hours=3, minutes=30),
        timedelta(hours=4),
    )

    baseline_spo2 = mean(
        event.spo2_pct
        for event in baseline
    )

    plateau_spo2 = mean(
        event.spo2_pct
        for event in plateau
    )

    assert plateau_spo2 < baseline_spo2 - 5.0


def test_hypoxemia_increases_respiration_rate() -> None:
    result = run_scenario_simulation(
        patient=make_patient(),
        config=make_config(),
        conditions=progressive_hypoxemia(),
    )

    baseline = events_between(
        result,
        timedelta(hours=1),
        timedelta(hours=2),
    )

    plateau = events_between(
        result,
        timedelta(hours=3, minutes=30),
        timedelta(hours=4),
    )

    baseline_rr = mean(
        event.respiration_rate_bpm
        for event in baseline
    )

    plateau_rr = mean(
        event.respiration_rate_bpm
        for event in plateau
    )

    assert plateau_rr > baseline_rr + 3.0


def test_hypoxemia_increases_heart_rate() -> None:
    result = run_scenario_simulation(
        patient=make_patient(),
        config=make_config(),
        conditions=progressive_hypoxemia(),
    )

    baseline = events_between(
        result,
        timedelta(hours=1),
        timedelta(hours=2),
    )

    plateau = events_between(
        result,
        timedelta(hours=3, minutes=30),
        timedelta(hours=4),
    )

    baseline_hr = mean(
        event.heart_rate_bpm
        for event in baseline
    )

    plateau_hr = mean(
        event.heart_rate_bpm
        for event in plateau
    )

    assert plateau_hr > baseline_hr + 5.0


def test_patient_recovers_toward_baseline() -> None:
    result = run_scenario_simulation(
        patient=make_patient(),
        config=make_config(),
        conditions=progressive_hypoxemia(),
    )

    plateau = events_between(
        result,
        timedelta(hours=3, minutes=30),
        timedelta(hours=4),
    )

    post_recovery = events_between(
        result,
        timedelta(hours=5, minutes=30),
        timedelta(hours=6),
    )

    plateau_spo2 = mean(
        event.spo2_pct
        for event in plateau
    )

    recovered_spo2 = mean(
        event.spo2_pct
        for event in post_recovery
    )

    assert recovered_spo2 > plateau_spo2 + 5.0
    assert abs(recovered_spo2 - 98.0) < 1.0


def test_ground_truth_records_condition_lifecycle() -> None:
    result = run_scenario_simulation(
        patient=make_patient(),
        config=make_config(),
        conditions=progressive_hypoxemia(),
    )

    event_types = [
        event.event_type.value
        for event in result.clinical_ground_truth
    ]

    assert "CONDITION_STARTED" in event_types
    assert "CONDITION_UPDATED" in event_types
    assert "CONDITION_ENDED" in event_types


def test_same_seed_reproduces_scenario() -> None:
    first = run_scenario_simulation(
        patient=make_patient(),
        config=make_config(),
        conditions=progressive_hypoxemia(),
    )

    second = run_scenario_simulation(
        patient=make_patient(),
        config=make_config(),
        conditions=progressive_hypoxemia(),
    )

    assert first == second