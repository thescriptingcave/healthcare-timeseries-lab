"""Unified simulation -> pipeline runner (Milestones 7-8).

Simulates a scenario (``baseline`` or a clinical condition from the scenario
library), then streams the result through:

    Kafka (Avro + Schema Registry) -> Iceberg lakehouse -> HAPI FHIR

By default an optional device/fault layer (Milestone 8) sits between the true
physiology and the observed telemetry; pass ``--no-device`` to skip it.
This supersedes the narrow ``run_kafka_streaming.py`` demo: it supports any
registered scenario and always pushes FHIR Observations for the simulated
window.

Run with::

    uv run python scripts/run_pipeline.py --scenario baseline
    uv run python scripts/run_pipeline.py --scenario progressive_hypoxemia
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from uuid import UUID

from healthcare_timeseries_lab.device import (
    default_bedside_monitor_config,
)
from healthcare_timeseries_lab.patients.models import PatientProfile
from healthcare_timeseries_lab.simulation.pipeline import (
    SCENARIOS,
    PipelineConfig,
    run_pipeline,
)

PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
SIMULATION_ID = UUID("33333333-3333-3333-3333-333333333333")
DEVICE_ID = UUID("22222222-2222-2222-2222-222222222222")

START_TIME = datetime(2026, 1, 1, tzinfo=UTC)

DEFAULT_MINUTES = 10
DEFAULT_STEP_SECONDS = 5


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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_pipeline.py",
        description="Simulate a scenario and stream it to Kafka/lakehouse/FHIR.",
    )
    parser.add_argument(
        "--scenario",
        choices=sorted(SCENARIOS),
        default="baseline",
        help="scenario to simulate (default: baseline)",
    )
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=DEFAULT_MINUTES,
        help=f"simulation duration in minutes (default: {DEFAULT_MINUTES})",
    )
    parser.add_argument(
        "--step-seconds",
        type=int,
        default=DEFAULT_STEP_SECONDS,
        help=f"sampling step in seconds (default: {DEFAULT_STEP_SECONDS})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="simulation random seed (default: 42)",
    )
    parser.add_argument(
        "--simulation-id",
        type=UUID,
        default=SIMULATION_ID,
        help="simulation UUID (default: deterministic constant)",
    )
    parser.add_argument(
        "--no-device",
        action="store_true",
        help="disable the device/fault layer (measure noise, latency, ...)",
    )
    return parser.parse_args(argv)


def run(args: argparse.Namespace | None = None) -> None:
    args = args or parse_args()

    config = PipelineConfig(
        patient=make_patient(),
        simulation_id=args.simulation_id,
        device_id=DEVICE_ID,
        scenario_name=args.scenario,
        scenario_version="1.0",
        start_time=START_TIME,
        duration=timedelta(minutes=args.duration_minutes),
        step=timedelta(seconds=args.step_seconds),
        seed=args.seed,
        device=(
            None
            if args.no_device
            else default_bedside_monitor_config()
        ),
    )

    print("== Milestone 8: unified pipeline with device layer ==")
    print(f"  scenario:   {config.scenario_name}")
    print(f"  duration:   {config.duration}")
    print(f"  step:       {config.step}")
    print(f"  seed:       {config.seed}")
    print(f"  device:     "
          f"{'disabled' if config.device is None else 'bedside monitor'}")
    print()

    result = run_pipeline(config=config)

    print(f"  1. simulation:     {len(result.events)} events")
    print(f"  2. kafka produce:  {result.produced} messages")
    print(f"  3. lakehouse:      {result.lakehouse_inserted} rows → "
          f"{config.lake_catalog}.lakehouse.vitals")
    print(f"  4. fhir (HAPI):    {result.fhir_transactions} entries "
          f"(status {result.fhir_status})")

    if result.fhir_issues:
        issues = [issue for issue in result.fhir_issues if "information/" not in issue]
        for issue in issues:
            print(f"     issue: {issue}")

    if result.clinical_ground_truth:
        print()
        print("  clinical ground truth:")
        for event in result.clinical_ground_truth:
            print(
                f"    {event.event_time.isoformat()} "
                f"{event.event_type.value} {event.condition_name} "
                f"[{event.condition_phase.value}] severity={event.severity}"
            )

    print()
    print(f"MILESTONE 8 PIPELINE OK ({config.scenario_name})")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)