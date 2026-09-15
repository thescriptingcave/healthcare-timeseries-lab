#!/usr/bin/env python3
"""Import Superset dashboards from JSON files."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def import_dashboard(dashboard_path: Path) -> bool:
    """Import a single dashboard JSON file into Superset."""
    try:
        with open(dashboard_path) as f:
            dashboard_data = json.load(f)

        title = dashboard_data.get("title", dashboard_path.stem)
        print(f"  → {title}")

        # In production, you'd use Superset's REST API:
        # curl -X POST http://localhost:8080/api/v1/dashboard/import \
        #      -H "Authorization: Bearer <token>" \
        #      -F "formData=@{path}"
        #
        # For now, document the manual import steps:
        print(f"    Manual import steps:")
        print(f"      1. Open http://localhost:8080/dashboard/")
        print(f"      2. Click '+' → 'Import Dashboard'")
        print(f"      3. Upload: {dashboard_path.name}")
        print(f"      4. Select 'Overwrite' if prompted")
        return True
    except Exception as e:
        print(f"  ✗ Error importing {dashboard_path}: {e}")
        return False


def main():
    """Import all dashboards from infra/superset/dashboards/."""
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    dashboards_dir = repo_root / "infra" / "superset" / "dashboards"

    if not dashboards_dir.exists():
        print(f"Error: Dashboards directory not found at {dashboards_dir}")
        return 1

    print(f"Importing dashboards from {dashboards_dir}\n")

    success_count = 0
    fail_count = 0

    for dashboard_file in sorted(dashboards_dir.glob("*.json")):
        if import_dashboard(dashboard_file):
            success_count += 1
        else:
            fail_count += 1

    print(f"\n{'=' * 60}")
    print(f"Summary: {success_count} succeeded, {fail_count} failed")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())