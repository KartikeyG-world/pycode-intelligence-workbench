"""
Pydantic v2 data models for Phase 1B.2 AST structural metrics, Halstead complexity,
and cyclomatic correlation analysis.

Complies strictly with Stage 0.7 specification.
"""

from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field, model_validator

PublicScopeType = Literal["module", "function", "method", "class_body"]

CORRELATION_DISCLAIMER: str = (
    "Statistical correlation reflects descriptive co-variation across complete "
    "procedural scopes within this submission. It does not demonstrate causality "
    "or predict runtime performance."
)


class UnclassifiedSyntaxRecord(BaseModel):
    """Diagnostic record of an unclassified AST syntax element encountered during Halstead analysis."""
    node_class: str
    lineno: Optional[int] = None
    col_offset: Optional[int] = None
    reason: str


class ScopeStructuralMetrics(BaseModel):
    """AST structural metrics characterizing syntax tree properties and statement suite composition."""
    statement_count: int
    top_level_statement_count: int
    ast_node_count: int
    ast_depth: int
    control_nesting_depth: int
    if_statement_count: int
    if_expression_count: int
    conditional_count: int
    boolean_operator_count: int
    assertion_count: int
    loop_count: int
    comprehension_count: int
    parameter_count: Optional[int] = None
    return_count: Optional[int] = None
    diagnostics: List[str] = Field(default_factory=list)


class ScopeHalsteadMetrics(BaseModel):
    """Halstead complexity metrics, token inventories, and syntax coverage status for a single scope."""
    # Mathematical Halstead Metrics
    distinct_operators: int
    distinct_operands: int
    total_operators: int
    total_operands: int
    vocabulary: int
    length: int
    volume: Optional[float] = None
    difficulty: Optional[float] = None
    effort: Optional[float] = None
    theoretical_time_seconds: Optional[float] = None
    theoretical_delivered_bugs: Optional[float] = None

    # Mathematical Status
    volume_status: Literal["AVAILABLE", "UNDEFINED_EMPTY_VOCABULARY"]
    difficulty_status: Literal["AVAILABLE", "UNDEFINED_ZERO_OPERANDS"]
    effort_status: Literal["AVAILABLE", "UNDEFINED_DEPENDENCY"]
    undefined_reasons: List[str] = Field(default_factory=list)

    # Tripartite Syntax Coverage Status (Required, no default value)
    syntax_coverage_status: Literal["FULL", "PARTIAL", "UNCLASSIFIED_SYNTAX"]
    unclassified_syntax_nodes: List[UnclassifiedSyntaxRecord] = Field(default_factory=list)

    # Detailed Inventories
    operator_inventory: Dict[str, int] = Field(default_factory=dict)
    operand_inventory: Dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_syntax_coverage_invariants(self) -> "ScopeHalsteadMetrics":
        if self.syntax_coverage_status == "FULL":
            if len(self.unclassified_syntax_nodes) > 0:
                raise ValueError("syntax_coverage_status 'FULL' requires unclassified_syntax_nodes to be empty")
        elif self.syntax_coverage_status in ("PARTIAL", "UNCLASSIFIED_SYNTAX"):
            if len(self.unclassified_syntax_nodes) == 0:
                raise ValueError(
                    f"syntax_coverage_status '{self.syntax_coverage_status}' requires at least one unclassified syntax record"
                )
        return self


class ScopeCyclomaticMetrics(BaseModel):
    """Validated cyclomatic complexity metrics and control-flow structural attributes for a single scope."""
    cyclomatic_status: Literal["COMPLETE", "PARTIAL", "UNSUPPORTED"]
    cyclomatic_complexity: Optional[int] = None
    graph_cyclomatic: Optional[int] = None
    decision_cyclomatic: Optional[int] = None
    cyclomatic_discrepancy: Optional[int] = None
    risk_rank: Optional[Literal["A", "B", "C", "D", "E", "F"]] = None
    is_provisional: bool = False
    total_nodes: int
    total_edges: int
    reachable_nodes: int
    reachable_edges: int
    unreachable_basic_blocks: int
    decision_points: Dict[str, int] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)


class UnifiedScopeMetrics(BaseModel):
    """Authoritative unified metrics container binding cyclomatic, structural, and Halstead analysis for one scope."""
    scope_id: str
    name: str
    scope_type: Literal["module", "function", "method", "class_body"]
    lineno: Optional[int] = None
    end_lineno: Optional[int] = None
    cyclomatic: ScopeCyclomaticMetrics
    structural: ScopeStructuralMetrics
    halstead: ScopeHalsteadMetrics


class CorrelationDataPoint(BaseModel):
    """Single observation pair for correlation analysis between cyclomatic complexity and another metric."""
    scope_id: str
    cyclomatic_complexity: int
    metric_value: float


class CorrelationDimension(BaseModel):
    """Statistical correlation results for cyclomatic complexity against one target structural or Halstead metric."""
    dimension_name: str
    pearson_r: Optional[float] = None
    spearman_rho: Optional[float] = None
    sample_size: int
    status: Literal["DESCRIPTIVE_ONLY", "INSUFFICIENT_SAMPLE", "ZERO_VARIANCE"]
    diagnostic_message: Optional[str] = None
    pairs: List[CorrelationDataPoint] = Field(default_factory=list)


class ProjectCorrelationReport(BaseModel):
    """Aggregate correlation report evaluating co-variation between cyclomatic and other complexity dimensions."""
    eligible_scope_count: int
    dimensions: Dict[str, CorrelationDimension] = Field(default_factory=dict)
    disclaimer: str = Field(default=CORRELATION_DISCLAIMER)


class ProjectMetricsSummary(BaseModel):
    """Project-level aggregation summarizing scope counts, procedural averages, and diagnostic populations."""
    # Scope Breakdown
    total_scopes: int
    procedural_scopes: int
    module_scopes: int
    class_scopes: int

    # Structural Procedural Averages (Denominator = procedural_scopes)
    average_statement_count: Optional[float] = None
    average_ast_depth: Optional[float] = None
    average_control_nesting_depth: Optional[float] = None

    # Cyclomatic Procedural Average (Denominator = cyclomatic_evaluated_scopes)
    average_cyclomatic_complexity: Optional[float] = None
    cyclomatic_evaluated_scopes: int = 0

    # Fully Classified Halstead Procedural Averages (Coverage == FULL)
    average_halstead_volume: Optional[float] = None
    average_halstead_effort: Optional[float] = None
    halstead_volume_evaluated_scopes: int = 0
    halstead_effort_evaluated_scopes: int = 0

    # Partial-Coverage Diagnostic Populations (Coverage == PARTIAL)
    partial_coverage_volume_scopes: int = 0
    average_partial_halstead_volume: Optional[float] = None
    partial_coverage_effort_scopes: int = 0
    average_partial_halstead_effort: Optional[float] = None

    # Unclassified Syntax Diagnostic Population (Coverage == UNCLASSIFIED_SYNTAX)
    unclassified_syntax_scopes: int = 0

    # Correlation Analysis
    correlation: ProjectCorrelationReport


__all__ = [
    "PublicScopeType",
    "CORRELATION_DISCLAIMER",
    "UnclassifiedSyntaxRecord",
    "ScopeStructuralMetrics",
    "ScopeHalsteadMetrics",
    "ScopeCyclomaticMetrics",
    "UnifiedScopeMetrics",
    "CorrelationDataPoint",
    "CorrelationDimension",
    "ProjectCorrelationReport",
    "ProjectMetricsSummary",
]
