"""Unified simulation-to-pipeline orchestration (Milestone 7).

Takes a scenario (``baseline`` or a clinical condition) and streams the
simulation trace end-to-end:

    simulate -> Kafka (Avro) -> Iceberg lakehouse -> HAPI FHIR

The stage functions are injectable so the orchestrator can be tested with
fakes (the repo convention keeps unit tests free of live infrastructure).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from healthcare_timeseries_lab.device.models import DeviceSimulationConfig
from healthcare_timeseries_lab.fhir.bundle import push_vitals_bundle
from healthcare_timeseries_lab.ground_truth.models import ClinicalGroundTruthEvent
from healthcare_timeseries_lab.lakehouse.writer import insert_vitals
from healthcare_timeseries_lab.patients.models import PatientProfile
from healthcare_timeseries_lab.physiology.models import PhysiologicalState
from healthcare_timeseries_lab.scenarios.engine import ConditionDefinition
from healthcare_timeseries_lab.scenarios.library import progressive_hypoxemia
from healthcare_timeseries_lab.simulation.models import SimulationRun
from healthcare_timeseries_lab.simulation.runner import (
    BaselineSimulationConfig,
    run_baseline_simulation,
)
from healthcare_timeseries_lab.simulation.scenario_runner import (
    ScenarioSimulationConfig,
    run_scenario_simulation,
)
from healthcare_timeseries_lab.streaming import (
    TOPIC_DEFAULT,
    consume_vitals,
    produce_vitals,
)
from healthcare_timeseries_lab.telemetry.events import VitalsTelemetryEvent

SCENARIO_BASELINE = "baseline"

SCENARIOS: dict[str, Callable[[], tuple[ConditionDefinition, ...]]] = {
    SCENARIO_BASELINE: lambda: (),
    "progressive_hypoxemia": progressive_hypoxemia,
}


@dataclass(frozen=True)
class PipelineConfig:
    patient: PatientProfile

    simulation_id: UUID
    device_id: UUID

    scenario_name: str
    scenario_version: str

    start_time: datetime
    duration: timedelta
    step: timedelta

    seed: int

    topic: str = TOPIC_DEFAULT
    encounter_id: str | None = None
    lake_catalog: str = "lake"
    device: DeviceSimulationConfig | None = None


@dataclass(frozen=True)
class PipelineResult:
    run: SimulationRun
    events: list[VitalsTelemetryEvent]
    states: list[PhysiologicalState]
    clinical_ground_truth: list[ClinicalGroundTruthEvent]

    produced: int
    consumed: int
    lakehouse_inserted: int

    fhir_status: str
    fhir_issues: list[str]
    fhir_transactions: int


def select_newest(
    records: list[dict],
    *,
    patient_id: UUID,
    simulation_id: UUID,
    count: int,
) -> list[dict]:
    """Return the newest ``count`` records for a simulation.

    Consumers read the whole topic from ``earliest`` without committing, so a
    topic may contain stale messages from earlier runs of the same simulation.
    Filtering by patient + simulation id and keeping the tail isolates the
    current run.
    """
    matched = [
        record
        for record in records
        if record.get("patient_id") == str(patient_id)
        and record.get("simulation_id") == str(simulation_id)
    ]
    return matched[-count:]


def run_pipeline(
    *,
    config: PipelineConfig,
    produce: Callable[[list[VitalsTelemetryEvent]], int] | None = None,
    consume: Callable[[int], list[dict]] | None = None,
    insert: Callable[[list[dict]], int] | None = None,
    push_fhir: Callable[[list[VitalsTelemetryEvent]], tuple[str, list[str], int]]
    | None = None,
) -> PipelineResult:
    """Simulate ``config.scenario_name`` and stream it through the pipeline."""
    if config.scenario_name == SCENARIO_BASELINE:
        result = run_baseline_simulation(
            patient=config.patient,
            config=BaselineSimulationConfig(
                simulation_id=config.simulation_id,
                device_id=config.device_id,
                start_time=config.start_time,
                duration=config.duration,
                step=config.step,
                seed=config.seed,
                scenario_name=config.scenario_name,
                scenario_version=config.scenario_version,
            ),
            device=config.device,
        )
        events = result.events
        ground_truth: list[ClinicalGroundTruthEvent] = []
    else:
        condition_factory = SCENARIOS.get(config.scenario_name)
        if condition_factory is None:
            raise ValueError(
                f"unknown scenario: {config.scenario_name!r} "
                f"(expected one of {sorted(SCENARIOS)})"
            )
        result = run_scenario_simulation(
            patient=config.patient,
            config=ScenarioSimulationConfig(
                simulation_id=config.simulation_id,
                device_id=config.device_id,
                scenario_name=config.scenario_name,
                scenario_version=config.scenario_version,
                start_time=config.start_time,
                duration=config.duration,
                step=config.step,
                seed=config.seed,
            ),
            conditions=condition_factory(),
            device=config.device,
        )
        events = result.events
        ground_truth = result.clinical_ground_truth

    producer = produce or (lambda evts: produce_vitals(evts, topic=config.topic))
    produced = producer(events)

    consumer = consume or (
        lambda max_messages: consume_vitals(
            topic=config.topic,
            max_messages=max_messages,
        )
    )

    # The consumer reads the whole topic from ``earliest`` without committing,
    # so it must walk past any older backlog before our newest messages appear.
    # The backlog can be much larger than today's run (e.g. a long demo from a
    # previous day), so retry with a growing read window until the current run
    # is fully covered.
    expected = len(events)
    window = max(expected * 4 + 1000, 500)
    records: list[dict] = []

    for _ in range(12):
        candidates = select_newest(
            consumer(max_messages=window),
            patient_id=config.patient.patient_id,
            simulation_id=config.simulation_id,
            count=expected,
        )
        records = candidates
        if len(records) >= expected:
            break
        window *= 2

    if records == [] and expected > 0:
        raise ValueError(
            "pipeline could not find the simulated events on the topic; "
            "check that Kafka is healthy and the consumer can reach the tail"
        )

    if not records:
        raise ValueError("nothing to insert")

    row_inserter = insert or insert_vitals
    inserted = row_inserter(records)

    expect = (inserted == len(events) == len(records))
    if not expect:
        raise ValueError(
            "pipeline mismatch at the lakehouse sink: "
            f"simulated={len(events)} consumed={len(records)} inserted={inserted}"
        )

    fhir_pusher = push_fhir or (
        lambda evts: push_vitals_bundle(
            evts,
            patient=config.patient,
            encounter_id=config.encounter_id
            or f"enc-{config.simulation_id}",
        )
    )
    fhir_status, fhir_issues, fhir_total = fhir_pusher(events)

    return PipelineResult(
        run=result.run,
        events=events,
        states=result.states,
        clinical_ground_truth=ground_truth,
        produced=produced,
        consumed=len(records),
        lakehouse_inserted=inserted,
        fhir_status=fhir_status,
        fhir_issues=fhir_issues,
        fhir_transactions=fhir_total,
    )


__all__ = [
    "SCENARIOS",
    "SCENARIO_BASELINE",
    "PipelineConfig",
    "PipelineResult",
    "run_pipeline",
    "select_newest",
]