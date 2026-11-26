# Analysis History API
This document describes the analysis-history API and database persistence behavior in the backend implementation inspected for this contribution.

## 1. Overview

The history API exposes three endpoints: GET /api/history, GET /api/history/{submission_id}, and DELETE /api/history/{submission_id}.

History records are created by the analysis service when database persistence succeeds. A successful analysis response does not necessarily mean that a history record was saved.

## 2. History List

### Endpoint

GET /api/history

Returns recent persisted analysis records.

### Query parameters

| Parameter | Type | Default | Description |
|---|---|---:|---|
| limit | Integer | 20 | Maximum number of records requested by the current query |

The current route does not define explicit minimum or maximum validation constraints for limit. Validation and bounded history limits are tracked in issue #15.


### Query behavior

The route:

1. Queries AnalysisResult records.
2. Joins each result to its associated CodeSubmission.
3. Orders results by AnalysisResult.created_at in descending order.
4. Applies the requested limit.
5. Constructs a HistoryItemResponse for each result.

Because the list query uses an inner join to CodeSubmission, returned records normally have a matching submission. The code_snippet contains the first 120 characters of the associated submission's code, followed by ... when the source is longer. The response-building code also defines fallback values (Untitled and an empty snippet) if the submission relationship is unavailable, although an orphaned result would ordinarily be excluded by the inner join.

### Response

A successful request returns a JSON array of HistoryItemResponse objects.

Example structure (illustrative values):

```json
[
  {
    "id": "analysis-result-uuid",
    "submission_id": "submission-uuid",
    "title": "Sorting example",
    "code_snippet": "def sort_items(items): return sorted(items)",
    "time_complexity": "O(n log n)",
    "space_complexity": "O(n)",
    "confidence": "high",
    "created_at": "2026-11-25T12:30:00"
  }
]

```



## 3. History Detail

### Endpoint

GET /api/history/{submission_id}

Returns the stored analysis result associated with the supplied submission ID.

### Not found behavior

If no matching analysis result exists, the endpoint returns HTTP 404 with the detail message Analysis result not found.

### Response fields

The response uses HistoryDetailResponse and includes:

- id and submission_id
- title and original code
- time_complexity and space_complexity
- confidence and complexity_reasoning
- statistics and structure
- graph_data
- detected_patterns and optimization_suggestions
- created_at

The title falls back to Untitled and the code falls back to an empty string when the associated submission is unavailable.


## 4. Delete History Entry

### Endpoint

DELETE /api/history/{submission_id}

Deletes the CodeSubmission associated with the supplied submission ID.

### Behavior

- If the submission exists, it is deleted and the database transaction is committed.
- The SQLAlchemy relationship uses cascade all, delete-orphan for associated analysis results.
- The AnalysisResult foreign key also declares ON DELETE CASCADE.
- A successful deletion returns HTTP 204 No Content.
- If the submission does not exist, the endpoint returns HTTP 404 with the detail message Submission not found.

### Important distinction

The delete endpoint looks up a CodeSubmission, not an AnalysisResult ID. Supply the submission_id returned by the analysis or history API.


## 5. Response Schemas

The response models are defined in backend/app/schemas/project.py.

### HistoryItemResponse

| Field | Type | Description |
|---|---|---|
| id | string | Analysis result ID |
| submission_id | string | Associated submission ID |
| title | string | Submission title |
| code_snippet | string | Short preview of submitted code |
| time_complexity | string | Reported time complexity |
| space_complexity | string | Reported space complexity |
| confidence | string | Analysis confidence value |
| created_at | datetime | Analysis result creation timestamp |

### HistoryDetailResponse

The detail response includes all the following fields:

| Field | Type |
|---|---|
| id | string |
| submission_id | string |
| title | string |
| code | string |
| time_complexity | string |
| space_complexity | string |
| confidence | string |
| complexity_reasoning | string |
| statistics | object |
| structure | object |
| graph_data | object |
| detected_patterns | array of strings |
| optimization_suggestions | array of strings |
| created_at | datetime |

Both response models use Pydantic from-attributes serialization.


## 6. Persistence Lifecycle

The persistence workflow is implemented in backend/app/services/analysis_service.py.

When a database session is supplied to the analysis service and analysis succeeds, the service:

