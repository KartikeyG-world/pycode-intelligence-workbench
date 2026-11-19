"""
Focused tests for Phase 1B.2 Unit 1 Pydantic Schemas & Data Contracts.
Validates structural, Halstead, cyclomatic, unified scope, correlation, and project summary schemas,
as well as additive backward compatibility with AnalyzeResponse.
"""

import pytest
from pydantic import ValidationError

from app.schemas.metrics import (
    UnclassifiedSyntaxRecord,
    ScopeStructuralMetrics,
    ScopeHalsteadMetrics,
    ScopeCyclomaticMetrics,
    UnifiedScopeMetrics,
    CorrelationDataPoint,
    CorrelationDimension,
    ProjectCorrelationReport,
    ProjectMetricsSummary,
    CORRELATION_DISCLAIMER,
)
from app.schemas.analysis import (
    AnalyzeResponse,
    CodeStatistics,
    CodeStructureData,
    TheoreticalGraphData,
    SpaceBreakdown,
    RecurrenceInfo,
)


# ============================================================================
# Helpers & Fixtures
# ============================================================================

def make_sample_structural_metrics(**kwargs) -> ScopeStructuralMetrics:
    defaults = {
        "statement_count": 3,
        "top_level_statement_count": 1,
        "ast_node_count": 17,
        "ast_depth": 6,
        "control_nesting_depth": 1,
        "if_statement_count": 0,
        "if_expression_count": 0,
        "conditional_count": 0,
        "boolean_operator_count": 0,
        "assertion_count": 0,
        "loop_count": 0,
        "comprehension_count": 0,
        "parameter_count": 1,
        "return_count": 2,
        "diagnostics": [],
    }
    defaults.update(kwargs)
    return ScopeStructuralMetrics(**defaults)


def make_sample_halstead_metrics(**kwargs) -> ScopeHalsteadMetrics:
    defaults = {
        "distinct_operators": 4,
        "distinct_operands": 4,
        "total_operators": 6,
        "total_operands": 6,
        "vocabulary": 8,
        "length": 12,
        "volume": 36.0,
        "difficulty": 3.0,
        "effort": 108.0,
        "theoretical_time_seconds": 6.0,
        "theoretical_delivered_bugs": 0.012,
        "volume_status": "AVAILABLE",
        "difficulty_status": "AVAILABLE",
        "effort_status": "AVAILABLE",
        "undefined_reasons": [],
        "syntax_coverage_status": "FULL",
        "unclassified_syntax_nodes": [],
        "operator_inventory": {"op:match": 1, "op:case": 2, "op:match_or": 1, "op:return": 2},
        "operand_inventory": {"id:value": 2, "lit:int:1": 2, "lit:int:2": 1, "lit:int:0": 1},
    }
    defaults.update(kwargs)
    return ScopeHalsteadMetrics(**defaults)


def make_sample_cyclomatic_metrics(**kwargs) -> ScopeCyclomaticMetrics:
    defaults = {
        "cyclomatic_status": "COMPLETE",
        "cyclomatic_complexity": 3,
        "graph_cyclomatic": 3,
        "decision_cyclomatic": 3,
        "cyclomatic_discrepancy": 0,
        "risk_rank": "A",
        "is_provisional": False,
        "total_nodes": 6,
        "total_edges": 7,
        "reachable_nodes": 6,
        "reachable_edges": 7,
        "unreachable_basic_blocks": 0,
        "decision_points": {"match_case": 2},
        "limitations": [],
    }
    defaults.update(kwargs)
    return ScopeCyclomaticMetrics(**defaults)


def make_sample_unified_scope(**kwargs) -> UnifiedScopeMetrics:
    defaults = {
        "scope_id": "match_value@1",
        "name": "match_value",
        "scope_type": "function",
        "lineno": 1,
        "end_lineno": 8,
        "cyclomatic": make_sample_cyclomatic_metrics(),
        "structural": make_sample_structural_metrics(),
        "halstead": make_sample_halstead_metrics(),
    }
    defaults.update(kwargs)
    return UnifiedScopeMetrics(**defaults)


# ============================================================================
# Section A: Halstead Coverage Validation
# ============================================================================

def test_halstead_coverage_valid_full():
    """1. Valid FULL with empty inventory succeeds."""
    m = make_sample_halstead_metrics(
        syntax_coverage_status="FULL",
        unclassified_syntax_nodes=[],
    )
    assert m.syntax_coverage_status == "FULL"
    assert len(m.unclassified_syntax_nodes) == 0


