from datetime import UTC, datetime, timedelta
from random import Random
from uuid import UUID

import pytest

from healthcare_timeseries_lab.patients.models import PatientProfile
from healthcare_timeseries_lab.physiology.engine import PhysiologyEngine
from healthcare_timeseries_lab.physiology.models import PhysiologicalState
from healthcare_timeseries_lab.scenarios.models import (
    ActiveCondition,
    ConditionPhase,
    PhysiologicalEffect,
)

PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")

START_TIME = datetime(
    2026,
    1,
    1,
    tzinfo=UTC,
)


def make_patient(
    *,
    variability_factor: float = 1.0,
) -> PatientProfile:
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
        variability_factor=variability_factor,
    )


def make_baseline_state(
    *,
    timestamp: datetime = START_TIME,
) -> PhysiologicalState:
    return PhysiologicalState(
        timestamp=timestamp,
        heart_rate_bpm=72.0,
        spo2_pct=98.0,
        respiration_rate_bpm=14.0,
        temperature_c=36.8,
        systolic_bp_mmhg=120.0,
        diastolic_bp_mmhg=76.0,
    )


def test_next_state_advances_timestamp() -> None:
    patient = make_patient()
    previous_state = make_baseline_state()

    engine = PhysiologyEngine(
        Random(42),
    )

    next_time = START_TIME + timedelta(seconds=5)

    next_state = engine.next_state(
        patient=patient,
        previous_state=previous_state,
        timestamp=next_time,
    )

    assert next_state.timestamp == next_time


def test_baseline_state_remains_near_patient_baseline() -> None:
    patient = make_patient(
        variability_factor=0.000001,
    )

    previous_state = make_baseline_state()

    engine = PhysiologyEngine(
        Random(42),
    )

    next_state = engine.next_state(
        patient=patient,
        previous_state=previous_state,
        timestamp=START_TIME + timedelta(seconds=5),
    )

    assert next_state.heart_rate_bpm == pytest.approx(
        72.0,
        abs=0.001,
    )

    assert next_state.spo2_pct == pytest.approx(
        98.0,
        abs=0.001,
    )

    assert next_state.respiration_rate_bpm == pytest.approx(
        14.0,
        abs=0.001,
    )

    assert next_state.temperature_c == pytest.approx(
        36.8,
        abs=0.001,
    )

    assert next_state.systolic_bp_mmhg == pytest.approx(
        120.0,
        abs=0.001,
    )

    assert next_state.diastolic_bp_mmhg == pytest.approx(
        76.0,
        abs=0.001,
    )


def test_no_conditions_preserves_baseline_behavior() -> None:
    patient = make_patient(
        variability_factor=0.000001,
    )

    previous_state = make_baseline_state()

    engine = PhysiologyEngine(
        Random(42),
    )

    next_state = engine.next_state(
        patient=patient,
        previous_state=previous_state,
        timestamp=START_TIME + timedelta(seconds=5),
        active_conditions=[],
    )

    assert next_state.heart_rate_bpm == pytest.approx(
        72.0,
        abs=0.001,
    )

    assert next_state.spo2_pct == pytest.approx(
        98.0,
        abs=0.001,
    )

    assert next_state.respiration_rate_bpm == pytest.approx(
        14.0,
        abs=0.001,
    )


def test_condition_changes_direct_physiological_target() -> None:
    patient = make_patient(
        variability_factor=0.000001,
    )

    previous_state = make_baseline_state()

    condition = ActiveCondition(
        name="test_condition",
        phase=ConditionPhase.PROGRESSION,
        severity=1.0,
        effect=PhysiologicalEffect(
            heart_rate_delta_bpm=10.0,
            spo2_delta_pct=-5.0,
            respiration_rate_delta_bpm=4.0,
        ),
    )

    engine = PhysiologyEngine(
        Random(42),
    )

    next_state = engine.next_state(
        patient=patient,
        previous_state=previous_state,
        timestamp=START_TIME + timedelta(seconds=5),
        active_conditions=[condition],
    )

    assert (
        next_state.heart_rate_bpm
        > previous_state.heart_rate_bpm
    )

    assert (
        next_state.spo2_pct
        < previous_state.spo2_pct
    )

    assert (
        next_state.respiration_rate_bpm
        > previous_state.respiration_rate_bpm
    )


