"""Unit tests for the lakehouse DDL, row parser, and analytics queries (Milestone 3).

These tests exercise pure logic — no live Trino/Postgres required.
"""

from healthcare_timeseries_lab.lakehouse import (
    _VITAL_MAP,
    ANALYTICS_AGG_QUERY,
    JDBC_CATALOG_NAMESPACE_PROPERTIES_DDL,
    JDBC_CATALOG_V0_DDL,
    JDBC_CATALOG_V1_ALTER,
    LAKEHOUSE_DDL_STATEMENTS,
    READ_BACK_QUERY,
    VITALS_TABLE_DDL,
    get_jdbc_catalog_cleanup,
    get_jdbc_catalog_seed_statements,
    parse_observation_row,
)
from healthcare_timeseries_lab.lakehouse.writer import (
    build_vitals_insert_sql,
    insert_vitals,
)

# ---------------------------------------------------------------------------
# JdbcCatalog USchema (extracted from Iceberg 1.11.0 JdbcUtil.class)
# ---------------------------------------------------------------------------


def test_v0_create_tables_ddl_contains_required_columns() -> None:
    for col in (
        "catalog_name VARCHAR(255) NOT NULL",
        "table_namespace VARCHAR(255) NOT NULL",
        "table_name VARCHAR(255) NOT NULL",
        "metadata_location VARCHAR(1000)",
        "previous_metadata_location VARCHAR(1000)",
        "PRIMARY KEY (catalog_name, table_namespace, table_name)",
    ):
        assert col in JDBC_CATALOG_V0_DDL, f"missing {col!r}"


def test_v0_ddl_starts_with_create_table_iceberg_tables() -> None:
    assert JDBC_CATALOG_V0_DDL.startswith("CREATE TABLE iceberg_tables(")


def test_v1_alter_adds_iceberg_type_column() -> None:
    assert JDBC_CATALOG_V1_ALTER == "ALTER TABLE iceberg_tables ADD COLUMN iceberg_type VARCHAR(5)"


def test_namespace_properties_ddl_has_expected_pk() -> None:
    assert "PRIMARY KEY (catalog_name, namespace, property_key)" in JDBC_CATALOG_NAMESPACE_PROPERTIES_DDL
    assert "namespace VARCHAR(255) NOT NULL" in JDBC_CATALOG_NAMESPACE_PROPERTIES_DDL
    assert "property_key VARCHAR(255)" in JDBC_CATALOG_NAMESPACE_PROPERTIES_DDL
    assert "property_value VARCHAR(1000)" in JDBC_CATALOG_NAMESPACE_PROPERTIES_DDL


def test_seed_statements_count() -> None:
    stmts = get_jdbc_catalog_seed_statements()
    assert len(stmts) == 3
    assert stmts[0] is JDBC_CATALOG_V0_DDL
    assert stmts[1] is JDBC_CATALOG_V1_ALTER
    assert stmts[2] is JDBC_CATALOG_NAMESPACE_PROPERTIES_DDL


def test_cleanup_only_touches_legacy_lake_schema() -> None:
    cleanup = get_jdbc_catalog_cleanup()
    joined = "\n".join(cleanup)
    assert "lake.iceberg_tables" in joined
    assert "lake.iceberg_columns" in joined
    assert "lake.iceberg_properties" in joined
    assert "DROP SCHEMA IF EXISTS lake" in joined
    # The live catalog metadata in public must never be dropped by provisioning
    for stmt in cleanup:
        assert "public." not in stmt.lower()


# ---------------------------------------------------------------------------
# Lakehouse schema + vitals table DDL
# ---------------------------------------------------------------------------


def test_vitals_table_ddl_has_all_six_vitals_columns() -> None:
    for col in (
        "heart_rate_bpm DOUBLE",
        "spo2_pct DOUBLE",
        "respiration_rate_bpm DOUBLE",
        "temperature_c DOUBLE",
        "systolic_bp_mmhg DOUBLE",
        "diastolic_bp_mmhg DOUBLE",
    ):
        assert col in VITALS_TABLE_DDL, f"missing {col!r}"


def test_vitals_table_ddl_partitions_by_day() -> None:
    assert "partitioning = ARRAY['day(event_time)']" in VITALS_TABLE_DDL


def test_vitals_table_ddl_uses_parquet_format() -> None:
    assert "format = 'PARQUET'" in VITALS_TABLE_DDL


def test_ddl_statements_count() -> None:
    assert len(LAKEHOUSE_DDL_STATEMENTS) == 2


def test_ddl_statements_match_schema_and_table() -> None:
    schema_stmt, table_stmt = LAKEHOUSE_DDL_STATEMENTS
    assert "lake.lakehouse" in schema_stmt
    assert "lake.lakehouse.vitals" in table_stmt


# ---------------------------------------------------------------------------
# FHIR Observation -> vitals row parser
# ---------------------------------------------------------------------------


def _sample_observation() -> dict:
    return {
        "resourceType": "Observation",
        "status": "final",
        "code": {
            "coding": [
                {"system": "http://loinc.org", "code": "85353-1", "display": "Vital signs"}
            ]
        },
        "subject": {"reference": "Patient/11111111-1111-1111-1111-111111111111"},
        "effectiveDateTime": "2026-01-01T00:00:05+00:00",
        "component": [
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4"}]},
                "valueQuantity": {"value": 72.5, "unit": "beats per minute"},
            },
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "2708-6"}]},
                "valueQuantity": {"value": 98.0, "unit": "percent"},
            },
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "9279-1"}]},
                "valueQuantity": {"value": 14.0, "unit": "breaths per minute"},
            },
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "8310-5"}]},
                "valueQuantity": {"value": 36.8, "unit": "celsius"},
            },
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "8480-6"}]},
                "valueQuantity": {"value": 120.0, "unit": "mmHg"},
            },
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "8462-4"}]},
                "valueQuantity": {"value": 76.0, "unit": "mmHg"},
            },
        ],
    }