def test_halstead_coverage_invalid_full():
    """2. Invalid FULL with non-empty inventory raises ValidationError."""
    record = UnclassifiedSyntaxRecord(node_class="CustomPattern", reason="Unsupported pattern extension")
    with pytest.raises(ValidationError) as exc_info:
        make_sample_halstead_metrics(
            syntax_coverage_status="FULL",
            unclassified_syntax_nodes=[record],
        )
    assert "syntax_coverage_status 'FULL' requires unclassified_syntax_nodes to be empty" in str(exc_info.value)


def test_halstead_coverage_valid_partial():
    """3. Valid PARTIAL with one or more records succeeds."""
    record = UnclassifiedSyntaxRecord(node_class="CustomPattern", lineno=5, col_offset=10, reason="Custom syntax node")
    m = make_sample_halstead_metrics(
        syntax_coverage_status="PARTIAL",
        unclassified_syntax_nodes=[record],
    )
    assert m.syntax_coverage_status == "PARTIAL"
    assert len(m.unclassified_syntax_nodes) == 1
    assert m.unclassified_syntax_nodes[0].node_class == "CustomPattern"


def test_halstead_coverage_invalid_partial():
    """4. Invalid PARTIAL with empty inventory raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        make_sample_halstead_metrics(
            syntax_coverage_status="PARTIAL",
            unclassified_syntax_nodes=[],
        )
    assert "syntax_coverage_status 'PARTIAL' requires at least one unclassified syntax record" in str(exc_info.value)


def test_halstead_coverage_valid_unclassified():
    """5. Valid UNCLASSIFIED_SYNTAX with records succeeds."""
    record = UnclassifiedSyntaxRecord(node_class="UnknownGrammar", lineno=1, reason="Grammar construct unhandled")
    m = make_sample_halstead_metrics(
        syntax_coverage_status="UNCLASSIFIED_SYNTAX",
        unclassified_syntax_nodes=[record],
    )
    assert m.syntax_coverage_status == "UNCLASSIFIED_SYNTAX"
    assert len(m.unclassified_syntax_nodes) == 1


def test_halstead_coverage_invalid_unclassified():
    """6. Invalid UNCLASSIFIED_SYNTAX with empty inventory raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        make_sample_halstead_metrics(
            syntax_coverage_status="UNCLASSIFIED_SYNTAX",
            unclassified_syntax_nodes=[],
        )
    assert "syntax_coverage_status 'UNCLASSIFIED_SYNTAX' requires at least one unclassified syntax record" in str(exc_info.value)


def test_halstead_coverage_missing_status():
    """7. Missing syntax_coverage_status is rejected."""
    fields = make_sample_halstead_metrics().model_dump()
    del fields["syntax_coverage_status"]
    with pytest.raises(ValidationError) as exc_info:
        ScopeHalsteadMetrics(**fields)
    assert "syntax_coverage_status" in str(exc_info.value)


# ============================================================================
# Section B: Mathematical Status & Optional Values
# ============================================================================

def test_empty_vocabulary_unavailable_volume():
    """1. Empty vocabulary can represent unavailable volume."""
    m = make_sample_halstead_metrics(
        distinct_operators=0,
        distinct_operands=0,
        total_operators=0,
        total_operands=0,
        vocabulary=0,
        length=0,
        volume=None,
        volume_status="UNDEFINED_EMPTY_VOCABULARY",
        undefined_reasons=["Empty scope contains no operators or operands"],
    )
    assert m.volume is None
    assert m.volume_status == "UNDEFINED_EMPTY_VOCABULARY"
    assert len(m.undefined_reasons) == 1


def test_zero_operands_unavailable_difficulty():
    """2. Zero operands can represent unavailable difficulty."""
    m = make_sample_halstead_metrics(
        distinct_operators=1,
        distinct_operands=0,
        total_operators=1,
        total_operands=0,
        vocabulary=1,
        length=1,
        volume=0.0,
        difficulty=None,
        difficulty_status="UNDEFINED_ZERO_OPERANDS",
        effort=None,
        effort_status="UNDEFINED_DEPENDENCY",
        undefined_reasons=["Difficulty undefined when distinct operands is zero"],
    )
    assert m.difficulty is None
    assert m.difficulty_status == "UNDEFINED_ZERO_OPERANDS"
    assert m.effort is None
    assert m.effort_status == "UNDEFINED_DEPENDENCY"


