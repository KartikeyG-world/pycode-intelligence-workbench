"""Regression tests for issue #18: internal exception details must not leak
into HTTP error responses.

- POST /api/analyze must return a generic 500 message when the analysis
  service raises, instead of embedding str(e).
- GET /api/health must return a generic database error string instead of
  the raw exception (a SQLAlchemy OperationalError string can embed the
  full DATABASE_URL, including credentials).
- Validation errors (422 / 400) are raised before the try block and must
  keep their full detail.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.routes import analyze as analyze_routes
from app.db.database import get_db
from app.main import app

SECRET = "SECRET_MARKER_DO_NOT_LEAK"


def test_analyze_500_hides_exception_details(client: TestClient, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError(f"boom {SECRET} postgres://user:password@host/db")

    monkeypatch.setattr(analyze_routes.analysis_service, "analyze_code", boom)
    response = client.post("/api/analyze", json={"title": "T", "code": "x = 1\n"})
    assert response.status_code == 500
    assert SECRET not in response.text
    assert "postgres://" not in response.text
    assert response.json()["detail"] == (
        "An unexpected internal error occurred during static analysis."
    )


class FailingSession:
    def execute(self, *args, **kwargs):
        raise Exception(f"connection failed {SECRET} postgres://user:password@host/db")


def test_health_hides_db_error_details(client: TestClient):
    app.dependency_overrides[get_db] = lambda: FailingSession()
    try:
        response = client.get("/api/health")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert SECRET not in response.text
    assert "postgres://" not in response.text
    assert data["database"]["error"] == "Database connection failed"


def test_validation_errors_stay_intact(client: TestClient):
    missing_code = client.post("/api/analyze", json={"title": "T"})
    assert missing_code.status_code == 422
    assert missing_code.json()["detail"]  # FastAPI validation detail preserved

    empty_code = client.post("/api/analyze", json={"title": "T", "code": "   "})
    assert empty_code.status_code == 400
    assert empty_code.json()["detail"] == "Source code cannot be empty."
