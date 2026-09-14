from dataclasses import dataclass
from datetime import datetime, timedelta
from random import Random
from uuid import UUID, uuid5

from healthcare_timeseries_lab.patients.models import PatientProfile
from healthcare_timeseries_lab.physiology.engine import PhysiologyEngine
from healthcare_timeseries_lab.physiology.models import PhysiologicalState
from healthcare_timeseries_lab.runtime.clock import SimulationClock
from healthcare_timeseries_lab.simulation.models import (
    SimulationRun,
    SimulationStatus,
)
from healthcare_timeseries_lab.telemetry.events import VitalsTelemetryEvent

EVENT_NAMESPACE = UUID("00000000-0000-0000-0000-000000000001")

SIMULATOR_VERSION = "0.1.0"


@dataclass(frozen=True)
class BaselineSimulationConfig:
    simulation_id: UUID
    device_id: UUID

    start_time: datetime
    duration: timedelta
    step: timedelta

    seed: int

    scenario_name: str = "baseline"
    scenario_version: str = "1.0"


@dataclass(frozen=True)
class BaselineSimulationResult:
    run: SimulationRun
    events: list[VitalsTelemetryEvent]


def run_baseline_simulation(
    *,
    patient: PatientProfile,
    config: BaselineSimulationConfig,
) -> BaselineSimulationResult:
    if config.duration <= timedelta(0):
        raise ValueError("duration must be greater than zero")

    if config.step <= timedelta(0):
        raise ValueError("step must be greater than zero")

    end_time = config.start_time + config.duration

    simulation_run = SimulationRun(
        simulation_id=config.simulation_id,
        scenario_name=config.scenario_name,
        scenario_version=config.scenario_version,
        seed=config.seed,
        start_time=config.start_time,
        end_time=end_time,
        step=config.step,
        simulator_version=SIMULATOR_VERSION,
        status=SimulationStatus.COMPLETED,
    )

    clock = SimulationClock(
        start_time=config.start_time,
        step=config.step,
    )

    engine = PhysiologyEngine(Random(config.seed))

    state = PhysiologicalState(
        timestamp=clock.now,
        heart_rate_bpm=patient.baseline_heart_rate_bpm,
        spo2_pct=patient.baseline_spo2_pct,
        respiration_rate_bpm=patient.baseline_respiration_rate_bpm,
        temperature_c=patient.baseline_temperature_c,
        systolic_bp_mmhg=patient.baseline_systolic_bp_mmhg,
        diastolic_bp_mmhg=patient.baseline_diastolic_bp_mmhg,
    )

    observation_count = config.duration // config.step

    events: list[VitalsTelemetryEvent] = []

    for sequence_number in range(1, observation_count + 1):
        timestamp = clock.advance()

        state = engine.next_state(
            patient=patient,
            previous_state=state,
            timestamp=timestamp,
        )

        event_id = uuid5(
            EVENT_NAMESPACE,
            f"{config.simulation_id}:{config.device_id}:{sequence_number}",
        )

        event = VitalsTelemetryEvent.from_physiological_state(
            event_id=event_id,
            simulation_id=config.simulation_id,
            patient_id=patient.patient_id,
            device_id=config.device_id,
            sequence_number=sequence_number,
            state=state,
        )

        events.append(event)

    return BaselineSimulationResult(
        run=simulation_run,
        events=events,
    )