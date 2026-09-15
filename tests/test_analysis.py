from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from healthcare_timeseries_lab.analysis import (
    align_observed_to_truth,
    dropout_count,
    error_metrics,
    quality_counts,
)
from healthcare_timeseries_lab.physiology.models import PhysiologicalState
from healthcare_timeseries_lab.telemetry.events import VitalsTelemetryEvent

EVENT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
SIMULATION_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
PATIENT_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
DEVICE_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")

START = datetime(2026, 1, 1, tzinfo=UTC)


def make_state(
    *,
    sequence_number: int,
    spo2_pct: float = 98.0,
) -> PhysiologicalState:
    return PhysiologicalState(
        timestamp=START,
        heart_rate_bpm=72.0,
        spo2_pct=spo2_pct,
        respiration_rate_bpm=14.0,
        temperature_c=36.8,
        systolic_bp_mmhg=120.0,
        diastolic_bp_mmhg=76.0,
    )


def make_event(
    *,
    sequence_number: int,
    spo2_pct: float,
    quality_code: str = "GOOD",
) -> VitalsTelemetryEvent:
    return VitalsTelemetryEvent(
        event_id=EVENT_ID,
        simulation_id=SIMULATION_ID,
        patient_id=PATIENT_ID,
        device_id=DEVICE_ID,
        event_time=START,
        sequence_number=sequence_number,
        heart_rate_bpm=72.0,
        spo2_pct=spo2_pct,
        respiration_rate_bpm=14.0,
        temperature_c=36.8,
        systolic_bp_mmhg=120.0,
        diastolic_bp_mmhg=76.0,
        quality_code=quality_code,
    )


def test_alignment_pairs_true_states_with_events_and_marks_gaps() -> None:
    states = [
        make_state(sequence_number=1),
        make_state(sequence_number=2),
        make_state(sequence_number=3),
    ]
    events = [
        make_event(sequence_number=1, spo2_pct=98.0),
        make_event(sequence_number=3, spo2_pct=98.0),
    ]

    samples = align_observed_to_truth(states, events)

    assert len(samples) == 3
    assert samples[0].event is not None
    assert samples[1].event is None
    assert samples[2].event is not None
    assert dropout_count(samples) == 1


def test_error_metrics_calculate_bias_mae_rmse() -> None:
    states = [
        make_state(sequence_number=1),
        make_state(sequence_number=2),
        make_state(sequence_number=3),
    ]
    events = [
        make_event(sequence_number=1, spo2_pct=96.0),
        make_event(sequence_number=2, spo2_pct=99.0),
        make_event(sequence_number=3, spo2_pct=102.0),
    ]

    metrics = error_metrics(
        align_observed_to_truth(states, events),
        "spo2_pct",
    )

    assert metrics.n == 3
    assert metrics.bias == pytest.approx(1.0)
    assert metrics.mae == pytest.approx(7 / 3)
    assert metrics.rmse == pytest.approx(7**0.5)
    assert metrics.max_abs_error == 4.0
    assert metrics.p95_abs_error == 4.0


def test_error_metrics_empty_samples() -> None:
    states = [
        make_state(sequence_number=1),
        make_state(sequence_number=2),
    ]

    metrics = error_metrics(
        align_observed_to_truth(states, []),
        "spo2_pct",
    )

    assert metrics.n == 0
    assert metrics.missing == 2
    assert metrics.rmse == 0.0


def test_error_metrics_rejects_unknown_channel() -> None:
    with pytest.raises(ValueError, match="unknown channel"):
        error_metrics([], "invalid_channel")


def test_quality_counts_tallies_present_samples() -> None:
    events = [
        make_event(sequence_number=1, spo2_pct=98.0, quality_code="GOOD"),
        make_event(sequence_number=2, spo2_pct=98.0, quality_code="DEGRADED"),
        make_event(sequence_number=3, spo2_pct=98.0, quality_code="GOOD"),
    ]

    samples = align_observed_to_truth(
        [make_state(sequence_number=i) for i in (1, 2, 3)],
        events,
    )

    assert quality_counts(samples) == {"GOOD": 2, "DEGRADED": 1}


def test_runner_events_and_states_align_by_sequence_number() -> None:
    from healthcare_timeseries_lab.patients.models import PatientProfile
    from healthcare_timeseries_lab.simulation.runner import (
        BaselineSimulationConfig,
        run_baseline_simulation,
    )

    patient = PatientProfile(
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

    config = BaselineSimulationConfig(
        simulation_id=SIMULATION_ID,
        device_id=DEVICE_ID,
        start_time=START,
        duration=timedelta(seconds=15),
        step=timedelta(seconds=5),
        seed=42,
    )

    result = run_baseline_simulation(patient=patient, config=config)

    samples = align_observed_to_truth(result.states, result.events)

    assert len(samples) == 3
    assert all(sample.event is not None for sample in samples)
    assert [sample.sequence_number for sample in samples] == [1, 2, 3]