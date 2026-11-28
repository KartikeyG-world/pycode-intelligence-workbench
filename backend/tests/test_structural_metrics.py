"""
Test suite for Structural AST Metrics Engine (Phase 1B.2 — Unit 3).

Verifies conformance to Stage 0.7 specification and Stage 1.0.2 architecture:
- All 16 Stage 0.7 structural acceptance matrix test cases.
- Mandatory generic class ownership regression fixture (Container[T]).
- Canonical scope discovery integration (analyze_all with discover_scopes).
- Ownership boundary enforcement (pruning child bodies, parent-owned decorators and bases).
- All 5 parameter categories in function and method scopes.
- AST immutability and original node preservation.
- Iterative depth protection on deeply nested structures.
- Control nesting depth and elif source-coordinate discrimination.
- Boolean operators, loops, comprehensions, conditionals, and assertions.
"""

import ast
import copy
import sys
import pytest

from app.analyzers.scope_discovery import discover_scopes, ScopeDefinition
from app.analyzers.structural_analyzer import (
    StructuralMetricsAnalyzer,
    EXCLUDED_AST_CLASSES,
)
from app.schemas.metrics import ScopeStructuralMetrics

_requires_pep695 = pytest.mark.skipif(
    sys.version_info < (3, 12), reason="PEP 695 syntax requires Python 3.12+"
)


# ==============================================================================
# Helper functions
# ==============================================================================

def get_scope_by_id(scopes, scope_id: str) -> ScopeDefinition:
    """Finds a scope definition by its scope_id."""
    for s in scopes:
        if s.scope_id == scope_id:
            return s
    raise KeyError(f"Scope with id {scope_id!r} not found in {[s.scope_id for s in scopes]}")


# ==============================================================================
# Group 1: Stage 0.7 Acceptance Matrix Fixtures (16 Cases)
# ==============================================================================

