"""Avro schema for vitals telemetry events + Schema Registry helpers (Milestone 4).

The Avro contract mirrors ``VitalsTelemetryEvent`` from the telemetry module.
Datetime is serialised as a UTC ISO-8601 string (Avro has no native datetime
type); UUIDs are serialised as canonical string forms.
"""

from __future__ import annotations

import json
from typing import Any

import requests

VITALS_AVRO_SCHEMA: dict[str, Any] = {
    "type": "record",
    "name": "VitalsTelemetryEvent",
    "namespace": "healthcare_timeseries_lab",
    "doc": "One simulated vital-signs observation.",
    "fields": [
        {"name": "event_id", "type": "string"},
        {"name": "simulation_id", "type": "string"},
        {"name": "patient_id", "type": "string"},
        {"name": "device_id", "type": "string"},
        {"name": "event_time", "type": "string"},
        {"name": "sequence_number", "type": "int"},
        {"name": "heart_rate_bpm", "type": "double"},
        {"name": "spo2_pct", "type": "double"},
        {"name": "respiration_rate_bpm", "type": "double"},
        {"name": "temperature_c", "type": "double"},
        {"name": "systolic_bp_mmhg", "type": "double"},
        {"name": "diastolic_bp_mmhg", "type": "double"},
        {"name": "device_status", "type": "string", "default": "CONNECTED"},
        {"name": "quality_code", "type": "string", "default": "GOOD"},
    ],
}

TOPIC_DEFAULT = "vitals"
SCHEMA_REGISTRY_URL_DEFAULT = "http://localhost:8081"
SCHEMA_REGISTRY_GROUP = "healthcare_timeseries_lab"
SCHEMA_REGISTRY_SUBJECT = "vitals-value"


def register_vitals_schema(schema_registry_url: str | None = None) -> int:
    """Register the vitals Avro schema; returns the Schema Registry ID.

    Idempotent: POSTing an identical schema returns the existing ID.
    """
    base = (schema_registry_url or SCHEMA_REGISTRY_URL_DEFAULT).rstrip("/")
    subject = SCHEMA_REGISTRY_SUBJECT

    response = requests.post(
        f"{base}/subjects/{subject}/versions",
        json={"schemaType": "AVRO", "schema": json.dumps(VITALS_AVRO_SCHEMA)},
        headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
        timeout=15,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Schema Registry registration failed: "
            f"{response.status_code} {response.text}"
        )
    return int(response.json()["id"])


__all__ = [
    "SCHEMA_REGISTRY_GROUP",
    "SCHEMA_REGISTRY_SUBJECT",
    "SCHEMA_REGISTRY_URL_DEFAULT",
    "TOPIC_DEFAULT",
    "VITALS_AVRO_SCHEMA",
    "register_vitals_schema",
]