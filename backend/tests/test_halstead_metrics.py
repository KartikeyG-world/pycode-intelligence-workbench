"""
Test suite for AST-Normalized Halstead Complexity Engine (Phase 1B.2 — Unit 4).

Verifies conformance to Stage 0.7 specification and Stage 1.0.2 architecture:
- All 15 Stage 0.7 Halstead acceptance matrix test cases.
- Mandatory generic class ownership fixture (Container[T]) across all 3 scopes.
- Canonical scope discovery integration (analyze_all with discover_scopes).
- Ownership boundary enforcement (pruning child bodies, parent-owned decorators, defaults, bases).
- Exclusion of type annotations, type parameters, and type alias values.
- PEP 634 pattern-matching classification (MatchOr, MatchAs, MatchStar, MatchMapping, MatchClass).
- Import and f-string classification.
- Mathematical derivations and availability statuses (AVAILABLE, UNDEFINED_EMPTY_VOCABULARY, UNDEFINED_ZERO_OPERANDS).
- Tripartite syntax coverage validation (FULL, PARTIAL, UNCLASSIFIED_SYNTAX).
- AST immutability and original node preservation.
"""

import ast
import copy
import math
import sys
import pytest
from pydantic import ValidationError

from app.analyzers.scope_discovery import discover_scopes, ScopeDefinition
from app.analyzers.halstead_analyzer import HalsteadAnalyzer
from app.schemas.metrics import ScopeHalsteadMetrics, UnclassifiedSyntaxRecord

_requires_pep695 = pytest.mark.skipif(
    sys.version_info < (3, 12), reason="PEP 695 syntax requires Python 3.12+"
)


def get_scope_by_id(scopes, scope_id: str) -> ScopeDefinition:
    """Finds a scope definition by its scope_id."""
    for s in scopes:
        if s.scope_id == scope_id:
            return s
    raise KeyError(f"Scope with id {scope_id!r} not found in {[s.scope_id for s in scopes]}")


# ==============================================================================
# Group 1: Stage 0.7 Halstead Acceptance Matrix (15 Cases)
# ==============================================================================

