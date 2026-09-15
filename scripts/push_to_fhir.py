from __future__ import annotations

from datetime import UTC, datetime, timedelta
from random import Random
from uuid import UUID, uuid4

from fhir.resources.bundle import Bundle

from healthcare_timeseries_lab.fhir import (
    VITALS_PANEL_DISPLAY,
    VITALS_PANEL_LOINC,
    HapiFhirClient,
    build_encounter,
    build_observation,
    build_patient,
)
from healthcare_timeseries_lab.patients.models import PatientProfile
from healthcare_timeseries_lab.physiology.engine import PhysiologyEngine
from healthcare_timeseries_lab.physiology.models import PhysiologicalState
from healthcare_timeseries_lab.runtime.clock import SimulationClock
from healthcare_timeseries_lab.telemetry.events import VitalsTelemetryEvent

SEED = 42
STEP_SECONDS = 5
TICKS = 12
PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
DEVICE_ID = UUID("22222222-2222-2222-2222-222222222222")
SIMULATION_ID = UUID("33333333-3333-3333-3333-333333333333")
ENCOUNTER_ID = "enc-2026-01-01-090000"
START = datetime(2026, 1, 1, tzinfo=UTC)


def main() -> None:
    profile = PatientProfile(
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

    clock = SimulationClock(
        start_time=START,
        step=timedelta(seconds=STEP_SECONDS),
    )
    engine = PhysiologyEngine(Random(SEED))

    patient_resource = build_patient(profile)

    fhir = HapiFhirClient()
    version = fhir.check_capability()
    print(f"capability version: {version}")

    state = PhysiologicalState(
        timestamp=clock.now,
        heart_rate_bpm=profile.baseline_heart_rate_bpm,
        spo2_pct=profile.baseline_spo2_pct,
        respiration_rate_bpm=profile.baseline_respiration_rate_bpm,
        temperature_c=profile.baseline_temperature_c,
        systolic_bp_mmhg=profile.baseline_systolic_bp_mmhg,
        diastolic_bp_mmhg=profile.baseline_diastolic_bp_mmhg,
    )

    first_event = None
    entries = []

    for seq in range(1, TICKS + 1):
        timestamp = clock.advance()
        state = engine.next_state(
            patient=profile,
            previous_state=state,
            timestamp=timestamp,
        )

        event = VitalsTelemetryEvent(
            event_id=uuid4(),
            simulation_id=SIMULATION_ID,
            patient_id=PATIENT_ID,
            device_id=DEVICE_ID,
            event_time=timestamp,
            sequence_number=seq,
            heart_rate_bpm=state.heart_rate_bpm,
            spo2_pct=state.spo2_pct,
            respiration_rate_bpm=state.respiration_rate_bpm,
            temperature_c=state.temperature_c,
            systolic_bp_mmhg=state.systolic_bp_mmhg,
            diastolic_bp_mmhg=state.diastolic_bp_mmhg,
        )
        if first_event is None:
            encounter = build_encounter(
                patient_ref=f"Patient/{PATIENT_ID}",
                encounter_id=ENCOUNTER_ID,
                event=event,
            )
            entries.append(
                {
                    "resource": patient_resource.model_dump(exclude_none=True),
                    "request": {"method": "POST", "url": "Patient"},
                }
            )
            entries.append(
                {
                    "resource": encounter.model_dump(exclude_none=True),
                    "request": {"method": "POST", "url": "Encounter"},
                }
            )
            first_event = event

        observation = build_observation(
            event,
            subject_ref=f"Patient/{PATIENT_ID}",
            encounter_ref=f"Encounter/{ENCOUNTER_ID}",
        )
        entries.append(
            {
                "resource": observation.model_dump(exclude_none=True),
                "request": {"method": "POST", "url": "Observation"},
            }
        )

    bundle = Bundle(
        type="transaction",
        entry=entries,
    )

    print(f"sending {len(entries)} entries ({TICKS} Observations) as transaction")
    status = fhir.send_transaction(bundle)
    print(f"transaction status: {status}")

    count = fhir.count_observations(VITALS_PANEL_LOINC)
    print(f"{VITALS_PANEL_LOINC} ({VITALS_PANEL_DISPLAY}) observations: {count}")
    if count < TICKS:
        print("FAIL: expected at least", TICKS)
        raise SystemExit(1)

    print("MILESTONE 2 PUSH OK")


if __name__ == "__main__":
    main()
