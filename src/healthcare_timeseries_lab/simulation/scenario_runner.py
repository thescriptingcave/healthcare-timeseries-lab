from dataclasses import dataclass
from datetime import datetime, timedelta
from random import Random
from uuid import UUID, uuid5

from healthcare_timeseries_lab.device.models import DeviceSimulationConfig
from healthcare_timeseries_lab.device.simulator import DeviceSimulator
from healthcare_timeseries_lab.ground_truth.models import (
    ClinicalGroundTruthEvent,
    ClinicalTruthEventType,
)
from healthcare_timeseries_lab.patients.models import PatientProfile
from healthcare_timeseries_lab.physiology.engine import PhysiologyEngine
from healthcare_timeseries_lab.physiology.models import PhysiologicalState
from healthcare_timeseries_lab.runtime.clock import SimulationClock
from healthcare_timeseries_lab.scenarios.engine import (
    ConditionDefinition,
    ScenarioEngine,
)
from healthcare_timeseries_lab.scenarios.models import (
    ActiveCondition,
    ConditionPhase,
)
from healthcare_timeseries_lab.simulation.models import (
    SimulationRun,
    SimulationStatus,
)
from healthcare_timeseries_lab.telemetry.events import VitalsTelemetryEvent

EVENT_NAMESPACE = UUID("00000000-0000-0000-0000-000000000001")
TRUTH_NAMESPACE = UUID("00000000-0000-0000-0000-000000000002")

SIMULATOR_VERSION = "0.1.0"


@dataclass(frozen=True)
class ScenarioSimulationConfig:
    simulation_id: UUID
    device_id: UUID

    scenario_name: str
    scenario_version: str

    start_time: datetime
    duration: timedelta
    step: timedelta

    seed: int


@dataclass(frozen=True)
class ScenarioSimulationResult:
    run: SimulationRun
    events: list[VitalsTelemetryEvent]
    states: list[PhysiologicalState]
    clinical_ground_truth: list[ClinicalGroundTruthEvent]


def run_scenario_simulation(
    *,
    patient: PatientProfile,
    config: ScenarioSimulationConfig,
    conditions: tuple[ConditionDefinition, ...],
    device: DeviceSimulationConfig | None = None,
) -> ScenarioSimulationResult:
    if config.duration <= timedelta(0):
        raise ValueError("duration must be greater than zero")

    if config.step <= timedelta(0):
        raise ValueError("step must be greater than zero")

    simulation_end_time = config.start_time + config.duration

    run = SimulationRun(
        simulation_id=config.simulation_id,
        scenario_name=config.scenario_name,
        scenario_version=config.scenario_version,
        seed=config.seed,
        start_time=config.start_time,
        end_time=simulation_end_time,
        step=config.step,
        simulator_version=SIMULATOR_VERSION,
        status=SimulationStatus.COMPLETED,
    )

    clock = SimulationClock(
        start_time=config.start_time,
        step=config.step,
    )

    scenario_engine = ScenarioEngine(
        simulation_start_time=config.start_time,
        conditions=conditions,
    )

    physiology_engine = PhysiologyEngine(Random(config.seed))

    simulator = (
        DeviceSimulator(config=device)
        if device is not None
        else None
    )

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
    states: list[PhysiologicalState] = []
    ground_truth: list[ClinicalGroundTruthEvent] = []

    previous_condition_state: dict[
        str,
        tuple[ConditionPhase, float],
    ] = {}

    for sequence_number in range(1, observation_count + 1):
        timestamp = clock.advance()

        active_conditions = scenario_engine.active_conditions(timestamp)

        ground_truth.extend(
            _create_ground_truth_events(
                simulation_id=config.simulation_id,
                patient_id=patient.patient_id,
                timestamp=timestamp,
                active_conditions=active_conditions,
                previous_condition_state=previous_condition_state,
            )
        )

        state = physiology_engine.next_state(
            patient=patient,
            previous_state=state,
            timestamp=timestamp,
            active_conditions=active_conditions,
        )

        states.append(state)

        event_id = uuid5(
            EVENT_NAMESPACE,
            f"{config.simulation_id}:{config.device_id}:{sequence_number}",
        )

        if simulator is not None:
            event = simulator.observe(
                state=state,
                simulation_id=config.simulation_id,
                patient_id=patient.patient_id,
                device_id=config.device_id,
                sequence_number=sequence_number,
                event_id=event_id,
            )
            if event is None:
                continue
        else:
            event = VitalsTelemetryEvent.from_physiological_state(
                event_id=event_id,
                simulation_id=config.simulation_id,
                patient_id=patient.patient_id,
                device_id=config.device_id,
                sequence_number=sequence_number,
                state=state,
            )

        events.append(event)

    ground_truth.extend(
        _create_final_condition_end_events(
            simulation_id=config.simulation_id,
            patient_id=patient.patient_id,
            timestamp=simulation_end_time,
            previous_condition_state=previous_condition_state,
        )
    )

    return ScenarioSimulationResult(
        run=run,
        events=events,
        states=states,
        clinical_ground_truth=ground_truth,
    )