class TestStage07HalsteadAcceptanceMatrix:
    """Validates the 15 exact test cases defined in Stage 0.7 Section 7.2."""

    @pytest.fixture
    def analyzer(self):
        return HalsteadAnalyzer()

    def test_case_01_empty_module(self, analyzer):
        """Case 1: Empty module ('')."""
        tree = ast.parse("")
        scopes = discover_scopes(tree)
        m = analyzer.analyze(scopes[0])

        assert m.distinct_operators == 0
        assert m.total_operators == 0
        assert m.distinct_operands == 0
        assert m.total_operands == 0
        assert m.vocabulary == 0
        assert m.length == 0
        assert m.volume is None
        assert m.difficulty is None
        assert m.effort is None
        assert m.theoretical_time_seconds is None
        assert m.theoretical_delivered_bugs is None
        assert m.volume_status == "UNDEFINED_EMPTY_VOCABULARY"
        assert m.difficulty_status == "UNDEFINED_ZERO_OPERANDS"
        assert m.effort_status == "UNDEFINED_DEPENDENCY"
        assert m.syntax_coverage_status == "FULL"
        assert m.unclassified_syntax_nodes == []

    def test_case_02_pass_module(self, analyzer):
        """Case 2: Pass module ('pass')."""
        tree = ast.parse("pass")
        scopes = discover_scopes(tree)
        m = analyzer.analyze(scopes[0])

        assert m.distinct_operators == 1
        assert m.total_operators == 1
        assert m.distinct_operands == 0
        assert m.total_operands == 0
        assert m.vocabulary == 1
        assert m.length == 1
        assert m.volume == 0.0
        assert m.difficulty is None
        assert m.effort is None
        assert m.theoretical_time_seconds is None
        assert m.theoretical_delivered_bugs == 0.0
        assert m.volume_status == "AVAILABLE"
        assert m.difficulty_status == "UNDEFINED_ZERO_OPERANDS"
        assert m.effort_status == "UNDEFINED_DEPENDENCY"
        assert m.syntax_coverage_status == "FULL"
        assert m.operator_inventory == {"op:pass": 1}

    def test_case_03_empty_function(self, analyzer):
        """Case 3: Empty function ('def f(): pass')."""
        tree = ast.parse("def f(): pass")
        scopes = discover_scopes(tree)
        f_scope = get_scope_by_id(scopes, "f@1")
        m = analyzer.analyze(f_scope)

        assert m.distinct_operators == 1
        assert m.total_operators == 1
        assert m.distinct_operands == 0
        assert m.total_operands == 0
        assert m.vocabulary == 1
        assert m.length == 1
        assert m.volume == 0.0
        assert m.difficulty is None
        assert m.effort is None
        assert m.volume_status == "AVAILABLE"
        assert m.difficulty_status == "UNDEFINED_ZERO_OPERANDS"
        assert m.effort_status == "UNDEFINED_DEPENDENCY"
        assert m.syntax_coverage_status == "FULL"
        assert m.operator_inventory == {"op:pass": 1}

    def test_case_04_declaration_example_parent_scope(self, analyzer):
        """Case 4: Declaration example - parent scope (<module>)."""
        code = "@cache(timeout=10)\ndef f(a=20) -> Result:\n    return a"
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        mod_scope = get_scope_by_id(scopes, "<module>")
        m = analyzer.analyze(mod_scope)

        assert m.distinct_operators == 4
        assert m.total_operators == 4
        assert m.distinct_operands == 5
        assert m.total_operands == 5
        assert m.vocabulary == 9
        assert m.length == 9
        assert pytest.approx(m.volume, rel=1e-3) == 28.53
        assert pytest.approx(m.difficulty, rel=1e-3) == 2.00
        assert m.volume_status == "AVAILABLE"
        assert m.difficulty_status == "AVAILABLE"
        assert m.effort_status == "AVAILABLE"
        assert m.syntax_coverage_status == "FULL"
        assert m.operator_inventory == {
            "op:def": 1,
            "op:decorator": 1,
            "op:call": 1,
            "op:default_arg": 1,
        }
        assert m.operand_inventory == {
            "id:f": 1,
            "id:cache": 1,
            "kw:timeout": 1,
            "lit:int:10": 1,
            "lit:int:20": 1,
        }

    def test_case_05_declaration_example_child_scope(self, analyzer):
        """Case 5: Declaration example - child scope (f@2)."""
        code = "@cache(timeout=10)\ndef f(a=20) -> Result:\n    return a"
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        f_scope = get_scope_by_id(scopes, "f@2")
        m = analyzer.analyze(f_scope)

        assert m.distinct_operators == 1
        assert m.total_operators == 1
        assert m.distinct_operands == 1
        assert m.total_operands == 2
        assert m.vocabulary == 2
        assert m.length == 3
        assert pytest.approx(m.volume, rel=1e-3) == 3.00
        assert pytest.approx(m.difficulty, rel=1e-3) == 1.00
        assert m.volume_status == "AVAILABLE"
        assert m.difficulty_status == "AVAILABLE"
        assert m.effort_status == "AVAILABLE"
        assert m.syntax_coverage_status == "FULL"
        assert m.operator_inventory == {"op:return": 1}
        assert m.operand_inventory == {"id:a": 2}

    @_requires_pep695
    def test_case_06_generic_type_alias(self, analyzer):
        """Case 6: Type alias ('type Vector[T] = list[T]')."""
        code = "type Vector[T] = list[T]"
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        mod_scope = get_scope_by_id(scopes, "<module>")
        m = analyzer.analyze(mod_scope)

        assert m.distinct_operators == 1
        assert m.total_operators == 1
        assert m.distinct_operands == 1
        assert m.total_operands == 1
        assert m.vocabulary == 2
        assert m.length == 2
        assert pytest.approx(m.volume, rel=1e-3) == 2.00
        assert pytest.approx(m.difficulty, rel=1e-3) == 0.50
        assert m.volume_status == "AVAILABLE"
        assert m.difficulty_status == "AVAILABLE"
        assert m.effort_status == "AVAILABLE"
        assert m.syntax_coverage_status == "FULL"
        assert m.operator_inventory == {"op:type_alias": 1}
        assert m.operand_inventory == {"id:Vector": 1}

    @_requires_pep695
    def test_case_07_generic_function(self, analyzer):
        """Case 7: Generic function ('def convert[T](value: T) -> T:\n    return value')."""
        code = "def convert[T](value: T) -> T:\n    return value"
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        conv_scope = get_scope_by_id(scopes, "convert@1")
        m = analyzer.analyze(conv_scope)

        assert m.distinct_operators == 1
        assert m.total_operators == 1
        assert m.distinct_operands == 1
        assert m.total_operands == 2
        assert m.vocabulary == 2
        assert m.length == 3
        assert pytest.approx(m.volume, rel=1e-3) == 3.00
        assert pytest.approx(m.difficulty, rel=1e-3) == 1.00
        assert m.volume_status == "AVAILABLE"
        assert m.difficulty_status == "AVAILABLE"
        assert m.effort_status == "AVAILABLE"
        assert m.syntax_coverage_status == "FULL"
        assert m.operator_inventory == {"op:return": 1}
        assert m.operand_inventory == {"id:value": 2}

    @_requires_pep695
    def test_case_08_generic_method(self, analyzer):
        """Case 8: Generic method ('Container.get@2')."""
        code = "class Container[T]:\n    def get(self, value: T) -> T:\n        return value"
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        get_scope = get_scope_by_id(scopes, "Container.get@2")
        m = analyzer.analyze(get_scope)

        assert m.distinct_operators == 1
        assert m.total_operators == 1
        assert m.distinct_operands == 2
        assert m.total_operands == 3
        assert m.vocabulary == 3
        assert m.length == 4
        assert pytest.approx(m.volume, rel=1e-3) == 6.34
        assert pytest.approx(m.difficulty, rel=1e-3) == 0.75
        assert m.volume_status == "AVAILABLE"
        assert m.difficulty_status == "AVAILABLE"
        assert m.effort_status == "AVAILABLE"
        assert m.syntax_coverage_status == "FULL"
        assert m.operator_inventory == {"op:return": 1}
        assert m.operand_inventory == {"id:self": 1, "id:value": 2}

    def test_case_09_bitwise_function(self, analyzer):
        """Case 9: Bitwise function ('def bitwise(a, b):\n    return a | b')."""
        code = "def bitwise(a, b):\n    return a | b"
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        bw_scope = get_scope_by_id(scopes, "bitwise@1")
        m = analyzer.analyze(bw_scope)

        assert m.distinct_operators == 2
        assert m.total_operators == 2
        assert m.distinct_operands == 2
        assert m.total_operands == 4
        assert m.vocabulary == 4
        assert m.length == 6
        assert pytest.approx(m.volume, rel=1e-3) == 12.00
        assert pytest.approx(m.difficulty, rel=1e-3) == 2.00
        assert m.volume_status == "AVAILABLE"
        assert m.difficulty_status == "AVAILABLE"
        assert m.effort_status == "AVAILABLE"
        assert m.syntax_coverage_status == "FULL"
        assert m.operator_inventory == {"op:return": 1, "op:bitor": 1}
        assert m.operand_inventory == {"id:a": 2, "id:b": 2}

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
        m = analyzer.analyze(mv_scope)

        assert m.distinct_operators == 4
        assert m.total_operators == 6
        assert m.distinct_operands == 4
        assert m.total_operands == 6
        assert m.vocabulary == 8
        assert m.length == 12
        assert pytest.approx(m.volume, rel=1e-3) == 36.00
        assert pytest.approx(m.difficulty, rel=1e-3) == 3.00
        assert m.volume_status == "AVAILABLE"
        assert m.difficulty_status == "AVAILABLE"
        assert m.effort_status == "AVAILABLE"
        assert m.syntax_coverage_status == "FULL"
        assert m.operator_inventory == {
            "op:match": 1,
            "op:case": 2,
            "op:match_or": 1,
            "op:return": 2,
        }
        assert m.operand_inventory == {
            "id:value": 2,
            "lit:int:1": 2,
            "lit:int:2": 1,
            "lit:int:0": 1,
        }

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
        m = analyzer.analyze(mt_scope)

        assert m.distinct_operators == 4
        assert m.total_operators == 7
        assert m.distinct_operands == 5
        assert m.total_operands == 7
        assert m.vocabulary == 9
        assert m.length == 14
        assert pytest.approx(m.volume, rel=1e-3) == 44.38
        assert pytest.approx(m.difficulty, rel=1e-3) == 2.80
        assert m.volume_status == "AVAILABLE"
        assert m.difficulty_status == "AVAILABLE"
        assert m.effort_status == "AVAILABLE"
        assert m.syntax_coverage_status == "FULL"
        assert m.operator_inventory == {
            "op:match": 1,
            "op:case": 2,
            "op:match_or": 2,
            "op:return": 2,
        }
        assert m.operand_inventory == {
            "id:value": 2,
            "lit:int:1": 2,
            "lit:int:2": 1,
            "lit:int:3": 1,
            "lit:int:0": 1,
        }

    def test_case_12_pattern_mapping_function(self, analyzer):
        """Case 12: Pattern mapping function (f@1)."""
        code = """def f(value):
    match value:
        case {"name": captured}:
            return captured"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        f_scope = get_scope_by_id(scopes, "f@1")
        m = analyzer.analyze(f_scope)

        assert m.distinct_operators == 4
        assert m.total_operators == 4
        assert m.distinct_operands == 3
        assert m.total_operands == 5
        assert m.vocabulary == 7
        assert m.length == 9
        assert pytest.approx(m.volume, rel=1e-3) == 25.27
        assert m.difficulty == pytest.approx(10 / 3, rel=1e-3)
        assert m.volume_status == "AVAILABLE"
        assert m.difficulty_status == "AVAILABLE"
        assert m.effort_status == "AVAILABLE"
        assert m.syntax_coverage_status == "FULL"
        assert m.operator_inventory == {
            "op:match": 1,
            "op:case": 1,
            "op:match_mapping": 1,
            "op:return": 1,
        }
        assert m.operand_inventory == {
            "id:value": 2,
            'lit:str:"name"': 1,
            "id:captured": 2,
        }

    def test_case_13_fstring_formatting(self, analyzer):
        """Case 13: F-string formatting (f@1)."""
        code = """def f():
    f"{value!r:>{width}}" """
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        f_scope = get_scope_by_id(scopes, "f@1")
        m = analyzer.analyze(f_scope)

        assert m.distinct_operators == 4
        assert m.total_operators == 5
        assert m.distinct_operands == 3
        assert m.total_operands == 3
        assert m.vocabulary == 7
        assert m.length == 8
        assert pytest.approx(m.volume, rel=1e-3) == 22.46
        assert pytest.approx(m.difficulty, rel=1e-3) == 2.00
        assert m.volume_status == "AVAILABLE"
        assert m.difficulty_status == "AVAILABLE"
        assert m.effort_status == "AVAILABLE"
        assert m.syntax_coverage_status == "FULL"
        assert m.operator_inventory == {
            "op:fstring": 1,
            "op:format_field": 2,
            "op:conv_repr": 1,
            "op:format_spec": 1,
        }
        assert m.operand_inventory == {
            "id:value": 1,
            'lit:str:">"': 1,
            "id:width": 1,
        }

    def test_case_14_chained_comparisons(self, analyzer):
        """Case 14: Chained comparisons (f@1)."""
        code = """def f(x):
    return 1 < x <= 10"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        f_scope = get_scope_by_id(scopes, "f@1")
        m = analyzer.analyze(f_scope)

        assert m.distinct_operators == 3
        assert m.total_operators == 3
        assert m.distinct_operands == 3
        assert m.total_operands == 4
        assert m.vocabulary == 6
        assert m.length == 7
        assert pytest.approx(m.volume, rel=1e-3) == 18.09
        assert pytest.approx(m.difficulty, rel=1e-3) == 2.00
        assert m.volume_status == "AVAILABLE"
        assert m.difficulty_status == "AVAILABLE"
        assert m.effort_status == "AVAILABLE"
        assert m.syntax_coverage_status == "FULL"
        assert m.operator_inventory == {
            "op:return": 1,
            "op:lt": 1,
            "op:lte": 1,
        }
        assert m.operand_inventory == {
            "id:x": 2,
            "lit:int:1": 1,
            "lit:int:10": 1,
        }

    def test_case_15_missing_coordinate_else_if_fallback(self, analyzer):
        """Case 15: Missing-coordinate else-if fallback (<module>)."""
        code = """if a:
    pass
else:
    if b:
        pass"""
        tree = ast.parse(code)
        inner = tree.body[0].orelse[0]
        inner.col_offset = None

        scopes = discover_scopes(tree)
        mod_scope = get_scope_by_id(scopes, "<module>")
        m = analyzer.analyze(mod_scope)

        assert m.distinct_operators == 3
        assert m.total_operators == 5
        assert m.distinct_operands == 2
        assert m.total_operands == 2
        assert m.vocabulary == 5
        assert m.length == 7
        assert pytest.approx(m.volume, rel=1e-3) == 16.25
        assert pytest.approx(m.difficulty, rel=1e-3) == 1.50
        assert m.volume_status == "AVAILABLE"
        assert m.difficulty_status == "AVAILABLE"
        assert m.effort_status == "AVAILABLE"
        assert m.syntax_coverage_status == "FULL"
        assert m.operator_inventory == {
            "op:if": 2,
            "op:else": 1,
            "op:pass": 2,
        }
        assert m.operand_inventory == {"id:a": 1, "id:b": 1}
        assert "MISSING_COORDINATES_FALLBACK_NESTED" in m.undefined_reasons


