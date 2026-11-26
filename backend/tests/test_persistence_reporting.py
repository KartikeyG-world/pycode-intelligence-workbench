import logging
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.models import AnalysisResult, CodeSubmission
from app.schemas.analysis import AnalyzeRequest
from app.services.analysis_service import AnalysisService

SAMPLE_CODE = """def sum_list(items):
    total = 0
    for item in items:
        total += item
    return total
"""


def test_service_persistence_skipped_when_db_is_none():
    service = AnalysisService()
    req = AnalyzeRequest(title="No DB", code=SAMPLE_CODE)

    res = service.analyze_code(req, db=None)

    assert res.success is True
    assert res.time_complexity == "O(n)"
    assert res.submission_id is None
    assert res.persistence_status == "skipped"
    assert res.persistence_warning is None


def test_service_persistence_success(db_session: Session):
    service = AnalysisService()
    req = AnalyzeRequest(title="Saved Snippet", code=SAMPLE_CODE)

    res = service.analyze_code(req, db=db_session)

    assert res.success is True
    assert res.submission_id is not None
    assert res.persistence_status == "saved"
    assert res.persistence_warning is None

    saved_submission = (
        db_session.query(CodeSubmission)
        .filter(CodeSubmission.id == res.submission_id)
        .first()
    )
    assert saved_submission is not None
    assert saved_submission.title == "Saved Snippet"

    saved_result = (
        db_session.query(AnalysisResult)
        .filter(AnalysisResult.submission_id == res.submission_id)
        .first()
    )
    assert saved_result is not None
    assert saved_result.time_complexity == res.time_complexity
    assert saved_result.space_complexity == res.space_complexity
    assert saved_result.confidence == res.confidence


def test_service_flush_failure_rolls_back_and_reports_warning(db_session: Session, caplog):
    service = AnalysisService()
    req = AnalyzeRequest(title="Flush Failure", code=SAMPLE_CODE)

    with (
        patch.object(db_session, "flush", side_effect=SQLAlchemyError("secret_internal_flush_detail")),
        patch.object(db_session, "rollback", wraps=db_session.rollback) as rollback_spy,
        caplog.at_level(logging.ERROR, logger="app.services.analysis_service"),
    ):
        res = service.analyze_code(req, db=db_session)

    assert rollback_spy.called
    assert res.success is True
    assert res.time_complexity == "O(n)"
    assert res.submission_id is None
    assert res.persistence_status == "failed"
    assert res.persistence_warning is not None
    assert "secret_internal_flush_detail" not in res.persistence_warning
    assert "Failed to persist analysis result to database" in caplog.text
    assert "secret_internal_flush_detail" in caplog.text


def test_service_commit_failure_rolls_back_submission(db_session: Session, caplog):
    service = AnalysisService()
    req = AnalyzeRequest(title="Commit Failure", code=SAMPLE_CODE)
    initial_submissions = db_session.query(CodeSubmission).count()
    initial_results = db_session.query(AnalysisResult).count()

    with (
        patch.object(db_session, "commit", side_effect=SQLAlchemyError("secret_internal_commit_detail")),
        patch.object(db_session, "rollback", wraps=db_session.rollback) as rollback_spy,
        caplog.at_level(logging.ERROR, logger="app.services.analysis_service"),
    ):
        res = service.analyze_code(req, db=db_session)

    assert rollback_spy.called
    assert res.success is True
    assert res.submission_id is None
    assert res.persistence_status == "failed"
    assert res.persistence_warning is not None
    assert "secret_internal_commit_detail" not in res.persistence_warning
    assert "Failed to persist analysis result to database" in caplog.text
    assert db_session.query(CodeSubmission).count() == initial_submissions
    assert db_session.query(AnalysisResult).count() == initial_results


def test_api_analyze_reports_persistence_failure_without_creating_history(client: TestClient):
    history_before = client.get("/api/history")
    assert history_before.status_code == 200
    before_ids = {item["submission_id"] for item in history_before.json()}

    with patch.object(Session, "commit", side_effect=SQLAlchemyError("db_commit_boom")):
        response = client.post(
            "/api/analyze",
            json={"title": "API Commit Failure", "code": SAMPLE_CODE},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["time_complexity"] == "O(n)"
    assert data["submission_id"] is None
    assert data["persistence_status"] == "failed"
    assert isinstance(data["persistence_warning"], str) and len(data["persistence_warning"]) > 0
    assert "db_commit_boom" not in data["persistence_warning"]

    history_after = client.get("/api/history")
    assert history_after.status_code == 200
    after_ids = {item["submission_id"] for item in history_after.json()}
    assert after_ids == before_ids


def test_api_analyze_success_persists_and_returns_in_history(client: TestClient):
    response = client.post(
        "/api/analyze",
        json={"title": "API Saved Snippet", "code": SAMPLE_CODE},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["persistence_status"] == "saved"
    assert data["persistence_warning"] is None
    submission_id = data["submission_id"]
    assert isinstance(submission_id, str) and len(submission_id) > 0

    history_response = client.get("/api/history")
    assert history_response.status_code == 200
    history_items = history_response.json()
    matching_items = [item for item in history_items if item["submission_id"] == submission_id]
    assert len(matching_items) == 1
    assert matching_items[0]["title"] == "API Saved Snippet"
    assert matching_items[0]["time_complexity"] == "O(n)"

    detail_response = client.get(f"/api/history/{submission_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["submission_id"] == submission_id
    assert detail["title"] == "API Saved Snippet"
    assert detail["code"] == SAMPLE_CODE
