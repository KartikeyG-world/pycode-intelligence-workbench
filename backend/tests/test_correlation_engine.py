"""
Test suite for Statistical Correlation Engine (Phase 1B.2 — Unit 5).

Verifies conformance to Stage 0.7 Section 7.3 and Stage 1.0.2 architecture:
- Stage 0.7 Dataset A: Monotonic non-linear co-variation (Pearson r=0.8241407, Spearman rho=1.0000000).
- Stage 0.7 Dataset B: Tied ranks co-variation (Pearson r=0.9511897, Spearman rho=0.9486833).
- Stage 0.7 Dataset C: Perfect negative relationship (Pearson r=-1.0000000, Spearman rho=-1.0000000).
- Insufficient sample size (n < 3 -> INSUFFICIENT_SAMPLE, coefficients None).
- Zero variance in X and Y (ZERO_VARIANCE when n >= 3, coefficients None).
- Scope population eligibility (modules and class bodies excluded, PARTIAL/UNSUPPORTED CFG excluded).
- Structural dimensions independent of Halstead coverage (PARTIAL/UNCLASSIFIED_SYNTAX included).
- Halstead dimensions restricted strictly to FULL coverage and available numeric values.
- Matched-pair scope ID preservation and deterministic ordering.
- Exact five approved correlation dimensions.
- Unit testing of rank and correlation helper functions.
- Non-finite numeric handling.
"""

import math
from typing import Any, Optional
import pytest

from app.schemas.metrics import (
    UnifiedScopeMetrics,
    ScopeCyclomaticMetrics,
    ScopeStructuralMetrics,
    ScopeHalsteadMetrics,
    UnclassifiedSyntaxRecord,
    ProjectCorrelationReport,
)
from app.analyzers.correlation_engine import (
    CorrelationAnalyzer,
    compute_ranks,
    compute_pearson_r,
    compute_spearman_rho,
)


def make_unified_scope(
    scope_id: str,
    scope_type: str = "function",
    cyclomatic_status: str = "COMPLETE",
    cyclomatic_complexity: Any = 1,
    statement_count: Any = 1,
    ast_depth: int = 2,
    control_nesting_depth: int = 0,
    syntax_coverage_status: str = "FULL",
    volume: Optional[float] = 10.0,
    effort: Optional[float] = 20.0,
) -> UnifiedScopeMetrics:
    """Helper to construct valid UnifiedScopeMetrics instances for test fixtures."""
    cov = syntax_coverage_status
    unclass_records = []
    if cov in ("PARTIAL", "UNCLASSIFIED_SYNTAX"):
        unclass_records = [
            UnclassifiedSyntaxRecord(
                node_class="MockUnclassifiedNode",
                lineno=1,
                col_offset=0,
                reason="Test diagnostic",
            )
        ]

    vol_status = "AVAILABLE" if volume is not None else "UNDEFINED_EMPTY_VOCABULARY"
    diff_status = "AVAILABLE" if volume is not None else "UNDEFINED_ZERO_OPERANDS"
    eff_status = (
        "AVAILABLE"
        if volume is not None and effort is not None
        else "UNDEFINED_DEPENDENCY"
    )

    if cyclomatic_complexity is not None and not math.isfinite(cyclomatic_complexity):
        cyclo = ScopeCyclomaticMetrics.model_construct(
            cyclomatic_status=cyclomatic_status,
            cyclomatic_complexity=cyclomatic_complexity,
            total_nodes=2,
            total_edges=1,
            reachable_nodes=2,
            reachable_edges=1,
            unreachable_basic_blocks=0,
        )
    else:
        cyclo = ScopeCyclomaticMetrics(
            cyclomatic_status=cyclomatic_status,
            cyclomatic_complexity=cyclomatic_complexity,
            total_nodes=2,
            total_edges=1,
            reachable_nodes=2,
            reachable_edges=1,
            unreachable_basic_blocks=0,
        )

    if statement_count is not None and not math.isfinite(statement_count):
        struct = ScopeStructuralMetrics.model_construct(
            statement_count=statement_count,
            top_level_statement_count=statement_count,
            ast_node_count=3,
            ast_depth=ast_depth,
            control_nesting_depth=control_nesting_depth,
            if_statement_count=0,
            if_expression_count=0,
            conditional_count=0,
            boolean_operator_count=0,
            assertion_count=0,
            loop_count=0,
            comprehension_count=0,
        )
    else:
        struct = ScopeStructuralMetrics(
            statement_count=statement_count,
            top_level_statement_count=statement_count,
            ast_node_count=statement_count * 3,
            ast_depth=ast_depth,
            control_nesting_depth=control_nesting_depth,
            if_statement_count=0,
            if_expression_count=0,
            conditional_count=0,
            boolean_operator_count=0,
            assertion_count=0,
            loop_count=0,
            comprehension_count=0,
        )

    return UnifiedScopeMetrics(
        scope_id=scope_id,
        name=scope_id.split("@")[0],
        scope_type=scope_type,
        lineno=1,
        end_lineno=10,
        cyclomatic=cyclo,
        structural=struct,
        halstead=ScopeHalsteadMetrics(
            distinct_operators=2,
            distinct_operands=2,
            total_operators=4,
            total_operands=4,
            vocabulary=4,
            length=8,
            volume=volume,
            difficulty=2.0 if volume is not None else None,
            effort=effort,
            volume_status=vol_status,
            difficulty_status=diff_status,
            effort_status=eff_status,
            syntax_coverage_status=cov,
            unclassified_syntax_nodes=unclass_records,
        ),
    )


