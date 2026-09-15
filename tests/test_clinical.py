"""Unit tests for the clinical store module (Milestone 5).

These tests exercise pure logic — DDL/seed statement construction and the
cross-catalog query text — with no live MySQL / Trino required.
"""

from __future__ import annotations

from healthcare_timeseries_lab.clinical import (
    CLINICAL_SCHEMA,
    ENCOUNTERS_TABLE,
    PATIENTS_TABLE,
    get_clinical_cleanup,
    get_clinical_create_statements,
    get_clinical_seed_statements,
)
from healthcare_timeseries_lab.clinical.ddl import (
    ENCOUNTERS_DDL,
    ENCOUNTERS_SEED_ROWS,
    PATIENTS_DDL,
    PATIENTS_SEED_ROWS,
)
from healthcare_timeseries_lab.clinical.queries import CLINICAL_SUMMARY_QUERY


def test_patients_ddl_columns() -> None:
    for col in (
        "patient_id VARCHAR(64) NOT NULL",
        "mrn VARCHAR(32) NOT NULL",
        "full_name VARCHAR(128) NOT NULL",
        "age INTEGER",
        "sex VARCHAR(16)",
        "admitted_at TIMESTAMP",
    ):
        assert col in PATIENTS_DDL, f"missing {col!r}"


def test_encounters_ddl_columns() -> None:
    for col in (
        "encounter_id VARCHAR(64) NOT NULL",
        "patient_id VARCHAR(64) NOT NULL",
        "started_at TIMESTAMP",
        "ended_at TIMESTAMP",
        "status VARCHAR(32) NOT NULL",
    ):
        assert col in ENCOUNTERS_DDL, f"missing {col!r}"


def test_create_statements_cover_both_tables() -> None:
    stmts = get_clinical_create_statements()
    assert len(stmts) == 2
    joined = "\n".join(stmts)
    assert f"mysql.{CLINICAL_SCHEMA}.{PATIENTS_TABLE}" in joined
    assert f"mysql.{CLINICAL_SCHEMA}.{ENCOUNTERS_TABLE}" in joined


def test_cleanup_only_touches_clinical_tables() -> None:
    joined = "\n".join(get_clinical_cleanup())
    assert f"mysql.{CLINICAL_SCHEMA}.{PATIENTS_TABLE}" in joined
    assert f"mysql.{CLINICAL_SCHEMA}.{ENCOUNTERS_TABLE}" in joined
    assert "lake." not in joined
    assert "fhir_pg." not in joined


def test_seed_rows_are_deterministic() -> None:
    assert len(PATIENTS_SEED_ROWS) == 2
    assert len(ENCOUNTERS_SEED_ROWS) == 2
    ava = PATIENTS_SEED_ROWS[0]
    assert ava[0] == "11111111-1111-1111-1111-111111111111"
    assert ava[3] == 45 and ava[4] == "female"


def test_seed_statements_quote_string_values() -> None:
    statements = "\n".join(get_clinical_seed_statements())
    assert "'MRN-000001'" in statements
    assert "'TIMESTAMP '" not in statements
    assert "TIMESTAMP '2026-01-01 00:00:00'" in statements
    assert "'COMPLETED'" in statements


def test_summary_query_spans_three_catalogs() -> None:
    q = CLINICAL_SUMMARY_QUERY
    assert "mysql.clinical.patients" in q
    assert "lake.lakehouse.vitals" in q
    assert "fhir_pg.public.hfj_res_ver" in q
    assert "fhir_pg.public.hfj_resource" in q


def test_summary_query_groups_and_orders() -> None:
    q = CLINICAL_SUMMARY_QUERY
    assert "GROUP BY patient_id" in q
    assert "ORDER BY p.patient_id" in q


def test_summary_query_joins_on_patient_id() -> None:
    q = CLINICAL_SUMMARY_QUERY
    assert "e.patient_id = p.patient_id" in q
    assert "v.patient_id = p.patient_id" in q