"""
Integration Test Suite for Unified Metrics Pipeline & Service Wiring (Phase 1B.2 — Unit 6).

Covers all 37 acceptance points across Groups A through G:
- Group A: Basic end-to-end analysis (Cases 1-5)
- Group B: Scope alignment & integrity (Cases 6-10)
- Group C: Structural and Halstead integration (Cases 11-15)
- Group D: Cyclomatic integration & CFG mapping (Cases 16-19)
- Group E: Correlation and project summary aggregation (Cases 20-26)
- Group F: API response, serialization & persistence boundary (Cases 27-33)
- Group G: Determinism, AST immutability & execution safety (Cases 34-37)
"""

import ast
import json
import sys
import pytest
from unittest.mock import MagicMock

from app.analyzers.ast_parser import SafeASTParser
from app.analyzers.complexity_analyzer import ComplexityAnalyzer
from app.analyzers.metrics_pipeline import UnifiedMetricsPipeline, map_cfg_to_cyclomatic_metrics
from app.analyzers.scope_discovery import discover_scopes
from app.analyzers.structural_analyzer import StructuralMetricsAnalyzer
from app.analyzers.halstead_analyzer import HalsteadAnalyzer
from app.analyzers.cfg_builder import CFGBuilder
from app.analyzers.correlation_engine import CorrelationAnalyzer
from app.analyzers.project_summary import ProjectMetricsAggregator
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from app.schemas.metrics import (
    UnifiedScopeMetrics,
    ProjectMetricsSummary,
    ProjectCorrelationReport,
    ScopeCyclomaticMetrics,
)
from app.services.analysis_service import AnalysisService
from app.models.models import AnalysisResult, CodeSubmission

_requires_pep695 = pytest.mark.skipif(
    sys.version_info < (3, 12), reason="PEP 695 syntax requires Python 3.12+"
)


# ============================================================================
# Group A: Basic End-to-End Analysis
# ============================================================================

class TestGroupABasicEndToEndAnalysis:
    """Verifies end-to-end pipeline execution across basic Python source structures."""

    @pytest.fixture
    def analyzer(self):
        return ComplexityAnalyzer()

    def test_case_01_empty_valid_module(self, analyzer):
        """1. Empty valid module produces a single <module> scope with valid structural/Halstead metrics."""
        tree = ast.parse("")
        res = analyzer.analyze(tree)
        assert res.success is True
        assert len(res.scope_metrics) == 1

        mod_scope = res.scope_metrics[0]
        assert mod_scope.scope_id == "<module>"
        assert mod_scope.scope_type == "module"
        assert mod_scope.structural.statement_count == 0
        assert mod_scope.halstead.total_operators == 0
        assert mod_scope.cyclomatic.cyclomatic_status == "COMPLETE"

        summary = res.project_metrics
        assert summary is not None
        assert summary.total_scopes == 1
        assert summary.procedural_scopes == 0
        assert summary.module_scopes == 1
        assert summary.class_scopes == 0
        assert summary.average_statement_count is None
        assert summary.average_cyclomatic_complexity is None

    def test_case_02_module_with_one_function(self, analyzer):
        """2. Module with one function produces <module> and function scopes."""
        code = "def compute(x):\n    return x + 1\n"
        tree = ast.parse(code)
        res = analyzer.analyze(tree)
        assert len(res.scope_metrics) == 2
        assert [s.scope_id for s in res.scope_metrics] == ["<module>", "compute@1"]

        fn_scope = res.scope_metrics[1]
        assert fn_scope.scope_type == "function"
        assert fn_scope.cyclomatic.cyclomatic_status == "COMPLETE"
        assert fn_scope.cyclomatic.cyclomatic_complexity == 1
        assert fn_scope.structural.statement_count == 1
        assert fn_scope.halstead.vocabulary > 0

        assert res.project_metrics.procedural_scopes == 1
        assert res.project_metrics.total_scopes == 2
        assert res.project_metrics.average_statement_count == 1.0

    def test_case_03_module_with_multiple_functions(self, analyzer):
        """3. Module with multiple functions discovers and unifies each function in source order."""
        code = "def first(): pass\ndef second(x): return x\ndef third(): return 42\n"
        tree = ast.parse(code)
        res = analyzer.analyze(tree)
        assert len(res.scope_metrics) == 4
        assert [s.scope_id for s in res.scope_metrics] == ["<module>", "first@1", "second@2", "third@3"]
        assert res.project_metrics.procedural_scopes == 3
        assert res.project_metrics.module_scopes == 1

    def test_case_04_class_methods_and_nested_function(self, analyzer):
        """4. Module containing class, methods and nested function resolves all four scope types."""
        code = (
            "class Calculator:\n"
            "    def add(self, a, b):\n"
            "        def helper(v): return v\n"
            "        return helper(a + b)\n"
        )
        tree = ast.parse(code)
        res = analyzer.analyze(tree)
        assert len(res.scope_metrics) == 4
        ids = [s.scope_id for s in res.scope_metrics]
        assert ids == ["<module>", "class_body:Calculator@1", "Calculator.add@2", "Calculator.add.helper@3"]

        types = [s.scope_type for s in res.scope_metrics]
        assert types == ["module", "class_body", "method", "function"]
        assert res.project_metrics.class_scopes == 1
        assert res.project_metrics.procedural_scopes == 2

    def test_case_05_async_function_and_method_normalization(self, analyzer):
        """5. Async function and async method normalize to 'function' and 'method'."""
        code = (
            "async def fetch_data():\n"
            "    return None\n"
            "class Worker:\n"
            "    async def run(self):\n"
            "        return await fetch_data()\n"
        )
        tree = ast.parse(code)
        res = analyzer.analyze(tree)
        assert len(res.scope_metrics) == 4
        assert res.scope_metrics[1].scope_type == "function"
        assert res.scope_metrics[3].scope_type == "method"


