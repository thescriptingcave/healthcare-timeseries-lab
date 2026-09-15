"""Kafka vitals streaming with Avro + Schema Registry (Milestone 4)."""

from __future__ import annotations

from healthcare_timeseries_lab.streaming.consumer import (
    consume_vitals,
    event_time_to_trino_timestamp,
)
from healthcare_timeseries_lab.streaming.producer import produce_vitals
from healthcare_timeseries_lab.streaming.schema import (
    SCHEMA_REGISTRY_URL_DEFAULT,
    TOPIC_DEFAULT,
    VITALS_AVRO_SCHEMA,
    register_vitals_schema,
)

__all__ = [
    "SCHEMA_REGISTRY_URL_DEFAULT",
    "TOPIC_DEFAULT",
    "VITALS_AVRO_SCHEMA",
    "consume_vitals",
    "event_time_to_trino_timestamp",
    "produce_vitals",
    "register_vitals_schema",
]
