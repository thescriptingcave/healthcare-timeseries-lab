"""FHIR vital-signs panel mapping + HAPI FHIR client (Milestone 2)."""

from __future__ import annotations

from healthcare_timeseries_lab.fhir.client import HapiFhirClient
from healthcare_timeseries_lab.fhir.models import (
    LOINC_SYSTEM,
    UCUM_SYSTEM,
    VITALS_PANEL_DISPLAY,
    VITALS_PANEL_LOINC,
    build_encounter,
    build_observation,
    build_patient,
)

__all__ = [
    "LOINC_SYSTEM",
    "UCUM_SYSTEM",
    "VITALS_PANEL_DISPLAY",
    "VITALS_PANEL_LOINC",
    "HapiFhirClient",
    "build_encounter",
    "build_observation",
    "build_patient",
]