def _create_ground_truth_events(
    *,
    simulation_id: UUID,
    patient_id: UUID,
    timestamp: datetime,
    active_conditions: list[ActiveCondition],
    previous_condition_state: dict[
        str,
        tuple[ConditionPhase, float],
    ],
) -> list[ClinicalGroundTruthEvent]:
    events: list[ClinicalGroundTruthEvent] = []

    current_names = {
        condition.name
        for condition in active_conditions
    }

    for condition in active_conditions:
        previous = previous_condition_state.get(condition.name)

        if previous is None:
            event_type = ClinicalTruthEventType.CONDITION_STARTED

        elif previous[0] != condition.phase:
            event_type = ClinicalTruthEventType.CONDITION_UPDATED

        else:
            previous_condition_state[condition.name] = (
                condition.phase,
                condition.severity,
            )
            continue

        event_id = uuid5(
            TRUTH_NAMESPACE,
            (
                f"{simulation_id}:"
                f"{patient_id}:"
                f"{condition.name}:"
                f"{timestamp.isoformat()}:"
                f"{event_type.value}"
            ),
        )

        events.append(
            ClinicalGroundTruthEvent(
                event_id=event_id,
                simulation_id=simulation_id,
                patient_id=patient_id,
                event_time=timestamp,
                event_type=event_type,
                condition_name=condition.name,
                condition_phase=condition.phase,
                severity=condition.severity,
            )
        )

        previous_condition_state[condition.name] = (
            condition.phase,
            condition.severity,
        )

    ended_conditions = (
        set(previous_condition_state)
        - current_names
    )

    for condition_name in ended_conditions:
        event_id = uuid5(
            TRUTH_NAMESPACE,
            (
                f"{simulation_id}:"
                f"{patient_id}:"
                f"{condition_name}:"
                f"{timestamp.isoformat()}:"
                f"{ClinicalTruthEventType.CONDITION_ENDED.value}"
            ),
        )

        events.append(
            ClinicalGroundTruthEvent(
                event_id=event_id,
                simulation_id=simulation_id,
                patient_id=patient_id,
                event_time=timestamp,
                event_type=ClinicalTruthEventType.CONDITION_ENDED,
                condition_name=condition_name,
                condition_phase=ConditionPhase.RESOLVED,
                severity=0.0,
            )
        )

        del previous_condition_state[condition_name]

    return events


def _create_final_condition_end_events(
    *,
    simulation_id: UUID,
    patient_id: UUID,
    timestamp: datetime,
    previous_condition_state: dict[
        str,
        tuple[ConditionPhase, float],
    ],
) -> list[ClinicalGroundTruthEvent]:
    events: list[ClinicalGroundTruthEvent] = []

    for condition_name in list(previous_condition_state):
        event_id = uuid5(
            TRUTH_NAMESPACE,
            (
                f"{simulation_id}:"
                f"{patient_id}:"
                f"{condition_name}:"
                f"{timestamp.isoformat()}:"
                f"{ClinicalTruthEventType.CONDITION_ENDED.value}"
            ),
        )

        events.append(
            ClinicalGroundTruthEvent(
                event_id=event_id,
                simulation_id=simulation_id,
                patient_id=patient_id,
                event_time=timestamp,
                event_type=ClinicalTruthEventType.CONDITION_ENDED,
                condition_name=condition_name,
                condition_phase=ConditionPhase.RESOLVED,
                severity=0.0,
            )
        )

        del previous_condition_state[condition_name]

    return events
