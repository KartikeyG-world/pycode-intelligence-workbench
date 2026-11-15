import pytest
from app.analyzers.ast_parser import SafeASTParser
from app.analyzers.complexity_analyzer import ComplexityAnalyzer
from app.schemas.analysis import AnalyzeResponse


def parse_and_analyze(code: str) -> AnalyzeResponse:
    tree, error = SafeASTParser.parse_code(code)
    if error is not None:
        raise ValueError(f"Parse error: {error.message}")
    analyzer = ComplexityAnalyzer()
    return analyzer.analyze(tree)


# ==============================================================================
# GROUP A — RECURSIVE MATHEMATICS (10 Tests)
# ==============================================================================

def test_a1_mutual_even_odd_linear_recursion():
    code = """
def is_even(n):
    if n <= 0:
        return True
    return is_odd(n - 1)

def is_odd(n):
    if n <= 0:
        return False
    return is_even(n - 1)
"""
    res = parse_and_analyze(code)
    assert res.time_complexity == "O(n)"
    assert res.tight_bound == "Θ(n)"
    assert res.confidence in ("HIGH", "MEDIUM")


def test_a2_single_recursive_call_with_linear_local_loop():
    code = """
def recursive_work(n):
    if n <= 1:
        return 0
    total = 0
    for i in range(n):
        total += i
    return total + recursive_work(n - 1)
"""
    res = parse_and_analyze(code)
    assert res.time_complexity == "O(n²)"
    assert res.tight_bound == "Θ(n²)"


def test_a3_single_recursive_call_with_quadratic_local_loop():
    code = """
def rec_quad(n):
    if n <= 1:
        return 0
    total = 0
    for i in range(n):
        for j in range(n):
            total += 1
    return total + rec_quad(n - 1)
"""
    res = parse_and_analyze(code)
    assert res.time_complexity == "O(n³)"
    assert res.tight_bound == "Θ(n³)"


def test_a4_multiple_recursive_calls_in_same_execution_path():
    code = """
def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)
"""
    res = parse_and_analyze(code)
    assert res.time_complexity in ("O(2^n)", "O(1.62^n)")
    assert res.recurrence.branching_factor >= 2


def test_a5_recursive_calls_in_mutually_exclusive_branches():
    code = """
def branch_rec(n):
    if n <= 1:
        return 0
    if n % 2 == 0:
        return branch_rec(n - 1)
    else:
        return branch_rec(n - 2)
"""
    res = parse_and_analyze(code)
    assert res.time_complexity == "O(n)"
    assert res.recurrence.branching_factor == 1


def test_a6_exponential_branching_recursion():
    code = """
def triple_branch(n):
    if n <= 1:
        return 1
    return triple_branch(n - 1) + triple_branch(n - 1) + triple_branch(n - 1)
"""
    res = parse_and_analyze(code)
    assert res.time_complexity in ("O(3^n)", "O(2^n)")
    assert res.recurrence.branching_factor == 3


def test_a7_two_independent_recursive_functions():
    code = """
def rec_linear(n):
    if n <= 1:
        return 1
    return rec_linear(n - 1)

def rec_exp(n):
    if n <= 1:
        return 1
    return rec_exp(n - 1) + rec_exp(n - 1)
"""
    res = parse_and_analyze(code)
    assert res.analysis_scope == "function_collection"
    assert res.time_complexity in ("O(2^n)", "O(2^n)")
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["rec_linear"] == "O(n)"
    assert fa["rec_exp"] in ("O(2^n)", "O(2^n)")


def test_a8_unreachable_recursive_function():
    code = """
def unused_rec(n):
    if n <= 1:
        return 1
    return unused_rec(n - 1) + unused_rec(n - 1)

def main(n):
    for i in range(n):
        print(i)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["main"] == "O(n)"
    assert fa["unused_rec"] in ("O(2^n)", "O(2^n)")


def test_a9_recursive_helper_called_in_loop():
    code = """
