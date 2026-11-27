# System Architecture Overview

**Verified source baseline:** `feat/phase-1c-metrics-overview`, Pre-remediation PR snapshot `d9753f4e79ed4d15069f13b1060ce151a82f99fb` (Phase 1C implementation checkpoint `9f70e57624aca59017fc5b570e42c67340987260`).
**Merged backend baseline:** public `main`, commit `c26fdd36837bc0782c9e840b370f478e306857a2`.

---

## 1. System Boundary

The application consists of a Next.js frontend, a FastAPI backend, static Python analysis modules, Pydantic request/response models and SQLAlchemy-backed persistence. Submitted source code is parsed as syntax and analyzed statically; the analysis service never executes the submitted program.

---

## 2. End-to-End Analysis Data Flow

```text
                  User / Browser
                        |
                        v
              Next.js Frontend (Page / Monaco)
                        |
                        | POST /api/analyze
                        v
                 FastAPI Backend
                        |
                        v
              Safe Static AST Parser (ast.parse)
                        |
                        v
                 Scope Discovery (Lexical Preorder)
                        |
          +-------------+-------------+
          |             |             |
          v             v             v
      Structural    Halstead       CFG /
       Metrics       Metrics    Cyclomatic
          |             |             |
          +-------------+-------------+
                        |
                        v
              Unified Metrics Pipeline
                        |
          +-------------+-------------+
          |                           |
          v                           v
      Scope Metrics             Project Metrics
   (UnifiedScopeMetrics[])   (ProjectMetricsSummary)
          |                           |
          +-------------+-------------+
                        |
                        v
                 API Response (AnalyzeResponse)
                        |
                        v
                 Next.js Frontend (React 19)
                        |
          +-------------+-------------+
          |             |             |
          v             v             v
       Overview    Correlations    Scope Explorer
  (MetricsOverview) (ProjectCorrelation) (ScopeMetricsTable)
                                      |
                                      v
                                Scope Inspector
                                (ScopeInspector)
```

---

## 3. Runtime Request Path