class TestStage07AcceptanceMatrix:
    """Validates the 16 exact test cases defined in Stage 0.7 Section 7.1."""

    @pytest.fixture
    def analyzer(self):
        return StructuralMetricsAnalyzer()

    def test_case_01_empty_module(self, analyzer):
        """Case 1: Empty module ('')."""
        tree = ast.parse("")
        scopes = discover_scopes(tree)
        metrics = analyzer.analyze(scopes[0])

        assert metrics.statement_count == 0
        assert metrics.top_level_statement_count == 0
        assert metrics.ast_node_count == 1
        assert metrics.ast_depth == 1
        assert metrics.control_nesting_depth == 0
        assert metrics.parameter_count is None
        assert metrics.return_count is None
        assert metrics.diagnostics == []

    def test_case_02_pass_module(self, analyzer):
        """Case 2: Pass module ('pass')."""
        tree = ast.parse("pass")
        scopes = discover_scopes(tree)
        metrics = analyzer.analyze(scopes[0])

        assert metrics.statement_count == 1
        assert metrics.top_level_statement_count == 1
        assert metrics.ast_node_count == 2
        assert metrics.ast_depth == 2
        assert metrics.control_nesting_depth == 0
        assert metrics.parameter_count is None
        assert metrics.return_count is None
        assert metrics.diagnostics == []

    def test_case_03_empty_function(self, analyzer):
        """Case 3: Empty function ('def f(): pass')."""
        tree = ast.parse("def f(): pass")
        scopes = discover_scopes(tree)
        f_scope = get_scope_by_id(scopes, "f@1")
        metrics = analyzer.analyze(f_scope)

        assert metrics.statement_count == 1
        assert metrics.top_level_statement_count == 1
        assert metrics.ast_node_count == 3
        assert metrics.ast_depth == 2
        assert metrics.control_nesting_depth == 0
        assert metrics.parameter_count == 0
        assert metrics.return_count == 0
        assert metrics.diagnostics == []

    def test_case_04_declaration_example_parent_scope(self, analyzer):
        """Case 4: Declaration example - parent scope (<module>)."""
        code = "@cache(timeout=10)\ndef f(a=20) -> Result:\n    return a"
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        mod_scope = get_scope_by_id(scopes, "<module>")
        metrics = analyzer.analyze(mod_scope)

        assert metrics.statement_count == 1
        assert metrics.top_level_statement_count == 1
        assert metrics.ast_node_count == 6
        assert metrics.ast_depth == 5
        assert metrics.control_nesting_depth == 0
        assert metrics.parameter_count is None
        assert metrics.return_count is None
        assert metrics.diagnostics == []

    def test_case_05_declaration_example_child_scope(self, analyzer):
        """Case 5: Declaration example - child scope (f@2)."""
        code = "@cache(timeout=10)\ndef f(a=20) -> Result:\n    return a"
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        f_scope = get_scope_by_id(scopes, "f@2")
        metrics = analyzer.analyze(f_scope)

        assert metrics.statement_count == 1
        assert metrics.top_level_statement_count == 1
        assert metrics.ast_node_count == 7
        assert metrics.ast_depth == 3
        assert metrics.control_nesting_depth == 0
        assert metrics.parameter_count == 1
        assert metrics.return_count == 1
        assert metrics.diagnostics == []

    @_requires_pep695
    def test_case_06_generic_type_alias(self, analyzer):
        """Case 6: Type alias ('type Vector[T] = list[T]')."""
        code = "type Vector[T] = list[T]"
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        mod_scope = get_scope_by_id(scopes, "<module>")
        metrics = analyzer.analyze(mod_scope)

        assert metrics.statement_count == 1
        assert metrics.top_level_statement_count == 1
        assert metrics.ast_node_count == 7
        assert metrics.ast_depth == 4
        assert metrics.control_nesting_depth == 0
        assert metrics.parameter_count is None
        assert metrics.return_count is None
        assert metrics.diagnostics == []

    @_requires_pep695
    def test_case_07_generic_function(self, analyzer):
        """Case 7: Generic function ('def convert[T](value: T) -> T:\n    return value')."""
        code = "def convert[T](value: T) -> T:\n    return value"
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        convert_scope = get_scope_by_id(scopes, "convert@1")
        metrics = analyzer.analyze(convert_scope)

        assert metrics.statement_count == 1
        assert metrics.top_level_statement_count == 1
        assert metrics.ast_node_count == 8
        assert metrics.ast_depth == 4
        assert metrics.control_nesting_depth == 0
        assert metrics.parameter_count == 1
        assert metrics.return_count == 1
        assert metrics.diagnostics == []

    @_requires_pep695
    def test_case_08_generic_method(self, analyzer):
        """Case 8: Generic method ('Container.get@2')."""
        code = "class Container[T]:\n    def get(self, value: T) -> T:\n        return value"
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        get_scope = get_scope_by_id(scopes, "Container.get@2")
        metrics = analyzer.analyze(get_scope)

        assert metrics.statement_count == 1
        assert metrics.top_level_statement_count == 1
        assert metrics.ast_node_count == 8
        assert metrics.ast_depth == 4
        assert metrics.control_nesting_depth == 0
        assert metrics.parameter_count == 2
        assert metrics.return_count == 1
        assert metrics.diagnostics == []

    def test_case_09_bitwise_function(self, analyzer):
        """
        Case 9: Bitwise function ('def bitwise(a, b):\n    return a | b').
        Direct AST calculation demonstrates 9 nodes and depth 4 (FunctionDef,
        arguments, arg(a), arg(b), Return, BinOp, BitOr, Name(a), Name(b)).
        """
        code = "def bitwise(a, b):\n    return a | b"
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        bitwise_scope = get_scope_by_id(scopes, "bitwise@1")
        metrics = analyzer.analyze(bitwise_scope)

        assert metrics.statement_count == 1
        assert metrics.top_level_statement_count == 1
        assert metrics.control_nesting_depth == 0
        assert metrics.parameter_count == 2
        assert metrics.return_count == 1
        assert metrics.diagnostics == []
        # Mathematical verification of node count and depth:
        assert metrics.ast_node_count == 9
        assert metrics.ast_depth == 4

    def test_case_10_pattern_match_value(self, analyzer):
        """Case 10: Pattern match value (match_value@1)."""
        code = """def match_value(value):
    match value:
        case 1 | 2:
            return 1
        case _:
            return 0"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        mv_scope = get_scope_by_id(scopes, "match_value@1")
        metrics = analyzer.analyze(mv_scope)

        assert metrics.statement_count == 3
        assert metrics.top_level_statement_count == 1
        assert metrics.ast_node_count == 17
        assert metrics.ast_depth == 6
        assert metrics.control_nesting_depth == 1
        assert metrics.parameter_count == 1
        assert metrics.return_count == 2
        assert metrics.diagnostics == []

    def test_case_11_pattern_match_three(self, analyzer):
        """Case 11: Pattern match three alternatives (match_three@1)."""
        code = """def match_three(value):
    match value:
        case 1 | 2 | 3:
            return 1
        case _:
            return 0"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        mt_scope = get_scope_by_id(scopes, "match_three@1")
        metrics = analyzer.analyze(mt_scope)

        assert metrics.statement_count == 3
        assert metrics.top_level_statement_count == 1
        assert metrics.ast_node_count == 19
        assert metrics.ast_depth == 6
        assert metrics.control_nesting_depth == 1
        assert metrics.parameter_count == 1
        assert metrics.return_count == 2
        assert metrics.diagnostics == []

    def test_case_12_pattern_mapping_function(self, analyzer):
        """Case 12: Pattern mapping function (f@1)."""
        code = """def f(value):
    match value:
        case {"name": captured}:
            return captured"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        f_scope = get_scope_by_id(scopes, "f@1")
        metrics = analyzer.analyze(f_scope)

        assert metrics.statement_count == 2
        assert metrics.top_level_statement_count == 1
        assert metrics.ast_node_count == 11
        assert metrics.ast_depth == 5
        assert metrics.control_nesting_depth == 1
        assert metrics.parameter_count == 1
        assert metrics.return_count == 1
        assert metrics.diagnostics == []

    def test_case_13_deep_loop_try_with(self, analyzer):
        """Case 13: Deep loop / try / with (f@1)."""
        code = """def f():
    for i in s:
        while i:
            try:
                with c:
                    pass
            except:
                pass"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        f_scope = get_scope_by_id(scopes, "f@1")
        metrics = analyzer.analyze(f_scope)

        assert metrics.statement_count == 6
        assert metrics.top_level_statement_count == 1
        assert metrics.ast_node_count == 14
        assert metrics.ast_depth == 7
        assert metrics.control_nesting_depth == 4
        assert metrics.parameter_count == 0
        assert metrics.return_count == 0
        assert metrics.diagnostics == []

    def test_case_14_flat_elif_chain(self, analyzer):
        """Case 14: Flat elif chain (f@1)."""
        code = """def f(x):
    if x:
        a = 1
    elif x == 0:
        b = 2
    else:
        c = 3
    return a"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        f_scope = get_scope_by_id(scopes, "f@1")
        metrics = analyzer.analyze(f_scope)

        assert metrics.statement_count == 6
        assert metrics.top_level_statement_count == 2
        assert metrics.ast_node_count == 21
        assert metrics.ast_depth == 5
        assert metrics.control_nesting_depth == 1
        assert metrics.parameter_count == 1
        assert metrics.return_count == 1
        assert metrics.diagnostics == []

    def test_case_15_nested_else_if(self, analyzer):
        """Case 15: Nested else-if (<module>)."""
        code = """if a:
    pass
