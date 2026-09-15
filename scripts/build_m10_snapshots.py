"""Pre-render the M10 lesson results to parquet snapshots.

Each lesson's canonical result set (the last query in its SQL file) is
executed against the live Trino lakehouse and stored under
``datasets/m10/lessons`` so the tutorial notebooks can be read even when the
compose stack is down.

Run with the stack up::

    uv run python scripts/build_m10_snapshots.py
"""

from __future__ import annotations

from healthcare_timeseries_lab.tutorials import (
    iter_lessons,
    load_lesson_sql,
    run_live,
    snapshot_lesson,
)


def run() -> None:
    print("== Building M10 lesson parquet snapshots ==")
    for lesson in iter_lessons():
        frame = run_live(load_lesson_sql(lesson))
        path = snapshot_lesson(lesson, frame)
        print(f"  {lesson.title}: {len(frame)} rows -> {path}")
    print()
    print("SNAPSHOTS OK")


if __name__ == "__main__":
    run()