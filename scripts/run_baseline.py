from datetime import UTC, datetime, timedelta
from statistics import mean, pstdev
from uuid import UUID

from healthcare_timeseries_lab.patients.models import PatientProfile
from healthcare_timeseries_lab.simulation.runner import (
    BaselineSimulationConfig,
    run_baseline_simulation,
)

SEED = 42
STEP_SECONDS = 5
DURATION_MINUTES = 60

PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
SIMULATION_ID = UUID("22222222-2222-2222-2222-222222222222")
DEVICE_ID = UUID("33333333-3333-3333-3333-333333333333")


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


def main() -> None:
    patient = make_patient()
    start_time = datetime(2026, 1, 1, tzinfo=UTC)

    result = run_baseline_simulation(
        patient=patient,
        config=BaselineSimulationConfig(
            simulation_id=SIMULATION_ID,
            device_id=DEVICE_ID,
            start_time=start_time,
            duration=timedelta(minutes=DURATION_MINUTES),
            step=timedelta(seconds=STEP_SECONDS),
            seed=SEED,
        ),
    )

    observations = [
        {
            "heart_rate_bpm": event.heart_rate_bpm,
            "spo2_pct": event.spo2_pct,
            "respiration_rate_bpm": event.respiration_rate_bpm,
            "temperature_c": event.temperature_c,
            "systolic_bp_mmhg": event.systolic_bp_mmhg,
            "diastolic_bp_mmhg": event.diastolic_bp_mmhg,
        }
        for event in result.events
    ]

    print(f"Observations: {len(observations)}")
    print(f"Start:        {result.events[0].event_time}")
    print(f"End:          {result.events[-1].event_time}")
    print()

    print_summary(
        "Heart Rate",
        [obs["heart_rate_bpm"] for obs in observations],
        patient.baseline_heart_rate_bpm,
    )

    print_summary(
        "SpO2",
        [obs["spo2_pct"] for obs in observations],
        patient.baseline_spo2_pct,
    )

    print_summary(
        "Respiration",
        [obs["respiration_rate_bpm"] for obs in observations],
        patient.baseline_respiration_rate_bpm,
    )

    print_summary(
        "Temperature",
        [obs["temperature_c"] for obs in observations],
        patient.baseline_temperature_c,
    )

    print_summary(
        "Systolic BP",
        [obs["systolic_bp_mmhg"] for obs in observations],
        patient.baseline_systolic_bp_mmhg,
    )

    print_summary(
        "Diastolic BP",
        [obs["diastolic_bp_mmhg"] for obs in observations],
        patient.baseline_diastolic_bp_mmhg,
    )

    print()
    print("First 5 observations:")

    for event in result.events[:5]:
        print(
            event.event_time,
            f"HR={event.heart_rate_bpm:.2f}",
            f"SpO2={event.spo2_pct:.2f}",
            f"RR={event.respiration_rate_bpm:.2f}",
            f"Temp={event.temperature_c:.2f}",
            f"SBP={event.systolic_bp_mmhg:.2f}",
            f"DBP={event.diastolic_bp_mmhg:.2f}",
        )


def print_summary(
    name: str,
    values: list[float],
    baseline: float,
) -> None:
    print(
        f"{name:<12} "
        f"baseline={baseline:7.2f} "
        f"mean={mean(values):7.2f} "
        f"stddev={pstdev(values):6.3f} "
        f"min={min(values):7.2f} "
        f"max={max(values):7.2f}"
    )


if __name__ == "__main__":
    main()