else:
    if b:
        pass"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        mod_scope = get_scope_by_id(scopes, "<module>")
        metrics = analyzer.analyze(mod_scope)

        assert metrics.statement_count == 4
        assert metrics.top_level_statement_count == 1
        assert metrics.ast_node_count == 7
        assert metrics.ast_depth == 4
        assert metrics.control_nesting_depth == 2
        assert metrics.parameter_count is None
        assert metrics.return_count is None
        assert metrics.diagnostics == []

    def test_case_16_missing_coordinate_else_if_fallback(self, analyzer):
        """Case 16: Missing-coordinate else-if fallback (<module>)."""
        code = """if a:
    pass
else:
    if b:
        pass"""
        tree = ast.parse(code)
        # Invalidate coordinate of inner If
        inner_if = tree.body[0].orelse[0]
        inner_if.col_offset = None

        scopes = discover_scopes(tree)
        mod_scope = get_scope_by_id(scopes, "<module>")
        metrics = analyzer.analyze(mod_scope)

        assert metrics.statement_count == 4
        assert metrics.top_level_statement_count == 1
        assert metrics.ast_node_count == 7
        assert metrics.ast_depth == 4
        assert metrics.control_nesting_depth == 2
        assert metrics.parameter_count is None
        assert metrics.return_count is None
        assert metrics.diagnostics == ["MISSING_COORDINATES_FALLBACK_NESTED"]


# ==============================================================================
# Group 2: Mandatory Generic Class Ownership Fixture (Section 6.4)
# ==============================================================================

