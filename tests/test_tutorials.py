"""Tests for the M10 tutorials helper (pure logic only, no infra)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from healthcare_timeseries_lab.tutorials import (
    LESSON_STEMS,
    TIERS,
    Lesson,
    iter_lessons,
    lesson_statements,
    run_lesson,
    snapshot_lesson,
)


def test_tiers_and_lesson_registry() -> None:
    assert TIERS == ("beginner", "intermediate", "advanced")
    lessons = iter_lessons()
    assert len(lessons) == 9
    assert [lesson.stem for lesson in lessons] == list(LESSON_STEMS)


def test_every_lesson_has_a_sql_file() -> None:
    for lesson in iter_lessons():
        assert lesson.sql_path.is_file(), lesson.title
        text = lesson.sql_path.read_text(encoding="utf-8")
        assert "SELECT" in text


def test_lesson_statements_strips_comment_blocks() -> None:
    sql = (
        "-- header comment\n"
        "-- more comment\n"
        "SELECT 1 AS one;\n"
        "-----\n"
        "-- second query\n"
        "WITH x AS (SELECT 2 AS two)\n"
        "SELECT two FROM x\n"
    )
    statements = lesson_statements(sql)
    assert statements == ["SELECT 1 AS one", "WITH x AS (SELECT 2 AS two)\nSELECT two FROM x"]


def test_lesson_statements_ignores_blank_blocks() -> None:
    assert lesson_statements("SELECT 1 AS one;;;") == ["SELECT 1 AS one"]


def test_run_lesson_falls_back_to_snapshot(tmp_path: Path) -> None:
    lesson = Lesson(tier="beginner", stem="b1_ward_census")
    frame = pd.DataFrame({"full_name": ["Naomi Brooks"], "mrn": ["MRN-000101"]})
    snapshot = tmp_path / "snap.parquet"
    frame.to_parquet(snapshot, index=False)

    result = run_lesson(lesson, live=False, snapshot=snapshot)
    assert result["mrn"].iloc[0] == "MRN-000101"


def test_run_lesson_raises_without_any_source(tmp_path: Path) -> None:
    lesson = Lesson(tier="beginner", stem="b1_ward_census")
    missing = tmp_path / "missing.parquet"
    try:
        run_lesson(lesson, live=False, snapshot=missing)
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")


def test_snapshot_lesson_writes_parquet(tmp_path: Path, monkeypatch) -> None:
    lesson = Lesson(tier="intermediate", stem="i1_first_drop")
    monkeypatch.setattr(
        "healthcare_timeseries_lab.tutorials.SNAPSHOT_ROOT",
        tmp_path / "lessons",
    )
    frame = pd.DataFrame({"event_time": ["2026-01-01"], "spo2": [88.0]})
    path = snapshot_lesson(lesson, frame)
    assert path.is_file()
    assert path.name == "intermediate__i1_first_drop.parquet"