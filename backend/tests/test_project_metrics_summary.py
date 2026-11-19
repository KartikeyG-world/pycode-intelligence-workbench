"""
Test suite for Project Metrics Aggregation (Phase 1B.2 — Unit 5).

Verifies conformance to Stage 0.7 Section 6 and Stage 1.0.2 architecture:
1. Scope counts across all four public scope types (total = proc + mod + class).
2. Procedural structural averages across all CFG statuses (denominator = procedural_scopes).
3. Empty procedural population handling (averages are None, not zero).
4. Cyclomatic average restricted strictly to COMPLETE procedural scopes.
5. Halstead volume FULL coverage headline average.
6. Halstead effort FULL coverage headline average.
7. Separate evaluated denominators for volume and effort (unavailable values excluded).
8. Available zero Halstead metrics (e.g. volume = 0.0) preserved and averaged.
9. Mathematically undefined Halstead metrics excluded from denominators.
10. PARTIAL diagnostic volume average and denominator isolation.
11. PARTIAL diagnostic effort average and denominator isolation.
12. UNCLASSIFIED_SYNTAX population counting without numeric aggregate leakage.
13. Zero leaking of partial/unclassified metrics into headline averages.
14. Verification that unauthorized aggregates (e.g. project-wide vocabulary/length totals) are absent.
15. Preservation and attachment of ProjectCorrelationReport.
16. Consistency of all population counters and denominators across integration scenarios.
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
    ProjectMetricsSummary,
)
from app.analyzers.correlation_engine import CorrelationAnalyzer
from app.analyzers.project_summary import ProjectMetricsAggregator


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
    """Helper to construct valid UnifiedScopeMetrics instances for aggregation fixtures."""
    cov = syntax_coverage_status
    unclass_records = []
    if cov in ("PARTIAL", "UNCLASSIFIED_SYNTAX"):
        unclass_records = [
            UnclassifiedSyntaxRecord(
                node_class="MockDiagnosticNode",
                lineno=1,
                col_offset=0,
                reason="Test limitation",
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


class TestProjectMetricsSummaryAggregation:
    """Validates project-level metrics summary calculations and population counting."""

    @pytest.fixture
    def aggregator(self):
        return ProjectMetricsAggregator()

    @pytest.fixture
    def correlation_analyzer(self):
        return CorrelationAnalyzer()

    def test_scope_counts_across_all_four_scope_types(self, aggregator, correlation_analyzer):
        """Reconciles total_scopes = procedural_scopes + module_scopes + class_scopes."""
        scopes = [
            make_unified_scope("<module>", scope_type="module"),
            make_unified_scope("class_body:C@1", scope_type="class_body"),
            make_unified_scope("f1@1", scope_type="function"),
            make_unified_scope("f2@1", scope_type="function"),
            make_unified_scope("C.m1@2", scope_type="method"),
        ]
        corr = correlation_analyzer.analyze(scopes)
        summary = aggregator.aggregate(scopes, corr)

        assert summary.total_scopes == 5
        assert summary.procedural_scopes == 3
        assert summary.module_scopes == 1
        assert summary.class_scopes == 1
        assert (
            summary.total_scopes
            == summary.procedural_scopes + summary.module_scopes + summary.class_scopes
        )

    def test_structural_averages_include_all_cfg_statuses(self, aggregator, correlation_analyzer):
        """Structural averages use procedural_scopes denominator regardless of CFG status."""
        scopes = [
            make_unified_scope(
                "f1@1",
                cyclomatic_status="COMPLETE",
                statement_count=10,
                ast_depth=4,
                control_nesting_depth=1,
            ),
            make_unified_scope(
                "f2@1",
                cyclomatic_status="PARTIAL",
                statement_count=20,
                ast_depth=6,
                control_nesting_depth=2,
            ),
            make_unified_scope(
                "f3@1",
                cyclomatic_status="UNSUPPORTED",
                statement_count=30,
                ast_depth=8,
                control_nesting_depth=3,
            ),
        ]
        corr = correlation_analyzer.analyze(scopes)
        summary = aggregator.aggregate(scopes, corr)

        assert summary.procedural_scopes == 3
        assert summary.average_statement_count == 20.0
        assert summary.average_ast_depth == 6.0
        assert summary.average_control_nesting_depth == 2.0

    def test_empty_procedural_population_yields_none_averages(self, aggregator, correlation_analyzer):
        """When 0 procedural scopes exist, averages are None, not 0.0."""
        scopes = [
            make_unified_scope("<module>", scope_type="module"),
            make_unified_scope("class_body:C@1", scope_type="class_body"),
        ]
        corr = correlation_analyzer.analyze(scopes)
        summary = aggregator.aggregate(scopes, corr)

        assert summary.total_scopes == 2
        assert summary.procedural_scopes == 0
        assert summary.module_scopes == 1
        assert summary.class_scopes == 1
        assert summary.average_statement_count is None
        assert summary.average_ast_depth is None
        assert summary.average_control_nesting_depth is None
        assert summary.average_cyclomatic_complexity is None
        assert summary.cyclomatic_evaluated_scopes == 0
        assert summary.average_halstead_volume is None
        assert summary.average_halstead_effort is None
        assert summary.halstead_volume_evaluated_scopes == 0
        assert summary.halstead_effort_evaluated_scopes == 0

    def test_cyclomatic_average_restricted_to_complete_cfg(self, aggregator, correlation_analyzer):
        """Only COMPLETE CFG scopes with numeric values enter average_cyclomatic_complexity."""
        scopes = [
            make_unified_scope("f1@1", cyclomatic_status="COMPLETE", cyclomatic_complexity=2),
            make_unified_scope("f2@1", cyclomatic_status="COMPLETE", cyclomatic_complexity=4),
            make_unified_scope("f3@1", cyclomatic_status="PARTIAL", cyclomatic_complexity=6),
            make_unified_scope("f4@1", cyclomatic_status="UNSUPPORTED", cyclomatic_complexity=None),
        ]
        corr = correlation_analyzer.analyze(scopes)
        summary = aggregator.aggregate(scopes, corr)

        assert summary.procedural_scopes == 4
        assert summary.cyclomatic_evaluated_scopes == 2
        assert summary.average_cyclomatic_complexity == 3.0

    def test_halstead_full_coverage_averages_and_separate_denominators(self, aggregator, correlation_analyzer):
        """Verifies that volume and effort have separate evaluated denominators."""
        scopes = [
            make_unified_scope("f1@1", syntax_coverage_status="FULL", volume=10.0, effort=20.0),
            make_unified_scope("f2@1", syntax_coverage_status="FULL", volume=30.0, effort=None),
            make_unified_scope("f3@1", syntax_coverage_status="FULL", volume=None, effort=None),
        ]
        corr = correlation_analyzer.analyze(scopes)
        summary = aggregator.aggregate(scopes, corr)

        assert summary.halstead_volume_evaluated_scopes == 2
        assert summary.average_halstead_volume == 20.0  # (10 + 30) / 2

        assert summary.halstead_effort_evaluated_scopes == 1
        assert summary.average_halstead_effort == 20.0  # 20 / 1

    def test_available_zero_halstead_metrics_preserved(self, aggregator, correlation_analyzer):
        """A genuinely available volume of 0.0 (e.g. pass function) is included in average and denominator."""
        scopes = [
            make_unified_scope("f1@1", syntax_coverage_status="FULL", volume=0.0, effort=None),
            make_unified_scope("f2@1", syntax_coverage_status="FULL", volume=20.0, effort=40.0),
        ]
        corr = correlation_analyzer.analyze(scopes)
        summary = aggregator.aggregate(scopes, corr)

        assert summary.halstead_volume_evaluated_scopes == 2
        assert summary.average_halstead_volume == 10.0  # (0.0 + 20.0) / 2

    def test_partial_coverage_diagnostic_population_isolation(self, aggregator, correlation_analyzer):
        """PARTIAL coverage metrics enter diagnostic averages and are isolated from headline averages."""
        scopes = [
            make_unified_scope("f1@1", syntax_coverage_status="FULL", volume=10.0, effort=20.0),
            make_unified_scope("f2@1", syntax_coverage_status="PARTIAL", volume=50.0, effort=100.0),
            make_unified_scope("f3@1", syntax_coverage_status="PARTIAL", volume=70.0, effort=None),
        ]
        corr = correlation_analyzer.analyze(scopes)
        summary = aggregator.aggregate(scopes, corr)

        # Headline FULL averages contain only f1
        assert summary.halstead_volume_evaluated_scopes == 1
        assert summary.average_halstead_volume == 10.0
        assert summary.halstead_effort_evaluated_scopes == 1
        assert summary.average_halstead_effort == 20.0

        # Diagnostic PARTIAL averages
        assert summary.partial_coverage_volume_scopes == 2
        assert summary.average_partial_halstead_volume == 60.0  # (50 + 70) / 2
        assert summary.partial_coverage_effort_scopes == 1
        assert summary.average_partial_halstead_effort == 100.0

    def test_unclassified_syntax_population_counting(self, aggregator, correlation_analyzer):
        """UNCLASSIFIED_SYNTAX scopes increment counter without leaking into averages."""
        scopes = [
            make_unified_scope("f1@1", syntax_coverage_status="FULL", volume=10.0, effort=20.0),
            make_unified_scope("f2@1", syntax_coverage_status="UNCLASSIFIED_SYNTAX", volume=None, effort=None),
            make_unified_scope("f3@1", syntax_coverage_status="UNCLASSIFIED_SYNTAX", volume=None, effort=None),
        ]
        corr = correlation_analyzer.analyze(scopes)
        summary = aggregator.aggregate(scopes, corr)

        assert summary.procedural_scopes == 3
        assert summary.unclassified_syntax_scopes == 2
        assert summary.halstead_volume_evaluated_scopes == 1
        assert summary.average_halstead_volume == 10.0
        assert summary.partial_coverage_volume_scopes == 0
        assert summary.average_partial_halstead_volume is None

    def test_no_unauthorized_aggregates_in_summary(self, aggregator, correlation_analyzer):
        """Ensures forbidden fields (e.g. total_vocabulary, total_length, M_all) do not exist."""
        scopes = [make_unified_scope("f1@1")]
        corr = correlation_analyzer.analyze(scopes)
        summary = aggregator.aggregate(scopes, corr)

        dumped = summary.model_dump()
        forbidden_keys = [
            "total_vocabulary",
            "total_length",
            "project_halstead_vocabulary",
            "project_halstead_length",
            "weighted_halstead",
            "M_all",
            "M_proc",
        ]
        for key in forbidden_keys:
            assert key not in dumped

    def test_correlation_report_preservation(self, aggregator, correlation_analyzer):
        """Verifies correlation report is correctly attached and preserved."""
        scopes = [
            make_unified_scope("f1@1", cyclomatic_complexity=1, statement_count=5),
            make_unified_scope("f2@1", cyclomatic_complexity=2, statement_count=10),
            make_unified_scope("f3@1", cyclomatic_complexity=3, statement_count=15),
        ]
        corr = correlation_analyzer.analyze(scopes)
        summary = aggregator.aggregate(scopes, corr)

        assert summary.correlation.eligible_scope_count == 3
        dim = summary.correlation.dimensions["cyclomatic_vs_statement_count"]
        assert dim.sample_size == 3
        assert dim.status == "DESCRIPTIVE_ONLY"
        assert pytest.approx(dim.pearson_r, abs=1e-7) == 1.0


class TestCombinedUnit5Integration:
    """Verifies end-to-end integration across correlation analysis and project summary aggregation."""

    def test_full_pipeline_consistency(self):
        analyzer = CorrelationAnalyzer()
        aggregator = ProjectMetricsAggregator()

        scopes = [
            make_unified_scope("<module>", scope_type="module", statement_count=2),
            make_unified_scope("class_body:Box@1", scope_type="class_body", statement_count=1),
            make_unified_scope("Box.get@2", scope_type="method", cyclomatic_status="COMPLETE", cyclomatic_complexity=1, statement_count=2, ast_depth=3, volume=10.0, effort=20.0),
            make_unified_scope("compute@1", scope_type="function", cyclomatic_status="COMPLETE", cyclomatic_complexity=2, statement_count=4, ast_depth=5, volume=20.0, effort=40.0),
            make_unified_scope("fallback@1", scope_type="function", cyclomatic_status="COMPLETE", cyclomatic_complexity=3, statement_count=6, ast_depth=7, volume=30.0, effort=60.0),
            make_unified_scope("partial_fn@1", scope_type="function", cyclomatic_status="PARTIAL", cyclomatic_complexity=4, statement_count=8, ast_depth=9, syntax_coverage_status="PARTIAL", volume=50.0, effort=100.0),
            make_unified_scope("broken_fn@1", scope_type="function", cyclomatic_status="COMPLETE", cyclomatic_complexity=5, statement_count=10, ast_depth=11, syntax_coverage_status="UNCLASSIFIED_SYNTAX", volume=None, effort=None),
        ]

        corr = analyzer.analyze(scopes)
        summary = aggregator.aggregate(scopes, corr)

        # Scopes: 1 module + 1 class + 5 procedural = 7 total
        assert summary.total_scopes == 7
        assert summary.procedural_scopes == 5
        assert summary.module_scopes == 1
        assert summary.class_scopes == 1

        # Eligible correlation scopes: 4 (Box.get, compute, fallback, broken_fn)
        # partial_fn excluded from correlation because CFG is PARTIAL
        assert corr.eligible_scope_count == 4

        # Structural correlation sample_size: all 4 COMPLETE procedural scopes
        dim_stmt = corr.dimensions["cyclomatic_vs_statement_count"]
        assert dim_stmt.sample_size == 4
        assert [p.scope_id for p in dim_stmt.pairs] == ["Box.get@2", "compute@1", "fallback@1", "broken_fn@1"]

        # Halstead correlation sample_size: only Box.get, compute, fallback (broken_fn has UNCLASSIFIED_SYNTAX)
        dim_vol = corr.dimensions["cyclomatic_vs_halstead_volume"]
        assert dim_vol.sample_size == 3
        assert [p.scope_id for p in dim_vol.pairs] == ["Box.get@2", "compute@1", "fallback@1"]

        # Procedural averages:
        # All 5 procedural scopes included in structural averages: (2 + 4 + 6 + 8 + 10) / 5 = 6.0
        assert summary.average_statement_count == 6.0

        # Cyclomatic evaluated: 4 scopes with COMPLETE CFG: (1 + 2 + 3 + 5) / 4 = 2.75
        assert summary.cyclomatic_evaluated_scopes == 4
        assert summary.average_cyclomatic_complexity == 2.75

        # FULL Halstead evaluated: 3 scopes: (10 + 20 + 30) / 3 = 20.0
        assert summary.halstead_volume_evaluated_scopes == 3
        assert summary.average_halstead_volume == 20.0

        # PARTIAL Halstead evaluated: 1 scope
        assert summary.partial_coverage_volume_scopes == 1
        assert summary.average_partial_halstead_volume == 50.0

        # UNCLASSIFIED_SYNTAX scopes: 1
        assert summary.unclassified_syntax_scopes == 1


class TestProjectMetricsNonFiniteHandling:
    """Verifies that non-finite values (NaN, +inf, -inf) are excluded from project-level averages and denominators."""

    @pytest.fixture
    def aggregator(self):
        return ProjectMetricsAggregator()

    @pytest.fixture
    def correlation_analyzer(self):
        return CorrelationAnalyzer()

    def test_nan_full_volume_exclusion(self, aggregator, correlation_analyzer):
        """Scopes with NaN FULL volume are excluded from halstead_volume_evaluated_scopes and average_halstead_volume."""
        scopes = [
            make_unified_scope("f1@1", volume=10.0),
            make_unified_scope("f2@1", volume=float("nan")),
            make_unified_scope("f3@1", volume=20.0),
        ]
        corr = correlation_analyzer.analyze(scopes)
        summary = aggregator.aggregate(scopes, corr)

        # Evaluated counter counts only finite values
        assert summary.halstead_volume_evaluated_scopes == 2
        # Average divides by evaluated counter, excluding NaN
        assert summary.average_halstead_volume == 15.0
        assert math.isfinite(summary.average_halstead_volume)

    def test_infinite_full_effort_exclusion(self, aggregator, correlation_analyzer):
        """Scopes with +inf or -inf FULL effort are excluded from halstead_effort_evaluated_scopes and average_halstead_effort."""
        scopes = [
            make_unified_scope("f1@1", effort=100.0),
            make_unified_scope("f2@1", effort=float("inf")),
            make_unified_scope("f3@1", effort=float("-inf")),
            make_unified_scope("f4@1", effort=200.0),
        ]
        corr = correlation_analyzer.analyze(scopes)
        summary = aggregator.aggregate(scopes, corr)

        assert summary.halstead_effort_evaluated_scopes == 2
        assert summary.average_halstead_effort == 150.0
        assert math.isfinite(summary.average_halstead_effort)

    def test_nan_partial_volume_exclusion(self, aggregator, correlation_analyzer):
        """Scopes with NaN PARTIAL volume are excluded from partial_coverage_volume_scopes and diagnostic average."""
        scopes = [
            make_unified_scope("p1@1", syntax_coverage_status="PARTIAL", volume=50.0),
            make_unified_scope("p2@1", syntax_coverage_status="PARTIAL", volume=float("nan")),
            make_unified_scope("p3@1", syntax_coverage_status="PARTIAL", volume=70.0),
        ]
        corr = correlation_analyzer.analyze(scopes)
        summary = aggregator.aggregate(scopes, corr)

        assert summary.partial_coverage_volume_scopes == 2
        assert summary.average_partial_halstead_volume == 60.0
        assert math.isfinite(summary.average_partial_halstead_volume)

    def test_infinite_partial_effort_exclusion(self, aggregator, correlation_analyzer):
        """Scopes with infinite PARTIAL effort are excluded from partial_coverage_effort_scopes and diagnostic average."""
        scopes = [
            make_unified_scope("p1@1", syntax_coverage_status="PARTIAL", effort=500.0),
            make_unified_scope("p2@1", syntax_coverage_status="PARTIAL", effort=float("-inf")),
            make_unified_scope("p3@1", syntax_coverage_status="PARTIAL", effort=float("inf")),
        ]
        corr = correlation_analyzer.analyze(scopes)
        summary = aggregator.aggregate(scopes, corr)

        assert summary.partial_coverage_effort_scopes == 1
        assert summary.average_partial_halstead_effort == 500.0
        assert math.isfinite(summary.average_partial_halstead_effort)

    def test_counters_match_actual_numerical_averaging_denominators(self, aggregator, correlation_analyzer):
        """Verifies that all evaluated counters strictly equal the denominators used for numerical means."""
        scopes = [
            make_unified_scope("f1@1", cyclomatic_status="COMPLETE", cyclomatic_complexity=2, volume=10.0, effort=100.0),
            make_unified_scope("f2@1", cyclomatic_status="COMPLETE", cyclomatic_complexity=float("nan"), volume=float("nan"), effort=float("inf")),
            make_unified_scope("f3@1", cyclomatic_status="COMPLETE", cyclomatic_complexity=4, volume=30.0, effort=300.0),
            make_unified_scope("p1@1", cyclomatic_status="PARTIAL", syntax_coverage_status="PARTIAL", volume=25.0, effort=float("nan")),
            make_unified_scope("p2@1", cyclomatic_status="PARTIAL", syntax_coverage_status="PARTIAL", volume=float("inf"), effort=250.0),
        ]
        corr = correlation_analyzer.analyze(scopes)
        summary = aggregator.aggregate(scopes, corr)

        # Total scopes
        assert summary.total_scopes == 5
        assert summary.procedural_scopes == 5

        # Cyclomatic: f1 and f3 are COMPLETE and finite (f2 is NaN, p1/p2 are PARTIAL CFG) -> 2 evaluated
        assert summary.cyclomatic_evaluated_scopes == 2
        assert summary.average_cyclomatic_complexity == (2 + 4) / 2.0

        # FULL volume: f1 (10.0) and f3 (30.0) -> 2 evaluated
        assert summary.halstead_volume_evaluated_scopes == 2
        assert summary.average_halstead_volume == (10.0 + 30.0) / 2.0

        # FULL effort: f1 (100.0) and f3 (300.0) -> 2 evaluated
        assert summary.halstead_effort_evaluated_scopes == 2
        assert summary.average_halstead_effort == (100.0 + 300.0) / 2.0

        # PARTIAL volume: p1 (25.0) -> 1 evaluated
        assert summary.partial_coverage_volume_scopes == 1
        assert summary.average_partial_halstead_volume == 25.0

        # PARTIAL effort: p2 (250.0) -> 1 evaluated
        assert summary.partial_coverage_effort_scopes == 1
        assert summary.average_partial_halstead_effort == 250.0

    def test_available_finite_zero_values_remain_included_alongside_non_finite(self, aggregator, correlation_analyzer):
        """Available finite 0.0 values remain included in averages and are not filtered out by non-finite filtering."""
        scopes = [
            make_unified_scope("f1@1", volume=0.0, effort=0.0),
            make_unified_scope("f2@1", volume=float("nan"), effort=float("inf")),
            make_unified_scope("f3@1", volume=10.0, effort=20.0),
        ]
        corr = correlation_analyzer.analyze(scopes)
        summary = aggregator.aggregate(scopes, corr)

        assert summary.halstead_volume_evaluated_scopes == 2
        assert summary.average_halstead_volume == 5.0  # (0.0 + 10.0) / 2

        assert summary.halstead_effort_evaluated_scopes == 2
        assert summary.average_halstead_effort == 10.0  # (0.0 + 20.0) / 2
