"""Patch sqlalchemy-trino for SQLAlchemy 2.x compatibility.

Superset 5.x ships SQLAlchemy 2.x, but the available ``sqlalchemy-trino``
wheel (0.4.0 — 0.5.0 on the index is an empty wheel) still calls
SQLAlchemy 1.4-only APIs. Without these patches, Trino is usable through
SQL Lab but virtual-dataset column derivation crashes, so REST-created
datasets end up with zero columns and charts cannot reference them.

Patches applied:
  1. ``do_execute`` reads ``context.should_autocommit`` (removed in
     SQLAlchemy 2.0) -> fall back to ``False`` via ``getattr``.
  2. ``get_isolation_level`` indexes a list with ``dbapi_conn.isolation_level``,
     which is an ``IsolationLevel`` enum -> use its integer ``.value``.

Run as root during the image build; it is idempotent.
"""

from __future__ import annotations

import sys
from pathlib import Path

DIALECT = Path(
    "/usr/local/lib/python3.11/site-packages/sqlalchemy_trino/dialect.py"
)

PATCHES = [
    (
        "        if context and context.should_autocommit:",
        '        if context and getattr(context, "should_autocommit", False):',
    ),
    (
        "        return level_names[dbapi_conn.isolation_level]",
        "        level = dbapi_conn.isolation_level\n"
        + '        return level_names[level.value if hasattr(level, "value") else level]',
    ),
]


def main() -> int:
    if not DIALECT.exists():
        print(f"Patch target not found: {DIALECT}", file=sys.stderr)
        return 1

    source = DIALECT.read_text()
    for old, new in PATCHES:
        if new in source:
            print(f"Already patched: {old.strip()[:48]}...")
            continue
        if old not in source:
            print(f"Pattern not found: {old.strip()!r}", file=sys.stderr)
            return 1
        source = source.replace(old, new)
        print(f"Patched: {old.strip()[:48]}...")

    DIALECT.write_text(source)
    print("sqlalchemy-trino patched for SQLAlchemy 2.x")
    return 0


if __name__ == "__main__":
    sys.exit(main())