class TestCorrelationMathematicalHelpers:
    """Tests the pure statistical calculation routines."""

    def test_compute_ranks_distinct(self):
        vals = [10.0, 50.0, 20.0, 40.0]
        assert compute_ranks(vals) == [1.0, 4.0, 2.0, 3.0]

    def test_compute_ranks_tied_average(self):
        # Stage 0.7 specified example: [1, 2, 2, 4] -> [1.0, 2.5, 2.5, 4.0]
        vals = [1.0, 2.0, 2.0, 4.0]
        assert compute_ranks(vals) == [1.0, 2.5, 2.5, 4.0]

    def test_compute_ranks_all_identical(self):
        vals = [3.0, 3.0, 3.0]
        assert compute_ranks(vals) == [2.0, 2.0, 2.0]

    def test_compute_ranks_empty(self):
        assert compute_ranks([]) == []

    def test_compute_ranks_raises_on_non_finite(self):
        with pytest.raises(ValueError, match="Cannot rank non-finite values"):
            compute_ranks([1.0, float("nan"), 3.0])
        with pytest.raises(ValueError, match="Cannot rank non-finite values"):
            compute_ranks([1.0, float("inf"), 3.0])
        with pytest.raises(ValueError, match="Cannot rank non-finite values"):
            compute_ranks([1.0, float("-inf"), 3.0])

    def test_pearson_insufficient_sample(self):
        assert compute_pearson_r([1.0, 2.0], [3.0, 4.0]) is None

    def test_pearson_zero_variance(self):
        assert compute_pearson_r([1.0, 1.0, 1.0], [2.0, 3.0, 4.0]) is None
        assert compute_pearson_r([1.0, 2.0, 3.0], [5.0, 5.0, 5.0]) is None

    def test_pearson_and_spearman_reject_non_finite(self):
        # NaN in x or y
        assert compute_pearson_r([1.0, float("nan"), 3.0], [2.0, 4.0, 6.0]) is None
        assert compute_pearson_r([1.0, 2.0, 3.0], [2.0, float("nan"), 6.0]) is None
        assert compute_spearman_rho([1.0, float("nan"), 3.0], [2.0, 4.0, 6.0]) is None
        assert compute_spearman_rho([1.0, 2.0, 3.0], [2.0, float("nan"), 6.0]) is None
        # Inf in x or y
        assert compute_pearson_r([1.0, float("inf"), 3.0], [2.0, 4.0, 6.0]) is None
        assert compute_pearson_r([1.0, 2.0, 3.0], [2.0, float("-inf"), 6.0]) is None
        assert compute_spearman_rho([1.0, float("inf"), 3.0], [2.0, 4.0, 6.0]) is None
        assert compute_spearman_rho([1.0, 2.0, 3.0], [2.0, float("-inf"), 6.0]) is None

    def test_canonical_datasets_via_pure_helpers(self):
        # Dataset A: M = [1, 2, 3, 4], V = [10, 100, 1000, 10000]
        r_a = compute_pearson_r([1.0, 2.0, 3.0, 4.0], [10.0, 100.0, 1000.0, 10000.0])
        rho_a = compute_spearman_rho([1.0, 2.0, 3.0, 4.0], [10.0, 100.0, 1000.0, 10000.0])
        assert pytest.approx(r_a, abs=1e-7) == 0.8241407
        assert pytest.approx(rho_a, abs=1e-7) == 1.0000000

        # Dataset B: M = [1, 2, 2, 4], S = [2, 3, 5, 8]
        r_b = compute_pearson_r([1.0, 2.0, 2.0, 4.0], [2.0, 3.0, 5.0, 8.0])
        rho_b = compute_spearman_rho([1.0, 2.0, 2.0, 4.0], [2.0, 3.0, 5.0, 8.0])
        assert pytest.approx(r_b, abs=1e-7) == 0.9511897
        assert pytest.approx(rho_b, abs=1e-7) == 0.9486833

        # Dataset C: M = [1, 2, 3, 4], S = [8, 6, 4, 2]
        r_c = compute_pearson_r([1.0, 2.0, 3.0, 4.0], [8.0, 6.0, 4.0, 2.0])
        rho_c = compute_spearman_rho([1.0, 2.0, 3.0, 4.0], [8.0, 6.0, 4.0, 2.0])
        assert pytest.approx(r_c, abs=1e-7) == -1.0000000
        assert pytest.approx(rho_c, abs=1e-7) == -1.0000000


