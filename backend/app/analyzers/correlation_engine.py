"""
Statistical Correlation Engine for Phase 1B.2.

Computes Pearson product-moment and Spearman rank correlation coefficients between
cyclomatic complexity and target structural and Halstead complexity dimensions.
Strictly implements the Stage 0.7 specification and Stage 1.0.2 architecture contract.
"""

from typing import Sequence, Dict, List, Optional, Tuple, Any
import math

from app.schemas.metrics import (
    UnifiedScopeMetrics,
    CorrelationDataPoint,
    CorrelationDimension,
    ProjectCorrelationReport,
    CORRELATION_DISCLAIMER,
)


def compute_ranks(values: Sequence[float]) -> List[float]:
    """
    Computes 1-based fractional (average) ranks for tied values in ascending order.
    Example: [1, 2, 2, 4] -> [1.0, 2.5, 2.5, 4.0]
    Raises ValueError if values contains non-finite numbers (NaN/Inf).
    """
    n = len(values)
    if n == 0:
        return []

    if any(not math.isfinite(v) for v in values):
        raise ValueError("Cannot rank non-finite values (NaN/Inf)")

    # Sort indices by value stably
    indexed = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        # Average rank for tied range from (i + 1) to (j + 1)
        avg_rank = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1
    return ranks


