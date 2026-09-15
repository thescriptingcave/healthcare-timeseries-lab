"""Kafka producer: encode vitals events as Avro and publish to a topic (M4)."""

from __future__ import annotations

import io
from collections.abc import Iterable

import fastavro
from confluent_kafka import Producer

from healthcare_timeseries_lab.streaming.schema import (
    TOPIC_DEFAULT,
    VITALS_AVRO_SCHEMA,
    register_vitals_schema,
)
from healthcare_timeseries_lab.telemetry.events import VitalsTelemetryEvent


def encode_vitals(event: VitalsTelemetryEvent, *, schema_id: int) -> bytes:
    """Encode one event as Schema-Registry-wrapped Avro (magic byte + ID)."""
    record = event_to_record(event)
    buffer = io.BytesIO()
    fastavro.schemaless_writer(buffer, VITALS_AVRO_SCHEMA, record)
    payload = buffer.getvalue()
    schema_id_bytes = schema_id.to_bytes(4, byteorder="big")
    return b"\x00" + schema_id_bytes + payload


def event_to_record(event: VitalsTelemetryEvent) -> dict:
    """Convert a ``VitalsTelemetryEvent`` into a plain Avro-writable dict."""
    return {
        "event_id": str(event.event_id),
        "simulation_id": str(event.simulation_id),
        "patient_id": str(event.patient_id),
        "device_id": str(event.device_id),
        "event_time": event.event_time.isoformat(),
        "sequence_number": event.sequence_number,
        "heart_rate_bpm": float(event.heart_rate_bpm),
        "spo2_pct": float(event.spo2_pct),
        "respiration_rate_bpm": float(event.respiration_rate_bpm),
        "temperature_c": float(event.temperature_c),
        "systolic_bp_mmhg": float(event.systolic_bp_mmhg),
        "diastolic_bp_mmhg": float(event.diastolic_bp_mmhg),
        "device_status": event.device_status,
        "quality_code": event.quality_code,
    }


def produce_vitals(
    events: Iterable[VitalsTelemetryEvent],
    *,
    bootstrap_servers: str = "localhost:9092",
    schema_registry_url: str = "http://localhost:8081",
    topic: str = TOPIC_DEFAULT,
) -> int:
    """Publish each event to ``topic`` (blocking wait). Returns message count."""
    schema_id = register_vitals_schema(schema_registry_url)
    producer = Producer({"bootstrap.servers": bootstrap_servers})

    sent = 0
    for event in events:
        value = encode_vitals(event, schema_id=schema_id)
        key = str(event.patient_id)
        producer.produce(topic, key=key, value=value)
        sent += 1
    producer.flush(timeout=45)

    return sent


__all__ = ["TOPIC_DEFAULT", "encode_vitals", "event_to_record", "produce_vitals"]