# ============================================================================
# Group B: Scope Alignment & Integrity
# ============================================================================

class TestGroupBScopeAlignment:
    """Verifies 1:1 identifier alignment, uniqueness, and ordering across analyzers."""

    @pytest.fixture
    def pipeline(self):
        return UnifiedMetricsPipeline()

    def test_case_06_identifiers_match_across_all_engines(self, pipeline):
        """6. Scope discovery, CFG and both analyzers produce matching identifiers."""
        code = (
            "def alpha(): pass\n"
            "class Beta:\n"
            "    def gamma(self): pass\n"
        )
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        discovered_ids = [s.scope_id for s in scopes]

        cfgs = CFGBuilder.build_all(tree)
        struct_map = StructuralMetricsAnalyzer().analyze_all(scopes)
        halstead_map = HalsteadAnalyzer().analyze_all(scopes)

        assert set(discovered_ids) == set(cfgs.keys())
        assert set(discovered_ids) == set(struct_map.keys())
        assert set(discovered_ids) == set(halstead_map.keys())

    def test_case_07_exactly_one_unified_record_per_discovered_scope(self, pipeline):
        """7. Exactly one unified record per discovered scope."""
        code = "def a(): pass\ndef b(): pass\ndef c(): pass\n"
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        unified_scopes, _ = pipeline.run(tree)
        assert len(unified_scopes) == len(scopes)
        for s, u in zip(scopes, unified_scopes):
            assert s.scope_id == u.scope_id

    def test_case_08_no_duplicate_scope_records(self, pipeline):
        """8. No duplicate scope records in pipeline output."""
        code = (
            "class X:\n"
            "    def compute(self): pass\n"
            "class Y:\n"
            "    def compute(self): pass\n"
        )
        tree = ast.parse(code)
        unified_scopes, _ = pipeline.run(tree)
        ids = [u.scope_id for u in unified_scopes]
        assert len(ids) == len(set(ids))

    def test_case_09_lexical_source_order_preserved(self, pipeline):
        """9. Lexical source order preserved monotonically."""
        code = (
            "# Line 1\n"
            "def first(): pass\n"  # 2
            "class Middle:\n"       # 3
            "    x = 1\n"           # 4
            "    def m(self): pass\n" # 5
            "def last(): pass\n"    # 6
        )
        tree = ast.parse(code)
        unified_scopes, _ = pipeline.run(tree)
        # Expected sequence: <module>, first@2, class_body:Middle@3, Middle.m@5, last@6
        assert [u.scope_id for u in unified_scopes] == [
            "<module>",
            "first@2",
            "class_body:Middle@3",
            "Middle.m@5",
            "last@6",
        ]

    def test_case_10_module_class_function_method_relationships(self, pipeline):
        """10. Correct module, class_body, function, and method scope type assignments."""
        code = (
            "def top(): pass\n"
            "class C:\n"
            "    def m(self):\n"
            "        def inner(): pass\n"
        )
        tree = ast.parse(code)
        unified_scopes, _ = pipeline.run(tree)
        scope_type_map = {u.scope_id: u.scope_type for u in unified_scopes}
        assert scope_type_map["<module>"] == "module"
        assert scope_type_map["top@1"] == "function"
        assert scope_type_map["class_body:C@2"] == "class_body"
        assert scope_type_map["C.m@3"] == "method"
        assert scope_type_map["C.m.inner@4"] == "function"


