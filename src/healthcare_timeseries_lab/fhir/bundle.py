"""FHIR transaction-Bundle builder shared by the pipelines (M7)."""

from __future__ import annotations

from fhir.resources.bundle import Bundle

from healthcare_timeseries_lab.fhir.client import HapiFhirClient
from healthcare_timeseries_lab.fhir.models import (
    build_encounter,
    build_observation,
    build_patient,
)
from healthcare_timeseries_lab.patients.models import PatientProfile
from healthcare_timeseries_lab.telemetry.events import VitalsTelemetryEvent


def build_vitals_bundle(
    events: list[VitalsTelemetryEvent],
    *,
    patient: PatientProfile,
    encounter_id: str,
) -> Bundle:
    """Build one FHIR ``transaction`` Bundle for a simulation's events.

    The Bundle carries the Patient and the Encounter exactly once, followed by
    one vital-signs panel ``Observation`` per event (LOINC ``85353-1``).
    """
    if not events:
        raise ValueError("cannot build a vitals bundle from an empty event list")

    patient_ref = f"Patient/{patient.patient_id}"
    encounter_ref = f"Encounter/{encounter_id}"

    entries: list[dict] = [
        {
            "resource": build_patient(patient).model_dump(exclude_none=True),
            "request": {"method": "POST", "url": "Patient"},
        },
        {
            "resource": build_encounter(
                events[0],
                patient_ref=patient_ref,
                encounter_id=encounter_id,
            ).model_dump(exclude_none=True),
            "request": {"method": "POST", "url": "Encounter"},
        },
    ]

    for event in events:
        observation = build_observation(
            event,
            subject_ref=patient_ref,
            encounter_ref=encounter_ref,
        )
        entries.append(
            {
                "resource": observation.model_dump(exclude_none=True),
                "request": {"method": "POST", "url": "Observation"},
            }
        )

    return Bundle(type="transaction", entry=entries)


def push_vitals_bundle(
    events: list[VitalsTelemetryEvent],
    *,
    patient: PatientProfile,
    encounter_id: str,
    client: HapiFhirClient | None = None,
) -> tuple[str, list[str], int]:
    """POST the vitals Bundle to HAPI; return ``(status, issues, total)``."""
    bundle = build_vitals_bundle(
        events,
        patient=patient,
        encounter_id=encounter_id,
    )
    fhir = client or HapiFhirClient()
    status, issues, total = fhir.send_transaction(bundle)
    return status, issues, total


__all__ = [
    "build_vitals_bundle",
    "push_vitals_bundle",
]