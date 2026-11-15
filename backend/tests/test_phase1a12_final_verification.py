import ast
from functools import cache, lru_cache
from typing import Dict, Any

from app.analyzers.ast_parser import SafeASTParser
from app.analyzers.complexity_analyzer import ComplexityAnalyzer
from app.analyzers.complexity_classes import ComplexityClass
from app.schemas.analysis import AnalyzeResponse


def parse_and_analyze(code: str) -> AnalyzeResponse:
    tree, error = SafeASTParser.parse_code(code)
    if error is not None:
        raise ValueError(f"Parse error: {error.message}")
    analyzer = ComplexityAnalyzer()
    return analyzer.analyze(tree)


# ==============================================================================
# 1. list.pop() vs list.pop(0)
# ==============================================================================
def test_1_list_pop_at_end_vs_pop_zero():
    code_pop_end = """
def pop_end(arr):
    for i in range(len(arr)):
        arr.pop()
"""
    res1 = parse_and_analyze(code_pop_end)
    assert res1.time_complexity == "O(n)"

    code_pop_zero = """
def pop_zero(arr):
    for i in range(len(arr)):
        arr.pop(0)
"""
    res2 = parse_and_analyze(code_pop_zero)
    assert res2.time_complexity == "O(n²)"


# ==============================================================================
# 2. Index-dependent list.pop(k)
# ==============================================================================
def test_2_index_dependent_pop_k():
    code_pop_k = """
def pop_k(arr):
    for i in range(len(arr)):
        arr.pop(1)
"""
    res1 = parse_and_analyze(code_pop_k)
    assert res1.time_complexity == "O(n²)"

    code_pop_last = """
def pop_last(arr):
    for i in range(len(arr)):
        arr.pop(-1)
"""
    res2 = parse_and_analyze(code_pop_last)
    assert res2.time_complexity == "O(n)"


# ==============================================================================
# 3. Append on known lists vs custom objects
# ==============================================================================
def test_3_append_known_list_vs_custom_object():
    code_list = """
def append_list(arr, items):
    for x in items:
        arr.append(x)
"""
    res1 = parse_and_analyze(code_list)
    assert res1.time_complexity in ("O(n)", "O(nm)", "O(n*m)")
    assert res1.analysis_complete is True

    code_custom = """
def append_custom(custom_obj, items):
    for x in items:
        custom_obj.custom_append(x)
"""
    res2 = parse_and_analyze(code_custom)
    assert res2.analysis_complete is False
    assert res2.analysis_status == "PARTIAL"


# ==============================================================================
# 4. Built-in print cost uncertainty (scalar vs container)
# ==============================================================================
def test_4_builtin_print_cost_uncertainty():
    code_scalar = """
def print_scalar(n):
    print("Done")
"""
    res1 = parse_and_analyze(code_scalar)
    assert res1.time_complexity == "O(1)"

    code_container = """
def print_container(arr):
    print(arr)
"""
    res2 = parse_and_analyze(code_container)
    assert res2.time_complexity == "O(n)"


# ==============================================================================
# 5. sorted with unresolved key function
# ==============================================================================
def test_5_sorted_with_unresolved_key_function():
    code_unresolved = """
def sort_items(arr):
    return sorted(arr, key=external_scorer)
"""
    res1 = parse_and_analyze(code_unresolved)
    assert res1.analysis_complete is False
    assert res1.analysis_status == "PARTIAL"

    code_standard = """
def sort_standard(arr):
    return sorted(arr)
"""
    res2 = parse_and_analyze(code_standard)
    assert res2.time_complexity == "O(n log n)"
    assert res2.analysis_complete is True


# ==============================================================================
# 6. sum over a known collection
# ==============================================================================
def test_6_sum_over_known_collection():
    code = """
def calculate_sum(arr):
    return sum(arr)
"""
    res = parse_and_analyze(code)
    assert res.time_complexity == "O(n)"
    assert res.analysis_complete is True