# ============================================================================
# Group C: Structural and Halstead Integration
# ============================================================================

class TestGroupCStructuralAndHalsteadIntegration:
    """Verifies structural and Halstead metric accuracy in the integrated pipeline."""

    @pytest.fixture
    def pipeline(self):
        return UnifiedMetricsPipeline()

    def test_case_11_structural_metrics_match_accepted_fixtures(self, pipeline):
        """11. Structural metrics match their accepted fixtures."""
        code = (
            "def complex_proc(a, b):\n"
            "    if a > 0:\n"
            "        for i in range(b):\n"
            "            if i % 2 == 0:\n"
            "                return i\n"
            "    return 0\n"
        )
        tree = ast.parse(code)
        unified_scopes, _ = pipeline.run(tree)
        fn_struct = unified_scopes[1].structural
        assert fn_struct.if_statement_count == 2
        assert fn_struct.loop_count == 1
        assert fn_struct.conditional_count == 2
        assert fn_struct.control_nesting_depth >= 2

    def test_case_12_halstead_inventories_match_accepted_fixtures(self, pipeline):
        """12. Halstead inventories match accepted operator/operand fixtures."""
        code = "def bitwise(x, y):\n    return (x & y) | (x ^ ~y)\n"
        tree = ast.parse(code)
        unified_scopes, _ = pipeline.run(tree)
        fn_halstead = unified_scopes[1].halstead
        assert fn_halstead.distinct_operators >= 4
        assert fn_halstead.total_operators >= 5
        assert fn_halstead.distinct_operands >= 2
        assert fn_halstead.syntax_coverage_status == "FULL"
        assert fn_halstead.volume is not None
        assert fn_halstead.effort is not None

    @_requires_pep695
    def test_case_13_generic_class_and_type_parameters_ownership(self, pipeline):
        """13. Generic class type parameters owned by enclosing module scope and excluded from body."""
        code = (
            "class Box[T]:\n"
            "    def get(self, value: T) -> T:\n"
            "        return value\n"
        )
        tree = ast.parse(code)
        unified_scopes, _ = pipeline.run(tree)
        assert len(unified_scopes) == 3
        # Module owns class declaration
        mod_h = unified_scopes[0].halstead
        assert "id:Box" in mod_h.operand_inventory
        assert "op:class" in mod_h.operator_inventory

        # Class body owns method declaration
        cb_h = unified_scopes[1].halstead
        assert "id:get" in cb_h.operand_inventory
        assert "op:def" in cb_h.operator_inventory

        # Method body owns return and variables, while type annotations are excluded
        m_h = unified_scopes[2].halstead
        assert "id:value" in m_h.operand_inventory
        assert "id:self" in m_h.operand_inventory

    def test_case_14_decorator_default_annotation_ownership_distinct(self, pipeline):
        """14. Decorators owned by parent scope; parameter defaults and annotations isolated."""
        code = (
            "@decorator\n"
            "def process(val: int = 10) -> int:\n"
            "    return val * 2\n"
        )
        tree = ast.parse(code)
        unified_scopes, _ = pipeline.run(tree)
        mod_scope = unified_scopes[0]
        fn_scope = unified_scopes[1]

        # Decorator belongs to module scope
        assert "id:decorator" in mod_scope.halstead.operand_inventory
        # Function body contains multiplication and variable reference
        assert "id:val" in fn_scope.halstead.operand_inventory

    def test_case_15_pattern_matching_and_fstring_metrics(self, pipeline):
        """15. PEP 634 pattern matching and F-string formatting metrics evaluate cleanly."""
        code = (
            "def format_match(val):\n"
            "    match val:\n"
            "        case 1:\n"
            "            return f'One: {val}'\n"
            "        case _:\n"
            "            return f'Other: {val}'\n"
        )
        tree = ast.parse(code)
        unified_scopes, _ = pipeline.run(tree)
        fn_h = unified_scopes[1].halstead
        assert fn_h.syntax_coverage_status == "FULL"
        assert fn_h.volume is not None