def test_parse_observation_row_happy_path() -> None:
    row = parse_observation_row(_sample_observation())
    assert row is not None
    assert row["event_time"] == "2026-01-01T00:00:05+00:00"
    assert row["patient_id"] == "11111111-1111-1111-1111-111111111111"
    assert row["heart_rate_bpm"] == 72.5
    assert row["spo2_pct"] == 98.0
    assert row["respiration_rate_bpm"] == 14.0
    assert row["temperature_c"] == 36.8
    assert row["systolic_bp_mmhg"] == 120.0
    assert row["diastolic_bp_mmhg"] == 76.0


def test_parse_observation_row_returns_none_when_no_effective() -> None:
    obs = _sample_observation()
    del obs["effectiveDateTime"]
    assert parse_observation_row(obs) is None


def test_parse_observation_row_handles_missing_components() -> None:
    obs = {
        "subject": {"reference": "Patient/aaaa"},
        "effectiveDateTime": "2026-01-01T00:00:05+00:00",
        "component": [],
    }
    row = parse_observation_row(obs)
    assert row is not None
    assert row["patient_id"] == "aaaa"
    assert "heart_rate_bpm" not in row


def test_parse_observation_row_ignores_unknown_loinc_code() -> None:
    obs = {
        "subject": {"reference": "Patient/x"},
        "effectiveDateTime": "2026-01-01T00:00:05+00:00",
        "component": [
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "99999-0"}]},
                "valueQuantity": {"value": 42.0},
            }
        ],
    }
    row = parse_observation_row(obs)
    assert row is not None
    assert len(row) == 2  # only event_time and patient_id


# ---------------------------------------------------------------------------
# Analytics queries
# ---------------------------------------------------------------------------


def test_analytics_query_references_vitals_table() -> None:
    assert "lake.lakehouse.vitals" in ANALYTICS_AGG_QUERY


def test_analytics_query_groups_by_patient() -> None:
    assert "GROUP BY patient_id" in ANALYTICS_AGG_QUERY


def test_analytics_query_orders_by_patient() -> None:
    assert "ORDER BY patient_id" in ANALYTICS_AGG_QUERY


def test_read_back_query_references_vitals_table() -> None:
    assert "lake.lakehouse.vitals" in READ_BACK_QUERY


def test_vital_map_loinc_codes_match_fhir_models() -> None:
    expected_codes = {"8867-4", "2708-6", "9279-1", "8310-5", "8480-6", "8462-4"}
    assert set(_VITAL_MAP.keys()) == expected_codes


# ---------------------------------------------------------------------------
# Vitals writer (shared INSERT builder, Milestone 7)
# ---------------------------------------------------------------------------


def _sample_vitals_record() -> dict:
    return {
        "event_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "simulation_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "patient_id": "11111111-1111-1111-1111-111111111111",
        "device_id": "22222222-2222-2222-2222-222222222222",
        "event_time": "2026-01-01T00:00:35+00:00",
        "sequence_number": 7,
        "heart_rate_bpm": 72.0,
        "spo2_pct": 98.0,
        "respiration_rate_bpm": 14.0,
        "temperature_c": 36.8,
        "systolic_bp_mmhg": 120.0,
        "diastolic_bp_mmhg": 76.0,
        "device_status": "CONNECTED",
        "quality_code": "GOOD",
    }


def test_build_vitals_insert_sql_targets_lakehouse_table() -> None:
    sql = build_vitals_insert_sql([_sample_vitals_record()])
    assert "INSERT INTO lake.lakehouse.vitals" in sql
    assert "event_time" in sql
    assert "diastolic_bp_mmhg" in sql


def test_build_vitals_insert_sql_renders_trino_literals() -> None:
    sql = build_vitals_insert_sql([_sample_vitals_record()])
    assert "TIMESTAMP '2026-01-01 00:00:35+00:00'" in sql
    assert "'11111111-1111-1111-1111-111111111111'" in sql
    assert "72.0" in sql
    assert "98.0" in sql
    assert "36.8" in sql


def test_build_vitals_insert_sql_handles_multiple_rows() -> None:
    sql = build_vitals_insert_sql(
        [_sample_vitals_record(), _sample_vitals_record()]
    )
    assert sql.count("TIMESTAMP ") == 2
    assert sql.count("+00:00") == 2


def test_insert_vitals_returns_row_count(monkeypatch) -> None:
    captured: dict = {}

    def fake_ddl(statements, catalog=None) -> None:
        captured["sql"] = statements[0]

    monkeypatch.setattr(
        "healthcare_timeseries_lab.lakehouse.writer.run_trino_ddl",
        fake_ddl,
    )

    count = insert_vitals([_sample_vitals_record(), _sample_vitals_record()])
    assert count == 2
    assert "INSERT INTO lake.lakehouse.vitals" in captured["sql"]

    count = insert_vitals([_sample_vitals_record()], catalog="other")
    assert count == 1
    assert "INSERT INTO other.lakehouse.vitals" in captured["sql"]