def binary_search(arr, low, high, x):
    if high >= low:
        mid = (high + low) // 2
        if arr[mid] == x:
            return mid
        elif arr[mid] > x:
            return binary_search(arr, low, mid - 1, x)
        else:
            return binary_search(arr, mid + 1, high, x)
    return -1

def search_all(arr, queries):
    n = len(queries)
    for q in queries:
        binary_search(arr, 0, len(arr) - 1, q)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["binary_search"] == "O(log n)"
    assert fa["search_all"] == "O(n log n)"


def test_a10_unsupported_mutual_recursion_unresolved_argument():
    code = """
def f(n):
    if n <= 0:
        return True
    return g(external_func(n))

def g(n):
    if n <= 0:
        return False
    return f(external_func(n))
"""
    res = parse_and_analyze(code)
    assert res.confidence in ("LOW", "UNSUPPORTED")
    assert res.analysis_complete is False


# ==============================================================================
# GROUP B — INPUT-SIZE PROPAGATION (10 Tests)
# ==============================================================================

def test_b1_helper_receives_constant_repeated_n_times():
    code = """
def helper(value):
    for i in range(value):
        pass

def caller(n):
    for i in range(n):
        helper(10)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(n)"


def test_b2_helper_receives_original_input_size_n():
    code = """
def helper(value):
    for i in range(value):
        pass

def caller(n):
    for i in range(n):
        helper(n)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(n²)"


def test_b3_helper_receives_original_input_collection():
    code = """
def helper(items):
    for item in items:
        pass

def caller(items):
    for i in range(len(items)):
        helper(items)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(n²)"


def test_b4_helper_receives_half_input_size():
    code = """
def helper(value):
    for i in range(value):
        pass

def caller(n):
    for i in range(n):
        helper(n // 2)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(n²)"


def test_b5_helper_receives_loop_variable_i():
    code = """
def helper(value):
    for j in range(value):
        pass

def caller(n):
    for i in range(n):
        helper(i)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(n²)"


def test_b6_helper_receives_collection_slice():
    code = """
def helper(items):
    for item in items:
        pass

def caller(items):
    for i in range(len(items)):
        helper(items[:i])
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(n²)"


def test_b7_two_independent_input_sizes():
    code = """
def helper(items):
    for item in items:
        pass

def caller(n, items):
    for i in range(n):
        helper(items)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] in ("O(nm)", "O(n*m)", "O(n²)")


def test_b8_unknown_argument_expression():
    code = """
def helper(value):
    for i in range(value):
        pass

def caller(n):
    for i in range(n):
        helper(external_lookup())
"""
    res = parse_and_analyze(code)
    assert res.analysis_complete is False


def test_b9_aliased_collection():
    code = """
def helper(items):
    for item in items:
        pass

def caller(items):
    alias = items
    for i in range(len(items)):
        helper(alias)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(n²)"


def test_b10_shadowed_identifier():
    code = """
def helper():
    for i in range(100):
        pass

def caller(n):
    helper = 5
    for i in range(n):
        pass
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(n)"


# ==============================================================================
# GROUP C — TIME AND MEMORY COMPOSITION (10 Tests)
# ==============================================================================

def test_c1_sequential_helper_calls_dominance():
    code = """
def helper_linear(n):
    for i in range(n):
        pass

def helper_quad(n):
    for i in range(n):
        for j in range(n):
            pass

def caller(n):
    helper_linear(n)
    helper_quad(n)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(n²)"


def test_c2_repeated_helper_calls_in_loop():
    code = """
def helper(n):
    for i in range(n):
        pass

def caller(n):
    for i in range(n):
        helper(n)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(n²)"


def test_c3_temporary_allocation_returned_and_discarded():
    code = """
def helper(n):
    temp = [0] * n
    return sum(temp)

def caller(n):
    for i in range(n):
        helper(n)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f for f in res.function_analyses}
    assert fa["caller"]["time_complexity"] == "O(n²)"
    assert fa["caller"]["space_complexity"] == "O(n)"