@_requires_pep695
class TestGenericClassOwnershipFixture:
    """Validates the exact scope ownership of Container[T] across all 3 scopes."""

    @pytest.fixture
    def analysis_result(self):
        code = """class Container[T]:
    def get(self, value: T) -> T:
        return value"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = StructuralMetricsAnalyzer()
        return analyzer.analyze_all(scopes)

    def test_container_module_scope(self, analysis_result):
        """Module owns ClassDef statement, prunes TypeVar and class body."""
        mod_metrics = analysis_result["<module>"]
        assert mod_metrics.statement_count == 1
        assert mod_metrics.top_level_statement_count == 1
        assert mod_metrics.ast_node_count == 2
        assert mod_metrics.ast_depth == 2
        assert mod_metrics.control_nesting_depth == 0
        assert mod_metrics.parameter_count is None
        assert mod_metrics.return_count is None
        assert mod_metrics.diagnostics == []

    def test_container_class_body_scope(self, analysis_result):
        """Class body owns ClassDef root, TypeVar, and method FunctionDef statement."""
        cls_metrics = analysis_result["class_body:Container@1"]
        assert cls_metrics.statement_count == 1
        assert cls_metrics.top_level_statement_count == 1
        assert cls_metrics.ast_node_count == 3
        assert cls_metrics.ast_depth == 2
        assert cls_metrics.control_nesting_depth == 0
        assert cls_metrics.parameter_count is None
        assert cls_metrics.return_count is None
        assert cls_metrics.diagnostics == []

    def test_container_method_scope(self, analysis_result):
        """Method scope owns FunctionDef, arguments, self, value: T, return T, Return, value."""
        mth_metrics = analysis_result["Container.get@2"]
        assert mth_metrics.statement_count == 1
        assert mth_metrics.top_level_statement_count == 1
        assert mth_metrics.ast_node_count == 8
        assert mth_metrics.ast_depth == 4
        assert mth_metrics.control_nesting_depth == 0
        assert mth_metrics.parameter_count == 2
        assert mth_metrics.return_count == 1
        assert mth_metrics.diagnostics == []


# ==============================================================================
# Group 3: Scope Ownership & Boundary Enforcement
# ==============================================================================

class TestScopeOwnershipBoundaries:
    """Verifies strict pruning and isolation between parent and nested scopes."""

    def test_nested_function_does_not_leak_into_enclosing_function(self):
        code = """def outer():
    def inner():
        x = 1
        y = 2
        return x + y
    return 42"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = StructuralMetricsAnalyzer()
        results = analyzer.analyze_all(scopes)

        outer_m = results["outer@1"]
        inner_m = results["outer.inner@2"]

        # Outer owns inner FunctionDef statement, and return 42 -> 2 statements
        assert outer_m.statement_count == 2
        assert outer_m.top_level_statement_count == 2
        assert outer_m.return_count == 1  # Only return 42, not return x + y

        # Inner owns x = 1, y = 2, return x + y -> 3 statements
        assert inner_m.statement_count == 3
        assert inner_m.top_level_statement_count == 3
        assert inner_m.return_count == 1

    def test_class_decorators_and_bases_owned_by_enclosing_scope(self):
        code = """@decorator
class MyClass(Base, metaclass=Meta):
    attr = 1"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = StructuralMetricsAnalyzer()
        results = analyzer.analyze_all(scopes)

        mod_m = results["<module>"]
        cls_m = results["class_body:MyClass@2"]

        # Module owns Module(1) -> ClassDef(2) -> @decorator(3), Base(3), keyword(3) -> Name(Meta)(4) -> 6 nodes, depth 4
        assert mod_m.ast_node_count == 6
        assert mod_m.ast_depth == 4

        # Class body owns ClassDef(1) -> Assign(2) -> Name(3), Constant(3) -> 4 nodes
        assert cls_m.ast_node_count == 4
        assert cls_m.ast_depth == 3

    def test_function_decorators_owned_by_parent_scope(self):
        code = """@dec1
@dec2(arg=1)
def foo():
    pass"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = StructuralMetricsAnalyzer()
        results = analyzer.analyze_all(scopes)

        mod_m = results["<module>"]
        foo_m = results["foo@3"]

        # foo owns FunctionDef(1) -> arguments(2), Pass(2) -> 3 nodes
        assert foo_m.ast_node_count == 3
        assert foo_m.ast_depth == 2

        # Module owns decorators: Module(1) -> FunctionDef(2) -> dec1(3), dec2(3) -> Call(3) -> Name, keyword, Constant
        assert mod_m.ast_node_count > 3


# ==============================================================================
# Group 4: Parameter & Return Counting
# ==============================================================================

