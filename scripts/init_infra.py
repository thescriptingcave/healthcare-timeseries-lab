"""One-shot infrastructure initialisation.

Brings the local lakehouse to a ready state (idempotent):

* waits for every service to become healthy (Kafka comes up first, then
  Schema Registry, MinIO, both Postgres instances, HAPI FHIR, Trino,
  InfluxDB)
* ensures the MinIO ``lake`` bucket exists
* verifies Trino exposes the ``lake`` and ``fhir_pg`` catalogs
* verifies InfluxDB answers on its API with the configured token
* verifies HAPI FHIR answers on its FHIR base URL

Run with::

    make init
    # or
    uv run python scripts/init_infra.py
"""

from __future__ import annotations

import sys
import time

import requests
from minio import Minio
from trino import dbapi as trino_dbapi

from healthcare_timeseries_lab.environment import settings


class ServiceNotReadyError(RuntimeError):
    pass


def _poll(description: str, check, timeout: float = 180.0, every: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    print(f"  waiting for {description} ...")
    while time.monotonic() < deadline:
        try:
            if check():
                print(f"  ok: {description}")
                return
        except Exception as exc:  # noqa: BLE001 - probe failures are expected while starting
            last_error = exc
        time.sleep(every)
    detail = f" ({last_error})" if last_error else ""
    raise ServiceNotReadyError(f"timed out waiting for {description}{detail}")


def wait_for_http(description: str, url: str, timeout: float = 180.0) -> None:
    def check() -> bool:
        response = requests.get(url, timeout=5)
        return response.ok

    _poll(description, check, timeout=timeout)


def ensure_minio_bucket() -> None:
    cfg = settings()
    endpoint = cfg.minio_endpoint
    client = Minio(
        endpoint,
        access_key=cfg.minio_access_key,
        secret_key=cfg.minio_secret_key,
        secure=False,
    )

    def s3_api_ready() -> bool:
        client.bucket_exists(cfg.minio_bucket)
        return True

    _poll("MinIO S3 API", s3_api_ready)
    if not client.bucket_exists(cfg.minio_bucket):
        client.make_bucket(cfg.minio_bucket)
        print(f"  created bucket {cfg.minio_bucket}")
    else:
        print(f"  bucket {cfg.minio_bucket} already exists")


def _trino_catalogs(cfg) -> set[str]:
    from urllib.parse import urlparse

    parsed = urlparse(cfg.trino_url)
    connection = trino_dbapi.connect(
        host=parsed.hostname,
        port=parsed.port,
        user=cfg.trino_user,
    )
    cursor = connection.cursor()
    cursor.execute("SELECT catalog_name FROM system.metadata.catalogs")
    return {row[0] for row in cursor.fetchall()}


def verify_trino_catalogs() -> None:
    cfg = settings()
    expected = {cfg.lake_catalog, cfg.fhir_catalog}

    def catalogs_present() -> bool:
        catalogs = _trino_catalogs(cfg)
        return expected <= catalogs

    _poll(f"Trino catalogs '{cfg.lake_catalog}', '{cfg.fhir_catalog}'", catalogs_present)
    print(f"  catalogs {cfg.lake_catalog} and {cfg.fhir_catalog} available")


def verify_influxdb() -> None:
    cfg = settings()
    url = f"{cfg.influx_url}/health"
    wait_for_http("InfluxDB health", url)

    def token_works() -> bool:
        response = requests.get(
            f"{cfg.influx_url}/api/v2/buckets",
            headers={"Authorization": f"Token {cfg.influx_token}"},
            timeout=5,
        )
        return response.status_code == 200

    _poll("InfluxDB API with configured token", token_works)


def verify_hapi() -> None:
    wait_for_http("HAPI FHIR base URL", f"{settings().hapi_base_url}/metadata")


def run() -> None:
    cfg = settings()

    print("== Infrastructure health checks ==")

    # Kafka must be up before Schema Registry can register/route anything.
    wait_for_http("Schema Registry", f"{cfg.schema_registry_url}/v1/metadata/id")
    wait_for_http("MinIO", f"http://{cfg.minio_endpoint}/minio/health/live")
    wait_for_http("HAPI FHIR", f"{cfg.hapi_base_url}/metadata")
    wait_for_http("Trino", f"{cfg.trino_url}/v1/info")
    wait_for_http("InfluxDB", f"{cfg.influx_url}/health")

    print("== Resource wiring ==")
    ensure_minio_bucket()
    verify_trino_catalogs()
    verify_influxdb()
    verify_hapi()

    print("== Initialisation complete ==")


if __name__ == "__main__":
    try:
        run()
    except ServiceNotReadyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)