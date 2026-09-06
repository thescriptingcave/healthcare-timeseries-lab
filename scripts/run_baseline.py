from datetime import UTC, datetime, timedelta
from random import Random
from statistics import mean, pstdev
from uuid import UUID

from healthcare_timeseries_lab.patients.models import PatientProfile
from healthcare_timeseries_lab.physiology.engine import PhysiologyEngine
from healthcare_timeseries_lab.physiology.models import PhysiologicalState
from healthcare_timeseries_lab.runtime.clock import SimulationClock

SEED = 42
STEP_SECONDS = 5
DURATION_MINUTES = 60


def main() -> None:
    patient = PatientProfile(
        patient_id=UUID("11111111-1111-1111-1111-111111111111"),
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

    start_time = datetime(2026, 1, 1, tzinfo=UTC)

    clock = SimulationClock(
        start_time=start_time,
        step=timedelta(seconds=STEP_SECONDS),
    )

    engine = PhysiologyEngine(Random(SEED))

    state = PhysiologicalState(
        timestamp=clock.now,
        heart_rate_bpm=patient.baseline_heart_rate_bpm,
        spo2_pct=patient.baseline_spo2_pct,
        respiration_rate_bpm=patient.baseline_respiration_rate_bpm,
        temperature_c=patient.baseline_temperature_c,
        systolic_bp_mmhg=patient.baseline_systolic_bp_mmhg,
        diastolic_bp_mmhg=patient.baseline_diastolic_bp_mmhg,
    )

    observations = []

    observation_count = (
        DURATION_MINUTES * 60
    ) // STEP_SECONDS

    for _ in range(observation_count):
        timestamp = clock.advance()

        state = engine.next_state(
            patient=patient,
            previous_state=state,
            timestamp=timestamp,
        )

        observations.append(state)

    print(f"Observations: {len(observations)}")
    print(f"Start:        {observations[0].timestamp}")
    print(f"End:          {observations[-1].timestamp}")
    print()

    print_summary(
        "Heart Rate",
        [state.heart_rate_bpm for state in observations],
        patient.baseline_heart_rate_bpm,
    )

    print_summary(
        "SpO2",
        [state.spo2_pct for state in observations],
        patient.baseline_spo2_pct,
    )

    print_summary(
        "Respiration",
        [state.respiration_rate_bpm for state in observations],
        patient.baseline_respiration_rate_bpm,
    )

    print_summary(
        "Temperature",
        [state.temperature_c for state in observations],
        patient.baseline_temperature_c,
    )

    print_summary(
        "Systolic BP",
        [state.systolic_bp_mmhg for state in observations],
        patient.baseline_systolic_bp_mmhg,
    )

    print_summary(
        "Diastolic BP",
        [state.diastolic_bp_mmhg for state in observations],
        patient.baseline_diastolic_bp_mmhg,
    )

    print()
    print("First 5 observations:")

    for state in observations[:5]:
        print(
            state.timestamp,
            f"HR={state.heart_rate_bpm:.2f}",
            f"SpO2={state.spo2_pct:.2f}",
            f"RR={state.respiration_rate_bpm:.2f}",
            f"Temp={state.temperature_c:.2f}",
            f"SBP={state.systolic_bp_mmhg:.2f}",
            f"DBP={state.diastolic_bp_mmhg:.2f}",
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