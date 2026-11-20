# System Architecture Overview

**Verified source baseline:** public `main`, Unit 5 commit `84ae1574d567160dcb70f56d6ba745424607dcd9`.

## 1. System boundary

The application consists of a Next.js frontend, a FastAPI backend, static Python analysis modules, Pydantic request/response models and SQLAlchemy-backed persistence. Submitted source is parsed as syntax and analyzed statically; the analysis service does not run the submitted program.

## 2. Runtime request path

The published Unit 5 request path is:

1. The browser submits an analysis request to `POST /api/analyze`.
2. FastAPI validates the request using `AnalyzeRequest` and delegates to `AnalysisService`.
3. `AnalysisService` calls `SafeASTParser.parse_code`.
4. On a syntax/parser error, the service returns an `AnalyzeResponse` containing structured error information and no successful analysis result.
5. On parse success, the service passes the AST to `ComplexityAnalyzer.analyze`.
6. `ComplexityAnalyzer` constructs a `FunctionIndex` and `CallGraph`, evaluates loops/recurrences/operations, composes interprocedural costs, and builds the legacy structure and theoretical growth data.
7. The service optionally persists the legacy result fields and returns the response.

The API also exposes a health route and persisted analysis-history routes. The health route executes a database connectivity query; the history routes read the persisted `AnalysisResult`/`CodeSubmission` model.

## 3. Published backend responsibilities

| Layer | Source area | Responsibility |
|---|---|---|
| HTTP application | `backend/app/main.py` | FastAPI app, CORS, lifespan and router registration |
| Analyze route | `backend/app/api/routes/analyze.py` | Request validation and service invocation |
| Health route | `backend/app/api/routes/health.py` | Service/database connectivity response |
| History route | `backend/app/api/routes/history.py` | Read persisted analysis history |
| Analysis service | `backend/app/services/analysis_service.py` | Parse, analyze and optionally persist |
| Parser | `backend/app/analyzers/ast_parser.py` | AST construction and parser resource/error boundaries |
| Phase 1A orchestration | `backend/app/analyzers/complexity_analyzer.py` | Algorithmic complexity analysis and response composition |
| Pydantic contracts | `backend/app/schemas/` | Request, response and metric models |
| ORM / database | `backend/app/models/`, `backend/app/db/` | Relational persistence and DB session handling |

## 4. Phase 1A analysis modules

The request path uses the interprocedural and asymptotic analysis family:

- `FunctionIndex` indexes callable definitions and their lexical relationships.
- `CallGraph` represents calls between indexed functions and identifies recursion components.
- `LoopAnalyzer` extracts supported loop patterns and bounds.
- `RecursionAnalyzer` identifies recursive relationships and recurrence candidates.
- `RecurrenceSolver` solves supported recurrence forms.
- `OperationAnalyzer` models selected built-in/container operations and allocation costs.
- `CostComposer` composes costs across loops, calls and function relationships.
- `StructureAnalyzer` produces the legacy structural statistics and graph model.

The exact supported pattern set and confidence semantics are determined by the implementation and regression tests; this overview does not promise exact complexity for arbitrary Python programs.

## 5. CFG and Phase 1B.2 components in the published tree

The public Unit 5 tree contains `cfg_builder.py`, Phase 1B.2 metric schemas, scope discovery, structural metrics, Halstead metrics, correlation and project-summary modules. These modules have focused tests. However, the Unit 5 `ComplexityAnalyzer` does not import or call `CFGBuilder` or a unified metrics pipeline. The request path therefore remains the Phase 1A pipeline at this published checkpoint.

The response model already declares `scope_metrics` (default empty list) and `project_metrics` (default null). The Unit 5 `ComplexityAnalyzer` return construction does not populate these fields. Schema presence must not be confused with an integrated capability.

The local Unit 6 commit `64adf3d256f04ff43796b933875887b2f34d3179` is reported to add `metrics_pipeline.py` and connect it to `ComplexityAnalyzer`. It is not present on the public remote in this documentation snapshot. See [Phase 1B metrics](phase-1b-metrics.md).

## 6. Persistence boundary

`AnalysisService` persists the legacy fields represented in `AnalysisResult`, including complexity, confidence, reasoning and serialized legacy statistics/structure/graph and suggestion data. The Phase 1B.2 metrics are not persisted under the accepted current Stage 1.0.2 contract. Historical analysis responses are therefore not equivalent to a live Unit 6 response that may include dynamic metric data.

A persistence change requires a separate architecture decision and migration plan; do not write new metric payloads into unrelated JSON fields as an undocumented shortcut.

## 7. Frontend boundary

The current frontend is built with Next.js/React and uses Monaco Editor, Recharts and React Flow for the existing analysis experience. The inspected `frontend/types/analysis.ts` does not declare the Phase 1B.2 metric objects, and the existing page/component set does not render CFG, Halstead, correlation or project-summary metric views. Frontend integration is separate future work.

## 8. Design invariants

- Submitted Python source is never executed.
- The parser returns a structured error rather than running malformed source.
- Analyzer outputs must preserve status, limitations and unavailable values.
- Canonical scope and metric contracts are defined by their schema/specification, not by UI assumptions.
- Static graph structure is not runtime branch coverage.
- Metrics calculated per request are not automatically persisted.

## 9. Source references

The baseline paths to inspect are `backend/app/main.py`, `backend/app/api/routes/`, `backend/app/services/analysis_service.py`, `backend/app/analyzers/ast_parser.py`, `backend/app/analyzers/complexity_analyzer.py`, `backend/app/analyzers/cfg_builder.py`, `backend/app/analyzers/scope_discovery.py`, `backend/app/analyzers/structural_analyzer.py`, `backend/app/analyzers/halstead_analyzer.py`, `backend/app/analyzers/correlation_engine.py`, `backend/app/analyzers/project_summary.py`, `backend/app/schemas/analysis.py`, `backend/app/schemas/metrics.py` and `backend/app/models/models.py`.
