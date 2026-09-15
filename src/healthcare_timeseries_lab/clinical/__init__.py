"""Clinical data store on MySQL with cross-catalog analytics (Milestone 5).

The clinical store keeps patient demographics and encounter windows in MySQL,
exposed to Trino via the ``mysql`` catalog. A single analytics query joins
``mysql.clinical`` (demographics), ``lake.lakehouse.vitals`` (telemetry), and
``fhir_pg.public`` (FHIR resources) by the shared synthetic patient UUID.
"""

from __future__ import annotations

from healthcare_timeseries_lab.clinical.ddl import (
    CLINICAL_SCHEMA,
    ENCOUNTERS_TABLE,
    PATIENTS_TABLE,
    get_clinical_cleanup,
    get_clinical_create_statements,
    get_clinical_seed_statements,
)
from healthcare_timeseries_lab.clinical.queries import CLINICAL_SUMMARY_QUERY

__all__ = [
    "CLINICAL_SCHEMA",
    "CLINICAL_SUMMARY_QUERY",
    "ENCOUNTERS_TABLE",
    "PATIENTS_TABLE",
    "get_clinical_cleanup",
    "get_clinical_create_statements",
    "get_clinical_seed_statements",
]