def test_c4_repeated_returned_allocations_retained_in_list():
    code = """
def helper(n):
    return [0] * n

def caller(n):
    results = []
    for i in range(n):
        results.append(helper(n))
    return results
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f for f in res.function_analyses}
    assert fa["caller"]["time_complexity"] == "O(n²)"
    assert fa["caller"]["space_complexity"] == "O(n²)"


def test_c5_nested_active_function_frames():
    code = """
def c(n):
    return n

def b(n):
    return c(n)

def a(n):
    return b(n)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["a"] == "O(1)"


def test_c6_repeated_sequential_recursion():
    code = """
def rec_linear(n):
    if n <= 1:
        return 1
    return rec_linear(n - 1)

def caller(n):
    rec_linear(n)
    rec_linear(n)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(n)"


def test_c7_returned_collection():
    code = """
def make_list(n):
    return [i for i in range(n)]

def caller(n):
    data = make_list(n)
    return data
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f for f in res.function_analyses}
    assert fa["caller"]["space_complexity"] == "O(n)"


def test_c8_aliased_output_objects():
    code = """
def create_grid(n):
    return [[0] * n for _ in range(n)]

def caller(n):
    grid = create_grid(n)
    ref = grid
    return ref
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f for f in res.function_analyses}
    assert fa["caller"]["space_complexity"] == "O(n²)"


def test_c9_unknown_object_retention():
    code = """
def caller(n):
    external_service.store([i for i in range(n)])
"""
    res = parse_and_analyze(code)
    assert res.analysis_complete is False


def test_c10_distinction_cumulative_allocations_vs_peak_live():
    code = """
def helper(n):
    temp = [0] * n
    return len(temp)

def caller(n):
    total = 0
    for i in range(n):
        total += helper(n)
    return total
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f for f in res.function_analyses}
    # Time is O(n^2), Peak Auxiliary Space is O(n)
    assert fa["caller"]["time_complexity"] == "O(n²)"
    assert fa["caller"]["space_complexity"] == "O(n)"


# ==============================================================================
# GROUP D — GENERATOR SEMANTICS (7 Tests)
# ==============================================================================

def test_d1_generator_function_creation_only():
    code = """
def generate(n):
    for i in range(n):
        yield i
"""
    res = parse_and_analyze(code)
    assert res.function_analyses[0]["func_type"] == "generator"


def test_d2_generator_creation_without_consumption():
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
    assert fa["generate"] == "O(n)"


def test_d3_full_iteration_through_generator():
    code = """
def generate(n):
    for i in range(n):
        yield i

def caller(n):
    for x in generate(n):
        pass
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(n)"


def test_d4_list_generator_consumption():
    code = """
def generate(n):
    for i in range(n):
        yield i

def caller(n):
    items = list(generate(n))
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(n)"


def test_d5_single_next_call():
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


def test_d6_yield_from_delegation():
    code = """
def sub_gen(n):
    for i in range(n):
        yield i

def main_gen(n):
    yield from sub_gen(n)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["func_type"] for f in res.function_analyses}
    assert fa["sub_gen"] == "generator"
    assert fa["main_gen"] == "generator"


def test_d7_generator_passed_to_unknown_consumer():
    code = """
def generate(n):
    for i in range(n):
        yield i

def caller(n):
    external_sink(generate(n))
"""
    res = parse_and_analyze(code)
    assert res.analysis_complete is False


# ==============================================================================
# GROUP E — ASYNC SEMANTICS (7 Tests)
# ==============================================================================

def test_e1_coroutine_function_definition():
    code = """
async def process(n):
    for i in range(n):
        pass
"""
    res = parse_and_analyze(code)
    assert res.function_analyses[0]["func_type"] == "async_function"


def test_e2_coroutine_object_creation_without_await():
    code = """