class TestParametersAndReturns:
    """Verifies all five parameter categories and return statement accounting."""

    def test_all_five_parameter_categories(self):
        # posonlyargs, args, vararg, kwonlyargs, kwarg
        code = """def complex_sig(p1, /, a1, a2=10, *args, k1, k2=20, **kwargs):
    return p1"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = StructuralMetricsAnalyzer()
        m = analyzer.analyze(scopes[1])

        # p1 (1 posonly) + a1, a2 (2 regular) + *args (1) + k1, k2 (2 kwonly) + **kwargs (1) = 7
        assert m.parameter_count == 7
        assert m.return_count == 1

    def test_method_includes_self_and_cls(self):
        code = """class Foo:
    def inst_method(self, x):
        return x
    @classmethod
    def cls_method(cls, y):
        return y"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = StructuralMetricsAnalyzer()
        results = analyzer.analyze_all(scopes)

        assert results["Foo.inst_method@2"].parameter_count == 2
        assert results["Foo.cls_method@5"].parameter_count == 2

    def test_module_and_class_body_parameters_and_returns_are_none(self):
        code = """class Foo:
    x = 1"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = StructuralMetricsAnalyzer()
        results = analyzer.analyze_all(scopes)

        assert results["<module>"].parameter_count is None
        assert results["<module>"].return_count is None
        assert results["class_body:Foo@1"].parameter_count is None
        assert results["class_body:Foo@1"].return_count is None


# ==============================================================================
# Group 5: Control Nesting & Specific Syntax Metrics
# ==============================================================================

class TestControlNestingAndSyntaxMetrics:
    """Verifies conditionals, boolean operators, loops, comprehensions, and assertions."""

    def test_conditionals_and_boolean_operators(self):
        code = """def test_cond(a, b, c):
    if a and b or c:
        x = 1 if a else 2
    assert x > 0"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = StructuralMetricsAnalyzer()
        m = analyzer.analyze(scopes[1])

        # 1 ast.If, 1 ast.IfExp -> conditional_count = 2
        assert m.if_statement_count == 1
        assert m.if_expression_count == 1
        assert m.conditional_count == 2

        # a and b or c: BoolOp(Or, values=[BoolOp(And, values=[a, b]), c])
        # Outer BoolOp has 2 values -> 2 - 1 = 1
        # Inner BoolOp has 2 values -> 2 - 1 = 1
        # Total boolean junctions = 2
        assert m.boolean_operator_count == 2
        assert m.assertion_count == 1

    def test_loops_and_comprehensions(self):
        code = """def test_loops(items):
    res = [x * 2 for x in items]
    s = {x for x in items}
    d = {x: x for x in items}
    g = (x for x in items)
    for i in items:
        while i > 0:
            pass"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = StructuralMetricsAnalyzer()
        m = analyzer.analyze(scopes[1])

        # 4 comprehensions (ListComp, SetComp, DictComp, GeneratorExp)
        assert m.comprehension_count == 4
        # 2 loops (For, While)
        assert m.loop_count == 2

    def test_try_except_finally_nesting(self):
        code = """def test_try():
    try:
        if True:
            pass
    except ValueError:
        pass
    finally:
        pass"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = StructuralMetricsAnalyzer()
        m = analyzer.analyze(scopes[1])

        # try body: nesting 1; if True: nesting 1, if body: nesting 2
        assert m.control_nesting_depth == 2


# ==============================================================================
# Group 6: Immutability, Traversal Safety & Error Handling
# ==============================================================================

class TestImmutabilityAndSafety:
    """Verifies that the AST is never mutated and traversal does not fail on deep trees."""

    @_requires_pep695
    def test_ast_immutability(self):
        code = """class Foo[T]:
    @decorator
    def bar(self, x: T) -> T:
        if x:
            return x
        return 0"""
        tree = ast.parse(code)
        tree_copy = copy.deepcopy(tree)

        scopes = discover_scopes(tree)
        analyzer = StructuralMetricsAnalyzer()
        analyzer.analyze_all(scopes)

        assert ast.dump(tree) == ast.dump(tree_copy)

    def test_iterative_deeply_nested_traversal(self):
        """Constructs an AST with 500 nested blocks to verify stack safety."""
        # Builds: if True: if True: ... pass
        current = ast.Pass()
        for _ in range(500):
            current = ast.If(test=ast.Constant(value=True), body=[current], orelse=[])

        mod = ast.Module(body=[current], type_ignores=[])
        scopes = discover_scopes(mod)
        analyzer = StructuralMetricsAnalyzer()

        # Should complete without RecursionError
        metrics = analyzer.analyze(scopes[0])
        assert metrics.control_nesting_depth == 500
        assert metrics.statement_count == 501  # 500 Ifs + 1 Pass

    def test_deterministic_mapping_and_order_preservation(self):
        code = """def a(): pass
def b(): pass
def c(): pass"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = StructuralMetricsAnalyzer()
        result = analyzer.analyze_all(scopes)

        assert list(result.keys()) == ["<module>", "a@1", "b@2", "c@3"]
        for s in scopes:
            assert s.scope_id in result
            assert isinstance(result[s.scope_id], ScopeStructuralMetrics)