# ==============================================================================
# 7. sum over a generator with work
# ==============================================================================
def test_7_sum_over_generator_with_work():
    code = """
def helper(n):
    total = 0
    for i in range(n):
        total += i
    return total

def caller(n):
    return sum(helper(n) for _ in range(n))
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(n²)"


# ==============================================================================
# 8. @cache vs @lru_cache(maxsize=1)
# ==============================================================================
def test_8_cache_vs_lru_cache_maxsize_one():
    code_unbounded = """
from functools import cache

@cache
def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)
"""
    res1 = parse_and_analyze(code_unbounded)
    fa1 = {f["name"]: f for f in res1.function_analyses}
    assert fa1["fib"]["time_complexity"] == "O(n)"
    assert fa1["fib"]["space_complexity"] == "O(n)"

    # With maxsize=1, multi-branch Fibonacci thrashes the single-slot cache, remaining exponential!
    code_bounded = """
from functools import lru_cache

@lru_cache(maxsize=1)
def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)
"""
    res2 = parse_and_analyze(code_bounded)
    fa2 = {f["name"]: f for f in res2.function_analyses}
    assert fa2["fib"]["time_complexity"] in ("O(2^n)", "O(1.62^n)")


# ==============================================================================
# 9. Unknown decorators
# ==============================================================================
def test_9_unknown_decorator_flags_limitation():
    code = """
@third_party_profiler
def process(n):
    for i in range(n):
        pass
"""
    res = parse_and_analyze(code)
    assert res.confidence in ("MEDIUM", "LOW")
    assert len(res.limitations) > 0
    assert any("decorator" in lim.lower() for lim in res.limitations)


# ==============================================================================
# 10. Property access cost
# ==============================================================================
def test_10_property_access_cost():
    code = """
class DataService:
    @property
    def items(self):
        result = []
        for i in range(100):
            result.append(i)
        return result

def query_all(n, service):
    for i in range(n):
        x = service.items
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["query_all"] in ("O(n)", "O(n²)")


# ==============================================================================
# 11. Default argument evaluation
# ==============================================================================
def test_11_default_argument_evaluation():
    code = """
def helper(n):
    total = 0
    for i in range(n):
        total += i
    return total

def f(x=helper(100)):
    pass
"""
    res = parse_and_analyze(code)
    assert res.statistics.function_count >= 2


# ==============================================================================
# 12. Expensive generator call arguments
# ==============================================================================
def test_12_expensive_generator_call_arguments():
    code = """
def expensive(n):
    total = 0
    for i in range(n):
        for j in range(n):
            total += 1
    return total

def gen(k):
    for i in range(k):
        yield i

def caller(n):
    # Generator body is unconsumed (deferred), but call argument expensive(n) executes eagerly!
    g = gen(expensive(n))
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(n²)"


# ==============================================================================
# 13. Expensive coroutine call arguments
# ==============================================================================
def test_13_expensive_coroutine_call_arguments():
    code = """
def expensive(n):
    total = 0
    for i in range(n):
        total += i
    return total

async def worker(k):
    pass

def caller(n):
    # Coroutine body is unawaited (deferred), but call argument expensive(n) executes eagerly!
    c = worker(expensive(n))
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(n)"


# ==============================================================================
# 14. Partial generator consumption
# ==============================================================================
def test_14_partial_generator_consumption():
    code = """
def generate(n):
    for i in range(n):
        yield i

def caller(n):
    g = generate(n)
    return next(g)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(1)"


# ==============================================================================
# 15. Generator never consumed
# ==============================================================================
def test_15_generator_never_consumed():
    code = """
def generate(n):
    for i in range(n):
        yield i

def caller(n):
    g = generate(n)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(1)"