# ==============================================================================
# Group 2: Mandatory Generic Class Ownership Fixture (Container[T])
# ==============================================================================

@_requires_pep695
class TestGenericClassHalsteadOwnership:
    """Verifies Container[T] Halstead inventories across all 3 scopes."""

    @pytest.fixture
    def results(self):
        code = """class Container[T]:
    def get(self, value: T) -> T:
        return value"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = HalsteadAnalyzer()
        return analyzer.analyze_all(scopes)

    def test_container_module_scope(self, results):
        """Module owns op:class (1) and id:Container (1)."""
        m = results["<module>"]
        assert m.operator_inventory == {"op:class": 1}
        assert m.operand_inventory == {"id:Container": 1}
        assert m.distinct_operators == 1
        assert m.total_operators == 1
        assert m.distinct_operands == 1
        assert m.total_operands == 1
        assert pytest.approx(m.volume, rel=1e-3) == 2.00
        assert pytest.approx(m.difficulty, rel=1e-3) == 0.50

    def test_container_class_body_scope(self, results):
        """Class body owns method declaration op:def (1) and id:get (1)."""
        m = results["class_body:Container@1"]
        assert m.operator_inventory == {"op:def": 1}
        assert m.operand_inventory == {"id:get": 1}
        assert m.distinct_operators == 1
        assert m.total_operators == 1
        assert m.distinct_operands == 1
        assert m.total_operands == 1
        assert pytest.approx(m.volume, rel=1e-3) == 2.00
        assert pytest.approx(m.difficulty, rel=1e-3) == 0.50

    def test_container_method_scope(self, results):
        """Method scope owns op:return (1), id:self (1), id:value (2)."""
        m = results["Container.get@2"]
        assert m.operator_inventory == {"op:return": 1}
        assert m.operand_inventory == {"id:self": 1, "id:value": 2}
        assert m.distinct_operators == 1
        assert m.total_operators == 1
        assert m.distinct_operands == 2
        assert m.total_operands == 3
        assert pytest.approx(m.volume, rel=1e-3) == 6.34
        assert pytest.approx(m.difficulty, rel=1e-3) == 0.75


# ==============================================================================
# Group 3: Scope Ownership & Boundary Enforcement
# ==============================================================================

class TestHalsteadScopeBoundaries:
    """Verifies isolation between parent operational scopes and child callable bodies."""

    def test_nested_function_does_not_leak_body_into_enclosing_function(self):
        code = """def outer():
    def inner():
        return 42
    return 10"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = HalsteadAnalyzer()
        res = analyzer.analyze_all(scopes)

        outer_m = res["outer@1"]
        inner_m = res["outer.inner@2"]

        # Outer owns op:def (1), id:inner (1), op:return (1), lit:int:10 (1)
        assert outer_m.operator_inventory == {"op:def": 1, "op:return": 1}
        assert outer_m.operand_inventory == {"id:inner": 1, "lit:int:10": 1}

        # Inner owns op:return (1), lit:int:42 (1)
        assert inner_m.operator_inventory == {"op:return": 1}
        assert inner_m.operand_inventory == {"lit:int:42": 1}

    def test_class_decorators_bases_keywords_owned_by_enclosing_scope(self):
        code = """@my_dec(k=1)
class Foo(Bar, metaclass=Meta):
    pass"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = HalsteadAnalyzer()
        res = analyzer.analyze_all(scopes)

        mod_m = res["<module>"]
        cls_m = res["class_body:Foo@2"]

        # Module owns class declaration, decorators, bases, keywords
        assert "op:class" in mod_m.operator_inventory
        assert "op:decorator" in mod_m.operator_inventory
        assert "id:Foo" in mod_m.operand_inventory
        assert "id:Bar" in mod_m.operand_inventory
        assert "kw:metaclass" in mod_m.operand_inventory
        assert "id:Meta" in mod_m.operand_inventory

        # Class body owns only op:pass (1)
        assert cls_m.operator_inventory == {"op:pass": 1}
        assert cls_m.operand_inventory == {}


# ==============================================================================
# Group 4: PEP 634 Pattern Matching & Advanced Operators
# ==============================================================================

class TestPatternMatchingAndOperators:
    """Verifies pattern matching, boolean junctions, try-star, and imports."""

    def test_pattern_match_four_alternatives(self):
        code = """def f(x):
    match x:
        case 1 | 2 | 3 | 4:
            return 1"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = HalsteadAnalyzer()
        m = analyzer.analyze(scopes[1])

        # 4 alternatives -> 4 - 1 = 3 match_or operators
        assert m.operator_inventory["op:match_or"] == 3

    def test_try_star_exception_group(self):
        code = """def test_try_star():
    try:
        pass
    except* ValueError as e:
        pass"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = HalsteadAnalyzer()
        m = analyzer.analyze(scopes[1])

        assert m.operator_inventory["op:try"] == 1
        assert m.operator_inventory["op:except_star"] == 1
        assert m.operator_inventory["op:as"] == 1
        assert m.operand_inventory["id:e"] == 1

    def test_imports_and_aliases(self):
        code = """import os
