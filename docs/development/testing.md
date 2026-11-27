# Test Strategy and Verification

## Verification principles

A passing test result is meaningful only when tied to the source revision and execution environment that produced it. Reports must distinguish analyzer unit tests, schema tests, integration tests, HTTP transport tests, database tests and frontend checks.

Do not publish an aggregate test total unless the complete suite was collected on one exact commit, every reported category is mutually exclusive or clearly accounted for, and the arithmetic reconciles.

## Backend test modules on published baseline

The public `main` commit `c26fdd36837bc0782c9e840b370f478e306857a2` contains these test modules:

| Area | Test module |
|---|---|
| API | `test_api.py` |
| CFG construction | `test_cfg_builder.py` |
| CFG control-flow edges | `test_cfg_control_flow.py` |
| Cyclomatic calculations | `test_cfg_cyclomatic.py` |
| Main complexity analyzer | `test_complexity_analyzer.py` |
| Correlation | `test_correlation_engine.py` |
| Halstead | `test_halstead_metrics.py` |
| Socket/database infrastructure | `test_infra_socket_db_regression.py` |
| Interprocedural analysis | `test_interprocedural.py` |
| Metrics pipeline integration | `test_metrics_pipeline_integration.py` |
| Metrics schemas | `test_metrics_schemas.py` |
| Persistence failure reporting | `test_persistence_reporting.py` |
| Phase 1A.1 verification | `test_phase1a12_final_verification.py` |
| Phase 1A.1.3 semantics closure | `test_phase1a13_semantics_closure.py` |
| Phase 1A.1 correctness | `test_phase1a1_correctness.py` |
| Project metric summary | `test_project_metrics_summary.py` |
| Recurrence regressions | `test_recurrence_regression.py` |
| Canonical scope discovery | `test_scope_discovery.py` |
| Structural metrics | `test_structural_metrics.py` |

This inventory is not a pass-count statement. Run the suite on the revision under review.

## Commands

Run the complete backend suite from `backend/`:

```powershell
uv run pytest tests/ -v
```

Run focused analyzer tests:

```powershell
uv run pytest tests/test_metrics_schemas.py tests/test_scope_discovery.py -v
uv run pytest tests/test_structural_metrics.py tests/test_halstead_metrics.py -v
uv run pytest tests/test_cfg_builder.py tests/test_cfg_control_flow.py tests/test_cfg_cyclomatic.py -v
uv run pytest tests/test_correlation_engine.py tests/test_project_metrics_summary.py -v
```

For frontend changes, run from `frontend/`:

```powershell
npm run lint
npx tsc --noEmit
npm run build
```

## Environment-dependent test results recorded during audit

The read-only source audit reported the following limitation in its Windows sandbox run:

- The socket-pair regression module had one loopback socketpair timeout; its other seven tests passed in that run.
- Five HTTP API TestClient tests errored during TestClient setup because loopback socket communication timed out. The endpoint behavior was not verified by those tests in that environment.
- The frontend TypeScript check (`npx tsc --noEmit`) completed with zero errors in the inspected workspace.

These are reported historical observations, not a promise that the same result will occur on another machine or commit. Re-run transport tests where local loopback sockets are permitted, and preserve the actual exception/exit status.

## Test-count reconciliation

The accepted Unit 6 checkpoint reported:
- 584 total collected tests.
- 571 passing in the specified offline regression command (15 earlier offline modules: 534 tests; Unit 6 integration suite `test_metrics_pipeline_integration.py`: 37 tests).
- 13 deselected by that command's module-name filter.
- Seven pure SQLite database tests separately passed.
- Six socket-dependent tests remained unverified in the restricted Windows environment.

These 13 deselected tests are not failures or purely PostgreSQL-dependent tests. HTTP API endpoint execution was not verified at runtime through the offline suite.

## Phase 1C verification evidence

On development branch `feat/phase-1c-metrics-overview` at checkpoint `9f70e57624aca59017fc5b570e42c67340987260`, the following multi-layer quality gates were executed and verified:

| Gate | Command | Result | Details |
|---|---|---|---|
| Git Diff Whitespace | `git diff --check` | Passed | 0 whitespace or formatting errors |
| TypeScript Compiler | `npx tsc --noEmit` | Passed | Version 5.9.3, 0 errors, exit code 0 |
| ESLint | `npm run lint` | Passed | ESLint completed with 0 errors or warnings, exit code 0 |
| Production Build | `npm run build` | Passed | Next.js 16.3.6 (Webpack) compiled in 4.8s; static pages generated |
| Backend Pipeline Integration | `pytest tests/test_metrics_pipeline_integration.py` | Passed | 37 passed in 0.41s |
| Runtime Smoke Test | Browser automated inspection | Passed | All 4 target viewports (1440×900, 1280×800, 768×1024, 390×844) verified; 14 after screenshots |

## Required evidence in PRs

Every PR that changes behavior should record:

- Full Git commit SHA and branch.
- Runtime versions and OS.
- Exact commands.
- Collection and pass/failure/skip/deselection/error counts.
- Relevant warnings and environment-specific blockers.
- Whether HTTP transport and database integration were actually exercised.
- Whether frontend typecheck, lint and build ran (where applicable).

A unit-test pass must not be described as end-to-end API success. A typecheck pass must not be described as a production build pass.