def compute_pearson_r(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    """
    Calculates Pearson product-moment correlation coefficient r.
    Returns None if sample size n < 3, if variance in either dimension is zero,
    or if any observation in x or y is non-finite (NaN or Inf).
    """
    n = len(x)
    if n != len(y) or n < 3:
        return None

    if any(not math.isfinite(xi) for xi in x) or any(not math.isfinite(yi) for yi in y):
        return None

    mx = sum(x) / float(n)
    my = sum(y) / float(n)

    var_x = sum((xi - mx) ** 2 for xi in x)
    var_y = sum((yi - my) ** 2 for yi in y)

    if var_x == 0.0 or var_y == 0.0:
        return None

    cov_xy = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    denom = math.sqrt(var_x * var_y)
    if denom == 0.0:
        return None

    r = cov_xy / denom
    # Clamp to [-1.0, 1.0] for floating point stability
    return max(-1.0, min(1.0, float(r)))


def compute_spearman_rho(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    """
    Calculates Spearman rank correlation coefficient rho using fractional ranks for ties.
    Returns None if sample size n < 3, if variance in either rank vector is zero,
    or if any observation in x or y is non-finite (NaN or Inf).
    """
    n = len(x)
    if n != len(y) or n < 3:
        return None

    if any(not math.isfinite(xi) for xi in x) or any(not math.isfinite(yi) for yi in y):
        return None

    rx = compute_ranks(x)
    ry = compute_ranks(y)

    return compute_pearson_r(rx, ry)


class CorrelationAnalyzer:
    """
    Computes statistical correlation reports across eligible complete procedural scopes.
    """

    DIMENSION_NAMES = [
        "cyclomatic_vs_statement_count",
        "cyclomatic_vs_ast_depth",
        "cyclomatic_vs_control_nesting_depth",
        "cyclomatic_vs_halstead_volume",
        "cyclomatic_vs_halstead_effort",
    ]

    def analyze(
        self, scopes: Sequence[UnifiedScopeMetrics]
    ) -> ProjectCorrelationReport:
        """
        Evaluates co-variation between cyclomatic complexity and each target metric dimension.
        """
        # Filter eligible procedural scopes: scope_type in ('function', 'method') and CFG status COMPLETE
        eligible_procedural_scopes = [
            s
            for s in scopes
            if s.scope_type in ("function", "method")
            and s.cyclomatic.cyclomatic_status == "COMPLETE"
        ]
        eligible_scope_count = len(eligible_procedural_scopes)

        dimensions: Dict[str, CorrelationDimension] = {}

        # 1. cyclomatic_vs_statement_count
        dimensions["cyclomatic_vs_statement_count"] = self._build_structural_dimension(
            dimension_name="cyclomatic_vs_statement_count",
            eligible_scopes=eligible_procedural_scopes,
            metric_extractor=lambda s: float(s.structural.statement_count),
        )

        # 2. cyclomatic_vs_ast_depth
        dimensions["cyclomatic_vs_ast_depth"] = self._build_structural_dimension(
            dimension_name="cyclomatic_vs_ast_depth",
            eligible_scopes=eligible_procedural_scopes,
            metric_extractor=lambda s: float(s.structural.ast_depth),
        )

        # 3. cyclomatic_vs_control_nesting_depth
        dimensions["cyclomatic_vs_control_nesting_depth"] = (
            self._build_structural_dimension(
                dimension_name="cyclomatic_vs_control_nesting_depth",
                eligible_scopes=eligible_procedural_scopes,
                metric_extractor=lambda s: float(s.structural.control_nesting_depth),
            )
        )

        # 4. cyclomatic_vs_halstead_volume (requires syntax_coverage_status == 'FULL' and volume not None)
        dimensions["cyclomatic_vs_halstead_volume"] = self._build_halstead_dimension(
            dimension_name="cyclomatic_vs_halstead_volume",
            eligible_scopes=eligible_procedural_scopes,
            metric_extractor=lambda s: s.halstead.volume,
        )

        # 5. cyclomatic_vs_halstead_effort (requires syntax_coverage_status == 'FULL' and effort not None)
        dimensions["cyclomatic_vs_halstead_effort"] = self._build_halstead_dimension(
            dimension_name="cyclomatic_vs_halstead_effort",
            eligible_scopes=eligible_procedural_scopes,
            metric_extractor=lambda s: s.halstead.effort,
        )

        return ProjectCorrelationReport(
            eligible_scope_count=eligible_scope_count,
            dimensions=dimensions,
            disclaimer=CORRELATION_DISCLAIMER,
        )

    def _build_structural_dimension(
        self,
        dimension_name: str,
        eligible_scopes: Sequence[UnifiedScopeMetrics],
        metric_extractor: Any,
    ) -> CorrelationDimension:
        pairs: List[CorrelationDataPoint] = []
        for s in eligible_scopes:
            if s.cyclomatic.cyclomatic_complexity is not None:
                val = metric_extractor(s)
                if val is not None and math.isfinite(val) and math.isfinite(s.cyclomatic.cyclomatic_complexity):
                    pairs.append(
                        CorrelationDataPoint(
                            scope_id=s.scope_id,
                            cyclomatic_complexity=s.cyclomatic.cyclomatic_complexity,
                            metric_value=float(val),
                        )
                    )
        return self._compute_dimension_statistics(dimension_name, pairs)

    def _build_halstead_dimension(
        self,
        dimension_name: str,
        eligible_scopes: Sequence[UnifiedScopeMetrics],
        metric_extractor: Any,
    ) -> CorrelationDimension:
        pairs: List[CorrelationDataPoint] = []
        for s in eligible_scopes:
            if (
                s.cyclomatic.cyclomatic_complexity is not None
                and s.halstead.syntax_coverage_status == "FULL"
            ):
                val = metric_extractor(s)
                if val is not None and math.isfinite(val) and math.isfinite(s.cyclomatic.cyclomatic_complexity):
                    pairs.append(
                        CorrelationDataPoint(
                            scope_id=s.scope_id,
                            cyclomatic_complexity=s.cyclomatic.cyclomatic_complexity,
                            metric_value=float(val),
                        )
                    )
        return self._compute_dimension_statistics(dimension_name, pairs)

    def _compute_dimension_statistics(
        self, dimension_name: str, pairs: List[CorrelationDataPoint]
    ) -> CorrelationDimension:
        n = len(pairs)
        if n < 3:
            return CorrelationDimension(
                dimension_name=dimension_name,
                pearson_r=None,
                spearman_rho=None,
                sample_size=n,
                status="INSUFFICIENT_SAMPLE",
                diagnostic_message=f"Insufficient sample size (n={n} < 3) for correlation analysis",
                pairs=pairs,
            )

        x = [float(p.cyclomatic_complexity) for p in pairs]
        y = [float(p.metric_value) for p in pairs]

        mx = sum(x) / float(n)
        my = sum(y) / float(n)
        var_x = sum((xi - mx) ** 2 for xi in x)
        var_y = sum((yi - my) ** 2 for yi in y)

        if var_x == 0.0 or var_y == 0.0:
            return CorrelationDimension(
                dimension_name=dimension_name,
                pearson_r=None,
                spearman_rho=None,
                sample_size=n,
                status="ZERO_VARIANCE",
                diagnostic_message="Zero variance in one or both dimensions; correlation is undefined",
                pairs=pairs,
            )

        r = compute_pearson_r(x, y)
        rho = compute_spearman_rho(x, y)

        return CorrelationDimension(
            dimension_name=dimension_name,
            pearson_r=r,
            spearman_rho=rho,
            sample_size=n,
            status="DESCRIPTIVE_ONLY",
            diagnostic_message=None,
            pairs=pairs,
        )