from math import sqrt as s"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = HalsteadAnalyzer()
        m = analyzer.analyze(scopes[0])

        assert m.operator_inventory["op:import"] == 1
        assert m.operator_inventory["op:from_import"] == 1
        assert m.operator_inventory["op:as"] == 1
        assert m.operand_inventory["id:os"] == 1
        assert m.operand_inventory["id:math"] == 1
        assert m.operand_inventory["id:sqrt"] == 1
        assert m.operand_inventory["id:s"] == 1

    def test_operand_type_segregation(self):
        """Verifies bool is distinct from int, None is distinct, float is distinct."""
        code = """def f():
    a = True
    b = 1
    c = 1.0
    d = None
    e = "text"
    f = b"bytes"
    g = 2j
    h = ..."""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = HalsteadAnalyzer()
        m = analyzer.analyze(scopes[1])

        # All literals must have unique keys in operand inventory
        assert m.operand_inventory["lit:bool:True"] == 1
        assert m.operand_inventory["lit:int:1"] == 1
        assert m.operand_inventory["lit:float:1.0"] == 1
        assert m.operand_inventory["lit:none:None"] == 1
        assert m.operand_inventory['lit:str:"text"'] == 1
        assert m.operand_inventory["lit:bytes:b'bytes'"] == 1
        assert m.operand_inventory["lit:complex:2j"] == 1
        assert m.operand_inventory["lit:ellipsis:..."] == 1

    def test_attribute_vs_keyword_vs_identifier_segregation(self):
        """Verifies attr:<name>, kw:<name>, and id:<name> are cleanly distinct."""
        code = """def f(target):
    func(target, target=target.target)"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = HalsteadAnalyzer()
        m = analyzer.analyze(scopes[1])

        assert "id:target" in m.operand_inventory
        assert "kw:target" in m.operand_inventory
        assert "attr:target" in m.operand_inventory

    def test_nested_match_or_counted_recursively(self):
        """Verifies nested MatchOr junctions: (1 | 2) | (3 | 4) -> 3 total junctions."""
        code = """def f(x):
    match x:
        case (1 | 2) | (3 | 4):
            return 1"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = HalsteadAnalyzer()
        m = analyzer.analyze(scopes[1])

        # Outer MatchOr has 2 alternatives (1 junction)
        # Left MatchOr has 2 alternatives (1 junction)
        # Right MatchOr has 2 alternatives (1 junction)
        # Total op:match_or = 3
        assert m.operator_inventory["op:match_or"] == 3


