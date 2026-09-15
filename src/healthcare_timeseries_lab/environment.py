"""Runtime settings for the streaming lakehouse services.

Values are read from environment variables (see `.env.example`). A local
`.env` file is loaded automatically when present so scripts run identically
from a shell.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv is a runtime dependency
    load_dotenv = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_env() -> None:
    if load_dotenv is not None:
        load_dotenv(PROJECT_ROOT / ".env", override=False)


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    kafka_bootstrap_servers: str
    schema_registry_url: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    influx_url: str
    influx_token: str
    influx_org: str
    influx_bucket: str
    hapi_base_url: str
    trino_url: str
    trino_user: str
    lake_catalog: str = "lake"
    fhir_catalog: str = "fhir_pg"

    @classmethod
    def from_env(cls) -> Settings:
        _load_env()
        return cls(
            kafka_bootstrap_servers=_env("HTL_KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            schema_registry_url=_env("HTL_SCHEMA_REGISTRY_URL", "http://localhost:8081"),
            minio_endpoint=_env("HTL_MINIO_ENDPOINT", "localhost:9000"),
            minio_access_key=_env("HTL_MINIO_ACCESS_KEY", "minioadmin"),
            minio_secret_key=_env("HTL_MINIO_SECRET_KEY", "minioadmin"),
            minio_bucket=_env("HTL_MINIO_BUCKET", "lake"),
            influx_url=_env("HTL_INFLUX_URL", "http://localhost:8086"),
            influx_token=_env(
                "HTL_INFLUX_TOKEN", "htl_telemetry_admin_token_0011223344556677"
            ),
            influx_org=_env("HTL_INFLUX_ORG", "healthcare"),
            influx_bucket=_env("HTL_INFLUX_BUCKET", "telemetry"),
            hapi_base_url=_env("HTL_HAPI_BASE_URL", "http://localhost:8080/fhir"),
            trino_url=_env("HTL_TRINO_URL", "http://localhost:8082"),
            trino_user=_env("HTL_TRINO_USER", "trino"),
        )


@lru_cache(maxsize=1)
def settings() -> Settings:
    """Cached settings accessor."""
    return Settings.from_env()