1. The browser submits Python source code to `POST /api/analyze`.
2. FastAPI validates the request via `AnalyzeRequest` and invokes `AnalysisService.analyze_code()`.
3. `AnalysisService` delegates to `SafeASTParser.parse_code()`.
4. On a syntax or parser limit error, the service immediately returns an `AnalyzeResponse` with `success: false` and structured error details; no code execution or partial analysis occurs.
5. On parse success, `AnalysisService` passes the AST to `ComplexityAnalyzer.analyze()`.
6. `ComplexityAnalyzer` executes `UnifiedMetricsPipeline.run(tree)` to discover canonical scopes, evaluate structural and Halstead metrics, construct procedural CFGs, calculate statistical correlations, and aggregate project-level metrics, populating `scope_metrics` and `project_metrics`.
7. `ComplexityAnalyzer` also constructs a `FunctionIndex` and `CallGraph`, evaluates loops/recurrences/operations, composes interprocedural costs, and builds legacy structure and theoretical asymptotic growth data.
8. `AnalysisService` optionally persists the legacy analysis fields (see [Persistence Boundary](#6-persistence-boundary)) and returns the complete `AnalyzeResponse`.
9. The Next.js frontend renders the integrated multi-level workspace: Project Metrics Overview, Correlation Analysis, Per-Scope Explorer, Detailed Scope Inspector, and Algorithmic Complexity breakdowns.

---

## 4. Published Backend Responsibilities

| Layer | Source area | Responsibility |
|---|---|---|
| HTTP application | `backend/app/main.py` | FastAPI application, CORS middleware, lifespan and router registration |
| Analyze route | `backend/app/api/routes/analyze.py` | Request validation and service invocation |
| Health route | `backend/app/api/routes/health.py` | Service and database connectivity response |
| History routes | `backend/app/api/routes/history.py` | Read and delete persisted analysis history |
| Analysis service | `backend/app/services/analysis_service.py` | Orchestrate parse, analyze and optional persistence |
| Parser | `backend/app/analyzers/ast_parser.py` | AST construction and resource/size boundary enforcement |
| Phase 1A orchestration | `backend/app/analyzers/complexity_analyzer.py` | Algorithmic complexity analysis and response composition |
| Unified metrics pipeline | `backend/app/analyzers/metrics_pipeline.py` | Authoritative coordinator for Phase 1B.2 metrics generation |
| CFG & cyclomatic engine | `backend/app/analyzers/cfg_builder.py` | Basic block graph construction and cyclomatic calculations |
| Scope discovery | `backend/app/analyzers/scope_discovery.py` | Deterministic canonical scope discovery in lexical preorder |
| Structural metrics | `backend/app/analyzers/structural_analyzer.py` | AST structural node and statement distribution metrics |
| Halstead analyzer | `backend/app/analyzers/halstead_analyzer.py` | AST-normalized token inventories and Halstead metrics |
| Correlation engine | `backend/app/analyzers/correlation_engine.py` | Pearson and Spearman correlation across 5 dimensions |
| Project summary | `backend/app/analyzers/project_summary.py` | Project-wide aggregation across distinct scope populations |
| Pydantic contracts | `backend/app/schemas/` | Request, response, metric, and history schemas |
| ORM / database | `backend/app/models/`, `backend/app/db/` | Relational persistence and DB session handling |

---

## 5. Phase 1A Analysis Modules

The request path uses the interprocedural and asymptotic analysis family:
- `FunctionIndex`: Indexes callable definitions and lexical relationships.
- `CallGraph`: Represents call edges and identifies recursion components.
- `LoopAnalyzer`: Extracts supported loop constructs and bounds.
- `RecursionAnalyzer`: Identifies recursive functions and recurrence forms.
- `RecurrenceSolver`: Solves supported recurrence equations.
- `OperationAnalyzer`: Models built-in container operations and allocation costs.
- `CostComposer`: Composes costs across loops, calls, and function hierarchies.
- `StructureAnalyzer`: Produces legacy structural statistics and hierarchy nodes.

---

## 6. CFG and Phase 1B.2 Unified Metrics Integration

In Unit 6 (`64adf3d256f04ff43796b933875887b2f34d3179`, merged via PR #26), `metrics_pipeline.py` was introduced as the unified coordinator and wired directly into `ComplexityAnalyzer.analyze()`.

The `AnalyzeResponse` returned by `/api/analyze` dynamically populates:
- `scope_metrics`: Unified records binding cyclomatic, structural, and Halstead complexity per canonical scope in lexical preorder.
- `project_metrics`: Project-wide summary aggregating procedural averages, diagnostic populations, and Pearson/Spearman correlations across the 5 approved dimensions.

For full metric specifications and mathematical formulas, see [Phase 1B Metrics: Contracts and Integration Status](phase-1b-metrics.md).

---

## 7. Persistence Boundary

`AnalysisService` persists legacy fields represented in `AnalysisResult`: core time/space complexity, confidence, reasoning, and JSON-serialized legacy statistics, structure, graph, detected patterns, and optimization suggestions.

**The Phase 1B.2 metric contracts (`scope_metrics` and `project_metrics`) are computed dynamically on each request and are not stored in the database.** Historical analysis responses retrieved via `GET /api/history/{submission_id}` therefore omit these fields.

Persistence status is explicitly communicated via:
- `persistence_status`: `"saved" | "failed" | "skipped" | null`
- `persistence_warning`: User-facing message if persistence fails without failing the analysis itself.

A persistence change requires a separate architecture decision and migration plan; new metric payloads are not written into unrelated JSON fields as an undocumented shortcut. For full history API details, see [Analysis History API](../api/ANALYSIS_HISTORY_API.md).

---

## 8. Frontend Boundary

The frontend is built with Next.js 16 (App Router), React 19, TypeScript 5, and Tailwind CSS v4, utilizing Monaco Editor, Recharts, and React Flow (`@xyflow/react`).

Phase 1C delivers an integrated analytical workspace:
- **`MetricsOverview.tsx`**: High-level project summary cards and diagnostic badges.
- **`ScopeMetricsTable.tsx`**: Interactive, sortable per-scope metrics table with canonical preorder reset and sticky scope pinning.
- **`ScopeInspector.tsx`**: Multi-tab drill-down modal/drawer for deep cyclomatic, structural, and Halstead analysis with explicit model disclaimers.
- **`ProjectCorrelationSection.tsx`**: Statistical correlation cards and canonical scatter plot rendered directly from backend `correlation.pairs`.
- **Workspace UX Integration**: Sticky desktop editor layout (`lg:sticky lg:top-20`), clean Empty State restoration upon editor reset, dark-themed React Flow controls, and responsive styling across mobile, tablet, and desktop viewports.

For complete frontend architectural details, component hierarchy, and UX design decisions, see [Phase 1C Frontend Metrics Integration Architecture](phase-1c-frontend-integration.md).

---

## 9. Design Invariants

1. **Zero Dynamic Execution:** Submitted Python source code is never executed (`no eval`, `no exec`, no subprocess).
2. **Deterministic Preorder:** Canonical scopes are discovered in lexical preorder; downstream analyzers and UI components preserve this canonical ordering.
3. **No Synthetic Data:** Undefined mathematical metrics remain explicitly `null`/`undefined`; the frontend never fabricates synthetic zeros or default numbers.
4. **Descriptive Correlation:** Correlation coefficients represent descriptive co-variation only and do not establish causation or runtime prediction.
5. **Separation of Analysis and Persistence:** Static analysis success and history persistence are separate outcomes with explicit status reporting.
6. **Theoretical Model Transparency:** Halstead time and bug estimates are prominently labeled as theoretical model estimates, not runtime measurements or verified bug counts.

---

## 10. Source References

- Backend Entry Point: `backend/app/main.py`
- Analysis Routes: `backend/app/api/routes/analyze.py`, `backend/app/api/routes/history.py`
- Analysis Service: `backend/app/services/analysis_service.py`
- Parser & Analyzers: `backend/app/analyzers/`
- Schemas: `backend/app/schemas/analysis.py`, `backend/app/schemas/metrics.py`, `backend/app/schemas/project.py`
- Models & DB: `backend/app/models/models.py`, `backend/app/db/database.py`
- Frontend Page: `frontend/app/page.tsx`
- Frontend Components: `frontend/components/metrics/`, `frontend/components/CodeEditor.tsx`, `frontend/components/StructureFlow.tsx`
- TypeScript Contracts: `frontend/types/analysis.ts`
