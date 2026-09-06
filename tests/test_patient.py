from uuid import UUID

import pytest

from healthcare_timeseries_lab.patients.models import PatientProfile

PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")


def make_patient(**overrides: object) -> PatientProfile:
    values = {
        "patient_id": PATIENT_ID,
        "age": 45,
        "sex": "female",
        "baseline_heart_rate_bpm": 72.0,
        "baseline_spo2_pct": 98.0,
        "baseline_respiration_rate_bpm": 14.0,
        "baseline_temperature_c": 36.8,
        "baseline_systolic_bp_mmhg": 120.0,
        "baseline_diastolic_bp_mmhg": 76.0,
        "variability_factor": 1.0,
    }

    values.update(overrides)

    return PatientProfile(**values)


def test_patient_profile_is_created_with_valid_values() -> None:
    patient = make_patient()

    assert patient.patient_id == PATIENT_ID
    assert patient.age == 45
    assert patient.baseline_heart_rate_bpm == 72.0
    assert patient.baseline_spo2_pct == 98.0


def test_patient_rejects_non_positive_age() -> None:
    with pytest.raises(ValueError, match="age must be greater than zero"):
        make_patient(age=0)


def test_patient_rejects_empty_sex() -> None:
    with pytest.raises(ValueError, match="sex must not be empty"):
        make_patient(sex="   ")


def test_patient_rejects_invalid_spo2() -> None:
    with pytest.raises(ValueError, match="SpO2"):
        make_patient(baseline_spo2_pct=101.0)


def test_patient_rejects_systolic_not_greater_than_diastolic() -> None:
    with pytest.raises(ValueError, match="systolic"):
        make_patient(
            baseline_systolic_bp_mmhg=75.0,
            baseline_diastolic_bp_mmhg=80.0,
        )


def test_patient_rejects_non_positive_variability_factor() -> None:
    with pytest.raises(ValueError, match="variability_factor"):
        make_patient(variability_factor=0.0)