from datetime import UTC, datetime
from uuid import UUID

import pytest

from healthcare_timeseries_lab.physiology.models import PhysiologicalState
from healthcare_timeseries_lab.telemetry.events import VitalsTelemetryEvent

EVENT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
SIMULATION_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
PATIENT_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
DEVICE_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")


def make_state() -> PhysiologicalState:
    return PhysiologicalState(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        heart_rate_bpm=72.0,
        spo2_pct=98.0,
        respiration_rate_bpm=14.0,
        temperature_c=36.8,
        systolic_bp_mmhg=120.0,
        diastolic_bp_mmhg=76.0,
    )


def test_telemetry_event_can_be_created_from_physiological_state() -> None:
    state = make_state()

    event = VitalsTelemetryEvent.from_physiological_state(
        event_id=EVENT_ID,
        simulation_id=SIMULATION_ID,
        patient_id=PATIENT_ID,
        device_id=DEVICE_ID,
        sequence_number=1,
        state=state,
    )

    assert event.event_time == state.timestamp
    assert event.heart_rate_bpm == state.heart_rate_bpm
    assert event.spo2_pct == state.spo2_pct
    assert event.respiration_rate_bpm == state.respiration_rate_bpm
    assert event.temperature_c == state.temperature_c
    assert event.systolic_bp_mmhg == state.systolic_bp_mmhg
    assert event.diastolic_bp_mmhg == state.diastolic_bp_mmhg

    assert event.device_status == "CONNECTED"
    assert event.quality_code == "GOOD"


def test_telemetry_event_preserves_identifiers() -> None:
    event = VitalsTelemetryEvent.from_physiological_state(
        event_id=EVENT_ID,
        simulation_id=SIMULATION_ID,
        patient_id=PATIENT_ID,
        device_id=DEVICE_ID,
        sequence_number=42,
        state=make_state(),
    )

    assert event.event_id == EVENT_ID
    assert event.simulation_id == SIMULATION_ID
    assert event.patient_id == PATIENT_ID
    assert event.device_id == DEVICE_ID
    assert event.sequence_number == 42


def test_telemetry_event_rejects_invalid_sequence_number() -> None:
    with pytest.raises(ValueError, match="sequence_number"):
        VitalsTelemetryEvent.from_physiological_state(
            event_id=EVENT_ID,
            simulation_id=SIMULATION_ID,
            patient_id=PATIENT_ID,
            device_id=DEVICE_ID,
            sequence_number=0,
            state=make_state(),
        )