# ==============================================================================
# Group 5: Tripartite Syntax Coverage & Schema Invariants
# ==============================================================================

class TestTripartiteSyntaxCoverage:
    """Verifies FULL, PARTIAL, and UNCLASSIFIED_SYNTAX coverage behaviors and schema invariants."""

    def test_case_01_full_ordinary_function(self):
        """Fully classified ordinary function produces FULL coverage."""
        code = """def add(a, b):
    return a + b"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = HalsteadAnalyzer()
        m = analyzer.analyze(scopes[1])

        assert m.syntax_coverage_status == "FULL"
        assert m.unclassified_syntax_nodes == []
        assert m.volume_status == "AVAILABLE"
        assert m.difficulty_status == "AVAILABLE"
        assert m.effort_status == "AVAILABLE"
        assert m.volume is not None
        assert m.difficulty is not None
        assert m.effort is not None

    @_requires_pep695
    def test_case_02_full_generic_function_with_excluded_annotations(self):
        """Fully classified generic function with intentionally excluded annotations produces FULL."""
        code = """def identity[T](value: T) -> T:
    return value"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = HalsteadAnalyzer()
        m = analyzer.analyze(scopes[1])

        assert m.syntax_coverage_status == "FULL"
        assert m.unclassified_syntax_nodes == []
        assert m.operator_inventory == {"op:return": 1}
        assert m.operand_inventory == {"id:value": 2}
        assert m.volume_status == "AVAILABLE"
        assert m.difficulty_status == "AVAILABLE"

    def test_case_03_full_recognized_pattern_matching(self):
        """Fully classified pattern matching constructs produce FULL coverage using canonical match_value fixture."""
        code = """def match_value(value):
    match value:
        case 1 | 2:
            return 1
        case _:
            return 0"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = HalsteadAnalyzer()
        m = analyzer.analyze(scopes[1])

        assert m.syntax_coverage_status == "FULL"
        assert m.unclassified_syntax_nodes == []
        assert m.operator_inventory == {
            "op:match": 1,
            "op:case": 2,
            "op:match_or": 1,
            "op:return": 2,
        }
        assert m.operand_inventory == {
            "id:value": 2,
            "lit:int:1": 2,
            "lit:int:2": 1,
            "lit:int:0": 1,
        }
        assert m.distinct_operators == 4
        assert m.total_operators == 6
        assert m.distinct_operands == 4
        assert m.total_operands == 6
        assert m.vocabulary == 8
        assert m.length == 12
        assert pytest.approx(m.volume, rel=1e-3) == 36.00
        assert pytest.approx(m.difficulty, rel=1e-3) == 3.00
        assert pytest.approx(m.effort, rel=1e-3) == 108.00
        assert m.volume_status == "AVAILABLE"
        assert m.difficulty_status == "AVAILABLE"
        assert m.effort_status == "AVAILABLE"

    def test_case_04_partial_locally_unclassified_node_with_reliable_baseline(self):
        """A locally unclassified AST node with otherwise reliable scope accounting produces PARTIAL."""
        code = """def compute(x):
    return x + 1"""
        tree = ast.parse(code)
        class CustomUnrecognizedExpr(ast.AST):
            _fields = ()

        # Insert custom unclassified expression inside body
        tree.body[0].body.insert(0, ast.Expr(value=CustomUnrecognizedExpr()))
        scopes = discover_scopes(tree)
        analyzer = HalsteadAnalyzer()
        m = analyzer.analyze(scopes[1])

        assert m.syntax_coverage_status == "PARTIAL"
        assert len(m.unclassified_syntax_nodes) == 1
        assert m.unclassified_syntax_nodes[0].node_class == "CustomUnrecognizedExpr"
        # Recognized baseline is preserved and computed independently
        assert m.operator_inventory == {"op:return": 1, "op:add": 1}
        assert m.operand_inventory == {"id:x": 2, "lit:int:1": 1}
        assert m.distinct_operators == 2
        assert m.total_operators == 2
        assert m.distinct_operands == 2
        assert m.total_operands == 3
        assert m.vocabulary == 4
        assert m.length == 5
        assert pytest.approx(m.volume, rel=1e-3) == 10.00
        assert pytest.approx(m.difficulty, rel=1e-3) == 1.50
        assert pytest.approx(m.effort, rel=1e-3) == 15.00
        assert m.volume_status == "AVAILABLE"
        assert m.difficulty_status == "AVAILABLE"
        assert m.effort_status == "AVAILABLE"

    def test_case_05_unclassified_syntax_unsupported_structure(self):
        """An unsupported structure making overall scope classification unreliable produces UNCLASSIFIED_SYNTAX."""
        class DummyUnsupportedNode(ast.AST):
            _fields = ()

        # Case 5a: Unsupported scope structure / invalid scope type
        unsupported_scope = ScopeDefinition(
            scope_id="custom_unsupported@1",
            name="custom_unsupported",
            scope_type="custom_type",  # invalid scope_type
            node=DummyUnsupportedNode(),
            lineno=1,
            end_lineno=1,
            parent_scope_id=None,
        )
        analyzer = HalsteadAnalyzer()
        m = analyzer.analyze(unsupported_scope)

        assert m.syntax_coverage_status == "UNCLASSIFIED_SYNTAX"
        assert len(m.unclassified_syntax_nodes) >= 1
        assert m.unclassified_syntax_nodes[0].node_class == "DummyUnsupportedNode"
        assert "Unsupported scope_type" in m.unclassified_syntax_nodes[0].reason
        # Mathematical metrics are evaluated independently from actual token count (here eta=0)
        assert m.vocabulary == 0
        assert m.volume is None
        assert m.difficulty is None
        assert m.effort is None
        assert m.theoretical_time_seconds is None
        assert m.theoretical_delivered_bugs is None
        assert m.volume_status == "UNDEFINED_EMPTY_VOCABULARY"
        assert m.difficulty_status == "UNDEFINED_ZERO_OPERANDS"
        assert m.effort_status == "UNDEFINED_DEPENDENCY"
        assert any("UNCLASSIFIED_SYNTAX" in r for r in m.undefined_reasons)

        # Case 5b: Function scope with missing body (corrupted/unsupported root structure)
        unsupported_root_scope = ScopeDefinition(
            scope_id="bad_root@1",
            name="bad_root",
            scope_type="function",
            node=ast.Pass(),  # ast.Pass has no body attribute
            lineno=1,
            end_lineno=1,
            parent_scope_id=None,
        )
        m2 = analyzer.analyze(unsupported_root_scope)

        assert m2.syntax_coverage_status == "UNCLASSIFIED_SYNTAX"
        assert len(m2.unclassified_syntax_nodes) == 1
        assert "Unsupported function scope root: missing body" in m2.unclassified_syntax_nodes[0].reason
        assert m2.vocabulary == 0
        assert m2.volume is None
        assert m2.volume_status == "UNDEFINED_EMPTY_VOCABULARY"

    def test_case_06_pydantic_validator_rejects_partial_with_empty_diagnostics(self):
        """Pydantic model validator rejects syntax_coverage_status='PARTIAL' with empty unclassified_syntax_nodes."""
        with pytest.raises(ValidationError, match="requires at least one unclassified syntax record"):
            ScopeHalsteadMetrics(
                distinct_operators=1,
                distinct_operands=1,
                total_operators=1,
                total_operands=1,
                vocabulary=2,
                length=2,
                volume=2.0,
                difficulty=0.5,
                effort=1.0,
                theoretical_time_seconds=1.0 / 18.0,
                theoretical_delivered_bugs=2.0 / 3000.0,
                volume_status="AVAILABLE",
                difficulty_status="AVAILABLE",
                effort_status="AVAILABLE",
                undefined_reasons=[],
                syntax_coverage_status="PARTIAL",
                unclassified_syntax_nodes=[],  # Invariant violation!
                operator_inventory={"op:return": 1},
                operand_inventory={"id:x": 1},
            )

    def test_case_07_pydantic_validator_rejects_unclassified_syntax_with_empty_diagnostics(self):
        """Pydantic model validator rejects syntax_coverage_status='UNCLASSIFIED_SYNTAX' with empty unclassified_syntax_nodes."""
        with pytest.raises(ValidationError, match="requires at least one unclassified syntax record"):
            ScopeHalsteadMetrics(
                distinct_operators=0,
                distinct_operands=0,
                total_operators=0,
                total_operands=0,
                vocabulary=0,
                length=0,
                volume=None,
                difficulty=None,
                effort=None,
                theoretical_time_seconds=None,
                theoretical_delivered_bugs=None,
                volume_status="UNDEFINED_EMPTY_VOCABULARY",
                difficulty_status="UNDEFINED_ZERO_OPERANDS",
                effort_status="UNDEFINED_DEPENDENCY",
                undefined_reasons=["Unreliable baseline"],
                syntax_coverage_status="UNCLASSIFIED_SYNTAX",
                unclassified_syntax_nodes=[],  # Invariant violation!
                operator_inventory={},
                operand_inventory={},
            )

    def test_case_08_pydantic_validator_rejects_full_with_non_empty_diagnostics(self):
        """Pydantic model validator rejects syntax_coverage_status='FULL' with non-empty unclassified_syntax_nodes."""
        record = UnclassifiedSyntaxRecord(
            node_class="CustomNode",
            lineno=1,
            col_offset=0,
            reason="Unrecognized node",
        )
        with pytest.raises(ValidationError, match="requires unclassified_syntax_nodes to be empty"):
            ScopeHalsteadMetrics(
                distinct_operators=1,
                distinct_operands=1,
                total_operators=1,
                total_operands=1,
                vocabulary=2,
                length=2,
                volume=2.0,
                difficulty=0.5,
                effort=1.0,
                theoretical_time_seconds=1.0 / 18.0,
                theoretical_delivered_bugs=2.0 / 3000.0,
                volume_status="AVAILABLE",
                difficulty_status="AVAILABLE",
                effort_status="AVAILABLE",
                undefined_reasons=[],
                syntax_coverage_status="FULL",
                unclassified_syntax_nodes=[record],  # Invariant violation!
                operator_inventory={"op:return": 1},
                operand_inventory={"id:x": 1},
            )


# ==============================================================================
# Group 6: Immutability, AST Safety & Order Preservation
# ==============================================================================

class TestImmutabilityAndSafety:
    """Verifies that the original AST is not mutated and results are deterministic."""

    @_requires_pep695
    def test_ast_immutability(self):
        code = """class Foo[T]:
    @dec(k=1)
    def bar(self, x: T) -> T:
        match x:
            case 1 | 2:
                return x
        return 0"""
        tree = ast.parse(code)
        tree_copy = copy.deepcopy(tree)

        scopes = discover_scopes(tree)
        analyzer = HalsteadAnalyzer()
        analyzer.analyze_all(scopes)

        assert ast.dump(tree) == ast.dump(tree_copy)

    def test_deterministic_order_preservation(self):
        code = """def a(): pass
def b(): pass
def c(): pass"""
        tree = ast.parse(code)
        scopes = discover_scopes(tree)
        analyzer = HalsteadAnalyzer()
        res = analyzer.analyze_all(scopes)

        assert list(res.keys()) == ["<module>", "a@1", "b@2", "c@3"]
        for s in scopes:
            assert s.scope_id in res
            assert isinstance(res[s.scope_id], ScopeHalsteadMetrics)