class TestStage07CanonicalCorrelationDatasets:
    """Verifies all 3 canonical Stage 0.7 correlation datasets to 7 decimal places via public CorrelationAnalyzer.analyze()."""

    @pytest.fixture
    def analyzer(self):
        return CorrelationAnalyzer()

    def test_dataset_a_monotonic_non_linear(self, analyzer):
        """
        Stage 0.7 Dataset A:
        M = [1, 2, 3, 4], V = [10, 100, 1000, 10000]
        Expected: Pearson r = 0.8241407, Spearman rho = 1.0000000, Status = DESCRIPTIVE_ONLY
        """
        M = [1, 2, 3, 4]
        V = [10.0, 100.0, 1000.0, 10000.0]
        scopes = [
            make_unified_scope(
                scope_id=f"f{i}@1",
                cyclomatic_complexity=M[i],
                volume=V[i],
                effort=V[i] * 2.0,
            )
            for i in range(4)
        ]

        report = analyzer.analyze(scopes)
        assert isinstance(report, ProjectCorrelationReport)
        assert report.eligible_scope_count == 4

        dim = report.dimensions["cyclomatic_vs_halstead_volume"]
        assert dim.dimension_name == "cyclomatic_vs_halstead_volume"
        assert dim.status == "DESCRIPTIVE_ONLY"
        assert dim.sample_size == 4
        assert len(dim.pairs) == 4
        assert [p.scope_id for p in dim.pairs] == [f"f{i}@1" for i in range(4)]
        assert [p.cyclomatic_complexity for p in dim.pairs] == M
        assert [p.metric_value for p in dim.pairs] == V
        assert pytest.approx(dim.pearson_r, abs=1e-7) == 0.8241407
        assert pytest.approx(dim.spearman_rho, abs=1e-7) == 1.0000000
        assert dim.diagnostic_message is None

    def test_dataset_b_tied_ranks(self, analyzer):
        """
        Stage 0.7 Dataset B:
        M = [1, 2, 2, 4], S = [2, 3, 5, 8]
        Expected: Pearson r = 0.9511897, Spearman rho = 0.9486833, Status = DESCRIPTIVE_ONLY
        """
        M = [1, 2, 2, 4]
        S = [2, 3, 5, 8]
        scopes = [
            make_unified_scope(
                scope_id=f"func_{i}@1",
                cyclomatic_complexity=M[i],
                statement_count=S[i],
            )
            for i in range(4)
        ]

        report = analyzer.analyze(scopes)
        assert isinstance(report, ProjectCorrelationReport)
        assert report.eligible_scope_count == 4

        dim = report.dimensions["cyclomatic_vs_statement_count"]
        assert dim.dimension_name == "cyclomatic_vs_statement_count"
        assert dim.status == "DESCRIPTIVE_ONLY"
        assert dim.sample_size == 4
        assert len(dim.pairs) == 4
        assert [p.scope_id for p in dim.pairs] == [f"func_{i}@1" for i in range(4)]
        assert [p.cyclomatic_complexity for p in dim.pairs] == M
        assert [p.metric_value for p in dim.pairs] == [float(s) for s in S]
        assert pytest.approx(dim.pearson_r, abs=1e-7) == 0.9511897
        assert pytest.approx(dim.spearman_rho, abs=1e-7) == 0.9486833
        assert dim.diagnostic_message is None

    def test_dataset_c_perfect_negative(self, analyzer):
        """
        Stage 0.7 Dataset C:
        M = [1, 2, 3, 4], S = [8, 6, 4, 2]
        Expected: Pearson r = -1.0000000, Spearman rho = -1.0000000, Status = DESCRIPTIVE_ONLY
        """
        M = [1, 2, 3, 4]
        S = [8, 6, 4, 2]
        scopes = [
            make_unified_scope(
                scope_id=f"neg_{i}@1",
                cyclomatic_complexity=M[i],
                statement_count=S[i],
            )
            for i in range(4)
        ]

        report = analyzer.analyze(scopes)
        assert isinstance(report, ProjectCorrelationReport)
        assert report.eligible_scope_count == 4

        dim = report.dimensions["cyclomatic_vs_statement_count"]
        assert dim.dimension_name == "cyclomatic_vs_statement_count"
        assert dim.status == "DESCRIPTIVE_ONLY"
        assert dim.sample_size == 4
        assert len(dim.pairs) == 4
        assert [p.scope_id for p in dim.pairs] == [f"neg_{i}@1" for i in range(4)]
        assert [p.cyclomatic_complexity for p in dim.pairs] == M
        assert [p.metric_value for p in dim.pairs] == [float(s) for s in S]
        assert pytest.approx(dim.pearson_r, abs=1e-7) == -1.0000000
        assert pytest.approx(dim.spearman_rho, abs=1e-7) == -1.0000000
        assert dim.diagnostic_message is None