def test_undefined_effort_without_fabricated_number():
    """3. Undefined effort can be represented without fabricating a numeric value."""
    m = make_sample_halstead_metrics(
        effort=None,
        effort_status="UNDEFINED_DEPENDENCY",
        undefined_reasons=["Cannot compute effort when difficulty is undefined"],
    )
    assert m.effort is None
    assert m.effort_status == "UNDEFINED_DEPENDENCY"


def test_valid_zero_volume_representable():
    """4. Valid zero-volume results remain representable."""
    m = make_sample_halstead_metrics(
        distinct_operators=1,
        distinct_operands=0,
        total_operators=1,
        total_operands=0,
        vocabulary=1,
        length=1,
        volume=0.0,
        volume_status="AVAILABLE",
    )
    assert m.volume == 0.0
    assert m.volume_status == "AVAILABLE"


def test_no_validation_manufactures_numeric_zero():
    """5. No validation rule should manufacture numeric zero for undefined metrics."""
    m = make_sample_halstead_metrics(
        volume=None,
        difficulty=None,
        effort=None,
        theoretical_time_seconds=None,
        theoretical_delivered_bugs=None,
        volume_status="UNDEFINED_EMPTY_VOCABULARY",
        difficulty_status="UNDEFINED_ZERO_OPERANDS",
        effort_status="UNDEFINED_DEPENDENCY",
    )
    assert m.volume is None
    assert m.difficulty is None
    assert m.effort is None
    assert m.theoretical_time_seconds is None
    assert m.theoretical_delivered_bugs is None


# ============================================================================
# Section C: Cyclomatic Schema
# ============================================================================

def test_cyclomatic_statuses_accepted():
    """1. All three cyclomatic statuses are accepted."""
    for st in ("COMPLETE", "PARTIAL", "UNSUPPORTED"):
        m = make_sample_cyclomatic_metrics(cyclomatic_status=st)
        assert m.cyclomatic_status == st


def test_cyclomatic_risk_ranks_accepted():
    """2. All risk ranks A–F are accepted, plus None."""
    for rank in ("A", "B", "C", "D", "E", "F", None):
        m = make_sample_cyclomatic_metrics(risk_rank=rank)
        assert m.risk_rank == rank


def test_cyclomatic_optional_values_representable():
    """3. Missing optional metric values are representable."""
    m = make_sample_cyclomatic_metrics(
        cyclomatic_status="UNSUPPORTED",
        cyclomatic_complexity=None,
        graph_cyclomatic=None,
        decision_cyclomatic=None,
        cyclomatic_discrepancy=None,
        risk_rank=None,
        is_provisional=True,
        limitations=["Async generator control flow unsupported"],
    )
    assert m.cyclomatic_complexity is None
    assert m.graph_cyclomatic is None
    assert m.is_provisional is True
    assert len(m.limitations) == 1


def test_cyclomatic_unreachable_basic_blocks():
    """4. The schema exposes unreachable_basic_blocks."""
    m = make_sample_cyclomatic_metrics(unreachable_basic_blocks=2)
    assert m.unreachable_basic_blocks == 2
    assert "unreachable_basic_blocks" in ScopeCyclomaticMetrics.model_fields


def test_cyclomatic_no_scope_id():
    """5. scope_id is not added to the nested cyclomatic model."""
    assert "scope_id" not in ScopeCyclomaticMetrics.model_fields


# ============================================================================
# Section D: Unified Scope Schema
# ============================================================================

def test_unified_scope_valid_types():
    """1. All four public scope types are accepted."""
    for st in ("module", "function", "method", "class_body"):
        s = make_sample_unified_scope(scope_type=st)
        assert s.scope_type == st


def test_unified_scope_invalid_types_rejected():
    """2. Invalid scope types are rejected."""
    for invalid in ("async_function", "async_method", "block", "global", "lambda"):
        with pytest.raises(ValidationError):
            make_sample_unified_scope(scope_type=invalid)


def test_unified_scope_required_fields():
    """3. Required scope identifiers and nested metric models are validated."""
    with pytest.raises(ValidationError):
        UnifiedScopeMetrics(
            scope_id="f@1",
            name="f",
            scope_type="function",
            # missing cyclomatic, structural, halstead
        )


