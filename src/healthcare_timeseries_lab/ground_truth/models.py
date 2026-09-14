from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from healthcare_timeseries_lab.scenarios.models import ConditionPhase


class ClinicalTruthEventType(StrEnum):
    CONDITION_STARTED = "CONDITION_STARTED"
    CONDITION_UPDATED = "CONDITION_UPDATED"
    CONDITION_ENDED = "CONDITION_ENDED"
    INTERVENTION_APPLIED = "INTERVENTION_APPLIED"


@dataclass(frozen=True)
class ClinicalGroundTruthEvent:
    event_id: UUID
    simulation_id: UUID
    patient_id: UUID

    event_time: datetime

    event_type: ClinicalTruthEventType

    condition_name: str
    condition_phase: ConditionPhase
    severity: float | None = None

    def __post_init__(self) -> None:
        if self.event_time.tzinfo is None:
            raise ValueError("event_time must be timezone-aware")

        if not self.condition_name.strip():
            raise ValueError("condition_name must not be empty")

        if self.severity is not None and not 0.0 <= self.severity <= 1.0:
            raise ValueError("severity must be between 0.0 and 1.0")