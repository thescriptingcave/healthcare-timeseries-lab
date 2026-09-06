from datetime import UTC, datetime, timedelta
from random import Random
from statistics import mean
from uuid import UUID

import pytest

from healthcare_timeseries_lab.patients.models import PatientProfile
from healthcare_timeseries_lab.physiology.engine import PhysiologyEngine
from healthcare_timeseries_lab.physiology.models import PhysiologicalState


def test_baseline_remains_stable_over_one_hour() -> None:
    patient = make_patient()
    engine = PhysiologyEngine(Random(42))

    state = make_state()
    states = []

    start_time = state.timestamp

    for step in range(1, 721):
        timestamp = start_time + timedelta(seconds=step * 5)

        state = engine.next_state(
            patient=patient,
            previous_state=state,
            timestamp=timestamp,
        )

        states.append(state)

    heart_rates = [state.heart_rate_bpm for state in states]
    spo2_values = [state.spo2_pct for state in states]
    respiration_rates = [state.respiration_rate_bpm for state in states]
    temperatures = [state.temperature_c for state in states]
    systolic_values = [state.systolic_bp_mmhg for state in states]
    diastolic_values = [state.diastolic_bp_mmhg for state in states]

    assert abs(mean(heart_rates) - patient.baseline_heart_rate_bpm) < 2.0
    assert abs(mean(spo2_values) - patient.baseline_spo2_pct) < 0.5
    assert (
        abs(
            mean(respiration_rates)
            - patient.baseline_respiration_rate_bpm
        )
        < 1.0
    )
    assert abs(mean(temperatures) - patient.baseline_temperature_c) < 0.2
    assert abs(mean(systolic_values) - patient.baseline_systolic_bp_mmhg) < 3.0
    assert abs(mean(diastolic_values) - patient.baseline_diastolic_bp_mmhg) < 3.0

    assert max(heart_rates) > min(heart_rates)
    assert max(spo2_values) > min(spo2_values)
    assert max(respiration_rates) > min(respiration_rates)
    assert max(temperatures) > min(temperatures)
    assert max(systolic_values) > min(systolic_values)
    assert max(diastolic_values) > min(diastolic_values)
def make_state(**overrides: object) -> PhysiologicalState:
    values = {
        "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
        "heart_rate_bpm": 72.0,
        "spo2_pct": 98.0,
        "respiration_rate_bpm": 14.0,
        "temperature_c": 36.8,
        "systolic_bp_mmhg": 120.0,
        "diastolic_bp_mmhg": 76.0,
    }

    values.update(overrides)

    return PhysiologicalState(**values)


def make_patient(**overrides: object) -> PatientProfile:
    values = {
        "patient_id": UUID("11111111-1111-1111-1111-111111111111"),
        "age": 45,
        "sex": "female",
        "baseline_heart_rate_bpm": 72.0,
        "baseline_spo2_pct": 98.0,
        "baseline_respiration_rate_bpm": 14.0,
        "baseline_temperature_c": 36.8,
        "baseline_systolic_bp_mmhg": 120.0,
        "baseline_diastolic_bp_mmhg": 76.0,
        "variability_factor": 1.0,
    }

    values.update(overrides)

    return PatientProfile(**values)


def test_valid_physiological_state_is_created() -> None:
    state = make_state()

    assert state.heart_rate_bpm == 72.0
    assert state.spo2_pct == 98.0
    assert state.systolic_bp_mmhg == 120.0


def test_state_rejects_naive_timestamp() -> None:
    timestamp = datetime(2026, 1, 1)  # noqa: DTZ001

    with pytest.raises(ValueError, match="timezone-aware"):
        make_state(timestamp=timestamp)


def test_state_rejects_heart_rate_outside_bounds() -> None:
    with pytest.raises(ValueError, match="heart rate"):
        make_state(heart_rate_bpm=250.0)


def test_state_rejects_spo2_outside_bounds() -> None:
    with pytest.raises(ValueError, match="SpO2"):
        make_state(spo2_pct=110.0)


def test_state_rejects_respiration_rate_outside_bounds() -> None:
    with pytest.raises(ValueError, match="respiration"):
        make_state(respiration_rate_bpm=70.0)


def test_state_rejects_temperature_outside_bounds() -> None:
    with pytest.raises(ValueError, match="temperature"):
        make_state(temperature_c=45.0)


def test_state_rejects_invalid_blood_pressure_relationship() -> None:
    with pytest.raises(ValueError, match="systolic"):
        make_state(
            systolic_bp_mmhg=75.0,
            diastolic_bp_mmhg=80.0,
        )


def test_engine_produces_new_state() -> None:
    patient = make_patient()
    previous = make_state()

    engine = PhysiologyEngine(Random(42))

    timestamp = datetime(2026, 1, 1, 0, 0, 5, tzinfo=UTC)

    state = engine.next_state(
        patient=patient,
        previous_state=previous,
        timestamp=timestamp,
    )

    assert state.timestamp == timestamp
    assert state != previous


def test_engine_is_reproducible_with_same_seed() -> None:
    patient = make_patient()
    previous = make_state()

    timestamp = datetime(2026, 1, 1, 0, 0, 5, tzinfo=UTC)

    engine_one = PhysiologyEngine(Random(42))
    engine_two = PhysiologyEngine(Random(42))

    state_one = engine_one.next_state(
        patient=patient,
        previous_state=previous,
        timestamp=timestamp,
    )

    state_two = engine_two.next_state(
        patient=patient,
        previous_state=previous,
        timestamp=timestamp,
    )

    assert state_one == state_two


def test_engine_changes_with_different_seed() -> None:
    patient = make_patient()
    previous = make_state()

    timestamp = datetime(2026, 1, 1, 0, 0, 5, tzinfo=UTC)

    engine_one = PhysiologyEngine(Random(42))
    engine_two = PhysiologyEngine(Random(99))

    state_one = engine_one.next_state(
        patient=patient,
        previous_state=previous,
        timestamp=timestamp,
    )

    state_two = engine_two.next_state(
        patient=patient,
        previous_state=previous,
        timestamp=timestamp,
    )

    assert state_one != state_two


def test_engine_moves_heart_rate_toward_baseline() -> None:
    patient = make_patient(
        variability_factor=0.000001,
    )

    previous = make_state(
        heart_rate_bpm=100.0,
    )

    engine = PhysiologyEngine(Random(42))

    state = engine.next_state(
        patient=patient,
        previous_state=previous,
        timestamp=datetime(2026, 1, 1, 0, 0, 5, tzinfo=UTC),
    )

    assert state.heart_rate_bpm < previous.heart_rate_bpm