async def process(n):
    for i in range(n):
        pass

def caller(n):
    coro = process(n)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(1)"
    assert fa["process"] == "O(n)"


def test_e3_direct_await_of_known_coroutine():
    code = """
async def process(n):
    for i in range(n):
        pass

async def caller(n):
    await process(n)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(n)"


def test_e4_coroutine_calls_with_unresolved_dependencies():
    code = """
async def process(n):
    await external_api.fetch(n)
"""
    res = parse_and_analyze(code)
    assert res.analysis_complete is False


def test_e5_async_generator_creation():
    code = """
async def async_gen(n):
    for i in range(n):
        yield i
"""
    res = parse_and_analyze(code)
    assert res.function_analyses[0]["func_type"] == "async_generator"


def test_e6_async_generator_consumption():
    code = """
async def async_gen(n):
    for i in range(n):
        yield i

async def consumer(n):
    async for x in async_gen(n):
        pass
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["func_type"] for f in res.function_analyses}
    assert fa["async_gen"] == "async_generator"


def test_e7_unsupported_concurrency_patterns():
    code = """
import asyncio

async def worker(n):
    pass

async def main(n):
    await asyncio.gather(*(worker(n) for _ in range(n)))
"""
    res = parse_and_analyze(code)
    assert res.analysis_complete is False or res.confidence in ("MEDIUM", "LOW")


# ==============================================================================
# GROUP F — DECORATORS AND DEFINITION-TIME EXECUTION (7 Tests)
# ==============================================================================

def test_f1_plain_uncalled_function_definition():
    code = """
def uncalled(n):
    for i in range(n):
        for j in range(n):
            pass
"""
    res = parse_and_analyze(code)
    assert res.analysis_scope == "function"
    assert res.function_analyses[0]["time_complexity"] == "O(n²)"


def test_f2_function_with_default_expression():
    code = """
def foo(x=sum([1, 2, 3])):
    return x
"""
    res = parse_and_analyze(code)
    assert res.function_analyses[0]["time_complexity"] == "O(1)"


def test_f3_function_with_known_safe_decorator():
    code = """
class MyMath:
    @staticmethod
    def add(a, b):
        return a + b
"""
    res = parse_and_analyze(code)
    assert res.function_analyses[0]["confidence"] == "HIGH"


def test_f4_unknown_decorator_flags_limitation():
    code = """
@custom_wrapper
def compute(n):
    return n
"""
    res = parse_and_analyze(code)
    assert any("custom_wrapper" in lim for lim in res.limitations)
    assert res.confidence in ("MEDIUM", "LOW")


def test_f5_class_body_execution():
    code = """
class MyConfig:
    total = 0
    for i in range(10):
        total += i
"""
    res = parse_and_analyze(code)
    assert res.time_complexity in ("O(1)", "O(n)")


def test_f6_method_call_on_known_class():
    code = """
class Calculator:
    def square(self, n):
        for i in range(n):
            pass
        return n
"""
    res = parse_and_analyze(code)
    assert res.function_analyses[0]["time_complexity"] == "O(n)"


def test_f7_unknown_dynamic_method_resolution():
    code = """
def execute_query(handler, data):
    handler.custom_run(data)
"""
    res = parse_and_analyze(code)
    assert res.analysis_complete is False


# ==============================================================================
# GROUP G — BUILT-IN CONTAINER COST MODELS (10 Tests)
# ==============================================================================

def test_g1_list_append():
    code = """
def populate(n):
    items = []
    for i in range(n):
        items.append(i)
"""
    res = parse_and_analyze(code)
    assert res.time_complexity == "O(n)"


def test_g2_list_pop_at_end():
    code = """
def drain(arr):
    for i in range(len(arr)):
        arr.pop()
"""
    res = parse_and_analyze(code)
    assert res.time_complexity == "O(n)"


