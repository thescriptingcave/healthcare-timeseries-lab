from datetime import UTC, datetime
from uuid import UUID

import pytest

from healthcare_timeseries_lab.ground_truth.models import (
    ClinicalGroundTruthEvent,
    ClinicalTruthEventType,
)
from healthcare_timeseries_lab.scenarios.models import ConditionPhase

EVENT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
SIMULATION_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
PATIENT_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def make_event(**overrides: object) -> ClinicalGroundTruthEvent:
    values = {
        "event_id": EVENT_ID,
        "simulation_id": SIMULATION_ID,
        "patient_id": PATIENT_ID,
        "event_time": datetime(
            2026,
            1,
            1,
            2,
            0,
            tzinfo=UTC,
        ),
        "event_type": ClinicalTruthEventType.CONDITION_STARTED,
        "condition_name": "hypoxemia",
        "condition_phase": ConditionPhase.ONSET,
        "severity": 0.4,
    }

    values.update(overrides)

    return ClinicalGroundTruthEvent(**values)


def test_ground_truth_event_is_created() -> None:
    event = make_event()

    assert event.event_id == EVENT_ID
    assert event.simulation_id == SIMULATION_ID
    assert event.patient_id == PATIENT_ID

    assert event.condition_name == "hypoxemia"
    assert event.condition_phase == ConditionPhase.ONSET
    assert event.severity == 0.4

    assert (
        event.event_type
        == ClinicalTruthEventType.CONDITION_STARTED
    )


def test_ground_truth_event_rejects_invalid_severity() -> None:
    with pytest.raises(ValueError, match="severity"):
        make_event(severity=1.5)


def test_ground_truth_event_allows_missing_severity() -> None:
    event = make_event(severity=None)

    assert event.severity is None


def test_ground_truth_event_rejects_empty_condition_name() -> None:
    with pytest.raises(ValueError, match="condition_name"):
        make_event(condition_name="")


def test_ground_truth_event_records_progression_phase() -> None:
    event = make_event(
        event_type=ClinicalTruthEventType.CONDITION_UPDATED,
        condition_phase=ConditionPhase.PROGRESSION,
        severity=0.6,
    )

    assert event.event_type == ClinicalTruthEventType.CONDITION_UPDATED
    assert event.condition_phase == ConditionPhase.PROGRESSION
    assert event.severity == 0.6


def test_resolved_condition_can_be_recorded() -> None:
    event = make_event(
        event_type=ClinicalTruthEventType.CONDITION_ENDED,
        condition_phase=ConditionPhase.RESOLVED,
        severity=0.0,
    )

    assert event.event_type == ClinicalTruthEventType.CONDITION_ENDED
    assert event.condition_phase == ConditionPhase.RESOLVED
    assert event.severity == 0.0