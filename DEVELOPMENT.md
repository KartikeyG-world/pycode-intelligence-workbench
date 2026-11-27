# Development and Operations Guide

This guide describes the repository's backend and frontend development workflow. Commands are written for PowerShell where Windows-specific paths are relevant. Verify the active branch and dependency lockfiles before interpreting a test result as evidence for a particular release.

## 1. Verified prerequisites

| Tool | Repository requirement / source |
|---|---|
| Python | `>=3.11`, declared in `backend/pyproject.toml` |
| Node.js | `>=20`, declared in `frontend/package.json` |
| Python dependency manager | `uv` recommended; `backend/uv.lock` is checked in |
| JavaScript package manager | npm; use `frontend/package-lock.json` via `npm ci` |
| Git | Required for branch and commit workflows |

The audit environment used Python 3.13.15. This records the environment observed during the audit; it does not narrow the package metadata requirement.

## 2. Repository layout

```text
.
├── backend/
│   ├── app/
│   │   ├── analyzers/       # Parser and static analysis engines
│   │   ├── api/routes/      # FastAPI route modules
│   │   ├── core/            # Runtime configuration
│   │   ├── db/              # SQLAlchemy engine/session setup
│   │   ├── models/          # ORM models
│   │   ├── schemas/         # Pydantic request/response contracts
│   │   └── services/        # Analysis service orchestration
│   ├── tests/               # Pytest suite
│   ├── pyproject.toml
│   ├── uv.lock
│   └── requirements.txt
├── frontend/
│   ├── app/                 # Next.js App Router
│   ├── components/          # UI components
│   ├── lib/                 # API client and frontend utilities
│   ├── types/               # TypeScript contracts
│   └── package.json
├── .env.example
├── README.md
└── DEVELOPMENT.md
```

## 3. Environment configuration

The root `.env.example` contains the project's example configuration, including the API prefix, local SQLite URL and parser limits. The backend settings load `.env` relative to the backend process working directory. For a backend process started from `backend/`, create `backend/.env` from the root example:

```powershell
cd backend
Copy-Item ..\.env.example .env
```

The default database URL uses SQLite. PostgreSQL can be selected through `DATABASE_URL` using a SQLAlchemy URL supported by the configured Psycopg driver. Do not commit `.env` files, database passwords or service credentials.

The frontend requires its own runtime configuration only where the frontend API client expects it. Inspect the current frontend API client before introducing or documenting additional environment variables; do not invent variable names.

## 4. Backend setup

From the repository root:

```powershell
cd backend
uv sync --extra dev
```

This installs the project dependencies and development extra using the checked-in lockfile. If `uv` is not installed, install it using its official installation instructions before running the command.

Start FastAPI from the `backend/` directory:

```powershell
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Useful endpoints:

- API root: `http://127.0.0.1:8000/`
- OpenAPI UI: `http://127.0.0.1:8000/docs`
- Analyze: `POST http://127.0.0.1:8000/api/analyze`
- Health: `GET http://127.0.0.1:8000/api/health`
- History: `GET http://127.0.0.1:8000/api/history`

The health route performs a database connectivity query. A healthy application process does not by itself establish that every analysis endpoint has been exercised successfully.

## 5. Frontend setup

From the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

The frontend development server normally uses `http://localhost:3000`.

Available repository scripts:

```powershell
npm run lint
npm run build
npm run start
```

The production build script invokes Next.js with Webpack (`next build --webpack`). TypeScript checking is available directly:

```powershell
npx tsc --noEmit
```

Run lint, typecheck and build as separate checks and report each result independently.

## 6. Backend tests

From `backend/`:

```powershell
uv run pytest tests/ -v
```

Run a focused module when iterating:

```powershell
uv run pytest tests/test_complexity_analyzer.py -v
uv run pytest tests/test_interprocedural.py -v
uv run pytest tests/test_cfg_builder.py tests/test_cfg_control_flow.py tests/test_cfg_cyclomatic.py -v
```

The published repository baseline contains the following test modules:

- `test_api.py`
- `test_cfg_builder.py`
- `test_cfg_control_flow.py`
- `test_cfg_cyclomatic.py`
- `test_complexity_analyzer.py`
- `test_correlation_engine.py`
- `test_halstead_metrics.py`
- `test_infra_socket_db_regression.py`
- `test_interprocedural.py`
- `test_metrics_pipeline_integration.py`
- `test_metrics_schemas.py`
- `test_persistence_reporting.py`
- `test_phase1a12_final_verification.py`
- `test_phase1a13_semantics_closure.py`
- `test_phase1a1_correctness.py`
- `test_project_metrics_summary.py`
- `test_recurrence_regression.py`
- `test_scope_discovery.py`
- `test_structural_metrics.py`

This list is a module inventory, not a claim that every test currently passes. The reconciled test suite baseline contains 571 passing offline tests and 13 deselected tests (584 total collected).

## 7. Test environment considerations

The source audit reported that the Windows sandbox could not complete Starlette `TestClient` setup because loopback socket communication timed out. In that run, API tests errored before endpoint behavior could be verified; a socket-pair infrastructure regression test also timed out. These outcomes must remain distinct from analyzer unit-test results.

When a test depends on local sockets, rerun it in a suitable environment that permits loopback networking. Capture the traceback and exact environment. Do not label an API test passed merely because the failure appears environmental, and do not infer a root cause from a timeout alone.

## 8. Published architecture status

The public `main` branch baseline documented here is `c26fdd36837bc0782c9e840b370f478e306857a2`. All six units of Phase 1B.2 (including Unit 6 at `64adf3d256f04ff43796b933875887b2f34d3179`) are merged via PR #26. The unified metrics pipeline `metrics_pipeline.py` is integrated directly into `ComplexityAnalyzer.analyze()`, populating `scope_metrics` and `project_metrics`.

On active branch `feat/phase-1c-metrics-overview` (Pre-remediation PR snapshot: `d9753f4e79ed4d15069f13b1060ce151a82f99fb`, Phase 1C implementation checkpoint: `9f70e57624aca59017fc5b570e42c67340987260`), Phase 1C Units 1–4 are fully implemented, delivering the integrated frontend dashboard (`MetricsOverview`, `ScopeMetricsTable`, `ScopeInspector`, `ProjectCorrelationSection`, and workspace UX refinements). See [Phase 1C Frontend Integration](docs/architecture/phase-1c-frontend-integration.md).

## 9. Static-analysis safety boundary

The parser uses Python's AST parser and does not execute submitted code. Current limits are 100,000 source bytes, 3,000 source lines, 10,000 AST nodes and AST depth 200. Node/depth checks are post-parse checks; they do not constrain parser-stage work before `ast.parse` returns. See `SECURITY.md` for residual-risk handling.

## 10. Verification report format

Every engineering report that cites test results should state:

1. Branch name and full commit SHA.
2. Python and Node versions where relevant.
3. OS and execution environment, including whether network/socket access is restricted.
4. Exact command(s).
5. Tests collected, passed, failed, skipped, deselected and errored.
6. Exit code and any environmental limitation.

Frontend checks and backend checks must be reported independently. A clean TypeScript check does not establish a successful production build; analyzer unit tests do not establish successful HTTP transport.
