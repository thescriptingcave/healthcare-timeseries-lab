"""Import Superset dashboards from JSON files via the REST API.

Reads the custom dashboard files in infra/superset/dashboards/ and creates
the Trino database, virtual datasets, charts, and dashboards using the
Superset REST API. The import is idempotent: existing elements are reused
instead of duplicated.

Usage:
    uv run python scripts/import_superset_dashboards.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import requests

DEFAULT_BASE_URL = "http://localhost:8088"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"
DATABASE_NAME = "trino"
TRINO_URI = "trino://trino@trino:8080/lake"
SCHEMA_TRINO = "lakehouse"

DASHBOARDS_DIR = Path(__file__).resolve().parents[1] / "infra" / "superset" / "dashboards"

TABLE_VIZ = "table"
TIMESERIES_VIZ = "echarts_timeseries_line"


def chart_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def query_slug(label: str) -> str:
    return chart_slug(label)


def dataset_name(dashboard_key: str, query_label: str) -> str:
    return f"{dashboard_key}__{query_slug(query_label)}"


def dashboard_slug(title: str) -> str:
    return chart_slug(title)


def _adhoc_metric(column: str) -> dict[str, Any]:
    """Build an ad-hoc aggregate metric for a numeric result column.

    The lesson queries are already aggregated at the row grain, so the
    dashboard only needs a light aggregate to satisfy Superset's metric
    requirement. Values whose names imply a boundary (``lowest_*``) use
    ``MIN``; counts use ``MAX``; everything else averages.
    """
    lowered = column.lower()
    if "lowest" in lowered or lowered.endswith("_min"):
        aggregate = "MIN"
    elif "count" in lowered or "readings" in lowered or "alert" in lowered:
        aggregate = "MAX"
    else:
        aggregate = "AVG"
    return {
        "expressionType": "SIMPLE",
        "column": {"column_name": column},
        "aggregate": aggregate,
        "label": column,
        "optionName": f"metric_{column}",
    }


class SupersetClient:
    """Thin wrapper around the Superset REST API with CSRF support."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL,
                 username: str = DEFAULT_USERNAME,
                 password: str = DEFAULT_PASSWORD) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.username = username
        self.password = password
        self.token: str | None = None
        self.csrf: str | None = None

    def login(self) -> None:
        resp = self.session.post(
            f"{self.base_url}/api/v1/security/login",
            json={
                "username": self.username,
                "password": self.password,
                "provider": "db",
                "refresh": False,
            },
        )
        resp.raise_for_status()
        self.token = resp.json()["access_token"]
        csrf_resp = self.session.get(
            f"{self.base_url}/api/v1/security/csrf_token/",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        csrf_resp.raise_for_status()
        self.csrf = csrf_resp.json()["result"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-CSRFToken": self.csrf if self.csrf else "",
        }

    def get(self, path: str) -> Any:
        resp = self.session.get(f"{self.base_url}{path}", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        resp = self.session.post(
            f"{self.base_url}{path}", headers=self._headers(), json=payload
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"POST {path} -> {resp.status_code}: {resp.text[:800]}"
            )
        return resp.json()

    def put(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        resp = self.session.put(
            f"{self.base_url}{path}", headers=self._headers(), json=payload or {}
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"PUT {path} -> {resp.status_code}: {resp.text[:800]}"
            )
        return resp.json() if resp.text else {}

    def delete(self, path: str) -> bool:
        resp = self.session.delete(
            f"{self.base_url}{path}", headers=self._headers()
        )
        return resp.status_code < 400


class SupersetImporter:
    """Creates databases, datasets, charts, and dashboards via the REST API."""

    def __init__(self, client: SupersetClient) -> None:
        self.client = client

    def get_database_id(self, name: str) -> int | None:
        data = self.client.get("/api/v1/database/?q=(columns:!(id,database_name))")
        for row in data.get("result", []):
            if row["database_name"] == name:
                return row["id"]
        return None

    def ensure_trino_database(self) -> int:
        existing = self.get_database_id(DATABASE_NAME)
        if existing is not None:
            return existing
        created = self.client.post(
            "/api/v1/database/",
            {
                "database_name": DATABASE_NAME,
                "sqlalchemy_uri": TRINO_URI,
                "expose_in_sqllab": True,
                "allow_run_async": False,
            },
        )
        return created["id"]

    def get_dataset_id(self, table_name: str) -> int | None:
        q = (
            "/api/v1/dataset/?q=(filters:!((col:'table_name',opr:'eq',value:"
            + table_name
            + ")),columns:!(id,table_name))"
        )
        data = self.client.get(q)
        rows = data.get("result", [])
        return rows[0]["id"] if rows else None

    def get_dashboard_id(self, slug: str) -> int | None:
        q = (
            "/api/v1/dashboard/?q=(filters:!((col:'slug',opr:'eq',value:"
            + slug
            + ")),columns:!(id,slug))"
        )
        data = self.client.get(q)
        rows = data.get("result", [])
        return rows[0]["id"] if rows else None

    def ensure_dataset(self, database_id: int, schema: str, sql: str,
                       table_name: str) -> int:
        existing = self.get_dataset_id(table_name)
        if existing is not None:
            return existing
        try:
            created = self.client.post(
                "/api/v1/dataset/",
                {
                    "sql": sql,
                    "database": database_id,
                    "schema": schema,
                    "table_name": table_name,
                    "normalize_columns": False,
                },
            )
            return created["id"]
        except RuntimeError as exc:
            message = str(exc)
            match = re.search(r"uuid ([0-9a-f-]{36})", message)
            if "soft-deleted" not in message or match is None:
                raise
            uuid = match.group(1)
            print(f"  - restoring soft-deleted dataset {table_name} ({uuid})")
            self.client.post(f"/api/v1/dataset/{uuid}/restore", {})
            restored = self.get_dataset_id(table_name)
            if restored is None:
                raise
            self.client.put(f"/api/v1/dataset/{restored}/refresh")
            return restored

    def get_dataset_columns(self, dataset_id: int) -> list[str]:
        data = self.client.get(f"/api/v1/dataset/{dataset_id}")
        dataset = data.get("result", data)
        return [c["column_name"] for c in dataset.get("columns", [])]

    def get_dataset_metrics(self, dataset_id: int) -> set[str]:
        data = self.client.get(f"/api/v1/dataset/{dataset_id}")
        dataset = data.get("result", data)
        return {m["metric_name"] for m in dataset.get("metrics", [])}

    def create_table_chart(self, dataset_id: int, title: str,
                           columns: list[str]) -> int:
        params = {
            "datasource": f"{dataset_id}__table",
            "viz_type": TABLE_VIZ,
            "time_range": "No filter",
            "query_mode": "raw",
            "all_columns": columns,
            "metrics": [],
            "order_by_cols": [],
            "row_limit": 100,
            "page_length": 10,
            "include_search": False,
        }
        created = self.client.post(
            "/api/v1/chart/",
            {
                "datasource_id": dataset_id,
                "datasource_type": "table",
                "slice_name": title,
                "viz_type": TABLE_VIZ,
                "params": json.dumps(params),
            },
        )
        return created["id"]

    def create_timeseries_chart(self, dataset_id: int, title: str,
                                metrics: list[str], time_column: str,
                                series_columns: list[str] | None,
                                columns: list[str],
                                dataset_metrics: set[str]) -> int:
        if time_column not in columns:
            raise RuntimeError(
                f"Timeseries chart '{title}' uses time column '{time_column}' "
                "which was not derived from the query"
            )
        if series_columns:
            valid_series = [c for c in series_columns if c in columns]
            missing = [c for c in series_columns if c not in columns]
            if missing:
                print(
                    f"  ! {title}: dropping series column(s) not returned by "
                    f"the query: {missing}"
                )
            series_columns = valid_series

        built_metrics: list[Any] = []
        for metric in metrics:
            if metric in dataset_metrics:
                built_metrics.append(metric)
            elif metric in columns:
                built_metrics.append(_adhoc_metric(metric))
            else:
                print(
                    f"  ! {title}: dropping metric '{metric}' not returned by "
                    "the query"
                )

        params = {
            "datasource": f"{dataset_id}__table",
            "viz_type": TIMESERIES_VIZ,
            "time_grain_sqla": "PT1S",
            "time_range": "No filter",
            "granularity_sqla": time_column,
            "metrics": built_metrics,
            "groupby": series_columns or [],
            "adhoc_filters": [],
            "line_width": 2,
            "show_legend": bool(series_columns),
            "y_axis_format": "SMART_NUMBER",
            "zoomable": True,
            "row_limit": 10000,
            "x_axis_title": time_column,
            "y_axis_title": "",
            "order_by_cols": [],
        }
        created = self.client.post(
            "/api/v1/chart/",
            {
                "datasource_id": dataset_id,
                "datasource_type": "table",
                "slice_name": title,
                "viz_type": TIMESERIES_VIZ,
                "params": json.dumps(params),
            },
        )
        return created["id"]

    def ensure_dashboard(self, title: str, slug: str,
                         position_json: str) -> int:
        existing = self.get_dashboard_id(slug)
        if existing is not None:
            return existing
        created = self.client.post(
            "/api/v1/dashboard/",
            {
                "dashboard_title": title,
                "slug": slug,
                "published": True,
                "position_json": position_json,
                "json_metadata": json.dumps(
                    {
                        "timed_refresh_immune_slices": [],
                        "expanded_slices": {},
                        "refresh_frequency": 0,
                        "default_filters": "{}",
                        "chart_configuration": {},
                    }
                ),
            },
        )
        return created["id"]

    def associate_charts(self, dashboard_id: int,
                         chart_ids: Iterable[int]) -> None:
        for chart_id in chart_ids:
            self.client.put(
                f"/api/v1/chart/{chart_id}", {"dashboards": [dashboard_id]}
            )


def build_position(title: str,
                   charts: dict[str, tuple[int, int, int, int]]) -> str:
    """Build the Superset dashboard position JSON from a chart id map.

    Each value is ``(x, y, w, h)`` already expressed on Superset's 12-column
    grid. Charts are grouped per grid row and wrapped in ``ROW`` components,
    matching the layout Superset itself generates (a chart placed directly
    under ``GRID`` crashes the dashboard view).
    """
    rows: dict[int, list[tuple[str, tuple[int, int, int, int]]]] = {}
    for chart_id, (x, y, w, h) in charts.items():
        rows.setdefault(y, []).append((chart_id, (x, y, w, h)))

    grid_positions = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID",
                    "children": ["GRID_ID"], "parents": []},
        "GRID_ID": {"type": "GRID", "id": "GRID_ID",
                    "children": [f"ROW-{y}" for y in sorted(rows)],
                    "parents": ["ROOT_ID"]},
        "HEADER_ID": {"type": "HEADER", "id": "HEADER_ID", "children": [],
                      "meta": {"text": title}, "parents": ["ROOT_ID"]},
    }
    for y, items in sorted(rows.items()):
        ordered = sorted(items, key=lambda item: item[1][0])
        grid_positions[f"ROW-{y}"] = {
            "type": "ROW",
            "id": f"ROW-{y}",
            "children": [f"CHART-{chart_id}" for chart_id, _ in ordered],
            "parents": ["ROOT_ID", "GRID_ID"],
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        }
    for chart_id, (x, y, w, h) in charts.items():
        grid_positions[f"CHART-{chart_id}"] = {
            "type": "CHART",
            "id": f"CHART-{chart_id}",
            "children": [],
            "parents": ["ROOT_ID", "GRID_ID", f"ROW-{y}"],
            "meta": {"chartId": chart_id, "width": w, "height": h,
                     "sliceName": ""},
        }
    return json.dumps(grid_positions)


def grid_pos_for(chart: dict[str, Any]) -> tuple[int, int, int, int]:
    """Map a Grafana 24-column ``gridPos`` onto Superset's 12-column grid."""
    pos = chart.get("gridPos", {}) or {}
    x = pos.get("x", 0) // 2
    y = pos.get("y", 0)
    w = max(1, pos.get("w", 12) // 2)
    h = max(1, pos.get("h", 8))
    return x, y, w, h


def import_dashboards(base_url: str, username: str, password: str) -> None:
    files = sorted(DASHBOARDS_DIR.glob("*.json"))
    if not files:
        print(f"No dashboard JSON files found in {DASHBOARDS_DIR}")
        return

    client = SupersetClient(base_url, username, password)
    client.login()
    importer = SupersetImporter(client)

    database_id = importer.ensure_trino_database()
    print(f"[DB] Trino database id={database_id}")

    for path in files:
        dashboard = json.loads(path.read_text())
        title = dashboard["title"]
        slug = dashboard_slug(title)
        schema = dashboard.get("schema", SCHEMA_TRINO)

        existing = importer.get_dashboard_id(slug)
        if existing is not None:
            print(f"[SKIP] {path.name}: dashboard already exists (id={existing})")
            continue

        dataset_ids: dict[str, int] = {}
        for query in dashboard.get("queries", []):
            label = query["label"]
            name = dataset_name(path.stem, label)
            dataset_id = importer.ensure_dataset(
                database_id, schema, query["sql"], name
            )
            dataset_ids[label] = dataset_id
            print(f"[DS] {name} id={dataset_id}")

        chart_ids: dict[str, int] = {}
        layout: dict[str, tuple[int, int, int, int]] = {}
        for chart in dashboard.get("charts", []):
            title2 = chart["title"]
            query = chart["query"]
            dataset_id = dataset_ids[query]
            columns = importer.get_dataset_columns(dataset_id)
            dtype = chart["type"]
            if dtype == "table":
                chart_id = importer.create_table_chart(
                    dataset_id, title2, columns
                )
            elif dtype == "timeseries":
                chart_id = importer.create_timeseries_chart(
                    dataset_id,
                    title2,
                    chart.get("metrics", ["count"]),
                    chart["timeColumns"][0],
                    chart.get("seriesColumns"),
                    columns,
                    importer.get_dataset_metrics(dataset_id),
                )
            else:
                raise RuntimeError(
                    f"Unsupported chart type '{dtype}' in {path.name}"
                )
            chart_ids[title2] = chart_id
            layout[f"chart-{chart['id']}"] = grid_pos_for(chart)
            print(f"[CHART] {title2} id={chart_id} ({dtype})")

        position_charts = {}
        for chart in dashboard.get("charts", []):
            chart_id = chart_ids[chart["title"]]
            position_charts[chart_id] = layout[f"chart-{chart['id']}"]

        position_json = build_position(title, position_charts)
        dashboard_id = importer.ensure_dashboard(title, slug, position_json)
        importer.associate_charts(dashboard_id, chart_ids.values())
        print(f"[DASH] {title} id={dashboard_id}")

    print("\nImport complete. Dashboards available at "
          f"{base_url}/dashboard/list/")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import Superset dashboards from JSON via REST API"
    )
    parser.add_argument("--url", default=DEFAULT_BASE_URL,
                        help="Superset base URL")
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    args = parser.parse_args()

    try:
        import_dashboards(args.url, args.username, args.password)
    except requests.HTTPError as exc:
        print(f"HTTP error: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())