def test_g3_list_pop_at_index_zero():
    code = """
def drain_front(arr):
    for i in range(len(arr)):
        arr.pop(0)
"""
    res = parse_and_analyze(code)
    assert res.time_complexity == "O(n²)"


def test_g4_list_insert_at_index_zero():
    code = """
def prepend_all(arr, items):
    for x in items:
        arr.insert(0, x)
"""
    res = parse_and_analyze(code)
    assert res.time_complexity in ("O(n²)", "O(nm)")


def test_g5_list_copy():
    code = """
def duplicate(arr):
    for i in range(len(arr)):
        arr.copy()
"""
    res = parse_and_analyze(code)
    assert res.time_complexity == "O(n²)"


def test_g6_list_membership():
    code = """
def find_all(arr, queries):
    for q in queries:
        if q in arr:
            pass
"""
    res = parse_and_analyze(code)
    assert res.time_complexity == "O(n²)"


def test_g7_list_slicing():
    code = """
def slice_all(arr):
    for i in range(len(arr)):
        sub = arr[:i]
"""
    res = parse_and_analyze(code)
    assert res.time_complexity == "O(n²)"


def test_g8_dictionary_lookup():
    code = """
def lookup_keys(mapping, keys):
    for k in keys:
        mapping.get(k)
"""
    res = parse_and_analyze(code)
    assert res.time_complexity == "O(n)"


def test_g9_set_membership():
    code = """
def check_set(unique_set, items):
    for item in items:
        if item in unique_set:
            pass
"""
    res = parse_and_analyze(code)
    assert res.time_complexity == "O(n)"


def test_g10_unknown_custom_object_method():
    code = """
def custom_pop(my_obj):
    for i in range(10):
        my_obj.custom_pop()
"""
    res = parse_and_analyze(code)
    assert res.analysis_complete is False


# ==============================================================================
# GROUP H — METADATA AND LEGACY DATA (10 Tests)
# ==============================================================================

def test_h1_complete_analysis():
    code = """
def solve(n):
    total = 0
    for i in range(n):
        total += i
    return total
"""
    res = parse_and_analyze(code)
    assert res.call_graph_complete is True
    assert res.cost_model_complete is True
    assert res.analysis_complete is True
    assert res.analysis_status == "COMPLETE"


def test_h2_partial_analysis():
    code = """
def solve(n):
    external_call(n)
    for i in range(n):
        pass
"""
    res = parse_and_analyze(code)
    assert res.analysis_complete is False
    assert res.analysis_status == "PARTIAL"


def test_h3_unknown_external_cost():
    code = """
def run():
    import numpy as np
    return np.linalg.inv([[1, 2], [3, 4]])
"""
    res = parse_and_analyze(code)
    assert res.analysis_complete is False


def test_h4_unsupported_dynamic_dispatch():
    code = """
def process(handler, x):
    getattr(handler, 'run')(x)
"""
    res = parse_and_analyze(code)
    assert res.analysis_complete is False


def test_h5_legacy_result_deserialization():
    # Legacy record missing new fields deserializes with explicit nullable/defaults
    legacy_data = {
        "success": True,
        "time_complexity": "O(n)",
        "space_complexity": "O(1)",
        "confidence": "HIGH",
        "complexity_reasoning": "Legacy reasoning",
        "statistics": {
            "function_count": 1, "loop_count": 1, "for_loop_count": 1,
            "while_loop_count": 0, "conditional_count": 0, "max_nesting_depth": 1,
            "recursion_detected": False, "recursion_count": 0, "operation_count": 0,
            "comprehension_count": 0, "imported_modules": []
        },
        "structure": {"nodes": [], "edges": []},
        "graph": {"active_complexity": "O(n)", "growth_points": []},
    }
    resp = AnalyzeResponse.model_validate(legacy_data)
    assert resp.analysis_schema_version is None
    assert resp.analysis_status == "LEGACY_RECORD"
    assert resp.analysis_complete is None
    assert resp.analysis_scope is None


