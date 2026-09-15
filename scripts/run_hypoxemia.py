from csv import DictWriter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import mean, stdev
from uuid import UUID

from healthcare_timeseries_lab.device import (
    default_bedside_monitor_config,
)
from healthcare_timeseries_lab.patients.models import PatientProfile
from healthcare_timeseries_lab.simulation.pipeline import (
    PipelineConfig,
    PipelineResult,
    run_pipeline,
)

PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
SIMULATION_ID = UUID("44444444-4444-4444-4444-444444444444")
DEVICE_ID = UUID("33333333-3333-3333-3333-333333333333")

START_TIME = datetime(
    2026,
    1,
    1,
    tzinfo=UTC,
)

OUTPUT_PATH = Path("output/progressive_hypoxemia.csv")
TRUTH_OUTPUT_PATH = Path("output/progressive_hypoxemia_truth.csv")


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


def make_config() -> PipelineConfig:
    return PipelineConfig(
        patient=make_patient(),
        simulation_id=SIMULATION_ID,
        device_id=DEVICE_ID,
        scenario_name="progressive_hypoxemia",
        scenario_version="1.0",
        start_time=START_TIME,
        duration=timedelta(hours=6),
        step=timedelta(seconds=5),
        seed=42,
        device=default_bedside_monitor_config(),
    )


def events_between(
    result: PipelineResult,
    start: timedelta,
    end: timedelta,
):
    window_start = START_TIME + start
    window_end = START_TIME + end

    return [
        event
        for event in result.events
        if window_start <= event.event_time < window_end
    ]


def summarize_signal(values: list[float]) -> str:
    return (
        f"mean={mean(values):6.2f} "
        f"std={stdev(values):5.2f} "
        f"min={min(values):6.2f} "
        f"max={max(values):6.2f}"
    )


def print_window_summary(
    result: PipelineResult,
    *,
    label: str,
    start: timedelta,
    end: timedelta,
) -> None:
    events = events_between(result, start, end)

    heart_rate = [
        event.heart_rate_bpm
        for event in events
    ]

    spo2 = [
        event.spo2_pct
        for event in events
    ]

    respiration = [
        event.respiration_rate_bpm
        for event in events
    ]

    temperature = [
        event.temperature_c
        for event in events
    ]

    systolic = [
        event.systolic_bp_mmhg
        for event in events
    ]

    diastolic = [
        event.diastolic_bp_mmhg
        for event in events
    ]

    print()
    print(label)
    print("-" * len(label))

    print(
        "Heart Rate     ",
        summarize_signal(heart_rate),
    )

    print(
        "SpO2           ",
        summarize_signal(spo2),
    )

    print(
        "Respiration    ",
        summarize_signal(respiration),
    )

    print(
        "Temperature    ",
        summarize_signal(temperature),
    )

    print(
        "Systolic BP    ",
        summarize_signal(systolic),
    )

    print(
        "Diastolic BP   ",
        summarize_signal(diastolic),
    )


def write_csv(result: PipelineResult) -> None:
    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = DictWriter(
            file,
            fieldnames=[
                "event_time",
                "sequence_number",
                "heart_rate_bpm",
                "spo2_pct",
                "respiration_rate_bpm",
                "temperature_c",
                "systolic_bp_mmhg",
                "diastolic_bp_mmhg",
                "device_status",
                "quality_code",
            ],
        )

        writer.writeheader()

        for event in result.events:
            writer.writerow(
                {
                    "event_time": event.event_time.isoformat(),
                    "sequence_number": event.sequence_number,
                    "heart_rate_bpm": event.heart_rate_bpm,
                    "spo2_pct": event.spo2_pct,
                    "respiration_rate_bpm": (
                        event.respiration_rate_bpm
                    ),
                    "temperature_c": event.temperature_c,
                    "systolic_bp_mmhg": (
                        event.systolic_bp_mmhg
                    ),
                    "diastolic_bp_mmhg": (
                        event.diastolic_bp_mmhg
                    ),
                    "device_status": event.device_status,
                    "quality_code": event.quality_code,
                }
            )


def write_truth_csv(result: PipelineResult) -> None:
    TRUTH_OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with TRUTH_OUTPUT_PATH.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = DictWriter(
            file,
            fieldnames=[
                "event_time",
                "sequence_number",
                "heart_rate_bpm",
                "spo2_pct",
                "respiration_rate_bpm",
                "temperature_c",
                "systolic_bp_mmhg",
                "diastolic_bp_mmhg",
            ],
        )

        writer.writeheader()

        for sequence_number, state in enumerate(result.states, start=1):
            writer.writerow(
                {
                    "event_time": state.timestamp.isoformat(),
                    "sequence_number": sequence_number,
                    "heart_rate_bpm": state.heart_rate_bpm,
                    "spo2_pct": state.spo2_pct,
                    "respiration_rate_bpm": state.respiration_rate_bpm,
                    "temperature_c": state.temperature_c,
                    "systolic_bp_mmhg": state.systolic_bp_mmhg,
                    "diastolic_bp_mmhg": state.diastolic_bp_mmhg,
                }
            )


def print_ground_truth(result: PipelineResult) -> None:
    print()
    print("Clinical Ground Truth")
    print("---------------------")

    for event in result.clinical_ground_truth:
        print(
            event.event_time.isoformat(),
            event.event_type.value,
            event.condition_name,
            f"severity={event.severity}",
        )


def execute() -> None:
    result = run_pipeline(config=make_config())

    print("Progressive Hypoxemia Simulation")
    print("================================")
    print(f"Simulation ID: {result.run.simulation_id}")
    print(f"Scenario:      {result.run.scenario_name}")
    print(f"Version:       {result.run.scenario_version}")
    print(f"Seed:          {result.run.seed}")
    print(f"Observations:  {len(result.events)}")
    print(f"Start:         {result.run.start_time}")
    print(f"End:           {result.run.end_time}")
    print(f"Kafka:         produced {result.produced}")
    print(f"Lakehouse:     {result.lakehouse_inserted} rows")
    print(
        "FHIR:          "
        f"{result.fhir_transactions} entries (status {result.fhir_status})"
    )

    for issue in result.fhir_issues:
        if "information/" in issue:
            continue
        print(f"  FHIR issue: {issue}")

    print_window_summary(
        result,
        label="Baseline: 01:00-02:00",
        start=timedelta(hours=1),
        end=timedelta(hours=2),
    )

    print_window_summary(
        result,
        label="Onset: 02:00-02:15",
        start=timedelta(hours=2),
        end=timedelta(hours=2, minutes=15),
    )

    print_window_summary(
        result,
        label="Progression: 02:15-03:00",
        start=timedelta(hours=2, minutes=15),
        end=timedelta(hours=3),
    )

    print_window_summary(
        result,
        label="Plateau: 03:00-04:00",
        start=timedelta(hours=3),
        end=timedelta(hours=4),
    )

    print_window_summary(
        result,
        label="Recovery: 04:00-05:00",
        start=timedelta(hours=4),
        end=timedelta(hours=5),
    )

    print_window_summary(
        result,
        label="Post-Recovery: 05:00-06:00",
        start=timedelta(hours=5),
        end=timedelta(hours=6),
    )

    print_ground_truth(result)

    write_csv(result)
    write_truth_csv(result)

    print()
    print(f"CSV written to: {OUTPUT_PATH}")
    print(f"Truth CSV written to: {TRUTH_OUTPUT_PATH}")


if __name__ == "__main__":
    execute()