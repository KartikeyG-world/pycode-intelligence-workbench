# Phase 1B Metrics: Contracts and Integration Status

**Specification family:** Stage 0.7 metric contract and Stage 1.0.2 architecture contract.  
**Published source baseline:** Unit 5, `84ae1574d567160dcb70f56d6ba745424607dcd9`.  
**Local integration checkpoint pending publication:** Unit 6, `64adf3d256f04ff43796b933875887b2f34d3179`.

## 1. Why the status distinction matters

The published Unit 5 repository contains the metric schemas and analyzer modules for Phase 1B.2. It does not contain `backend/app/analyzers/metrics_pipeline.py`, and the published `ComplexityAnalyzer` does not invoke the CFG builder or the Phase 1B.2 analyzers. Although `AnalyzeResponse` declares `scope_metrics` and `project_metrics`, Unit 5 leaves them at their model defaults (empty list and null project summary).

The local Unit 6 commit is reported to add the unified pipeline and integrate it into `ComplexityAnalyzer`. Until that commit is pushed and verified on GitHub, do not describe this integration as part of the public `main` branch.

## 2. Component inventory

| Component | Source module | Published Unit 5 status |
|---|---|---|
| Metrics Pydantic schemas | `backend/app/schemas/metrics.py` | Present |
| Canonical scope discovery | `backend/app/analyzers/scope_discovery.py` | Present |
| Structural AST metrics | `backend/app/analyzers/structural_analyzer.py` | Present |
| AST-normalized Halstead analysis | `backend/app/analyzers/halstead_analyzer.py` | Present |
| Control Flow Graph / cyclomatic | `backend/app/analyzers/cfg_builder.py` | Present and independently tested |
| Correlation engine | `backend/app/analyzers/correlation_engine.py` | Present |
| Project metrics aggregation | `backend/app/analyzers/project_summary.py` | Present |
| Unified metrics orchestration | `backend/app/analyzers/metrics_pipeline.py` | Not present in published Unit 5 |
| Phase 1B.2 API response population | `backend/app/analyzers/complexity_analyzer.py` | Not integrated in published Unit 5 |
| Phase 1B.2 frontend | `frontend/types/analysis.ts`, `frontend/components/` | Not implemented |

## 3. Canonical scope contract

The canonical scope categories are:

- `module`
- `function`
- `method`
- `class_body`

Scope discovery is deterministic and emits lexical preorder: parent scopes before nested children, with siblings in source order. The module identifier is `<module>`. Callable identifiers are derived from `FunctionIndex`; class-body identifiers use the `class_body:<qualified-name>@<line>` convention. Async functions use the same public function/method categories rather than introducing another scope type.

Downstream analyzers must join by canonical `scope_id`; they must not independently invent a competing scope inventory or reorder the canonical output.

## 4. Structural AST metrics

The structural analyzer measures source-AST properties per canonical scope, including statement counts, direct top-level statements, AST node count/depth, control-nesting depth and selected control/statement properties.

Important contract distinctions:

- Structural scope ownership is not interchangeable with Halstead token ownership.
- AST expression-context nodes (`Load`, `Store`, `Del`) and `TypeIgnore` are excluded from structural node counts/depth according to the accepted contract.
- Scope-root depth is one.
- Child callable/class bodies are pruned from the parent scope's owned subtree; the declaration itself remains part of the parent where specified.
- Control-nesting depth is not raw AST depth.
- A flat `elif` chain is distinguished from a nested `else: if` using source coordinates. If required coordinates are missing, the analyzer reports its fallback diagnostic rather than silently pretending the distinction was exact.

The authoritative implementation is `structural_analyzer.py`; schema fields and validators are in `schemas/metrics.py`. The Stage 0.7 acceptance fixtures define exact expected counts.

## 5. Halstead metrics

The analyzer produces normalized operator/operand inventories and computes the standard derived quantities where their dependencies are available:

- Vocabulary: `eta = eta1 + eta2`.
- Program length: `N = N1 + N2`.
- Volume: `V = N * log2(eta)` when vocabulary is defined.
- Difficulty: `D = (eta1 / 2) * (N2 / eta2)` when the operand denominator is defined.
- Effort: `E = D * V` when both dependencies are available.
- Estimated time: `T = E / 18` under the adopted Stroud-number convention.
- Estimated delivered bugs: `B = V / 3000` under the adopted heuristic.

`T` and `B` are model-derived estimates, not measured developer time or actual defect counts. Undefined formulas remain explicitly undefined; do not coerce them to zero.

The syntax coverage states are:

- `FULL`: no unclassified syntax records.
- `PARTIAL`: one or more unclassified syntax records while the scope structure remains supported.
- `UNCLASSIFIED_SYNTAX`: unsupported scope structure with at least one unclassified syntax record.

Coverage status and mathematical availability are separate concepts. Consult `halstead_analyzer.py`, `schemas/metrics.py` and `test_halstead_metrics.py` for token classification, ownership and exact edge cases.

