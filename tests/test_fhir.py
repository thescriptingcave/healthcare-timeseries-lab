"""Unit tests for the FHIR vitals transaction-Bundle helper (Milestone 7).

Pure contract checks — no live HAPI FHIR required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from healthcare_timeseries_lab.fhir.bundle import (
    build_vitals_bundle,
    push_vitals_bundle,
)
from healthcare_timeseries_lab.patients.models import PatientProfile
from healthcare_timeseries_lab.telemetry.events import VitalsTelemetryEvent

PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
SIMULATION_ID = UUID("33333333-3333-3333-3333-333333333333")
DEVICE_ID = UUID("22222222-2222-2222-2222-222222222222")
ENCOUNTER_ID = "enc-33333333-3333-3333-3333-333333333333"


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


def make_event(sequence_number: int) -> VitalsTelemetryEvent:
    return VitalsTelemetryEvent(
        event_id=UUID(f"aaaaaaaa-aaaa-aaaa-aaaa-{sequence_number:012d}"),
        simulation_id=SIMULATION_ID,
        patient_id=PATIENT_ID,
        device_id=DEVICE_ID,
        event_time=datetime(
            2026,
            1,
            1,
            0,
            0,
            sequence_number * 5,
            tzinfo=UTC,
        ),
        sequence_number=sequence_number,
        heart_rate_bpm=72.0,
        spo2_pct=98.0,
        respiration_rate_bpm=14.0,
        temperature_c=36.8,
        systolic_bp_mmhg=120.0,
        diastolic_bp_mmhg=76.0,
    )


def test_bundle_is_a_transaction() -> None:
    bundle = build_vitals_bundle(
        [make_event(1)],
        patient=make_patient(),
        encounter_id=ENCOUNTER_ID,
    )
    assert bundle.type == "transaction"
    assert len(bundle.entry) == 3


def test_bundle_carries_patient_encounter_then_observations() -> None:
    bundle = build_vitals_bundle(
        [make_event(1), make_event(2), make_event(3)],
        patient=make_patient(),
        encounter_id=ENCOUNTER_ID,
    )

    resource_types = [
        type(entry.resource).__resource_type__
        for entry in bundle.entry
    ]

    assert resource_types == [
        "Patient",
        "Encounter",
        "Observation",
        "Observation",
        "Observation",
    ]

    assert bundle.entry[1].request.url == "Encounter"
    assert bundle.entry[2].request.url == "Observation"


def test_observations_reference_patient_and_encounter() -> None:
    bundle = build_vitals_bundle(
        [make_event(1)],
        patient=make_patient(),
        encounter_id=ENCOUNTER_ID,
    )

    observation = bundle.entry[2].resource
    assert observation.subject.reference == f"Patient/{PATIENT_ID}"
    assert observation.encounter.reference == f"Encounter/{ENCOUNTER_ID}"
    assert observation.code.coding[0].code == "85353-1"


def test_empty_event_list_is_rejected() -> None:
    with pytest.raises(ValueError, match="empty"):
        build_vitals_bundle(
            [],
            patient=make_patient(),
            encounter_id=ENCOUNTER_ID,
        )


def test_push_vitals_bundle_forwards_client_result() -> None:
    class FakeClient:
        def send_transaction(self, bundle):
            self.received = bundle
            return "201", [], len(bundle.entry)

    client = FakeClient()
    status, issues, total = push_vitals_bundle(
        [make_event(1), make_event(2)],
        patient=make_patient(),
        encounter_id=ENCOUNTER_ID,
        client=client,  # type: ignore[arg-type]
    )

    assert status == "201"
    assert issues == []
    assert total == 4
    assert client.received.type == "transaction"