"""Kafka consumer: read Avro-encoded vitals messages from a topic (M4)."""

from __future__ import annotations

import io
from typing import Any

import fastavro
from confluent_kafka import Consumer

from healthcare_timeseries_lab.streaming.schema import (
    TOPIC_DEFAULT,
    VITALS_AVRO_SCHEMA,
)


def decode_vitals(value: bytes) -> dict[str, Any]:
    """Decode a Schema-Registry-wrapped Avro value into a plain dict.

    Expects the Confluent wire format: magic byte ``0x00`` + 4-byte schema
    ID + binary Avro payload (schema-less encode).
    """
    if not value or value[0] != 0x00:
        raise ValueError("not a Schema Registry Avro message")
    payload = value[5:]
    return fastavro.schemaless_reader(io.BytesIO(payload), VITALS_AVRO_SCHEMA)


def _format_event_time(iso_string: str) -> str:
    """Render an ISO-8601 timestamp as a Trino TIMESTAMP literal.

    The trailing UTC offset is preserved so the literal is interpreted
    unambiguously regardless of the Trino session time zone.
    """
    parsed = iso_string.replace("T", " ")
    if parsed.endswith("Z"):
        parsed = parsed[:-1] + "+00:00"
    if parsed.endswith("+00:00"):
        return parsed
    return parsed + "+00:00"


def event_time_to_trino_timestamp(value: dict[str, Any]) -> str:
    """Convert a decoded vitals record's ``event_time`` to Trino SQL literal."""
    return _format_event_time(value["event_time"])


def consume_vitals(
    *,
    bootstrap_servers: str = "localhost:9092",
    topic: str = TOPIC_DEFAULT,
    max_messages: int = 100,
    timeout_seconds: float = 30.0,
    group_id: str = "htl-vitals-reader",
) -> list[dict[str, Any]]:
    """Consume up to ``max_messages`` Avro vitals messages and decode them."""
    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([topic])

    messages: list[dict[str, Any]] = []
    try:
        while len(messages) < max_messages:
            msg = consumer.poll(timeout_seconds)
            if msg is None:
                break
            if msg.error():
                continue
            messages.append(decode_vitals(msg.value()))
    finally:
        consumer.close()

    return messages


__all__ = [
    "TOPIC_DEFAULT",
    "consume_vitals",
    "decode_vitals",
    "event_time_to_trino_timestamp",
]