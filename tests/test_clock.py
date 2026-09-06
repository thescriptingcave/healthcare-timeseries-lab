from datetime import UTC, datetime, timedelta

import pytest

from healthcare_timeseries_lab.runtime.clock import SimulationClock


def test_clock_starts_at_configured_time() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)

    clock = SimulationClock(
        start_time=start,
        step=timedelta(seconds=5),
    )

    assert clock.now == start


def test_clock_advances_by_configured_step() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)

    clock = SimulationClock(
        start_time=start,
        step=timedelta(seconds=5),
    )

    clock.advance()

    assert clock.now == start + timedelta(seconds=5)


def test_clock_can_advance_multiple_times() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)

    clock = SimulationClock(
        start_time=start,
        step=timedelta(seconds=5),
    )

    clock.advance()
    clock.advance()
    clock.advance()

    assert clock.now == start + timedelta(seconds=15)


def test_clock_rejects_naive_datetime() -> None:
    start = datetime(2026, 1, 1)  # noqa: DTZ001

    with pytest.raises(ValueError, match="timezone-aware"):
        SimulationClock(
            start_time=start,
            step=timedelta(seconds=5),
        )


def test_clock_rejects_zero_step() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)

    with pytest.raises(ValueError, match="greater than zero"):
        SimulationClock(
            start_time=start,
            step=timedelta(0),
        )