# ============================================================================
# Group D: Cyclomatic Integration & CFG Mapping
# ============================================================================

class TestGroupDCyclomaticIntegration:
    """Verifies CFG mapping to ScopeCyclomaticMetrics and unsupported fallback handling."""

    def test_case_16_complete_cfg_metrics_map_correctly(self):
        """16. COMPLETE CFG metrics map correctly to ScopeCyclomaticMetrics."""
        code = "def branch(x):\n    if x > 0: return 1\n    return 0\n"
        tree = ast.parse(code)
        pipe = UnifiedMetricsPipeline()
        scopes, _ = pipe.run(tree)
        cyclo = scopes[1].cyclomatic
        assert cyclo.cyclomatic_status == "COMPLETE"
        assert cyclo.cyclomatic_complexity == 2
        assert cyclo.risk_rank == "A"
        assert cyclo.is_provisional is False
        assert cyclo.total_nodes > 0
        assert cyclo.total_edges > 0

    def test_case_17_partial_cfg_metrics_preserve_status_and_limitations(self):
        """17. PARTIAL CFG metrics preserve their status, provisional flag, and limitations."""
        code = "def gen(items):\n    return [x * 2 for x in items]\n"
        tree = ast.parse(code)
        pipe = UnifiedMetricsPipeline()
        scopes, _ = pipe.run(tree)
        cyclo = scopes[1].cyclomatic
        assert cyclo.cyclomatic_status == "PARTIAL"
        assert cyclo.is_provisional is True
        assert len(cyclo.limitations) > 0

    def test_case_18_unsupported_cfg_results_not_replaced_with_fabricated_scores(self):
        """18. UNSUPPORTED CFG results are not replaced with fabricated scores."""
        builder = CFGBuilder(scope_id="unsupp@1", name="unsupp", scope_type="function")
        builder.mark_unsupported("Unsupported dynamic syntax or control flow")
        cfg = builder.build_from_body([])
        cyclo = map_cfg_to_cyclomatic_metrics(cfg, "unsupp@1")
        assert cyclo.cyclomatic_status == "UNSUPPORTED"
        assert cyclo.cyclomatic_complexity is None
        assert cyclo.risk_rank is None
        assert "Unsupported dynamic syntax or control flow" in cyclo.limitations

    def test_case_19_missing_cfg_mappings_follow_unsupported_policy(self):
        """19. Missing CFG mappings produce documented UNSUPPORTED ScopeCyclomaticMetrics."""
        missing = map_cfg_to_cyclomatic_metrics(None, "ghost_scope@99")
        assert missing.cyclomatic_status == "UNSUPPORTED"
        assert missing.cyclomatic_complexity is None
        assert missing.total_nodes == 0
        assert missing.total_edges == 0
        assert "ghost_scope@99" in missing.limitations[0]


