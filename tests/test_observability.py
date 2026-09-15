"""Unit tests for the M6 observability artifacts.

These tests exercise pure contract checks — Grafana provisioning YAML, the
provisioned dashboard JSON, and the Jupyter notebook source — with no live
Grafana / Trino required.
"""

from __future__ import annotations

import json
from pathlib import Path

import nbformat
import yaml

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = ROOT / "infra" / "grafana" / "dashboards" / "vitals.json"
DATASOURCES_YAML = ROOT / "infra" / "grafana" / "provisioning" / "datasources" / "trino.yaml"
PROVIDERS_YAML = ROOT / "infra" / "grafana" / "provisioning" / "dashboards" / "dashboards.yaml"
NOTEBOOK_PATH = ROOT / "notebooks" / "vitals_analysis.ipynb"


def _dashboard() -> dict:
    return json.loads(DASHBOARD_PATH.read_text())


def test_dashboard_is_valid_json_with_identity() -> None:
    dashboard = _dashboard()
    assert dashboard["uid"] == "lakehouse-vitals"
    assert dashboard["title"] == "Lakehouse Vitals"
    assert dashboard["schemaVersion"] >= 30


def test_dashboard_panels_target_trino_datasource() -> None:
    for panel in _dashboard()["panels"]:
        assert panel["datasource"] == {"type": "trino-datasource", "uid": "trino"}
        for target in panel["targets"]:
            assert target["datasource"] == {"type": "trino-datasource", "uid": "trino"}
            assert target["format"] == 0  # FormatOptions.TimeSeries
            assert "event_time AS time" in target["rawSql"]
            assert " FROM lake.lakehouse.vitals" in target["rawSql"]


def test_dashboard_covers_heart_rate_and_spo2() -> None:
    all_sql = " ".join(t["rawSql"] for p in _dashboard()["panels"] for t in p["targets"])
    assert "heart_rate_bpm" in all_sql
    assert "spo2_pct" in all_sql


def test_datasource_provisioning_points_at_trino() -> None:
    cfg = yaml.safe_load(DATASOURCES_YAML.read_text())
    ds = cfg["datasources"][0]
    assert ds["type"] == "trino-datasource"
    assert ds["uid"] == "trino"
    assert ds["url"] == "http://trino:8080"
    assert ds["isDefault"] is True


def test_dashboard_provider_mounts_dashboard_directory() -> None:
    cfg = yaml.safe_load(PROVIDERS_YAML.read_text())
    assert cfg["providers"][0]["options"]["path"] == "/var/lib/grafana/dashboards"


def test_notebook_is_valid_and_well_shaped() -> None:
    nb = nbformat.read(NOTEBOOK_PATH, as_version=4)
    assert nb.metadata["kernelspec"]["name"] == "python3"
    assert [c.cell_type for c in nb.cells] == ["markdown", "code", "code", "code", "markdown"]


def test_notebook_queries_all_six_channels() -> None:
    code = "\n".join(c.source for c in nbformat.read(NOTEBOOK_PATH, as_version=4).cells if c.cell_type == "code")
    for col in (
        "heart_rate_bpm",
        "temperature_c",
        "spo2_pct",
        "respiration_rate_bpm",
        "systolic_bp_mmhg",
        "diastolic_bp_mmhg",
    ):
        assert col in code
    assert "FROM lake.lakehouse.vitals" in code
    assert 'timezone="UTC"' in code