def test_condition_severity_scales_direct_effect() -> None:
    patient = make_patient(
        variability_factor=0.000001,
    )

    previous_state = make_baseline_state()

    mild_condition = ActiveCondition(
        name="test_condition",
        phase=ConditionPhase.PROGRESSION,
        severity=0.25,
        effect=PhysiologicalEffect(
            spo2_delta_pct=-8.0,
        ),
    )

    severe_condition = ActiveCondition(
        name="test_condition",
        phase=ConditionPhase.PROGRESSION,
        severity=1.0,
        effect=PhysiologicalEffect(
            spo2_delta_pct=-8.0,
        ),
    )

    mild_engine = PhysiologyEngine(
        Random(42),
    )

    severe_engine = PhysiologyEngine(
        Random(42),
    )

    mild_state = mild_engine.next_state(
        patient=patient,
        previous_state=previous_state,
        timestamp=START_TIME + timedelta(seconds=5),
        active_conditions=[mild_condition],
    )

    severe_state = severe_engine.next_state(
        patient=patient,
        previous_state=previous_state,
        timestamp=START_TIME + timedelta(seconds=5),
        active_conditions=[severe_condition],
    )

    assert severe_state.spo2_pct < mild_state.spo2_pct


def test_multiple_conditions_combine_direct_effects() -> None:
    patient = make_patient(
        variability_factor=0.000001,
    )

    previous_state = make_baseline_state()

    first_condition = ActiveCondition(
        name="condition_one",
        phase=ConditionPhase.PROGRESSION,
        severity=1.0,
        effect=PhysiologicalEffect(
            temperature_delta_c=1.0,
        ),
    )

    second_condition = ActiveCondition(
        name="condition_two",
        phase=ConditionPhase.PROGRESSION,
        severity=1.0,
        effect=PhysiologicalEffect(
            heart_rate_delta_bpm=10.0,
        ),
    )

    engine = PhysiologyEngine(
        Random(42),
    )

    next_state = engine.next_state(
        patient=patient,
        previous_state=previous_state,
        timestamp=START_TIME + timedelta(seconds=5),
        active_conditions=[
            first_condition,
            second_condition,
        ],
    )

    assert (
        next_state.temperature_c
        > previous_state.temperature_c
    )

    assert (
        next_state.heart_rate_bpm
        > previous_state.heart_rate_bpm
    )


def test_same_seed_produces_same_physiological_state() -> None:
    patient = make_patient()

    previous_state = make_baseline_state()

    first_engine = PhysiologyEngine(
        Random(42),
    )

    second_engine = PhysiologyEngine(
        Random(42),
    )

    first_state = first_engine.next_state(
        patient=patient,
        previous_state=previous_state,
        timestamp=START_TIME + timedelta(seconds=5),
    )

    second_state = second_engine.next_state(
        patient=patient,
        previous_state=previous_state,
        timestamp=START_TIME + timedelta(seconds=5),
    )

    assert first_state == second_state


def test_different_seeds_produce_different_physiological_states() -> None:
    patient = make_patient()

    previous_state = make_baseline_state()

    first_engine = PhysiologyEngine(
        Random(42),
    )

    second_engine = PhysiologyEngine(
        Random(99),
    )

    first_state = first_engine.next_state(
        patient=patient,
        previous_state=previous_state,
        timestamp=START_TIME + timedelta(seconds=5),
    )

    second_state = second_engine.next_state(
        patient=patient,
        previous_state=previous_state,
        timestamp=START_TIME + timedelta(seconds=5),
    )

    assert first_state != second_state


def test_low_spo2_response_respects_configured_lags() -> None:
    patient = make_patient(
        variability_factor=0.000001,
    )

    engine = PhysiologyEngine(
        Random(42),
    )

    state = PhysiologicalState(
        timestamp=START_TIME,
        heart_rate_bpm=72.0,
        spo2_pct=90.0,
        respiration_rate_bpm=14.0,
        temperature_c=36.8,
        systolic_bp_mmhg=120.0,
        diastolic_bp_mmhg=76.0,
    )

    states: list[PhysiologicalState] = []

    for step_number in range(1, 25):
        state = engine.next_state(
            patient=patient,
            previous_state=state,
            timestamp=(
                START_TIME
                + timedelta(seconds=5 * step_number)
            ),
        )

        states.append(state)

    state_at_20_seconds = states[3]
    state_at_45_seconds = states[8]
    state_at_75_seconds = states[14]

    # Neither compensatory response should be meaningfully
    # present before the shortest configured lag.
    assert abs(
        state_at_20_seconds.respiration_rate_bpm
        - 14.0
    ) < 0.1

    assert abs(
        state_at_20_seconds.heart_rate_bpm
        - 72.0
    ) < 0.1

    # Respiration has a 30-second lag. By 45 seconds,
    # the respiratory response should be visible.
    assert (
        state_at_45_seconds.respiration_rate_bpm
        > 14.1
    )

    # Heart rate has a 60-second lag, so it should still
    # be approximately at baseline at 45 seconds.
    assert abs(
        state_at_45_seconds.heart_rate_bpm
        - 72.0
    ) < 0.1

    # After 60 seconds, both compensatory responses
    # should be present.
    assert (
        state_at_75_seconds.respiration_rate_bpm
        > 14.1
    )

    assert (
        state_at_75_seconds.heart_rate_bpm
        > 72.1
    )