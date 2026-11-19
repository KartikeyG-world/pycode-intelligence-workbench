"""
Project-Level Metrics Aggregator for Phase 1B.2.

Computes project-wide procedural complexity averages, diagnostic population counters,
and binds the correlation report, strictly conforming to Stage 0.7 specification.
"""

from typing import Sequence, Optional
import math
from app.schemas.metrics import (
    UnifiedScopeMetrics,
    ProjectCorrelationReport,
    ProjectMetricsSummary,
)


class ProjectMetricsAggregator:
    """
    Aggregates project-level metrics summary from an ordered collection of UnifiedScopeMetrics
    and its associated ProjectCorrelationReport, conforming strictly to Stage 0.7 specification.
    """

    def aggregate(
        self,
        scopes: Sequence[UnifiedScopeMetrics],
        correlation: ProjectCorrelationReport,
    ) -> ProjectMetricsSummary:
        """
        Aggregates scope metrics into project summary adhering to Stage 0.7 population rules.
        """
        total_scopes = len(scopes)
        procedural_scopes = sum(
            1 for s in scopes if s.scope_type in ("function", "method")
        )
        module_scopes = sum(1 for s in scopes if s.scope_type == "module")
        class_scopes = sum(1 for s in scopes if s.scope_type == "class_body")

        proc_scopes = [
            s for s in scopes if s.scope_type in ("function", "method")
        ]

        # Structural Procedural Averages (Denominator = procedural_scopes)
        avg_stmt: Optional[float] = None
        avg_ast_depth: Optional[float] = None
        avg_nesting: Optional[float] = None

        if procedural_scopes > 0:
            avg_stmt = sum(
                s.structural.statement_count for s in proc_scopes
            ) / float(procedural_scopes)
            avg_ast_depth = sum(
                s.structural.ast_depth for s in proc_scopes
            ) / float(procedural_scopes)
            avg_nesting = sum(
                s.structural.control_nesting_depth for s in proc_scopes
            ) / float(procedural_scopes)

        # Cyclomatic Average (Denominator = cyclomatic_evaluated_scopes, COMPLETE CFG status only)
        # Non-finite values (NaN/Inf) are excluded from numerical averages and denominators.
        cyclo_scopes = [
            s
            for s in proc_scopes
            if s.cyclomatic.cyclomatic_status == "COMPLETE"
            and s.cyclomatic.cyclomatic_complexity is not None
            and math.isfinite(s.cyclomatic.cyclomatic_complexity)
        ]
        cyclo_eval_count = len(cyclo_scopes)
        avg_cyclo: Optional[float] = None
        if cyclo_eval_count > 0:
            avg_cyclo = sum(
                s.cyclomatic.cyclomatic_complexity for s in cyclo_scopes
            ) / float(cyclo_eval_count)

        # Fully Classified Halstead Procedural Averages (Coverage == FULL)
        # Non-finite values (NaN/Inf) are excluded from numerical averages and denominators.
        vol_scopes = [
            s
            for s in proc_scopes
            if s.halstead.syntax_coverage_status == "FULL"
            and s.halstead.volume is not None
            and math.isfinite(s.halstead.volume)
        ]
        vol_eval_count = len(vol_scopes)
        avg_vol: Optional[float] = None
        if vol_eval_count > 0:
            avg_vol = sum(s.halstead.volume for s in vol_scopes) / float(
                vol_eval_count
            )

        eff_scopes = [
            s
            for s in proc_scopes
            if s.halstead.syntax_coverage_status == "FULL"
            and s.halstead.effort is not None
            and math.isfinite(s.halstead.effort)
        ]
        eff_eval_count = len(eff_scopes)
        avg_eff: Optional[float] = None
        if eff_eval_count > 0:
            avg_eff = sum(s.halstead.effort for s in eff_scopes) / float(
                eff_eval_count
            )

        # Partial-Coverage Diagnostic Populations (Coverage == PARTIAL)
        # Non-finite values (NaN/Inf) are excluded from diagnostic numerical averages and denominators.
        part_vol_scopes = [
            s
            for s in proc_scopes
            if s.halstead.syntax_coverage_status == "PARTIAL"
            and s.halstead.volume is not None
            and math.isfinite(s.halstead.volume)
        ]
        part_vol_count = len(part_vol_scopes)
        avg_part_vol: Optional[float] = None
        if part_vol_count > 0:
            avg_part_vol = sum(s.halstead.volume for s in part_vol_scopes) / float(
                part_vol_count
            )

        part_eff_scopes = [
            s
            for s in proc_scopes
            if s.halstead.syntax_coverage_status == "PARTIAL"
            and s.halstead.effort is not None
            and math.isfinite(s.halstead.effort)
        ]
        part_eff_count = len(part_eff_scopes)
        avg_part_eff: Optional[float] = None
        if part_eff_count > 0:
            avg_part_eff = sum(s.halstead.effort for s in part_eff_scopes) / float(
                part_eff_count
            )

        # Unclassified Syntax Diagnostic Population (Coverage == UNCLASSIFIED_SYNTAX)
        unclassified_count = sum(
            1
            for s in proc_scopes
            if s.halstead.syntax_coverage_status == "UNCLASSIFIED_SYNTAX"
        )

        return ProjectMetricsSummary(
            total_scopes=total_scopes,
            procedural_scopes=procedural_scopes,
            module_scopes=module_scopes,
            class_scopes=class_scopes,
            average_statement_count=avg_stmt,
            average_ast_depth=avg_ast_depth,
            average_control_nesting_depth=avg_nesting,
            average_cyclomatic_complexity=avg_cyclo,
            cyclomatic_evaluated_scopes=cyclo_eval_count,
            average_halstead_volume=avg_vol,
            average_halstead_effort=avg_eff,
            halstead_volume_evaluated_scopes=vol_eval_count,
            halstead_effort_evaluated_scopes=eff_eval_count,
            partial_coverage_volume_scopes=part_vol_count,
            average_partial_halstead_volume=avg_part_vol,
            partial_coverage_effort_scopes=part_eff_count,
            average_partial_halstead_effort=avg_part_eff,
            unclassified_syntax_scopes=unclassified_count,
            correlation=correlation,
        )