def test_h6_missing_analysis_scope_handling():
    legacy_data = {
        "success": True,
        "time_complexity": "O(1)",
        "space_complexity": "O(1)",
        "confidence": "HIGH",
        "complexity_reasoning": "Reasoning",
        "statistics": {
            "function_count": 0, "loop_count": 0, "for_loop_count": 0,
            "while_loop_count": 0, "conditional_count": 0, "max_nesting_depth": 0,
            "recursion_detected": False, "recursion_count": 0, "operation_count": 0,
            "comprehension_count": 0, "imported_modules": []
        },
        "structure": {"nodes": [], "edges": []},
        "graph": {"active_complexity": "O(1)", "growth_points": []},
    }
    resp = AnalyzeResponse.model_validate(legacy_data)
    assert resp.analysis_scope is None


def test_h7_missing_confidence_evidence():
    code = """
def unknown_func(n):
    return unknown_backend(n)
"""
    res = parse_and_analyze(code)
    assert res.confidence in ("LOW", "UNSUPPORTED")


def test_h8_existing_database_record_compatibility():
    # Verifies serialization and deserialization roundtrip
    code = "def f(n):\n    return n"
    res = parse_and_analyze(code)
    data = res.model_dump()
    reconstructed = AnalyzeResponse.model_validate(data)
    assert reconstructed.time_complexity == res.time_complexity
    assert reconstructed.analysis_complete == res.analysis_complete


def test_h9_new_analysis_serialization():
    code = "def f(n):\n    for i in range(n): pass"
    res = parse_and_analyze(code)
    serialized = res.model_dump_json()
    assert "analysis_schema_version" in serialized
    assert "analysis_status" in serialized


def test_h10_analysis_schema_version():
    code = "x = 1"
    res = parse_and_analyze(code)
    assert res.analysis_schema_version == "1.1"


# ==============================================================================
# GROUP I — RESOURCE PROTECTION (6 Tests)
# ==============================================================================

def test_i1_input_byte_limit_violation():
    huge_code = "# " + ("A" * 105_000)
    tree, error = SafeASTParser.parse_code(huge_code)
    assert tree is None
    assert error is not None
    assert "size" in error.message.lower()


def test_i2_input_line_limit_violation():
    many_lines = "\n".join(["x = 1"] * 3050)
    tree, error = SafeASTParser.parse_code(many_lines)
    assert tree is None
    assert error is not None
    assert "line count" in error.message.lower()


def test_i3_deep_ast_structure_protection():
    # Build a 250-level nested expression e.g. (1 + (1 + ...))
    deep_expr = "1"
    for _ in range(250):
        deep_expr = f"({deep_expr} + 1)"
    tree, error = SafeASTParser.parse_code(deep_expr)
    assert tree is None
    assert error is not None
    assert "depth" in error.message.lower() or "limit" in error.message.lower() or "nested" in error.message.lower() or "parentheses" in error.message.lower()


def test_i4_excessive_node_count_protection():
    # 15,000 additions: 1 + 1 + 1 + ...
    big_addition = " + ".join(["1"] * 12_000)
    tree, error = SafeASTParser.parse_code(big_addition)
    assert tree is None
    assert error is not None
    assert "node count" in error.message.lower() or "limit" in error.message.lower()


def test_i5_malformed_syntax_handling():
    syntax_error_code = "def foo(\n   print('unclosed'"
    tree, error = SafeASTParser.parse_code(syntax_error_code)
    assert tree is None
    assert error is not None
    assert error.line >= 1


def test_i6_controlled_traversal_failure():
    # Bounded AST doesn't cause recursion crash in analyzer
    nested_blocks = "x = 1\n"
    for _ in range(50):
        nested_blocks = "if True:\n" + "\n".join("    " + line if line else "" for line in nested_blocks.splitlines()) + "\n"
    res = parse_and_analyze(nested_blocks)
    assert res.time_complexity == "O(1)"


