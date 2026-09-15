"""LOINC/UCUM vital-signs panel mapping for simulated telemetry.

One ``VitalsTelemetryEvent`` becomes a single FHIR ``Observation`` whose
``code`` is the LOINC *Vital signs* panel ``85353-1``, with each of the six
simulated channels serialised as one ``component`` (LOINC ``Coding`` +
UCUM ``Quantity``).
"""

from __future__ import annotations

from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
from fhir.resources.encounter import Encounter
from fhir.resources.observation import Observation, ObservationComponent
from fhir.resources.patient import Patient
from fhir.resources.quantity import Quantity

from healthcare_timeseries_lab.patients.models import PatientProfile
from healthcare_timeseries_lab.telemetry.events import VitalsTelemetryEvent

LOINC_SYSTEM = "http://loinc.org"
UCUM_SYSTEM = "http://unitsofmeasure.org"

VITALS_PANEL_LOINC = "85353-1"
VITALS_PANEL_DISPLAY = "Vital signs"

# channel -> (LOINC code, LOINC display, UCUM unit-code, UCUM display)
VITAL_LOINC_CODES: dict[str, tuple[str, str, str, str]] = {
    "heart_rate": ("8867-4", "Heart rate", "/min", "beats per minute"),
    "spo2": ("2708-6", "Oxygen saturation", "%", "percent"),
    "respiration": ("9279-1", "Respiratory rate", "/min", "breaths per minute"),
    "temperature": ("8310-5", "Body temperature", "Cel", "celsius"),
    "systolic_bp": ("8480-6", "Systolic blood pressure", "mm[Hg]", "mmHg"),
    "diastolic_bp": ("8462-4", "Diastolic blood pressure", "mm[Hg]", "mmHg"),
}

# telemetry event attribute -> channel key in VITAL_LOINC_CODES
_EVENT_ATTR_TO_CHANNEL: dict[str, str] = {
    "heart_rate_bpm": "heart_rate",
    "spo2_pct": "spo2",
    "respiration_rate_bpm": "respiration",
    "temperature_c": "temperature",
    "systolic_bp_mmhg": "systolic_bp",
    "diastolic_bp_mmhg": "diastolic_bp",
}


def _coding(loinc_code: str, display: str) -> Coding:
    return Coding(system=LOINC_SYSTEM, code=loinc_code, display=display)


def _component(loinc_code: str, display: str, value: float, unit_code: str, unit_display: str) -> ObservationComponent:
    return ObservationComponent(
        code=CodeableConcept(coding=[_coding(loinc_code, display)]),
        valueQuantity=Quantity(
            value=value,
            unit=unit_display,
            system=UCUM_SYSTEM,
            code=unit_code,
        ),
    )


def build_observation(
    event: VitalsTelemetryEvent,
    *,
    subject_ref: str,
    encounter_ref: str,
) -> Observation:
    """Build one vital-signs panel ``Observation`` from a telemetry event."""
    components: list[ObservationComponent] = []
    for attr, channel in _EVENT_ATTR_TO_CHANNEL.items():
        loinc_code, loinc_display, ucum_code, ucum_display = VITAL_LOINC_CODES[channel]
        components.append(
            _component(loinc_code, loinc_display, getattr(event, attr), ucum_code, ucum_display)
        )

    return Observation(
        status="final",
        code=CodeableConcept(coding=[_coding(VITALS_PANEL_LOINC, VITALS_PANEL_DISPLAY)]),
        subject={"reference": subject_ref},
        encounter={"reference": encounter_ref},
        effectiveDateTime=event.event_time.isoformat(),
        component=components,
    )






def build_patient(profile: PatientProfile) -> Patient:
    """Build the FHIR ``Patient`` resource for a simulated profile."""
    return Patient(
        id=str(profile.patient_id),
        identifier=[
            {
                "system": "https://sim.htl/patient",
                "value": str(profile.patient_id),
            }
        ],
        gender=str(profile.sex),
    )


def build_encounter(
    event: VitalsTelemetryEvent,
    *,
    patient_ref: str,
    encounter_id: str,
) -> Encounter:
    """Build the FHIR ``Encounter`` for a simulation window."""
    return Encounter(
        id=encounter_id,
        status="in-progress",
        class_fhir=[
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                        "code": "AMB",
                        "display": "ambulatory",
                    }
                ],
            }
        ],
        subject={"reference": patient_ref},
        actualPeriod={
            "start": event.event_time.isoformat(),
        },
    )