class TestCorrelationStatusPrecedenceAndBoundaries:
    """Verifies statistical status precedence: n < 3 -> INSUFFICIENT_SAMPLE, zero variance -> ZERO_VARIANCE."""

    @pytest.fixture
    def analyzer(self):
        return CorrelationAnalyzer()

    def test_insufficient_sample_size_empty(self, analyzer):
        report = analyzer.analyze([])
        assert report.eligible_scope_count == 0
        for name, dim in report.dimensions.items():
            assert dim.sample_size == 0
            assert dim.status == "INSUFFICIENT_SAMPLE"
            assert dim.pearson_r is None
            assert dim.spearman_rho is None
            assert "Insufficient sample size" in dim.diagnostic_message

    def test_insufficient_sample_size_two_scopes(self, analyzer):
        scopes = [
            make_unified_scope("f1@1", cyclomatic_complexity=1, statement_count=5),
            make_unified_scope("f2@1", cyclomatic_complexity=2, statement_count=10),
        ]
        report = analyzer.analyze(scopes)
        assert report.eligible_scope_count == 2
        dim = report.dimensions["cyclomatic_vs_statement_count"]
        assert dim.sample_size == 2
        assert dim.status == "INSUFFICIENT_SAMPLE"
        assert dim.pearson_r is None
        assert dim.spearman_rho is None
        assert "n=2 < 3" in dim.diagnostic_message

    def test_sample_size_precedence_over_zero_variance(self, analyzer):
        """When n=2 and variance is 0, sample size (n < 3) takes precedence."""
        scopes = [
            make_unified_scope("f1@1", cyclomatic_complexity=2, statement_count=5),
            make_unified_scope("f2@1", cyclomatic_complexity=2, statement_count=5),
        ]
        report = analyzer.analyze(scopes)
        dim = report.dimensions["cyclomatic_vs_statement_count"]
        assert dim.sample_size == 2
        assert dim.status == "INSUFFICIENT_SAMPLE"

    def test_zero_variance_in_x_with_n_ge_3(self, analyzer):
        """When n=4 and cyclomatic complexity is constant, status is ZERO_VARIANCE."""
        scopes = [
            make_unified_scope(f"f{i}@1", cyclomatic_complexity=2, statement_count=i + 1)
            for i in range(4)
        ]
        report = analyzer.analyze(scopes)
        dim = report.dimensions["cyclomatic_vs_statement_count"]
        assert dim.sample_size == 4
        assert dim.status == "ZERO_VARIANCE"
        assert dim.pearson_r is None
        assert dim.spearman_rho is None
        assert "Zero variance" in dim.diagnostic_message

    def test_zero_variance_in_y_with_n_ge_3(self, analyzer):
        """When n=4 and target metric is constant, status is ZERO_VARIANCE."""
        scopes = [
            make_unified_scope(f"f{i}@1", cyclomatic_complexity=i + 1, statement_count=5)
            for i in range(4)
        ]
        report = analyzer.analyze(scopes)
        dim = report.dimensions["cyclomatic_vs_statement_count"]
        assert dim.sample_size == 4
        assert dim.status == "ZERO_VARIANCE"
        assert dim.pearson_r is None
        assert dim.spearman_rho is None


