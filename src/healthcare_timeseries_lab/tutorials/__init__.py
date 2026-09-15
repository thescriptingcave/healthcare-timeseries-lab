"""M10 tutorials: business-question lessons over the live lakehouse.

The tutorials package turns the ``sql/dql`` library (one file per business
question, split into ``beginner`` / ``intermediate`` / ``advanced`` tiers)
into DataFrames for the companion notebooks.

Every lesson can run in one of two ways:

* **live** — executed against the Trino lakehouse (using the repository's
  ``trino`` client) so readers get fresh answers;
* **parquet** — the same canonical result, pre-rendered to a snapshot under
  ``datasets/m10/lessons`` by ``scripts/build_m10_snapshots.py``, used when
  the compose stack is down.

Wherever Trino is reachable the notebooks prefer the live path and silently
fall back to the snapshot if it is not.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from trino import dbapi as trino_dbapi

from healthcare_timeseries_lab.environment import settings

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

TIERS = ("beginner", "intermediate", "advanced")

LESSON_STEMS = (
    "b1_ward_census",
    "b2_hourly_handoff",
    "b3_flag_attention",
    "i1_first_drop",
    "i2_moving_average",
    "i3_worst_ranked",
    "a1_desaturation_episodes",
    "a2_alarm_sessions",
    "a3_observed_vs_truth",
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
SQL_ROOT = _REPO_ROOT / "sql" / "dql"
SNAPSHOT_ROOT = _REPO_ROOT / "datasets" / "m10" / "lessons"

_WARD_NAMES = {
    "55555555-5555-5555-5555-555555555555": "Naomi Brooks",
    "66666666-6666-6666-6666-666666666666": "Cole Freeman",
    "77777777-7777-7777-7777-777777777777": "Ivy Watson",
}


@dataclass(frozen=True)
class Lesson:
    tier: str
    stem: str

    @property
    def title(self) -> str:
        return f"{self.tier}/{self.stem}"

    @property
    def sql_path(self) -> Path:
        return SQL_ROOT / self.tier / f"{self.stem}.sql"

    @property
    def snapshot_path(self) -> Path:
        return SNAPSHOT_ROOT / f"{self.tier}__{self.stem}.parquet"


# ---------------------------------------------------------------------------
# Catalog helpers
# ---------------------------------------------------------------------------


def iter_lessons() -> list[Lesson]:
    lessons: list[Lesson] = []
    for stem in LESSON_STEMS:
        tier = (
            "beginner"
            if stem.startswith("b")
            else "intermediate"
            if stem.startswith("i")
            else "advanced"
        )
        lessons.append(Lesson(tier=tier, stem=stem))
    return lessons


def load_lesson_sql(lesson: Lesson) -> str:
    return lesson.sql_path.read_text(encoding="utf-8")


def lesson_statements(sql: str) -> list[str]:
    """Split a lesson's SQL (comments kept) into executable statements.

    Full-line ``--`` comments are stripped first so comment blocks never
    reach Trino; the fragment markers between queries (``-----`` comment
    lines) disappear with them.
    """
    body = "\n".join(
        line
        for line in sql.splitlines()
        if not line.strip().startswith("--")
    )
    return [
        statement.strip()
        for statement in body.split(";")
        if statement.strip()
    ]


def ward_names() -> dict[str, str]:
    return dict(_WARD_NAMES)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def _trino_connection() -> trino_dbapi.Connection:
    cfg = settings()
    parsed = urlparse(cfg.trino_url)
    return trino_dbapi.connect(
        host=parsed.hostname,
        port=parsed.port,
        user=cfg.trino_user,
        timezone="UTC",
    )


def run_live(sql: str) -> pd.DataFrame:
    """Run SQL against the Trino lakehouse, returning the LAST result set."""
    connection = _trino_connection()
    cursor = connection.cursor()

    frame: pd.DataFrame | None = None
    for statement in lesson_statements(sql):
        cursor.execute(statement)
        if cursor.description is not None:
            columns = [column.name for column in cursor.description]
            frame = pd.DataFrame(cursor.fetchall(), columns=columns)

    cursor.close()
    connection.close()

    if frame is None:
        raise ValueError("statement produced no result set")

    return frame


def run_lesson(
    lesson: Lesson,
    *,
    live: bool = True,
    snapshot: Path | None = None,
) -> pd.DataFrame:
    """Run one lesson, preferring the live stack and falling back to parquet.

    ``snapshot`` overrides where the fallback is read from; by default it is
    the lesson's canonical ``datasets/m10/lessons`` snapshot.
    """
    active_error: BaseException | None = None

    if live:
        try:
            frame = run_live(load_lesson_sql(lesson))
        except Exception as exc:  # noqa: BLE001 - any stack failure means offline
            active_error = exc
        else:
            return frame

    fallback = snapshot if snapshot is not None else lesson.snapshot_path

    if not fallback.is_file():
        raise FileNotFoundError(
            f"no parquet fallback for {lesson.title}: "
            "run 'uv run python scripts/build_m10_snapshots.py' with the "
            "stack up"
        ) from active_error

    return pd.read_parquet(fallback)


def snapshot_lesson(lesson: Lesson, frame: pd.DataFrame) -> Path:
    SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(lesson.snapshot_path, index=False)
    return lesson.snapshot_path


__all__ = [
    "LESSON_STEMS",
    "SNAPSHOT_ROOT",
    "SQL_ROOT",
    "TIERS",
    "Lesson",
    "iter_lessons",
    "lesson_statements",
    "load_lesson_sql",
    "run_lesson",
    "run_live",
    "snapshot_lesson",
    "ward_names",
]