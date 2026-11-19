"""
Unified Metrics Pipeline for Phase 1B.2.

Coordinates canonical scope discovery, structural AST analysis, AST-normalized Halstead
complexity analysis, control-flow graph (CFG) cyclomatic analysis, statistical correlation,
and project-level metrics aggregation into an authoritative per-scope and project-level inventory.
Strictly implements the Stage 0.7 specification and Stage 1.0.2 architecture contract.
"""

import ast
from typing import List, Dict, Optional, Tuple, Any

from app.analyzers.scope_discovery import discover_scopes, ScopeDefinition
from app.analyzers.structural_analyzer import StructuralMetricsAnalyzer
from app.analyzers.halstead_analyzer import HalsteadAnalyzer
from app.analyzers.cfg_builder import CFGBuilder, ControlFlowGraph
from app.analyzers.correlation_engine import CorrelationAnalyzer
from app.analyzers.project_summary import ProjectMetricsAggregator
from app.schemas.metrics import (
    ScopeCyclomaticMetrics,
    ScopeStructuralMetrics,
    ScopeHalsteadMetrics,
    UnifiedScopeMetrics,
    ProjectCorrelationReport,
    ProjectMetricsSummary,
)


def map_cfg_to_cyclomatic_metrics(
    cfg: Optional[ControlFlowGraph], scope_id: str
) -> ScopeCyclomaticMetrics:
    """
    Maps an authoritative ControlFlowGraph instance into a validated ScopeCyclomaticMetrics schema.
    Preserves all Stage 0.7 cyclomatic fields without adding scope_id to the cyclomatic sub-model.
    If the CFG result is missing for an expected scope, constructs a documented UNSUPPORTED result
    without fabricating COMPLETE status or zero scores.
    """
    if cfg is None:
        return ScopeCyclomaticMetrics(
            cyclomatic_status="UNSUPPORTED",
            cyclomatic_complexity=None,
            graph_cyclomatic=None,
            decision_cyclomatic=None,
            cyclomatic_discrepancy=None,
            risk_rank=None,
            is_provisional=False,
            total_nodes=0,
            total_edges=0,
            reachable_nodes=0,
            reachable_edges=0,
            unreachable_basic_blocks=0,
            decision_points={},
            limitations=[f"No control flow graph generated for scope '{scope_id}'"],
        )

    return ScopeCyclomaticMetrics(
        cyclomatic_status=cfg.cyclomatic_status,
        cyclomatic_complexity=cfg.cyclomatic_complexity,
        graph_cyclomatic=cfg.graph_cyclomatic,
        decision_cyclomatic=cfg.decision_cyclomatic,
        cyclomatic_discrepancy=cfg.cyclomatic_discrepancy,
        risk_rank=cfg.risk_rank,
        is_provisional=cfg.is_provisional,
        total_nodes=cfg.total_nodes,
        total_edges=cfg.total_edges,
        reachable_nodes=cfg.reachable_nodes,
        reachable_edges=cfg.reachable_edges,
        unreachable_basic_blocks=cfg.unreachable_basic_blocks,
        decision_points=dict(cfg.decision_points),
        limitations=list(cfg.limitations),
    )


class UnifiedMetricsPipeline:
    """
    Authoritative coordinator for Phase 1B.2 metrics generation.
    Orchestrates scope discovery, structural, Halstead, CFG cyclomatic analysis,
    correlation analysis, and project summary aggregation.
    """

    def __init__(
        self,
        structural_analyzer: Optional[StructuralMetricsAnalyzer] = None,
        halstead_analyzer: Optional[HalsteadAnalyzer] = None,
        correlation_analyzer: Optional[CorrelationAnalyzer] = None,
        project_aggregator: Optional[ProjectMetricsAggregator] = None,
    ):
        self.structural_analyzer = structural_analyzer or StructuralMetricsAnalyzer()
        self.halstead_analyzer = halstead_analyzer or HalsteadAnalyzer()
        self.correlation_analyzer = correlation_analyzer or CorrelationAnalyzer()
        self.project_aggregator = project_aggregator or ProjectMetricsAggregator()

    def run(
        self, tree: ast.AST
    ) -> Tuple[List[UnifiedScopeMetrics], ProjectMetricsSummary]:
        """
        Executes the full Phase 1B.2 static metrics pipeline on the provided AST.
        Returns a tuple of (unified_scope_metrics, project_metrics_summary).
        """
        # 1. Discover canonical scopes exactly once from original AST
        scopes: List[ScopeDefinition] = discover_scopes(tree)

        # 2. Execute per-scope analyzers over the discovered scope inventory
        structural_metrics: Dict[str, ScopeStructuralMetrics] = (
            self.structural_analyzer.analyze_all(scopes)
        )
        halstead_metrics: Dict[str, ScopeHalsteadMetrics] = (
            self.halstead_analyzer.analyze_all(scopes)
        )
        cfg_map: Dict[str, ControlFlowGraph] = CFGBuilder.build_all(tree)

        # 3. Construct UnifiedScopeMetrics for each canonical scope in source order
        unified_scopes: List[UnifiedScopeMetrics] = []
        for scope in scopes:
            scope_id = scope.scope_id

            if scope_id not in structural_metrics:
                raise RuntimeError(
                    f"Structural metrics analyzer failed to produce metrics for scope '{scope_id}'"
                )
            if scope_id not in halstead_metrics:
                raise RuntimeError(
                    f"Halstead analyzer failed to produce metrics for scope '{scope_id}'"
                )

            cfg = cfg_map.get(scope_id)
            cyclomatic_metric = map_cfg_to_cyclomatic_metrics(cfg, scope_id)

            unified_record = UnifiedScopeMetrics(
                scope_id=scope_id,
                name=scope.name,
                scope_type=scope.scope_type,
                lineno=scope.lineno,
                end_lineno=scope.end_lineno,
                cyclomatic=cyclomatic_metric,
                structural=structural_metrics[scope_id],
                halstead=halstead_metrics[scope_id],
            )
            unified_scopes.append(unified_record)

        # 4. Compute correlation across eligible complete procedural scopes
        correlation_report: ProjectCorrelationReport = (
            self.correlation_analyzer.analyze(unified_scopes)
        )

        # 5. Compute project-level summary aggregation
        project_summary: ProjectMetricsSummary = (
            self.project_aggregator.aggregate(unified_scopes, correlation_report)
        )

        return unified_scopes, project_summary