1. Creates a CodeSubmission record.
2. Adds the submission to the database session.
3. Flushes the session to obtain the submission ID.
4. Creates an AnalysisResult containing the analysis output.
5. Adds the analysis result to the session.
6. Commits the transaction.
7. Sets `submission_id` on the analysis response, sets `persistence_status` to `"saved"`, and keeps `persistence_warning` as `null` after the commit succeeds.

Syntax errors return an unsuccessful analysis response (`success: false`) and do not enter this persistence workflow (`persistence_status` remains `null`).

If the analysis service is called without a database session (`db=None`), it returns the analysis response with `persistence_status` set to `"skipped"` and `persistence_warning` as `null` without saving a history record.

## 7. Persistence Status Contract and Failure Behavior

`AnalyzeResponse` (defined in `backend/app/schemas/analysis.py`) exposes two optional fields to communicate whether an analysis result was persisted to history:

| Field | Type | Description |
|---|---|---|
| `persistence_status` | `"saved" \| "failed" \| "skipped" \| null` | Outcome of persisting the analysis to history (`null` when analysis did not enter persistence, such as syntax errors). |
| `persistence_warning` | `string \| null` | Safe, user-facing warning message when `persistence_status` is `"failed"`; `null` otherwise. |

### Status values

- `"saved"`: Both `CodeSubmission` and `AnalysisResult` were committed to the database, and `submission_id` is populated on the response.
- `"skipped"`: No database session was supplied to `AnalysisService.analyze_code()`, so persistence was intentionally bypassed (`submission_id` is `null`).
- `"failed"`: Static analysis succeeded, but persisting the history record failed during `flush()` or `commit()`.

### Failure-reporting behavior

If an exception occurs during persistence, `AnalysisService.analyze_code()` (`backend/app/services/analysis_service.py`):

