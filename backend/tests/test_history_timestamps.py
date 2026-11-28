"""Regression tests for issue #17: UTC offsets must survive the
analysis-history round-trip.

SQLite (the default local DATABASE_URL) strips tzinfo on write and
returns naive datetimes on read, so ``created_at`` used to lose its UTC
offset: the API emitted ``2026-11-28T14:30:00`` with no offset and the
frontend parsed it as local time. ``UTCTimestamp`` must keep every
timestamp offset-aware through SQLite, including rows written before
the fix.
"""

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.database import SessionLocal
from app.models.models import AnalysisResult, CodeSubmission


def _make_submission_and_result(created_at=None):
    """Insert one submission + result pair and return their ids."""
    db = SessionLocal()
    try:
        submission = CodeSubmission(title="UTC check", code="x = 1\n")
        db.add(submission)
        db.flush()
        kwargs = dict(
            submission_id=submission.id,
            time_complexity="O(1)",
            space_complexity="O(1)",
            confidence="HIGH",
            complexity_reasoning="Constant time.",
            statistics={},
            structure={},
            graph_data={},
            detected_patterns=[],
            optimization_suggestions=[],
        )
        if created_at is not None:
            kwargs["created_at"] = created_at
        result = AnalysisResult(**kwargs)
        db.add(result)
        db.commit()
        return submission.id, result.id
    finally:
        db.close()


def test_created_at_stays_utc_aware_after_sqlite_round_trip(db_session):
    """An aware created_at survives a SQLite write + read unchanged."""
    instant = datetime(2026, 11, 28, 14, 30, 0, tzinfo=timezone.utc)
    _, result_id = _make_submission_and_result(created_at=instant)

    db_session.expire_all()
    result = db_session.query(AnalysisResult).filter_by(id=result_id).one()

    assert result.created_at.tzinfo is not None
    assert result.created_at.utcoffset().total_seconds() == 0
    assert result.created_at == instant


def test_default_created_at_is_utc_aware(db_session):
    """The get_utc_now default is stored and read back as aware UTC."""
    _, result_id = _make_submission_and_result()

    db_session.expire_all()
    result = db_session.query(AnalysisResult).filter_by(id=result_id).one()

    assert result.created_at.tzinfo is not None
    assert result.created_at.utcoffset().total_seconds() == 0


def test_legacy_naive_row_is_read_as_utc(db_session):
    """A row written before the fix (naive timestamp in SQLite) reads
    back as UTC instead of naive, so old history is not mis-parsed."""
    submission_id, _ = _make_submission_and_result()
    legacy_id = "legacy-naive-row"
    db_session.execute(
        text(
            "INSERT INTO analysis_results (id, submission_id, time_complexity,"
            " space_complexity, confidence, complexity_reasoning, statistics,"
            " structure, graph_data, detected_patterns,"
            " optimization_suggestions, created_at)"
            " VALUES (:id, :sid, 'O(1)', 'O(1)', 'HIGH', 'Legacy.',"
            " '{}', '{}', '{}', '[]', '[]', '2026-11-28 14:30:00.000000')"
        ),
        {"id": legacy_id, "sid": submission_id},
    )
    db_session.commit()

    db_session.expire_all()
    result = db_session.query(AnalysisResult).filter_by(id=legacy_id).one()

    assert result.created_at.tzinfo is not None
    assert result.created_at.utcoffset().total_seconds() == 0
    assert result.created_at == datetime(2026, 11, 28, 14, 30, tzinfo=timezone.utc)


def test_non_utc_aware_datetime_is_normalised_to_utc(db_session):
    """An aware datetime in another zone is stored and read back as UTC
    with the same instant."""
    from datetime import timedelta

    plus_five_thirty = timezone(timedelta(hours=5, minutes=30))
    instant = datetime(2026, 11, 28, 20, 0, 0, tzinfo=plus_five_thirty)
    _, result_id = _make_submission_and_result(created_at=instant)

    db_session.expire_all()
    result = db_session.query(AnalysisResult).filter_by(id=result_id).one()

    assert result.created_at.tzinfo is not None
    assert result.created_at.utcoffset().total_seconds() == 0
    assert result.created_at == instant  # same instant, normalised to UTC


def test_updated_at_stays_utc_aware_on_update(db_session):
    """Project.updated_at (onupdate=get_utc_now) round-trips aware."""
    from app.models.models import Project

    db = SessionLocal()
    try:
        project = Project(name="UTC project")
        db.add(project)
        db.commit()
        project_id = project.id
        project.name = "UTC project (renamed)"
        db.commit()
    finally:
        db.close()

    db_session.expire_all()
    project = db_session.query(Project).filter_by(id=project_id).one()

    assert project.created_at.tzinfo is not None
    assert project.created_at.utcoffset().total_seconds() == 0
    assert project.updated_at.tzinfo is not None
    assert project.updated_at.utcoffset().total_seconds() == 0
    assert project.updated_at >= project.created_at


def test_history_endpoint_returns_offset_aware_created_at(client: TestClient):
    """GET /api/history emits created_at with a UTC offset (Z)."""
    instant = datetime(2026, 11, 28, 14, 30, 0, tzinfo=timezone.utc)
    _make_submission_and_result(created_at=instant)

    response = client.get("/api/history")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1

    raw = items[0]["created_at"]
    assert raw.endswith(("+00:00", "Z")), f"expected a UTC offset, got {raw!r}"
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert parsed == instant


def test_history_detail_endpoint_returns_offset_aware_created_at(client: TestClient):
    """GET /api/history/{id} emits created_at with a UTC offset (Z)."""
    instant = datetime(2026, 11, 28, 9, 15, 0, tzinfo=timezone.utc)
    submission_id, _ = _make_submission_and_result(created_at=instant)

    response = client.get(f"/api/history/{submission_id}")
    assert response.status_code == 200
    raw = response.json()["created_at"]
    assert raw.endswith(("+00:00", "Z")), f"expected a UTC offset, got {raw!r}"
    assert datetime.fromisoformat(raw.replace("Z", "+00:00")) == instant