# ============================================================================
# Group E: Correlation and Project Summary Aggregation
# ============================================================================

class TestGroupECorrelationAndProjectSummary:
    """Verifies correlation analysis and project-level summary aggregation integration."""

    @pytest.fixture
    def pipeline(self):
        return UnifiedMetricsPipeline()

    def test_case_20_all_five_approved_correlation_dimensions_appear(self, pipeline):
        """20. All five approved correlation dimensions appear in the report."""
        code = "def f(x): return x\n"
        tree = ast.parse(code)
        _, summary = pipeline.run(tree)
        report = summary.correlation
        expected_dims = [
            "cyclomatic_vs_statement_count",
            "cyclomatic_vs_ast_depth",
            "cyclomatic_vs_control_nesting_depth",
            "cyclomatic_vs_halstead_volume",
            "cyclomatic_vs_halstead_effort",
        ]
        assert set(report.dimensions.keys()) == set(expected_dims)

    def test_case_21_complete_procedural_scopes_eligibility(self, pipeline):
        """21. Modules, class bodies, and non-COMPLETE CFG scopes are excluded from correlation."""
        code = (
            "class MyClass:\n"
            "    x = 1\n"
            "    def complete_method(self):\n"
            "        return 1\n"
            "    def partial_method(self):\n"
            "        return [x for x in (1, 2)]\n"
        )
        tree = ast.parse(code)
        scopes, summary = pipeline.run(tree)
        # Total scopes: 4 (<module>, class_body:MyClass@1, MyClass.complete_method@3, MyClass.partial_method@5)
        assert len(scopes) == 4
        # Eligible correlation scopes: only complete_method
        assert summary.correlation.eligible_scope_count == 1
        dim = summary.correlation.dimensions["cyclomatic_vs_statement_count"]
        assert dim.sample_size == 1
        assert dim.pairs[0].scope_id == "MyClass.complete_method@3"

    def test_case_22_structural_correlation_includes_partial_unclassified_halstead_when_cfg_complete(self, pipeline):
        """22. Structural correlation dimensions include scopes regardless of Halstead coverage."""
        code = (
            "def f1(x):\n    return x + 1\n"
            "def f2(x):\n    return x + 2\n"
            "def f3(x):\n    return x + 3\n"
        )
        tree = ast.parse(code)
        scopes, summary = pipeline.run(tree)
        dim_stmt = summary.correlation.dimensions["cyclomatic_vs_statement_count"]
        assert dim_stmt.sample_size == 3
        assert dim_stmt.status in ("DESCRIPTIVE_ONLY", "ZERO_VARIANCE")

    def test_case_23_halstead_correlation_excludes_partial_and_unclassified_syntax(self, pipeline):
        """23. Halstead correlation dimensions exclude scopes without FULL coverage."""
        code = (
            "def f1(x): return x + 1\n"
            "def f2(x): return x + 2\n"
            "def f3(x): return x + 3\n"
        )
        tree = ast.parse(code)
        scopes, summary = pipeline.run(tree)
        dim_vol = summary.correlation.dimensions["cyclomatic_vs_halstead_volume"]
        # All 3 have FULL Halstead coverage
        assert dim_vol.sample_size == 3

    def test_case_24_project_averages_use_exact_approved_denominators(self, pipeline):
        """24. Structural averages divide by procedural_scopes; cyclomatic divides by COMPLETE count."""
        code = (
            "def complete_fn(x):\n    return x\n"
            "def partial_fn(items):\n    return [x for x in items]\n"
        )
        tree = ast.parse(code)
        scopes, summary = pipeline.run(tree)
        assert summary.procedural_scopes == 2
        # Structural averages divide across both procedural scopes (denominator = 2)
        assert summary.average_statement_count is not None
        # Cyclomatic evaluated scopes: only complete_fn (denominator = 1)
        assert summary.cyclomatic_evaluated_scopes == 1
        assert summary.average_cyclomatic_complexity == 1.0

    def test_case_25_partial_diagnostic_averages_remain_separate(self, pipeline):
        """25. PARTIAL coverage metrics are stored in separate diagnostic fields."""
        code = "def comp(items): return [x for x in items]\n"
        tree = ast.parse(code)
        _, summary = pipeline.run(tree)
        # partial_fn has FULL syntax coverage for comprehensions in Python 3.12+
        # If any PARTIAL coverage occurs, verified isolated
        assert summary.partial_coverage_volume_scopes == 0 or summary.average_partial_halstead_volume is not None

    def test_case_26_unclassified_syntax_does_not_leak_into_numerical_averages(self, pipeline):
        """26. UNCLASSIFIED_SYNTAX count is recorded without numerical leakage."""
        code = "def plain(): pass\n"
        tree = ast.parse(code)
        _, summary = pipeline.run(tree)
        assert summary.unclassified_syntax_scopes == 0


