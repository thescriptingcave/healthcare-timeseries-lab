from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID


class SimulationStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class SimulationRun:
    simulation_id: UUID

    scenario_name: str
    scenario_version: str

    seed: int

    start_time: datetime
    end_time: datetime

    step: timedelta

    simulator_version: str

    status: SimulationStatus

    def __post_init__(self) -> None:
        if self.start_time.tzinfo is None:
            raise ValueError("start_time must be timezone-aware")

        if self.end_time.tzinfo is None:
            raise ValueError("end_time must be timezone-aware")

        if self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time")

        if self.step <= timedelta(0):
            raise ValueError("step must be greater than zero")

        if not self.scenario_name.strip():
            raise ValueError("scenario_name must not be empty")

        if not self.scenario_version.strip():
            raise ValueError("scenario_version must not be empty")

        if not self.simulator_version.strip():
            raise ValueError("simulator_version must not be empty")

    @property
    def duration(self) -> timedelta:
        return self.end_time - self.start_time