import pytest

from healthcare_timeseries_lab.scenarios.models import (
    ActiveCondition,
    ConditionPhase,
    PhysiologicalEffect,
)


def test_condition_can_be_created() -> None:
    condition = ActiveCondition(
        name="hypoxemia",
        phase=ConditionPhase.PROGRESSION,
        severity=0.5,
        effect=PhysiologicalEffect(
            heart_rate_delta_bpm=5.0,
            spo2_delta_pct=-4.0,
            respiration_rate_delta_bpm=2.0,
        ),
    )

    assert condition.name == "hypoxemia"
    assert condition.phase == ConditionPhase.PROGRESSION
    assert condition.severity == 0.5
    assert condition.effect.spo2_delta_pct == -4.0


def test_condition_rejects_invalid_severity() -> None:
    with pytest.raises(ValueError, match="severity"):
        ActiveCondition(
            name="hypoxemia",
            phase=ConditionPhase.PROGRESSION,
            severity=1.5,
            effect=PhysiologicalEffect(),
        )


def test_condition_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="condition name"):
        ActiveCondition(
            name="",
            phase=ConditionPhase.BASELINE,
            severity=0.0,
            effect=PhysiologicalEffect(),
        )


def test_effect_defaults_to_no_change() -> None:
    effect = PhysiologicalEffect()

    assert effect.heart_rate_delta_bpm == 0.0
    assert effect.spo2_delta_pct == 0.0
    assert effect.respiration_rate_delta_bpm == 0.0
    assert effect.temperature_delta_c == 0.0
    assert effect.systolic_bp_delta_mmhg == 0.0
    assert effect.diastolic_bp_delta_mmhg == 0.0