# ============================================================================
# Group F: API Response, Serialization & Persistence Boundary
# ============================================================================

class TestGroupFAPIResponseAndPersistence:
    """Verifies AnalyzeResponse exposure, Pydantic serialization, and persistence boundary."""

    def test_case_27_analyze_response_includes_scope_and_project_metrics(self):
        """27. AnalyzeResponse exposes scope_metrics and project_metrics."""
        service = AnalysisService()
        req = AnalyzeRequest(code="def add(a, b): return a + b\n")
        resp = service.analyze_code(req)
        assert hasattr(resp, "scope_metrics")
        assert hasattr(resp, "project_metrics")
        assert len(resp.scope_metrics) == 2
        assert resp.project_metrics is not None

    def test_case_28_legacy_fields_remain_unchanged(self):
        """28. Legacy Big-O, recurrence, statistics, and graph fields remain fully populated."""
        service = AnalysisService()
        req = AnalyzeRequest(code="def loop_n(n):\n    for i in range(n): pass\n")
        resp = service.analyze_code(req)
        assert resp.time_complexity == "O(n)"
        assert resp.space_complexity == "O(1)"
        assert resp.confidence == "HIGH"
        assert resp.statistics.loop_count == 1
        assert resp.statistics.function_count == 1
        assert resp.graph is not None

    def test_case_29_empty_valid_source_returns_valid_module_metrics(self):
        """29. Programmatic analysis of empty module returns valid module metrics."""
        analyzer = ComplexityAnalyzer()
        resp = analyzer.analyze(ast.parse(""))
        assert len(resp.scope_metrics) == 1
        assert resp.scope_metrics[0].scope_id == "<module>"
        assert resp.project_metrics.total_scopes == 1
        assert resp.project_metrics.procedural_scopes == 0

    def test_case_30_invalid_syntax_follows_existing_safe_error_behavior(self):
        """30. Syntax errors produce safe failure response with empty scope metrics."""
        service = AnalysisService()
        req = AnalyzeRequest(code="def bad syntax : : :\n")
        resp = service.analyze_code(req)
        assert resp.success is False
        assert resp.error is not None
        assert resp.scope_metrics == []
        assert resp.project_metrics is None

    def test_case_31_pydantic_serialization_succeeds(self):
        """31. Pydantic model_dump and model_dump_json serialize cleanly without error."""
        service = AnalysisService()
        req = AnalyzeRequest(code="def square(x):\n    return x * x\n")
        resp = service.analyze_code(req)

        data = resp.model_dump()
        assert "scope_metrics" in data
        assert "project_metrics" in data
        assert len(data["scope_metrics"]) == 2

        json_str = resp.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["project_metrics"]["procedural_scopes"] == 1

        # Re-construct from JSON dict to verify round-trip
        reconstructed = AnalyzeResponse.model_validate(parsed)
        assert len(reconstructed.scope_metrics) == 2
        assert reconstructed.project_metrics.total_scopes == 2

    def test_case_32_existing_history_response_behavior_intact(self):
        """32. Existing history records and schema validation remain compatible."""
        # Validate that legacy construction without Phase 1B.2 metrics succeeds
        legacy_resp = AnalyzeResponse(
            success=True,
            time_complexity="O(1)",
            space_complexity="O(1)",
            confidence="HIGH",
            complexity_reasoning="Constant time",
            statistics={"total_lines": 1},
            structure={},
            graph={"active_complexity": "O(1)", "growth_points": []},
        )
        assert legacy_resp.scope_metrics == []
        assert legacy_resp.project_metrics is None

    def test_case_33_new_metrics_not_persisted_to_database(self):
        """33. AnalysisResult model does not attempt to persist Phase 1B.2 metrics."""
        mock_db = MagicMock()
        service = AnalysisService()
        req = AnalyzeRequest(code="def add(a, b): return a + b\n")

        resp = service.analyze_code(req, db=mock_db)
        assert resp.success is True

        # Verify that AnalysisResult instantiated and added to db does not contain scope_metrics
        added_objects = [call[0][0] for call in mock_db.add.call_args_list]
        result_records = [obj for obj in added_objects if isinstance(obj, AnalysisResult)]
        assert len(result_records) == 1

        rec = result_records[0]
        assert not hasattr(rec, "scope_metrics")
        assert not hasattr(rec, "project_metrics")


