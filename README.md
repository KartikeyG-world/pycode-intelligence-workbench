# Python Code Intelligence & Performance Workbench

A static-analysis workbench for inspecting Python program structure and reasoning about algorithmic complexity without executing submitted source code.

> **Repository-state note (20 November 2026):** This documentation draft targets the published GitHub baseline `84ae1574d567160dcb70f56d6ba745424607dcd9` (Unit 5). The local Unit 6 commit `64adf3d256f04ff43796b933875887b2f34d3179` is not present on the GitHub remote yet. The Unit 6 unified metrics pipeline is therefore described as pending publication, not as part of the current public `main` branch.

## What the workbench does

The currently published application accepts Python source, parses it into an Abstract Syntax Tree (AST), and performs static analysis to produce algorithmic time/space complexity reasoning and a structured analysis response. Its Phase 1A analysis includes function indexing, interprocedural call relationships, recursion/recurrence reasoning, loop analysis, operation-cost models and asymptotic cost composition.

The repository also contains a Control Flow Graph (CFG) builder and Phase 1B.2 metric components. Their presence in the source tree must be distinguished from integration into the current HTTP analysis path; see [Current capability status](#current-capability-status) and the [Phase 1B metrics status note](docs/architecture/phase-1b-metrics.md).

## Current capability status

Status below is evaluated against the published Unit 5 commit identified above.

| Capability | Published status | Notes |
|---|---|---|
| Safe Python AST parsing | Implemented | Static parsing with source-size, line-count, AST-node and AST-depth limits. |
| Phase 1A complexity analysis | Implemented / API-integrated | Function indexing, call graph, loops, recursion/recurrences, operation-cost analysis and cost composition. |
| CFG construction and cyclomatic analysis | Implemented as backend modules | CFG implementation and tests are present; the current `ComplexityAnalyzer` HTTP path does not invoke the CFG builder. |
| Phase 1B.2 schemas and analyzer modules | Present in backend source | Scope discovery, structural metrics, Halstead metrics, correlation and project-summary modules exist. |
| Unified Phase 1B.2 metrics pipeline | Pending publication | The local Unit 6 commit adds `metrics_pipeline.py` and wires it into `ComplexityAnalyzer`; that commit is not on GitHub as of this snapshot. |
| Phase 1B.2 frontend visualization | Not implemented | The current frontend types and components do not render the new metrics. |
| Runtime profiling / benchmarking | Not implemented | The application does not execute submitted code or measure runtime performance. |
| Automatic source optimization / rewriting | Not implemented | Suggestions are rule-based text; no semantics-preserving rewrite engine is present. |

The published `AnalyzeResponse` schema includes `scope_metrics` and `project_metrics` fields. On the published Unit 5 baseline, the analyzer does not populate these fields; they retain their schema defaults (an empty scope list and a null project summary). Do not infer an integrated metrics API from schema-field presence alone.

## Architecture at a glance

```text
Browser (Next.js / React)
        |
        | HTTP requests
        v
FastAPI routes (/api/analyze, /api/health, /api/history)
        |
        v
AnalysisService
        |
        v
SafeASTParser (ast.parse; no submitted-code execution)
        |
        v
ComplexityAnalyzer (published Phase 1A request path)
        |
        +--> FunctionIndex / CallGraph / LoopAnalyzer
        +--> RecursionAnalyzer / RecurrenceSolver
        +--> OperationAnalyzer / CostComposer
        +--> StructureAnalyzer
        |
        v
AnalyzeResponse (Pydantic)
        |
        +--> optional persistence of the legacy analysis fields
```

Additional CFG and Phase 1B.2 metric engines are available as backend modules, but the unified Unit 6 orchestration is pending publication at this baseline. Detailed ownership boundaries are in [System architecture](docs/architecture/system-overview.md).

## Technology stack

### Backend

- Python `>=3.11` (declared in `backend/pyproject.toml`)
- FastAPI and Uvicorn
- Pydantic v2 and pydantic-settings
- SQLAlchemy 2.x and Alembic
- Psycopg 3 for PostgreSQL connectivity
- Pytest and HTTPX in the development extra
- `uv` with the checked-in lockfile

### Frontend

- Node.js `>=20`
- Next.js 16 and React 19
- TypeScript 5 and Tailwind CSS v4
- Monaco Editor, React Flow, Recharts and Lucide React

### Persistence

The backend defaults to SQLite when no database URL is supplied and supports PostgreSQL through the configured SQLAlchemy URL. The current persistence model stores the legacy analysis result fields; Phase 1B.2 metric persistence is not part of the accepted current contract.

## Local development

See [DEVELOPMENT.md](DEVELOPMENT.md) for full setup and verification instructions.

### Backend

```powershell
cd backend
uv sync --extra dev
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```powershell
cd frontend
npm ci
npm run dev
```

## HTTP API

The FastAPI application mounts the following routes under `/api`:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/analyze` | Analyze submitted Python source statically. |
| `GET` | `/api/health` | Report service and database connectivity status. |
| `GET` | `/api/history` | Retrieve recent persisted analysis records. |
| `GET` | `/api/history/{submission_id}` | Retrieve a persisted analysis detail record. |

FastAPI's interactive API documentation is available at `/docs` when the backend is running. The endpoint contracts are defined by the route and Pydantic schema modules; do not treat live analysis responses and historical persistence responses as identical data models.

For history endpoint behavior, response schemas, persistence lifecycle, and known limitations, see [Analysis History API](docs/api/ANALYSIS_HISTORY_API.md).

## Static-analysis and security boundary

Submitted Python is parsed into AST data and analyzed without being executed. The parser enforces a 100,000-byte source limit, a 3,000-line limit, a 10,000-node AST limit and a depth limit of 200. The AST node/depth checks run after `ast.parse` has produced the tree; they do not eliminate all resource risks inside the interpreter's parsing stage. Deployments that accept hostile input should use process/container isolation and operating-system resource limits in addition to application-level checks.

Static results are not runtime measurements. The workbench does not provide measured execution time, actual peak memory, dynamic branch coverage or proof that a statically represented path is feasible for a particular input.

See [SECURITY.md](SECURITY.md) for the security boundary and disclosure guidance.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for the complete license text.

## Winter of Code Social (WOCS) 2026

This project participates in **[Winter of Code Social (WOCS) 2026](https://woc.codesocial.tech/)**, an open-source mentorship initiative organised by Code Social.

External contributors, student developers, and open-source participants are welcome to contribute! To ensure a smooth onboarding process:

1. **Find Available Issues:** Browse open, unassigned tasks on the project's [GitHub Issues tracker](https://github.com/KartikeyG-world/pycode-intelligence-workbench/issues).
2. **Review Contribution Standards:** Read the [CONTRIBUTING.md](CONTRIBUTING.md) guide for strict static-analysis invariants, branch naming conventions, and testing expectations.
3. **Request Issue Assignment:** Leave a comment on the relevant issue expressing interest and outlining your proposed technical approach.
4. **Wait for Formal Assignment:** **Do not begin work or submit a pull request until a Project Admin or Mentor explicitly assigns the issue to you.** Unassigned pull requests will be closed.
5. **Follow the Code of Conduct:** All participants must abide by the project's [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) across all discussions and reviews.
6. **Join Community Discussions:** Connect with maintainers and participants in the **[Code Social Discord Server](https://discord.gg/MSTNyRSPYW)**. (A dedicated project forum channel will be created and shared by the Project Admin).

## Documentation map

- [Development and operations](DEVELOPMENT.md)
- [Contribution workflow](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security policy](SECURITY.md)
- [Project license](LICENSE)
- [Documentation index](docs/README.md)
- [System architecture](docs/architecture/system-overview.md)
- [Phase 1B metric contracts and integration status](docs/architecture/phase-1b-metrics.md)
- [Test strategy and verification](docs/development/testing.md)

## Known documentation and integration gaps

1. The runtime default `PROJECT_NAME` in `backend/app/core/config.py` and `.env.example` still uses the legacy name `Code Complexity Visualizer`; this is a configuration-alignment item, not a claim that the runtime title has already been changed.
2. The Phase 1B.2 unified pipeline exists in a local Unit 6 commit but has not been published to GitHub at the snapshot recorded here.
3. The frontend does not yet expose Phase 1B/1B.2 metrics.
4. HTTP `TestClient` execution was blocked by loopback socket setup failures in the reported Windows sandbox. API transport verification must be repeated in an environment that supports the required local sockets.
5. Test totals reported in the source audit did not reconcile arithmetically. This documentation intentionally does not publish an aggregate test count.

## Repository baseline

- Repository: `KartikeyG-world/pycode-intelligence-workbench`
- Published branch baseline: `main` at `84ae1574d567160dcb70f56d6ba745424607dcd9`
- Local Unit 6 checkpoint pending publication: `64adf3d256f04ff43796b933875887b2f34d3179`
- Documentation snapshot date: 20 November 2026
