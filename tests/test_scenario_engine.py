from datetime import UTC, datetime, timedelta

import pytest

from healthcare_timeseries_lab.scenarios.engine import (
    ConditionDefinition,
    ScenarioEngine,
    ScenarioPhaseDefinition,
)
from healthcare_timeseries_lab.scenarios.models import (
    ConditionPhase,
    PhysiologicalEffect,
)

START_TIME = datetime(
    2026,
    1,
    1,
    0,
    0,
    0,
    tzinfo=UTC,
)


def make_hypoxemia_definition() -> ConditionDefinition:
    return ConditionDefinition(
        name="hypoxemia",
        effect=PhysiologicalEffect(
            heart_rate_delta_bpm=12.0,
            spo2_delta_pct=-10.0,
            respiration_rate_delta_bpm=6.0,
        ),
        phases=(
            ScenarioPhaseDefinition(
                phase=ConditionPhase.ONSET,
                start_offset=timedelta(hours=2),
                end_offset=timedelta(hours=2, minutes=15),
                start_severity=0.0,
                end_severity=0.2,
            ),
            ScenarioPhaseDefinition(
                phase=ConditionPhase.PROGRESSION,
                start_offset=timedelta(hours=2, minutes=15),
                end_offset=timedelta(hours=3),
                start_severity=0.2,
                end_severity=1.0,
            ),
            ScenarioPhaseDefinition(
                phase=ConditionPhase.PLATEAU,
                start_offset=timedelta(hours=3),
                end_offset=timedelta(hours=4),
                start_severity=1.0,
                end_severity=1.0,
            ),
            ScenarioPhaseDefinition(
                phase=ConditionPhase.RECOVERY,
                start_offset=timedelta(hours=4),
                end_offset=timedelta(hours=5),
                start_severity=1.0,
                end_severity=0.0,
            ),
        ),
    )


def make_engine() -> ScenarioEngine:
    return ScenarioEngine(
        simulation_start_time=START_TIME,
        conditions=(make_hypoxemia_definition(),),
    )


def test_no_condition_before_onset() -> None:
    engine = make_engine()

    active = engine.active_conditions(
        START_TIME + timedelta(hours=1),
    )

    assert active == []


def test_condition_activates_during_onset() -> None:
    engine = make_engine()

    active = engine.active_conditions(
        START_TIME + timedelta(hours=2, minutes=5),
    )

    assert len(active) == 1
    assert active[0].name == "hypoxemia"
    assert active[0].phase == ConditionPhase.ONSET


def test_progression_interpolates_severity() -> None:
    engine = make_engine()

    active = engine.active_conditions(
        START_TIME + timedelta(
            hours=2,
            minutes=37,
            seconds=30,
        ),
    )

    assert len(active) == 1

    condition = active[0]

    assert condition.phase == ConditionPhase.PROGRESSION
    assert condition.severity == pytest.approx(0.6)


def test_plateau_holds_constant_severity() -> None:
    engine = make_engine()

    active = engine.active_conditions(
        START_TIME + timedelta(
            hours=3,
            minutes=30,
        ),
    )

    assert active[0].phase == ConditionPhase.PLATEAU
    assert active[0].severity == pytest.approx(1.0)


def test_recovery_reduces_severity() -> None:
    engine = make_engine()

    active = engine.active_conditions(
        START_TIME + timedelta(
            hours=4,
            minutes=30,
        ),
    )

    assert active[0].phase == ConditionPhase.RECOVERY
    assert active[0].severity == pytest.approx(0.5)


def test_condition_is_inactive_after_final_phase() -> None:
    engine = make_engine()

    active = engine.active_conditions(
        START_TIME + timedelta(hours=5),
    )

    assert active == []


def test_overlapping_phases_are_rejected() -> None:
    with pytest.raises(ValueError, match="overlap"):
        ConditionDefinition(
            name="hypoxemia",
            effect=PhysiologicalEffect(),
            phases=(
                ScenarioPhaseDefinition(
                    phase=ConditionPhase.ONSET,
                    start_offset=timedelta(hours=1),
                    end_offset=timedelta(hours=2),
                    start_severity=0.0,
                    end_severity=0.5,
                ),
                ScenarioPhaseDefinition(
                    phase=ConditionPhase.PROGRESSION,
                    start_offset=timedelta(hours=1, minutes=30),
                    end_offset=timedelta(hours=3),
                    start_severity=0.5,
                    end_severity=1.0,
                ),
            ),
        )