# ==============================================================================
# METAMORPHIC AND PROPERTY-BASED VALIDATION (10 Tests)
# ==============================================================================

def test_m1_renaming_local_variable_preserves_complexity():
    code1 = "def f(n):\n    total = 0\n    for i in range(n):\n        total += i\n    return total"
    code2 = "def f(n):\n    accumulator = 0\n    for idx in range(n):\n        accumulator += idx\n    return accumulator"
    res1 = parse_and_analyze(code1)
    res2 = parse_and_analyze(code2)
    assert res1.time_complexity == res2.time_complexity == "O(n)"
    assert res1.space_complexity == res2.space_complexity == "O(1)"


def test_m2_adding_comments_preserves_complexity():
    code1 = "def f(n):\n    for i in range(n):\n        pass"
    code2 = "# Explanation\ndef f(n):\n    # Inner loop\n    for i in range(n):\n        # Pass\n        pass"
    res1 = parse_and_analyze(code1)
    res2 = parse_and_analyze(code2)
    assert res1.time_complexity == res2.time_complexity == "O(n)"


def test_m3_adding_unreachable_function_preserves_module_complexity():
    code1 = "for i in range(10):\n    print(i)"
    code2 = "def uncalled(n):\n    for i in range(n):\n        for j in range(n):\n            pass\nfor i in range(10):\n    print(i)"
    res1 = parse_and_analyze(code1)
    res2 = parse_and_analyze(code2)
    assert res1.time_complexity == res2.time_complexity == "O(1)"


def test_m4_adding_sequential_linear_preserves_quadratic():
    code1 = "def f(n):\n    for i in range(n):\n        for j in range(n):\n            pass"
    code2 = "def f(n):\n    for i in range(n):\n        for j in range(n):\n            pass\n    for k in range(n):\n        pass"
    res1 = parse_and_analyze(code1)
    res2 = parse_and_analyze(code2)
    assert res1.time_complexity == res2.time_complexity == "O(n²)"


def test_m5_calling_linear_helper_in_linear_loop_produces_quadratic():
    code = """
def helper(n):
    for i in range(n):
        pass

def caller(n):
    for i in range(n):
        helper(n)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(n²)"


def test_m6_calling_constant_helper_in_linear_loop_produces_linear():
    code = """
def helper():
    return 42

def caller(n):
    for i in range(n):
        helper()
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(n)"


def test_m7_constant_argument_does_not_inherit_caller_input_size():
    code = """
def helper(x):
    for i in range(x):
        pass

def caller(n):
    for i in range(n):
        helper(5)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(n)"


def test_m8_making_helper_argument_input_sized_updates_cost():
    code_const = "def h(x):\n    for i in range(x): pass\ndef c(n):\n    for i in range(n): h(5)"
    code_var = "def h(x):\n    for i in range(x): pass\ndef c(n):\n    for i in range(n): h(n)"
    res_c = parse_and_analyze(code_const)
    res_v = parse_and_analyze(code_var)
    fa_c = {f["name"]: f["time_complexity"] for f in res_c.function_analyses}
    fa_v = {f["name"]: f["time_complexity"] for f in res_v.function_analyses}
    assert fa_c["c"] == "O(n)"
    assert fa_v["c"] == "O(n²)"


def test_m9_unconsumed_generator_does_not_execute_body():
    code = """
def my_gen(n):
    for i in range(n):
        for j in range(n):
            yield i * j

def caller(n):
    g = my_gen(n)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(1)"
    assert fa["my_gen"] == "O(n²)"


def test_m10_unawaited_coroutine_does_not_execute_body():
    code = """
async def my_coro(n):
    for i in range(n):
        pass

def caller(n):
    c = my_coro(n)
"""
    res = parse_and_analyze(code)
    fa = {f["name"]: f["time_complexity"] for f in res.function_analyses}
    assert fa["caller"] == "O(1)"
    assert fa["my_coro"] == "O(n)"
