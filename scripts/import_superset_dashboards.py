#!/usr/bin/env python3
"""Import Superset dashboards from JSON files.

This script provides instructions for importing dashboards manually via the Superset UI
or command line, as the REST API requires CSRF tokens and proper authentication flow.

For Superset, dashboards are typically imported through the web UI:
  1. Go to http://localhost:8080/dashboard/
  2. Click '+' → 'Import Dashboard'
  3. Upload one of the JSON files from infra/superset/dashboards/

Or use the command line with superset CLI (requires database pre-configuration):

  # First, set up Trino database connection (one-time setup in Superset UI)
  # - Go to Data → Databases → '+' to add new database
  # - Database Name: trino
  # - SQLAlchemy URI: trino://trino:trino@localhost:8080/trino
  # - Click 'Test Connection' to verify
  # - Click 'Save'

  # Then import dashboards:
  cd infra/superset/dashboards
  for f in *.json; do
    echo "Importing $f..."
    superset dashboard import "$f" --overwrite
  done

Note: The database connection must be configured first through Superset UI.
"""

from pathlib import Path


def print_import_instructions():
    """Print instructions for importing dashboards."""
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    dashboards_dir = repo_root / "infra" / "superset" / "dashboards"

    print(__doc__)
    print("\n" + "=" * 60)
    print(f"Available dashboards in {dashboards_dir}:")
    print("=" * 60)

    for dashboard_file in sorted(dashboards_dir.glob("*.json")):
        title = dashboard_file.stem
        print(f"  - {title}.json")

    print("\nTo import:")
    print("  1. Go to http://localhost:8088/dashboard/")
    print("  2. Click '+' → 'Import Dashboard'")
    print("  3. Select a JSON file from the list above")
    print("  4. Choose 'Overwrite' if prompted")
    print("  5. Select the 'trino' database when prompted")


if __name__ == "__main__":
    print_import_instructions()