def test_unified_scope_runs_halstead_coverage_validator():
    """4. Halstead coverage validation runs when constructing a unified scope."""
    record = UnclassifiedSyntaxRecord(node_class="CustomPattern", reason="Custom")
    with pytest.raises(ValidationError) as exc_info:
        make_sample_unified_scope(
            halstead={
                **make_sample_halstead_metrics().model_dump(),
                "syntax_coverage_status": "FULL",
                "unclassified_syntax_nodes": [record.model_dump()],
            }
        )
    assert "syntax_coverage_status 'FULL' requires unclassified_syntax_nodes to be empty" in str(exc_info.value)


# ============================================================================
# Section E: Correlation Schemas
# ============================================================================

def test_correlation_statuses_accepted():
    """1. All three correlation statuses are accepted."""
    for st in ("DESCRIPTIVE_ONLY", "INSUFFICIENT_SAMPLE", "ZERO_VARIANCE"):
        cd = CorrelationDimension(
            dimension_name="ast_node_count",
            sample_size=4,
            status=st,
        )
        assert cd.status == st


def test_correlation_optional_coefficients():
    """2. Optional Pearson/Spearman values are representable."""
    cd_none = CorrelationDimension(
        dimension_name="ast_depth",
        pearson_r=None,
        spearman_rho=None,
        sample_size=2,
        status="INSUFFICIENT_SAMPLE",
        diagnostic_message="Sample size n < 3 insufficient for descriptive correlation.",
    )
    assert cd_none.pearson_r is None
    assert cd_none.spearman_rho is None

    cd_val = CorrelationDimension(
        dimension_name="ast_depth",
        pearson_r=0.9511897,
        spearman_rho=0.9486833,
        sample_size=4,
        status="DESCRIPTIVE_ONLY",
    )
    assert cd_val.pearson_r == 0.9511897
    assert cd_val.spearman_rho == 0.9486833


def test_correlation_datapoints():
    """3. Matched pairs are represented through CorrelationDataPoint."""
    p1 = CorrelationDataPoint(scope_id="f1@1", cyclomatic_complexity=2, metric_value=10.0)
    p2 = CorrelationDataPoint(scope_id="f2@10", cyclomatic_complexity=4, metric_value=25.0)
    cd = CorrelationDimension(
        dimension_name="halstead_volume",
        sample_size=2,
        status="INSUFFICIENT_SAMPLE",
        pairs=[p1, p2],
    )
    assert len(cd.pairs) == 2
    assert cd.pairs[0].scope_id == "f1@1"
    assert cd.pairs[1].metric_value == 25.0


def test_project_correlation_disclaimer_default():
    """4. Project disclaimer has the approved default."""
    report = ProjectCorrelationReport(eligible_scope_count=3)
    assert report.disclaimer == CORRELATION_DISCLAIMER
    assert "Statistical correlation reflects descriptive co-variation" in report.disclaimer
    assert "It does not demonstrate causality or predict runtime performance." in report.disclaimer


# ============================================================================
# Section F: Project Summary
# ============================================================================

def test_project_metrics_summary_fields():
    """1. Approved field names are present."""
    summary = ProjectMetricsSummary(
        total_scopes=3,
        procedural_scopes=2,
        module_scopes=1,
        class_scopes=0,
        correlation=ProjectCorrelationReport(eligible_scope_count=2),
    )
    assert summary.total_scopes == 3
    assert summary.procedural_scopes == 2
    assert summary.module_scopes == 1
    assert summary.class_scopes == 0


def test_project_metrics_summary_defaults():
    """2. Default counters are zero."""
    summary = ProjectMetricsSummary(
        total_scopes=1,
        procedural_scopes=0,
        module_scopes=1,
        class_scopes=0,
        correlation=ProjectCorrelationReport(eligible_scope_count=0),
    )
    assert summary.cyclomatic_evaluated_scopes == 0
    assert summary.halstead_volume_evaluated_scopes == 0
    assert summary.halstead_effort_evaluated_scopes == 0
    assert summary.partial_coverage_volume_scopes == 0
    assert summary.partial_coverage_effort_scopes == 0
    assert summary.unclassified_syntax_scopes == 0


def test_project_metrics_summary_optional_averages():
    """3. Optional average values can be None."""
    summary = ProjectMetricsSummary(
        total_scopes=0,
        procedural_scopes=0,
        module_scopes=0,
        class_scopes=0,
        average_statement_count=None,
        average_ast_depth=None,
        average_control_nesting_depth=None,
        average_cyclomatic_complexity=None,
        average_halstead_volume=None,
        average_halstead_effort=None,
        average_partial_halstead_volume=None,
        average_partial_halstead_effort=None,
        correlation=ProjectCorrelationReport(eligible_scope_count=0),
    )
    assert summary.average_statement_count is None
    assert summary.average_cyclomatic_complexity is None
    assert summary.average_halstead_volume is None


