# Test Strategy and Verification

## Verification principles

A passing test result is meaningful only when tied to the source revision and execution environment that produced it. Reports must distinguish analyzer unit tests, schema tests, integration tests, HTTP transport tests, database tests and frontend checks.

Do not publish an aggregate test total unless the complete suite was collected on one exact commit, every reported category is mutually exclusive or clearly accounted for, and the arithmetic reconciles.

## Backend test modules on published Unit 5

The public Unit 5 commit `84ae1574d567160dcb70f56d6ba745424607dcd9` contains these test modules:

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
| Metrics schemas | `test_metrics_schemas.py` |
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

## Test-count reconciliation warning

The source audit provided 15 per-module test counts whose arithmetic sum is 534, while its stated subtotal was 495. A separate earlier Unit 6 report described 584 collected, 13 deselected and 571 offline passes, plus a separate 37-test pipeline integration module. These reports do not establish one reconciled aggregate. This documentation intentionally publishes no total test count.

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
