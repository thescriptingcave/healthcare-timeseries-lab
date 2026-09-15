"""Unit tests for the Kafka vitals streaming module (Milestone 4).

These tests exercise pure logic — fastavro encode/decode round-trips and the
Trino timestamp helper — with no live Kafka or Schema Registry required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import fastavro

from healthcare_timeseries_lab.streaming.consumer import (
    decode_vitals,
    event_time_to_trino_timestamp,
)
from healthcare_timeseries_lab.streaming.producer import (
    encode_vitals,
    event_to_record,
)
from healthcare_timeseries_lab.streaming.schema import (
    SCHEMA_REGISTRY_SUBJECT,
    VITALS_AVRO_SCHEMA,
)
from healthcare_timeseries_lab.telemetry.events import VitalsTelemetryEvent


def _sample_event() -> VitalsTelemetryEvent:
    return VitalsTelemetryEvent(
        event_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        simulation_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        patient_id=UUID("11111111-1111-1111-1111-111111111111"),
        device_id=UUID("22222222-2222-2222-2222-222222222222"),
        event_time=datetime(2026, 1, 1, 0, 0, 35, tzinfo=UTC),
        sequence_number=7,
        heart_rate_bpm=72.0,
        spo2_pct=98.0,
        respiration_rate_bpm=14.0,
        temperature_c=36.8,
        systolic_bp_mmhg=120.0,
        diastolic_bp_mmhg=76.0,
    )


def test_avro_schema_is_valid() -> None:
    parsed = fastavro.parse_schema(VITALS_AVRO_SCHEMA)
    assert parsed is not None
    assert parsed["name"] == "healthcare_timeseries_lab.VitalsTelemetryEvent"


def test_avro_schema_has_all_vital_fields() -> None:
    names = {field["name"] for field in VITALS_AVRO_SCHEMA["fields"]}
    for expected in (
        "event_id",
        "simulation_id",
        "patient_id",
        "device_id",
        "event_time",
        "sequence_number",
        "heart_rate_bpm",
        "spo2_pct",
        "respiration_rate_bpm",
        "temperature_c",
        "systolic_bp_mmhg",
        "diastolic_bp_mmhg",
    ):
        assert expected in names, f"missing {expected!r}"


def test_event_to_record_stringifies_ids_and_time() -> None:
    record = event_to_record(_sample_event())
    assert record["patient_id"] == "11111111-1111-1111-1111-111111111111"
    assert record["event_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert record["event_time"] == "2026-01-01T00:00:35+00:00"
    assert record["sequence_number"] == 7
    assert record["heart_rate_bpm"] == 72.0


def test_encode_decode_round_trip_preserves_values() -> None:
    event = _sample_event()
    encoded = encode_vitals(event, schema_id=42)
    decoded = decode_vitals(encoded)

    assert decoded["event_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert decoded["simulation_id"] == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    assert decoded["patient_id"] == "11111111-1111-1111-1111-111111111111"
    assert decoded["device_id"] == "22222222-2222-2222-2222-222222222222"
    assert decoded["event_time"] == "2026-01-01T00:00:35+00:00"
    assert decoded["sequence_number"] == 7
    assert round(decoded["heart_rate_bpm"], 2) == 72.0
    assert round(decoded["spo2_pct"], 2) == 98.0
    assert round(decoded["respiration_rate_bpm"], 2) == 14.0
    assert round(decoded["temperature_c"], 2) == 36.8
    assert round(decoded["systolic_bp_mmhg"], 2) == 120.0
    assert round(decoded["diastolic_bp_mmhg"], 2) == 76.0
    assert decoded["device_status"] == "CONNECTED"
    assert decoded["quality_code"] == "GOOD"


def test_encode_result_starts_with_confluent_magic_bytes() -> None:
    encoded = encode_vitals(_sample_event(), schema_id=42)
    assert encoded[0] == 0x00
    assert int.from_bytes(encoded[1:5], byteorder="big") == 42


def test_decode_rejects_non_confluent_message() -> None:
    try:
        decode_vitals(b"\x01garbage")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for bad magic byte")


def test_event_time_to_trino_timestamp_preserves_utc_offset() -> None:
    record = event_to_record(_sample_event())
    ts = event_time_to_trino_timestamp(record)
    assert ts == "2026-01-01 00:00:35+00:00"


def test_event_time_to_trino_timestamp_handles_z_suffix() -> None:
    record = {
        "event_time": "2026-01-01T00:00:35Z",
    }
    assert event_time_to_trino_timestamp(record) == "2026-01-01 00:00:35+00:00"


def test_schema_registry_subject_is_vitals_value() -> None:
    assert SCHEMA_REGISTRY_SUBJECT == "vitals-value"