1. Rolls back the database session (`db.rollback()`).
2. Logs the full exception server-side via `logger.exception("Failed to persist analysis result to database")`.
3. Sets `submission_id` to `null`.
4. Sets `persistence_status` to `"failed"`.
5. Sets `persistence_warning` to `"Analysis succeeded, but saving to history failed. This result will not appear in your analysis history."` (without leaking internal database error details to API clients).
6. Returns the completed analysis response (`success: true`) so clients still receive the complexity analysis while being explicitly informed that history persistence failed (addressing [issue #16](https://github.com/KartikeyG-world/pycode-intelligence-workbench/issues/16)).



## 8. Database Configuration

The database engine is configured through the DATABASE_URL setting in backend/app/core/config.py.

- The default database URL is sqlite+pysqlite:///./complexity.db.
- DATABASE_URL can be supplied through an environment variable or the configured .env file to select another SQLAlchemy database URL.
- The settings configuration specifies env_file=".env"; this relative path is resolved from the process working directory, not automatically from the backend directory.
- The SQLAlchemy engine is configured with pool_pre_ping enabled. SQLite connections use check_same_thread=False.
- Database sessions use autocommit=False, autoflush=False, and expire_on_commit=False.

The database session dependency closes the session after the request. See backend/app/db/database.py for the engine, session factory, and dependency implementation.

## 9. Database Initialization and Migrations

During application startup, backend/app/main.py performs a database connectivity check using SELECT 1.

- For SQLite, the application creates missing tables using SQLAlchemy Base.metadata.create_all.
- Startup database connection failures are logged as warnings, and the application continues starting.
- The repository contains an initial Alembic migration at backend/alembic/versions/c79742664bb5_initial_schema.py.
- The migration environment reads the database URL from application settings.

The inspected backend directory does not contain an alembic.ini configuration file. Therefore, a complete, executable Alembic migration workflow is not established by the current repository setup. Do not assume that PostgreSQL schema migrations can be applied through a ready-to-use command. See [issue #19](https://github.com/KartikeyG-world/pycode-intelligence-workbench/issues/19) for the tracked migration-workflow correction.

The SQLite create_all startup behavior should not be confused with a versioned migration process.

## 10. Timestamp Behavior

The CodeSubmission and AnalysisResult models define created_at using datetime.now(timezone.utc) as the default value.

The history endpoints return created_at through the Pydantic response schemas as a datetime value.

Although timestamps are created using UTC-aware Python datetimes, the current database and serialization path does not guarantee that the original UTC offset is preserved when values are read back. In particular, SQLite may return a datetime without timezone information.

Clients should not assume that every history timestamp includes an explicit UTC offset. See [issue #17](https://github.com/KartikeyG-world/pycode-intelligence-workbench/issues/17) for the tracked timestamp correction.

## 11. Test Coverage

The inspected backend test suite includes history-list endpoint tests in `backend/tests/test_api.py` and dedicated persistence-reporting tests in `backend/tests/test_persistence_reporting.py`.

The existing tests verify:

- `GET /api/history` returns HTTP 200 and a JSON list.
- `POST /api/analyze` returns `persistence_status: "saved"` and a valid `submission_id`, persists both `CodeSubmission` and `AnalysisResult`, and makes the entry retrievable via `GET /api/history` and `GET /api/history/{submission_id}`.
- `AnalysisService.analyze_code()` sets `persistence_status: "skipped"` when `db=None`.
- Database `flush()` and `commit()` failures trigger `db.rollback()`, log the server-side exception, avoid creating partial history rows, and return `persistence_status: "failed"` with a sanitized `persistence_warning`.

The backend test fixtures use a separate SQLite database for test execution.

The inspected tests do not provide dedicated coverage for all remaining history behaviors, including:

- Missing submission IDs on history detail (`GET /api/history/{submission_id}` 404).
- Deleting a history entry and cascade behavior.
- Minimum and maximum validation for the limit parameter.
- Preservation of timezone offsets in returned timestamps.
- Execution of the PostgreSQL migration workflow.

These are test-coverage observations from the inspected repository snapshot, not claims that the behaviors are necessarily broken. Related implementation corrections are tracked in issues #15, #17, and #19.

## 12. Related Issues

The following issues track corrections or improvements related to the analysis-history implementation:

| Issue | Topic | Status / Documented limitation |
|---|---|---|
| [#15](https://github.com/KartikeyG-world/pycode-intelligence-workbench/issues/15) | History result limits | Missing explicit minimum and maximum validation for the limit parameter. |
| [#16](https://github.com/KartikeyG-world/pycode-intelligence-workbench/issues/16) | Persistence failures | Addressed: persistence exceptions roll back, log server-side, and report `persistence_status: "failed"` with `persistence_warning`. |
| [#17](https://github.com/KartikeyG-world/pycode-intelligence-workbench/issues/17) | Timestamp offsets | UTC offset preservation is not guaranteed through the current database path. |
| [#19](https://github.com/KartikeyG-world/pycode-intelligence-workbench/issues/19) | PostgreSQL migrations | A complete executable Alembic migration workflow is not established. |

These references describe tracked work and do not imply that the proposed corrections have already been merged.

## 13. Implementation Source References

The current behavior described in this document was checked against these implementation and test files:

| File | Relevant implementation |
|---|---|
| backend/app/api/routes/history.py | History list, detail, and delete endpoints. |
| backend/app/schemas/analysis.py | `AnalyzeResponse` persistence status and warning fields. |
| backend/app/schemas/project.py | HistoryItemResponse and HistoryDetailResponse schemas. |
| backend/app/models/models.py | CodeSubmission and AnalysisResult models, relationships, and timestamp defaults. |
| backend/app/services/analysis_service.py | Analysis persistence lifecycle and failure handling. |
| backend/app/db/database.py | Database engine and session configuration. |
| backend/app/core/config.py | DATABASE_URL and application settings. |
| backend/app/main.py | Startup database checks and SQLite table creation. |
| backend/alembic/env.py | Alembic migration environment configuration. |
| backend/alembic/versions/c79742664bb5_initial_schema.py | Initial database schema migration. |
| backend/tests/test_api.py | Existing API endpoint tests, including history-list and analyze persistence checks. |
| backend/tests/test_persistence_reporting.py | Persistence lifecycle, rollback, logging, and API history-retrieval tests. |
| backend/conftest.py | Test database and client fixtures. |

This document describes the implementation inspected in the contributor's working checkout. The repository README identifies the published Unit 5 baseline as commit 84ae1574d567160dcb70f56d6ba745424607dcd9. All 11 implementation and test files referenced above were verified to match that baseline in the current checkout.