# ==============================================================================
# 16. Complete vs partial status invariants
# ==============================================================================
def test_16_complete_vs_partial_status_invariants():
    code_complete = """
def solve(n):
    for i in range(n):
        pass
"""
    res1 = parse_and_analyze(code_complete)
    assert res1.analysis_status == "COMPLETE"
    assert res1.analysis_complete is True

    code_partial = """
def solve(n):
    unknown_external(n)
"""
    res2 = parse_and_analyze(code_partial)
    assert res2.analysis_status == "PARTIAL"
    assert res2.analysis_complete is False


# ==============================================================================
# 17. Unversioned historical records
# ==============================================================================
def test_17_unversioned_historical_records():
    legacy_json = {
        "success": True,
        "time_complexity": "O(n²)",
        "space_complexity": "O(1)",
        "confidence": "HIGH",
        "complexity_reasoning": "Historical pre-1A analysis",
        "statistics": {
            "function_count": 1, "loop_count": 2, "for_loop_count": 2,
            "while_loop_count": 0, "conditional_count": 0, "max_nesting_depth": 2,
            "recursion_detected": False, "recursion_count": 0, "operation_count": 0,
            "comprehension_count": 0, "imported_modules": []
        },
        "structure": {"nodes": [], "edges": []},
        "graph": {"active_complexity": "O(n²)", "growth_points": []},
    }
    resp = AnalyzeResponse.model_validate(legacy_json)
    assert resp.analysis_schema_version is None
    assert resp.analysis_status == "LEGACY_RECORD"
    assert resp.analysis_complete is None


# ==============================================================================
# 18. Upper-bound vs tight-bound distinction
# ==============================================================================
def test_18_upper_bound_vs_tight_bound_distinction():
    c_upper = ComplexityClass.from_big_o("O(n²)")
    assert c_upper.big_o == "O(n²)"
    assert c_upper.is_tight is False
    assert c_upper.tight_bound == "Unknown"

    c_theta = ComplexityClass.from_big_o("Θ(n²)")
    assert c_theta.is_tight is True
    assert c_theta.tight_bound == "Θ(n²)"


# ==============================================================================
# 19. AST parsing errors before node validation
# ==============================================================================
def test_19_ast_parsing_errors_before_node_validation():
    # 1. Byte limit check happens before ast.parse
    huge_bytes = "# " + ("B" * 105_000)
    tree1, err1 = SafeASTParser.parse_code(huge_bytes)
    assert tree1 is None
    assert err1 is not None
    assert "size" in err1.message.lower()

    # 2. Line limit check happens before ast.parse
    many_lines = "\n".join(["x = 1"] * 3005)
    tree2, err2 = SafeASTParser.parse_code(many_lines)
    assert tree2 is None
    assert err2 is not None
    assert "line count" in err2.message.lower()

    # 3. Syntax error caught by parser
    syntax_err = "def foo(\n   bad_syntax +"
    tree3, err3 = SafeASTParser.parse_code(syntax_err)
    assert tree3 is None
    assert err3 is not None
    assert err3.line >= 1


# ==============================================================================
# 20. Recursive local work and aliased memory retention
# ==============================================================================
def test_20_recursive_local_work_and_aliased_memory_retention():
    # Recursive function with nested local loop: T(n) = T(n-1) + O(n^2) => Theta(n^3)
    code_rec = """
def rec_nested(n):
    if n <= 1:
        return 1
    total = 0
    for i in range(n):
        for j in range(n):
            total += 1
    return total + rec_nested(n - 1)
"""
    res1 = parse_and_analyze(code_rec)
    assert res1.time_complexity == "O(n³)"
    assert res1.tight_bound == "Θ(n³)"

    # Aliased helper allocation retained in loop: O(n^2) retained space
    code_aliased_space = """
def helper(n):
    return [0] * n

def caller(n):
    results = []
    for i in range(n):
        val = helper(n)
        results.append(val)
    return results
"""
    res2 = parse_and_analyze(code_aliased_space)
    fa = {f["name"]: f for f in res2.function_analyses}
    assert fa["caller"]["space_complexity"] == "O(n²)"