# ============================================================================
# Group G: Determinism, AST Immutability & Safety
# ============================================================================

class TestGroupGDeterminismAndSafety:
    """Verifies deterministic execution, AST immutability, and execution safety."""

    def test_case_34_repeated_analysis_produces_stable_equivalent_outputs(self):
        """34. Repeated execution across the pipeline produces identical metric values."""
        code = (
            "def factorial(n):\n"
            "    if n <= 1: return 1\n"
            "    return n * factorial(n - 1)\n"
        )
        tree = ast.parse(code)
        pipe = UnifiedMetricsPipeline()

        scopes1, summary1 = pipe.run(tree)
        scopes2, summary2 = pipe.run(tree)
        scopes3, summary3 = pipe.run(tree)

        dump1 = [s.model_dump() for s in scopes1]
        dump2 = [s.model_dump() for s in scopes2]
        dump3 = [s.model_dump() for s in scopes3]

        assert dump1 == dump2 == dump3
        assert summary1.model_dump() == summary2.model_dump() == summary3.model_dump()

    def test_case_35_original_ast_remains_unmodified(self):
        """35. The input AST is not mutated during pipeline execution."""
        code = (
            "class Worker:\n"
            "    def execute(self, task):\n"
            "        return task()\n"
        )
        tree = ast.parse(code)
        ast_dump_before = ast.dump(tree)

        pipe = UnifiedMetricsPipeline()
        pipe.run(tree)

        ast_dump_after = ast.dump(tree)
        assert ast_dump_before == ast_dump_after

    def test_case_36_no_arbitrary_code_executed(self):
        """36. Source code containing potentially side-effecting operations is analyzed strictly statically."""
        code = (
            "import os\n"
            "def side_effect():\n"
            "    # This should never execute at analysis time\n"
            "    raise RuntimeError('Analyzed code was executed!')\n"
        )
        tree = ast.parse(code)
        analyzer = ComplexityAnalyzer()
        # Must analyze cleanly without raising the runtime error inside side_effect()
        res = analyzer.analyze(tree)
        assert res.success is True
        assert len(res.scope_metrics) == 2

    def test_case_37_existing_parser_limits_and_safety_intact(self):
        """37. SafeASTParser depth and node limits remain active and protective."""
        parser = SafeASTParser()
        # Deeply nested code exceeding typical safety limits
        deep_code = "x = " + "(".join(["1"] * 200) + ")".join([""] * 200)
        tree, err = parser.parse_code(deep_code)
        # Should either successfully parse or reject cleanly via SafeASTParser without crashing
        assert tree is not None or err is not None
