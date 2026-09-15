"""Clinical schema DDL + seed data for the MySQL store (Milestone 5).

The tables are created through Trino's ``mysql`` connector, which surfaces
MySQL databases as schemas. Trino's connector grammar does not support
inline ``PRIMARY KEY`` constraints or the MySQL ``DATETIME`` type, so tables
use ``TIMESTAMP`` columns and plain ``NOT NULL`` column constraints. Primary
keys can be applied directly in MySQL later if needed.
"""

from __future__ import annotations

CLINICAL_CATALOG = "mysql"
CLINICAL_SCHEMA = "clinical"
PATIENTS_TABLE = "patients"
ENCOUNTERS_TABLE = "encounters"

PATIENTS_DDL = (
    f"CREATE TABLE IF NOT EXISTS {CLINICAL_CATALOG}.{CLINICAL_SCHEMA}.{PATIENTS_TABLE} ("
    "patient_id VARCHAR(64) NOT NULL,"
    "mrn VARCHAR(32) NOT NULL,"
    "full_name VARCHAR(128) NOT NULL,"
    "age INTEGER,"
    "sex VARCHAR(16),"
    "admitted_at TIMESTAMP"
    ")"
)

ENCOUNTERS_DDL = (
    f"CREATE TABLE IF NOT EXISTS {CLINICAL_CATALOG}.{CLINICAL_SCHEMA}.{ENCOUNTERS_TABLE} ("
    "encounter_id VARCHAR(64) NOT NULL,"
    "patient_id VARCHAR(64) NOT NULL,"
    "started_at TIMESTAMP,"
    "ended_at TIMESTAMP,"
    "status VARCHAR(32) NOT NULL"
    ")"
)


def _quote(value) -> str:
    return f"'{value}'"


# (patient_id, mrn, full_name, age, sex, admitted_at)
PATIENTS_SEED_ROWS: list[tuple] = [
    (
        "11111111-1111-1111-1111-111111111111",
        "MRN-000001",
        "Ava Chen",
        45,
        "female",
        "2026-01-01 00:00:00",
    ),
    (
        "44444444-4444-4444-4444-444444444444",
        "MRN-000002",
        "Marcus Lee",
        61,
        "male",
        "2026-01-01 00:30:00",
    ),
]

# (encounter_id, patient_id, started_at, ended_at, status)
ENCOUNTERS_SEED_ROWS: list[tuple] = [
    (
        "enc-2026-01-01-090000",
        "11111111-1111-1111-1111-111111111111",
        "2026-01-01 00:00:00",
        "2026-01-01 00:01:00",
        "COMPLETED",
    ),
    (
        "enc-2026-01-01-110000",
        "44444444-4444-4444-4444-444444444444",
        "2026-01-01 00:30:00",
        "2026-01-01 01:30:00",
        "COMPLETED",
    ),
]


def _literal(value) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    return _quote(value)


def _timestamps(value) -> str:
    return f"TIMESTAMP {_quote(value)}"


def _patients_insert() -> str:
    columns = "patient_id, mrn, full_name, age, sex, admitted_at"
    values: list[str] = []
    for row in PATIENTS_SEED_ROWS:
        patient_id, mrn, full_name, age, sex, admitted_at = row
        values.append(
            f"({_quote(patient_id)}, {_quote(mrn)}, {_quote(full_name)}, "
            f"{_literal(age)}, {_quote(sex)}, {_timestamps(admitted_at)})"
        )
    return (
        f"INSERT INTO {CLINICAL_CATALOG}.{CLINICAL_SCHEMA}.{PATIENTS_TABLE}"
        f" ({columns}) VALUES {', '.join(values)}"
    )


def _encounters_insert() -> str:
    columns = "encounter_id, patient_id, started_at, ended_at, status"
    values: list[str] = []
    for row in ENCOUNTERS_SEED_ROWS:
        encounter_id, patient_id, started_at, ended_at, status = row
        values.append(
            f"({_quote(encounter_id)}, {_quote(patient_id)}, "
            f"{_timestamps(started_at)}, {_timestamps(ended_at)}, {_quote(status)})"
        )
    return (
        f"INSERT INTO {CLINICAL_CATALOG}.{CLINICAL_SCHEMA}.{ENCOUNTERS_TABLE}"
        f" ({columns}) VALUES {', '.join(values)}"
    )


def get_clinical_cleanup() -> list[str]:
    """Drop the clinical tables (idempotent provisioning start)."""
    return [
        f"DROP TABLE IF EXISTS {CLINICAL_CATALOG}.{CLINICAL_SCHEMA}.{ENCOUNTERS_TABLE}",
        f"DROP TABLE IF EXISTS {CLINICAL_CATALOG}.{CLINICAL_SCHEMA}.{PATIENTS_TABLE}",
    ]


def get_clinical_create_statements() -> list[str]:
    """Create the patients and encounters tables."""
    return [PATIENTS_DDL, ENCOUNTERS_DDL]


def get_clinical_seed_statements() -> list[str]:
    """Insert the deterministic clinical seed rows."""
    return [_patients_insert(), _encounters_insert()]


__all__ = [
    "CLINICAL_CATALOG",
    "CLINICAL_SCHEMA",
    "ENCOUNTERS_DDL",
    "ENCOUNTERS_SEED_ROWS",
    "ENCOUNTERS_TABLE",
    "PATIENTS_DDL",
    "PATIENTS_SEED_ROWS",
    "PATIENTS_TABLE",
    "get_clinical_cleanup",
    "get_clinical_create_statements",
    "get_clinical_seed_statements",
]