def test_project_metrics_summary_no_unauthorized_fields():
    """4. No unauthorized project aggregate fields are introduced."""
    fields = set(ProjectMetricsSummary.model_fields.keys())
    unauthorized = {
        "M_all",
        "M_proc",
        "total_halstead_vocabulary",
        "total_halstead_length",
        "weighted_halstead_volume",
        "weighted_halstead_effort",
    }
    assert unauthorized.isdisjoint(fields)


# ============================================================================
# Section G: AnalyzeResponse Compatibility
# ============================================================================

def make_sample_analyze_response(**kwargs) -> AnalyzeResponse:
    defaults = {
        "success": True,
        "time_complexity": "O(n)",
        "space_complexity": "O(1)",
        "space_breakdown": SpaceBreakdown(),
        "confidence": "HIGH",
        "confidence_reasons": ["Single linear scan"],
        "complexity_reasoning": "Traverses input array once.",
        "recurrence": RecurrenceInfo(),
        "statistics": CodeStatistics(),
        "detected_patterns": ["Linear traversal"],
        "optimization_suggestions": [],
        "structure": CodeStructureData(),
        "graph": TheoreticalGraphData(active_complexity="O(n)"),
        "analysis_status": "COMPLETE",
        "analysis_schema_version": "1.0",
    }
    defaults.update(kwargs)
    return AnalyzeResponse(**defaults)


def test_analyze_response_backward_compatibility_construction():
    """1. Constructing an old-style response without the new fields still succeeds."""
    resp = make_sample_analyze_response()
    assert resp.success is True
    assert resp.time_complexity == "O(n)"


def test_analyze_response_default_scope_metrics():
    """2. scope_metrics defaults to an empty list."""
    resp = make_sample_analyze_response()
    assert resp.scope_metrics == []
    assert isinstance(resp.scope_metrics, list)


def test_analyze_response_default_project_metrics():
    """3. project_metrics defaults to None."""
    resp = make_sample_analyze_response()
    assert resp.project_metrics is None


def test_analyze_response_populated_serialization():
    """4. A response with populated new metrics serializes correctly."""
    scope = make_sample_unified_scope()
    summary = ProjectMetricsSummary(
        total_scopes=1,
        procedural_scopes=1,
        module_scopes=0,
        class_scopes=0,
        average_statement_count=3.0,
        average_cyclomatic_complexity=3.0,
        cyclomatic_evaluated_scopes=1,
        average_halstead_volume=36.0,
        halstead_volume_evaluated_scopes=1,
        correlation=ProjectCorrelationReport(
            eligible_scope_count=1,
            dimensions={
                "ast_node_count": CorrelationDimension(
                    dimension_name="ast_node_count",
                    sample_size=1,
                    status="INSUFFICIENT_SAMPLE",
                )
            },
        ),
    )
    resp = make_sample_analyze_response(
        scope_metrics=[scope],
        project_metrics=summary,
    )

    dump = resp.model_dump()
    assert len(dump["scope_metrics"]) == 1
    assert dump["scope_metrics"][0]["scope_id"] == "match_value@1"
    assert dump["project_metrics"]["total_scopes"] == 1
    assert dump["project_metrics"]["average_cyclomatic_complexity"] == 3.0

    # JSON roundtrip
    json_str = resp.model_dump_json()
    reconstructed = AnalyzeResponse.model_validate_json(json_str)
    assert len(reconstructed.scope_metrics) == 1
    assert reconstructed.scope_metrics[0].scope_id == "match_value@1"
    assert reconstructed.project_metrics.average_halstead_volume == 36.0


def test_analyze_response_existing_validators_functional():
    """5. Existing fields and validators remain functional."""
    # Test validator converts missing schema/status to LEGACY_RECORD
    legacy_payload = {
        "success": True,
        "time_complexity": "O(1)",
        "space_complexity": "O(1)",
        "confidence": "HIGH",
        "complexity_reasoning": "Constant time",
        "statistics": CodeStatistics().model_dump(),
        "structure": CodeStructureData().model_dump(),
        "graph": TheoreticalGraphData(active_complexity="O(1)").model_dump(),
    }
    resp = AnalyzeResponse.model_validate(legacy_payload)
    assert resp.analysis_status == "LEGACY_RECORD"
    assert resp.analysis_complete is None
    assert resp.scope_metrics == []
    assert resp.project_metrics is None