## 6. CFG and cyclomatic metrics

The CFG builder constructs a static graph with basic blocks and typed control-flow edges, and tracks graph reachability. It does not execute a function or prove that a path is feasible for a given runtime input.

The accepted graph cyclomatic formula is:

`M_graph = E_reachable - N_reachable + 2P`

where `P` is the number of connected components in the reachable graph model. Decision cyclomatic complexity is defined by the accepted decision inventory:

`M_decision = 1 + sum(pi_i)`

A scope's output must retain the status/limitations accompanying the score:

- `COMPLETE`: complete under the supported CFG model; the accepted graph score and risk-rank rules apply.
- `PARTIAL`: model limitations remain; output is provisional and must not receive an unqualified risk rank.
- `UNSUPPORTED`: numeric score and risk rank remain unavailable.

Partial support must never be disguised as complete CFG semantics. Static reachability is not runtime test coverage.

## 7. Correlation contract

Exactly five dimensions are approved:

1. `cyclomatic_vs_statement_count`
2. `cyclomatic_vs_ast_depth`
3. `cyclomatic_vs_control_nesting_depth`
4. `cyclomatic_vs_halstead_volume`
5. `cyclomatic_vs_halstead_effort`

The eligible base population consists of procedural scopes (`function` and `method`) with `cyclomatic_status == COMPLETE`. Modules, class bodies and non-complete CFG scopes are excluded.

Structural dimensions require a finite structural value and finite cyclomatic value. They are not gated by Halstead coverage. Halstead volume/effort dimensions additionally require `syntax_coverage_status == FULL` and a corresponding finite metric value. Each dimension retains its own matched sample.

The engine calculates Pearson `r` and Spearman `rho`; tied Spearman values use average fractional ranks. Status rules:

- `n < 3`: `INSUFFICIENT_SAMPLE`.
- `n >= 3` with zero variance in either variable: `ZERO_VARIANCE`.
- `n >= 3` with non-zero variance: `DESCRIPTIVE_ONLY`.

The result is descriptive co-variation only. Do not claim statistical significance, causal relationships or prediction of runtime performance.

## 8. Project summary denominators

The project summary must retain distinct eligible populations and denominators:

| Summary values | Denominator / eligibility |
|---|---|
| Average statement count, AST depth and control-nesting depth | All procedural scopes (`function` and `method`) |
| Average cyclomatic complexity | COMPLETE procedural scopes with finite cyclomatic values (`cyclomatic_evaluated_scopes`) |
| Average Halstead volume | FULL-coverage procedural scopes with finite volume (`halstead_volume_evaluated_scopes`) |
| Average Halstead effort | FULL-coverage procedural scopes with finite effort (`halstead_effort_evaluated_scopes`) |
| Partial-coverage volume/effort diagnostics | Separate partial-coverage populations and denominators |
| Unclassified syntax | Separate `unclassified_syntax_scopes` population |

Finite zero is a valid value. NaN and positive/negative infinity are excluded from numerical means and denominators. Undefined values remain unavailable, not zero.

Do not add project-wide sums of Halstead vocabulary/length, weighted Halstead totals or invented aggregate scores unless a reviewed specification explicitly defines them.

## 9. Persistence and frontend boundaries

Under Stage 1.0.2, Phase 1B.2 `scope_metrics` and `project_metrics` are computed dynamically and are not persisted in the existing `analysis_results` table. Historical retrieval therefore does not provide those fields from stored records. Any persistence change requires an explicit architecture decision and migration plan.

The inspected frontend response types and components do not yet expose the Phase 1B.2 metric models, CFG view, Halstead inventory, correlation report or project summary dashboard. Do not claim frontend integration until types, API handling and rendered components are implemented and tested.

## 10. Evidence and tests

Primary source modules:

- `backend/app/schemas/metrics.py`
- `backend/app/analyzers/scope_discovery.py`
- `backend/app/analyzers/structural_analyzer.py`
- `backend/app/analyzers/halstead_analyzer.py`
- `backend/app/analyzers/cfg_builder.py`
- `backend/app/analyzers/correlation_engine.py`
- `backend/app/analyzers/project_summary.py`

Relevant test modules:

- `backend/tests/test_metrics_schemas.py`
- `backend/tests/test_scope_discovery.py`
- `backend/tests/test_structural_metrics.py`
- `backend/tests/test_halstead_metrics.py`
- `backend/tests/test_cfg_builder.py`
- `backend/tests/test_cfg_control_flow.py`
- `backend/tests/test_cfg_cyclomatic.py`
- `backend/tests/test_correlation_engine.py`
- `backend/tests/test_project_metrics_summary.py`

The local Unit 6 integration test module `test_metrics_pipeline_integration.py` and `metrics_pipeline.py` were reported in local commit `64adf3d...`; neither is part of the published Unit 5 GitHub baseline. After Unit 6 is published, update this document with the new immutable source commit and the verified integration test results.
