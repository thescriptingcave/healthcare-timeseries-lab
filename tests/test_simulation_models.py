from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from healthcare_timeseries_lab.simulation.models import (
    SimulationRun,
    SimulationStatus,
)

SIMULATION_ID = UUID("22222222-2222-2222-2222-222222222222")


def make_run(**overrides: object) -> SimulationRun:
    values = {
        "simulation_id": SIMULATION_ID,
        "scenario_name": "baseline",
        "scenario_version": "1.0",
        "seed": 42,
        "start_time": datetime(2026, 1, 1, tzinfo=UTC),
        "end_time": datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
        "step": timedelta(seconds=5),
        "simulator_version": "0.1.0",
        "status": SimulationStatus.COMPLETED,
    }

    values.update(overrides)

    return SimulationRun(**values)


def test_simulation_run_is_created() -> None:
    run = make_run()

    assert run.simulation_id == SIMULATION_ID
    assert run.status == SimulationStatus.COMPLETED
    assert run.duration == timedelta(hours=1)


def test_simulation_run_rejects_naive_start_time() -> None:
    with pytest.raises(ValueError, match="start_time"):
        make_run(
            start_time=datetime(2026, 1, 1),  # noqa: DTZ001
        )


def test_simulation_run_rejects_invalid_time_range() -> None:
    with pytest.raises(ValueError, match="end_time"):
        make_run(
            end_time=datetime(2025, 12, 31, tzinfo=UTC),
        )


def test_simulation_run_rejects_invalid_step() -> None:
    with pytest.raises(ValueError, match="step"):
        make_run(step=timedelta(0))


def test_simulation_run_rejects_empty_scenario_name() -> None:
    with pytest.raises(ValueError, match="scenario_name"):
        make_run(scenario_name="   ")