class TestScopeEligibilityAndGating:
    """Verifies scope type and coverage gating boundaries across dimensions."""

    @pytest.fixture
    def analyzer(self):
        return CorrelationAnalyzer()

    def test_module_and_class_body_scopes_strictly_excluded(self, analyzer):
        scopes = [
            make_unified_scope("<module>", scope_type="module", cyclomatic_complexity=1),
            make_unified_scope("class_body:C@1", scope_type="class_body", cyclomatic_complexity=1),
            make_unified_scope("f1@1", scope_type="function", cyclomatic_complexity=1, statement_count=2),
            make_unified_scope("m1@1", scope_type="method", cyclomatic_complexity=2, statement_count=4),
            make_unified_scope("f2@1", scope_type="function", cyclomatic_complexity=3, statement_count=6),
        ]
        report = analyzer.analyze(scopes)
        # Only f1, m1, f2 qualify (3 procedural scopes)
        assert report.eligible_scope_count == 3
        dim = report.dimensions["cyclomatic_vs_statement_count"]
        assert dim.sample_size == 3
        assert [p.scope_id for p in dim.pairs] == ["f1@1", "m1@1", "f2@1"]

    def test_non_complete_cfg_statuses_strictly_excluded(self, analyzer):
        scopes = [
            make_unified_scope("f1@1", cyclomatic_status="COMPLETE", cyclomatic_complexity=1, statement_count=2),
            make_unified_scope("f2@1", cyclomatic_status="PARTIAL", cyclomatic_complexity=2, statement_count=4),
            make_unified_scope("f3@1", cyclomatic_status="UNSUPPORTED", cyclomatic_complexity=None, statement_count=6),
            make_unified_scope("f4@1", cyclomatic_status="COMPLETE", cyclomatic_complexity=3, statement_count=8),
            make_unified_scope("f5@1", cyclomatic_status="COMPLETE", cyclomatic_complexity=4, statement_count=10),
        ]
        report = analyzer.analyze(scopes)
        # f2 and f3 excluded because CFG is not COMPLETE
        assert report.eligible_scope_count == 3
        dim = report.dimensions["cyclomatic_vs_statement_count"]
        assert dim.sample_size == 3
        assert [p.scope_id for p in dim.pairs] == ["f1@1", "f4@1", "f5@1"]

    def test_structural_dimensions_independent_of_halstead_coverage(self, analyzer):
        """Structural dimensions accept scopes even when Halstead coverage is PARTIAL or UNCLASSIFIED_SYNTAX."""
        scopes = [
            make_unified_scope("f1@1", cyclomatic_complexity=1, statement_count=2, syntax_coverage_status="FULL"),
            make_unified_scope("f2@1", cyclomatic_complexity=2, statement_count=4, syntax_coverage_status="PARTIAL"),
            make_unified_scope("f3@1", cyclomatic_complexity=3, statement_count=6, syntax_coverage_status="UNCLASSIFIED_SYNTAX"),
        ]
        report = analyzer.analyze(scopes)
        # All 3 scopes have COMPLETE CFG and are procedural -> eligible for structural dimensions
        dim_stmt = report.dimensions["cyclomatic_vs_statement_count"]
        assert dim_stmt.sample_size == 3
        assert dim_stmt.status == "DESCRIPTIVE_ONLY"

        # Halstead dimensions enforce syntax_coverage_status == 'FULL' -> only f1 qualifies
        dim_vol = report.dimensions["cyclomatic_vs_halstead_volume"]
        assert dim_vol.sample_size == 1
        assert dim_vol.status == "INSUFFICIENT_SAMPLE"
        assert [p.scope_id for p in dim_vol.pairs] == ["f1@1"]

    def test_halstead_dimensions_exclude_undefined_metrics(self, analyzer):
        """FULL-coverage scopes with volume=None or effort=None are excluded from Halstead pairs."""
        scopes = [
            make_unified_scope("f1@1", cyclomatic_complexity=1, volume=10.0, effort=20.0),
            make_unified_scope("f2@1", cyclomatic_complexity=2, volume=20.0, effort=None),
            make_unified_scope("f3@1", cyclomatic_complexity=3, volume=None, effort=None),
            make_unified_scope("f4@1", cyclomatic_complexity=4, volume=40.0, effort=80.0),
        ]
        report = analyzer.analyze(scopes)
        dim_vol = report.dimensions["cyclomatic_vs_halstead_volume"]
        # f1, f2, f4 have volume not None -> sample_size = 3
        assert dim_vol.sample_size == 3
        assert [p.scope_id for p in dim_vol.pairs] == ["f1@1", "f2@1", "f4@1"]

        dim_eff = report.dimensions["cyclomatic_vs_halstead_effort"]
        # only f1 and f4 have effort not None -> sample_size = 2 -> INSUFFICIENT_SAMPLE
        assert dim_eff.sample_size == 2
        assert dim_eff.status == "INSUFFICIENT_SAMPLE"
        assert [p.scope_id for p in dim_eff.pairs] == ["f1@1", "f4@1"]

    def test_matched_pair_scope_id_and_values(self, analyzer):
        """Verifies that each CorrelationDataPoint correctly binds scope_id and metric values."""
        scopes = [
            make_unified_scope("f1@1", cyclomatic_complexity=2, statement_count=10, ast_depth=4, control_nesting_depth=1),
            make_unified_scope("f2@1", cyclomatic_complexity=4, statement_count=20, ast_depth=6, control_nesting_depth=2),
            make_unified_scope("f3@1", cyclomatic_complexity=6, statement_count=30, ast_depth=8, control_nesting_depth=3),
        ]
        report = analyzer.analyze(scopes)
        dim_depth = report.dimensions["cyclomatic_vs_ast_depth"]
        assert len(dim_depth.pairs) == 3
        assert dim_depth.pairs[0].scope_id == "f1@1"
        assert dim_depth.pairs[0].cyclomatic_complexity == 2
        assert dim_depth.pairs[0].metric_value == 4.0

        dim_nest = report.dimensions["cyclomatic_vs_control_nesting_depth"]
        assert len(dim_nest.pairs) == 3
        assert dim_nest.pairs[1].scope_id == "f2@1"
        assert dim_nest.pairs[1].cyclomatic_complexity == 4
        assert dim_nest.pairs[1].metric_value == 2.0


class TestCorrelationNonFiniteHandling:
    """Verifies that non-finite values (NaN, +inf, -inf) do not contaminate correlation analysis."""

    @pytest.fixture
    def analyzer(self):
        return CorrelationAnalyzer()

    def test_nan_cyclomatic_and_metric_observation(self, analyzer):
        """Scopes with NaN cyclomatic complexity or NaN metric value are excluded from pairs."""
        scopes = [
            make_unified_scope("f0@1", cyclomatic_complexity=float("nan"), volume=10.0),
            make_unified_scope("f1@1", cyclomatic_complexity=2, volume=float("nan")),
            make_unified_scope("f2@1", cyclomatic_complexity=3, volume=30.0),
            make_unified_scope("f3@1", cyclomatic_complexity=4, volume=40.0),
        ]
        report = analyzer.analyze(scopes)
        dim_vol = report.dimensions["cyclomatic_vs_halstead_volume"]
        # Only f2 and f3 have finite cyclomatic complexity and finite volume
        assert dim_vol.sample_size == 2
        assert len(dim_vol.pairs) == 2
        assert [p.scope_id for p in dim_vol.pairs] == ["f2@1", "f3@1"]
        assert dim_vol.status == "INSUFFICIENT_SAMPLE"
        assert dim_vol.pearson_r is None
        assert dim_vol.spearman_rho is None

    def test_positive_infinity_observation(self, analyzer):
        """Scopes with +inf values are excluded from correlation matched pairs."""
        scopes = [
            make_unified_scope("f0@1", cyclomatic_complexity=float("inf"), volume=10.0),
            make_unified_scope("f1@1", cyclomatic_complexity=2, volume=float("inf")),
            make_unified_scope("f2@1", cyclomatic_complexity=3, volume=30.0),
            make_unified_scope("f3@1", cyclomatic_complexity=4, volume=40.0),
            make_unified_scope("f4@1", cyclomatic_complexity=5, volume=50.0),
        ]
        report = analyzer.analyze(scopes)
        dim_vol = report.dimensions["cyclomatic_vs_halstead_volume"]
        assert dim_vol.sample_size == 3
        assert len(dim_vol.pairs) == 3
        assert [p.scope_id for p in dim_vol.pairs] == ["f2@1", "f3@1", "f4@1"]
        assert dim_vol.status == "DESCRIPTIVE_ONLY"
        assert math.isfinite(dim_vol.pearson_r)
        assert math.isfinite(dim_vol.spearman_rho)

    def test_negative_infinity_observation(self, analyzer):
        """Scopes with -inf values are excluded from correlation matched pairs."""
        scopes = [
            make_unified_scope("f0@1", cyclomatic_complexity=float("-inf"), effort=10.0),
            make_unified_scope("f1@1", cyclomatic_complexity=2, effort=float("-inf")),
            make_unified_scope("f2@1", cyclomatic_complexity=3, effort=30.0),
            make_unified_scope("f3@1", cyclomatic_complexity=4, effort=40.0),
            make_unified_scope("f4@1", cyclomatic_complexity=5, effort=50.0),
        ]
        report = analyzer.analyze(scopes)
        dim_eff = report.dimensions["cyclomatic_vs_halstead_effort"]
        assert dim_eff.sample_size == 3
        assert len(dim_eff.pairs) == 3
        assert [p.scope_id for p in dim_eff.pairs] == ["f2@1", "f3@1", "f4@1"]
        assert dim_eff.status == "DESCRIPTIVE_ONLY"
        assert math.isfinite(dim_eff.pearson_r)
        assert math.isfinite(dim_eff.spearman_rho)

    def test_finite_matched_pair_population_remains_correctly_aligned(self, analyzer):
        """Interleaved non-finite observations do not shift or misalign remaining valid pairs."""
        scopes = [
            make_unified_scope("f0@1", cyclomatic_complexity=1, statement_count=10),
            make_unified_scope("f1@1", cyclomatic_complexity=2, statement_count=float("nan")),
            make_unified_scope("f2@1", cyclomatic_complexity=3, statement_count=30),
            make_unified_scope("f3@1", cyclomatic_complexity=float("inf"), statement_count=40),
            make_unified_scope("f4@1", cyclomatic_complexity=5, statement_count=50),
        ]
        report = analyzer.analyze(scopes)
        dim_stmt = report.dimensions["cyclomatic_vs_statement_count"]
        assert dim_stmt.sample_size == 3
        assert len(dim_stmt.pairs) == 3

        # Exactly f0, f2, f4 retained
        assert [p.scope_id for p in dim_stmt.pairs] == ["f0@1", "f2@1", "f4@1"]
        # Pairwise values strictly correspond to their respective scopes
        assert [p.cyclomatic_complexity for p in dim_stmt.pairs] == [1, 3, 5]
        assert [p.metric_value for p in dim_stmt.pairs] == [10.0, 30.0, 50.0]

    def test_sample_size_after_filtering_uses_remaining_eligible_pairs(self, analyzer):
        """Status precedence uses filtered sample size n, not raw scope count."""
        # 4 scopes, but 2 have non-finite metric values -> remaining n = 2 < 3 -> INSUFFICIENT_SAMPLE
        scopes_insufficient = [
            make_unified_scope("f0@1", cyclomatic_complexity=1, volume=10.0),
            make_unified_scope("f1@1", cyclomatic_complexity=2, volume=20.0),
            make_unified_scope("f2@1", cyclomatic_complexity=3, volume=float("nan")),
            make_unified_scope("f3@1", cyclomatic_complexity=4, volume=float("inf")),
        ]
        rep1 = analyzer.analyze(scopes_insufficient)
        dim1 = rep1.dimensions["cyclomatic_vs_halstead_volume"]
        assert dim1.sample_size == 2
        assert dim1.status == "INSUFFICIENT_SAMPLE"
        assert dim1.pearson_r is None

        # 5 scopes, 1 non-finite -> remaining n = 4 >= 3 with variance -> DESCRIPTIVE_ONLY
        scopes_descriptive = [
            make_unified_scope("f0@1", cyclomatic_complexity=1, volume=10.0),
            make_unified_scope("f1@1", cyclomatic_complexity=2, volume=20.0),
            make_unified_scope("f2@1", cyclomatic_complexity=3, volume=30.0),
            make_unified_scope("f3@1", cyclomatic_complexity=4, volume=40.0),
            make_unified_scope("f4@1", cyclomatic_complexity=5, volume=float("nan")),
        ]
        rep2 = analyzer.analyze(scopes_descriptive)
        dim2 = rep2.dimensions["cyclomatic_vs_halstead_volume"]
        assert dim2.sample_size == 4
        assert dim2.status == "DESCRIPTIVE_ONLY"
        assert dim2.pearson_r is not None
