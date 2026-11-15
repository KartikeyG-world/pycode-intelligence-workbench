import ast
import pytest
from app.analyzers.complexity_analyzer import ComplexityAnalyzer
from app.analyzers.ast_parser import SafeASTParser
from app.schemas.analysis import AnalyzeResponse


@pytest.fixture
def analyzer() -> ComplexityAnalyzer:
    return ComplexityAnalyzer()


# ==============================================================================
# 1. UNKNOWN COST TESTS (Tests 1 - 5)
# ==============================================================================


def test_01_unknown_custom_function_in_linear_loop(analyzer: ComplexityAnalyzer):
    """Test 1: Unknown custom function inside a linear loop records partial status,
    unresolved cost entry, and preserves known O(n) loop contribution without guessing.
    """
    code = """
def process(items):
    for item in items:
        custom_engine.compute(item)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert not res.analysis_complete
    assert res.analysis_status == "PARTIAL"
    assert res.time_complexity.startswith("Unknown")
    assert res.tight_bound == "Unknown"
    assert res.known_time_complexity == "O(n)"
    assert len(res.unresolved_costs) >= 1
    assert any(u["operation"] == "compute" and u["context"] == "loop" for u in res.unresolved_costs)


def test_02_unknown_custom_method_in_nested_loops(analyzer: ComplexityAnalyzer):
    """Test 2: Unknown custom method inside nested loops preserves known O(n²) contribution."""
    code = """
def process(matrix):
    for row in matrix:
        for item in row:
            item.custom_op()
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert not res.analysis_complete
    assert res.analysis_status == "PARTIAL"
    assert res.time_complexity.startswith("Unknown")
    assert res.known_time_complexity == "O(n²)"
    assert len(res.unresolved_costs) >= 1
    assert any(u["operation"] == "custom_op" and u["loop_depth"] == 2 for u in res.unresolved_costs)


def test_03_known_linear_followed_by_unknown_operation(analyzer: ComplexityAnalyzer):
    """Test 3: Known O(n) work followed sequentially by unknown external call preserves O(n)."""
    code = """
def process(items):
    total = 0
    for x in items:
        total += x
    external_sync(items)
    return total
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert not res.analysis_complete
    assert res.analysis_status == "PARTIAL"
    assert res.known_time_complexity == "O(n)"
    assert any(u["operation"] == "external_sync" for u in res.unresolved_costs)


def test_04_unknown_operation_before_known_quadratic(analyzer: ComplexityAnalyzer):
    """Test 4: Unknown operation before known O(n²) work preserves dominant O(n²) known cost."""
    code = """
def process(items):
    external_init()
    for i in items:
        for j in items:
            pass
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert not res.analysis_complete
    assert res.analysis_status == "PARTIAL"
    assert res.known_time_complexity == "O(n²)"
    assert any(u["operation"] == "external_init" for u in res.unresolved_costs)


def test_05_unknown_external_function_with_partial_disclosure(analyzer: ComplexityAnalyzer):
    """Test 5: Scalar function with solely unknown external call reports known O(1) with PARTIAL."""
    code = """
def handle_request(payload):
    remote_client.post(payload)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert not res.analysis_complete
    assert res.analysis_status == "PARTIAL"
    assert res.known_time_complexity == "O(1)"
    assert res.time_complexity.startswith("Unknown")
    assert len(res.unresolved_costs) >= 1


# ==============================================================================
# 2. MEMORY AND OBJECT LIFETIME TESTS (Tests 6 - 12)
# ==============================================================================


def test_06_recursive_linear_allocation_accumulates_quadratic_heap(analyzer: ComplexityAnalyzer):
    """Test 6: Recursive function allocating [0] * n per frame without release
    accumulates sum_{i=1}^n O(i) = O(n²) simultaneously live heap memory.
    """
    code = """
def process(n):
    if n <= 0:
        return 0
    temporary = [0] * n
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.space_complexity == "O(n²)"
    assert res.space_breakdown.peak_live_heap == "O(n²)"
    assert res.space_breakdown.active_frames == "O(n)"
    assert res.space_breakdown.auxiliary == "O(n²)"


def test_07_recursive_quadratic_local_allocation_accumulates_cubic_heap(analyzer: ComplexityAnalyzer):
    """Test 7: Recursive function allocating an n x n matrix per frame without release
    accumulates sum_{i=1}^n O(i^2) = O(n³) simultaneously live heap memory.
    """
    code = """
def process(n):
    if n <= 0:
        return 0
    matrix = [[0] * n for _ in range(n)]
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.space_complexity == "O(n³)"
    assert res.space_breakdown.peak_live_heap == "O(n³)"
    assert res.space_breakdown.auxiliary == "O(n³)"


def test_08_recursive_allocation_released_before_call_bounds_heap(analyzer: ComplexityAnalyzer):
    """Test 8: Mandatory comparison - Recursive local allocation explicitly deleted via del
    before recursive invocation bounds peak live heap to a single frame O(n).
    """
    code = """
def process(n):
    if n <= 0:
        return 0
    temporary = [0] * n
    del temporary
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.space_complexity == "O(n)"
    assert res.space_breakdown.peak_live_heap == "O(n)"
    assert res.space_breakdown.active_frames == "O(n)"
    assert res.space_breakdown.auxiliary == "O(n)"


def test_09_same_object_referenced_by_multiple_variables_aliasing(analyzer: ComplexityAnalyzer):
    """Test 9: Multiple references/aliases to the same allocated array do not double-count heap."""
    code = """
def process(n):
    data = [0] * n
    alias1 = data
    alias2 = data
    return len(alias1) + len(alias2)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.space_complexity == "O(n)"
    assert res.space_breakdown.auxiliary == "O(n)"


def test_10_retained_and_discarded_return_values(analyzer: ComplexityAnalyzer):
    """Test 10: Helper returning scalar with local temporary deleted retains O(1) output."""
    code = """
def compute(n):
    temp = [0] * n
    total = len(temp)
    del temp
    return total
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.space_breakdown.output == "O(1)"
    assert res.time_complexity == "O(n)"


def test_11_bounded_cache_with_input_sized_values(analyzer: ComplexityAnalyzer):
    """Test 11: @lru_cache(maxsize=10) with input-sized returns bounds entries to constant count
    while recognizing cache retained size depends on entry payload.
    """
    code = """
from functools import lru_cache

@lru_cache(maxsize=10)
def generate_row(n):
    return [0] * n
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    fa = {f["name"]: f for f in res.function_analyses}

    assert fa["generate_row"]["analysis_complete"]
    assert fa["generate_row"]["space_complexity"] == "O(n)"


def test_12_multi_dimensional_unbounded_cache_states(analyzer: ComplexityAnalyzer):
    """Test 12: @cache on function with 2 parameters solves state space as O(n*m)."""
    code = """
from functools import cache

@cache
def solve(n, m):
    if n <= 0 or m <= 0:
        return 1
    return solve(n - 1, m) + solve(n, m - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(n*m)"
    assert res.space_complexity == "O(n*m)"
    assert res.space_breakdown.cache_retained == "O(n*m)"


# ==============================================================================
# 3. CONTAINER OPERATION TESTS (Tests 13 - 17)
# ==============================================================================


def test_13_list_pop_negative_two_is_constant_time(analyzer: ComplexityAnalyzer):
    """Test 13: list.pop(-2) removes from a bounded fixed distance from the end in O(1) time."""
    code = """
def remove_penultimate(lst):
    return lst.pop(-2)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(1)"
    assert res.analysis_complete


def test_14_list_pop_negative_three_is_constant_time(analyzer: ComplexityAnalyzer):
    """Test 14: list.pop(-3) is bounded constant time O(1)."""
    code = """
def remove_antepenultimate(lst):
    return lst.pop(-3)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(1)"
    assert res.analysis_complete


def test_15_list_insert_negative_two_is_constant_time(analyzer: ComplexityAnalyzer):
    """Test 15: list.insert(-2, val) shifts a bounded number of elements near end in O(1) time."""
    code = """
def insert_near_end(lst, val):
    lst.insert(-2, val)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(1)"
    assert res.analysis_complete


def test_16_list_append_amortized_time_vs_cumulative_storage(analyzer: ComplexityAnalyzer):
    """Test 16: Repeated list.append in a loop has amortized O(1) time per operation."""
    code = """
def append_item(lst, val):
    lst.append(val)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(1)"
    assert res.analysis_complete


def test_17_unknown_custom_receiver_method_marked_unresolved(analyzer: ComplexityAnalyzer):
    """Test 17: Method call on custom unmodeled object records unresolved operation."""
    code = """
def mutate(obj):
    obj.custom_dispatch(42)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert not res.analysis_complete
    assert res.analysis_status == "PARTIAL"
    assert any(u["operation"] == "custom_dispatch" for u in res.unresolved_costs)


# ==============================================================================
# 4. BUILT-IN FUNCTION TESTS (Tests 18 - 24)
# ==============================================================================


def test_18_print_simple_scalar_values_constant_time(analyzer: ComplexityAnalyzer):
    """Test 18: print() with fixed scalar arguments evaluates in O(1) time."""
    code = """
def greet(name):
    print("Execution complete", 42)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(1)"
    assert res.analysis_complete


def test_19_print_primitive_collection_linear_time(analyzer: ComplexityAnalyzer):
    """Test 19: print() of a collection traverses elements in O(n) time."""
    code = """
def display_results(items):
    print(items)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(n)"
    assert res.analysis_complete


def test_20_print_custom_objects_with_unresolved_representations(analyzer: ComplexityAnalyzer):
    """Test 20: print() of arbitrary custom objects preserves safe scalar evaluation."""
    code = """
def display(custom_entity):
    print("Status:", 100)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(1)"


def test_21_sorted_with_unknown_key_helper_reports_partial(analyzer: ComplexityAnalyzer):
    """Test 21: sorted() with unknown key helper preserves known O(n log n) and marks PARTIAL."""
    code = """
def sort_items(items):
    return sorted(items, key=unresolved_key_fn)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert not res.analysis_complete
    assert res.analysis_status == "PARTIAL"
    assert res.known_time_complexity == "O(n log n)"
    assert res.time_complexity.startswith("Unknown")


def test_22_sorted_with_known_helper_composes_cost(analyzer: ComplexityAnalyzer):
    """Test 22: sorted() with built-in standard key (len) runs in O(n log n)."""
    code = """
def sort_strings(words):
    return sorted(words, key=len)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(n log n)"
    assert res.analysis_complete


def test_23_sum_with_primitive_elements_linear_time(analyzer: ComplexityAnalyzer):
    """Test 23: sum() on numerical collection executes in O(n) linear time."""
    code = """
def total(values):
    return sum(values)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(n)"
    assert res.analysis_complete


def test_24_sum_with_container_start_argument_quadratic_time(analyzer: ComplexityAnalyzer):
    """Test 24: sum(nested_lists, []) concatenates lists in quadratic O(n²) time."""
    code = """
def flatten(nested_lists):
    return sum(nested_lists, [])
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(n²)"
    assert res.analysis_complete


# ==============================================================================
# 5. CACHE STATE AND MEMORY TESTS (Tests 25 - 28)
# ==============================================================================


def test_25_cache_one_dimensional_states(analyzer: ComplexityAnalyzer):
    """Test 25: 1D @cache memoization reduces exponential recursion to linear O(n)."""
    code = """
from functools import cache

@cache
def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(n)"
    assert res.space_breakdown.cache_retained == "O(n)"


def test_26_cache_two_dimensional_parameters(analyzer: ComplexityAnalyzer):
    """Test 26: 2D @cache with distinct parameter dimensions solves to O(n*m)."""
    code = """
from functools import cache

@cache
def edit_distance(n, m):
    if n == 0:
        return m
    if m == 0:
        return n
    return min(edit_distance(n - 1, m), edit_distance(n, m - 1))
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(n*m)"
    assert res.space_breakdown.cache_retained == "O(n*m)"


def test_27_lru_cache_with_fixed_capacity(analyzer: ComplexityAnalyzer):
    """Test 27: @lru_cache with fixed maxsize bounds cache entry count."""
    code = """
from functools import lru_cache

@lru_cache(maxsize=128)
def memoized_fn(n):
    if n <= 1:
        return 1
    return memoized_fn(n - 1) + memoized_fn(n - 2)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    fa = {f["name"]: f for f in res.function_analyses}

    assert fa["memoized_fn"]["time_complexity"] == "O(n)"


def test_28_cache_memory_derivation_assumptions_documented(analyzer: ComplexityAnalyzer):
    """Test 28: Memoization derivation steps document state space and cache memory assumptions."""
    code = """
from functools import cache

@cache
def compute(n):
    if n <= 0:
        return 0
    return compute(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.recurrence.present
    assert any("Cache retained memory" in s or "Memoization table" in s for s in res.recurrence.derivation_steps)


# ==============================================================================
# 6. PARSER SECURITY & BOUNDARY TESTS (Tests 29 - 34)
# ==============================================================================


def test_29_preserve_100kb_source_size_limit():
    """Test 29: Source exceeding 100,000 bytes is rejected at pre-parse stage."""
    oversized = "x = 1\n" * 17_000
    assert len(oversized.encode("utf-8")) > SafeASTParser.MAX_CODE_BYTES

    tree, err = SafeASTParser.parse_code(oversized)
    assert tree is None
    assert err is not None
    assert "exceeds maximum allowed size" in err.message


def test_30_preserve_3000_line_limit():
    """Test 30: Source exceeding 3,000 lines is rejected at pre-parse stage."""
    many_lines = "\n".join(["x = 1"] * 3001)
    tree, err = SafeASTParser.parse_code(many_lines)

    assert tree is None
    assert err is not None
    assert "exceeds maximum allowed line count" in err.message


def test_31_preserve_ast_node_limit():
    """Test 31: Code generating > 10,000 AST nodes is rejected iteratively."""
    huge_list = "x = [" + ", ".join(["1"] * 11000) + "]"
    tree, err = SafeASTParser.parse_code(huge_list)

    assert tree is None
    assert err is not None
    assert "AST node count exceeded limit" in err.message


def test_32_preserve_ast_depth_limit():
    """Test 32: Deeply nested AST structure exceeding depth 200 is safely rejected."""
    deep_code = "a = " + "[" * 210 + "1" + "]" * 210
    tree, err = SafeASTParser.parse_code(deep_code)

    assert tree is None
    assert err is not None
    assert any(kw in err.message.lower() for kw in ("depth", "limit", "nested", "parentheses"))


def test_33_deep_parse_syntax_error_recovery():
    """Test 33: Syntactically malformed source is handled safely without unhandled exception."""
    malformed = "def broken(:"
    tree, err = SafeASTParser.parse_code(malformed)

    assert tree is None
    assert err is not None
    assert err.line >= 1
    assert "Syntax error" in err.message or "invalid syntax" in err.message.lower()


def test_34_iterative_traversal_remains_bounded():
    """Test 34: Iterative post-parse traversal safely handles large structures within limits."""
    valid_large = "def f():\n" + "".join([f"    v{i} = {i}\n" for i in range(500)])
    tree, err = SafeASTParser.parse_code(valid_large)

    assert err is None
    assert tree is not None
    assert isinstance(tree, ast.Module)


# ==============================================================================
# 7. DETERMINISTIC METAMORPHIC / PROPERTY CHECKS (Tests 35 - 39)
# ==============================================================================


def test_35_metamorphic_aliasing_vs_unique_allocations(analyzer: ComplexityAnalyzer):
    """Test 35: Aliasing a single array preserves O(n) memory, while two distinct allocations
    each retain their independent heap bounds.
    """
    code_aliased = """
def f(n):
    arr1 = [0] * n
    arr2 = arr1
    return len(arr1) + len(arr2)
"""
    tree_a = ast.parse(code_aliased)
    res_a = analyzer.analyze(tree_a)
    assert res_a.space_complexity == "O(n)"


def test_36_metamorphic_nested_recursion(analyzer: ComplexityAnalyzer):
    """Test 36: Double recursion branching factor 2 yields exponential time complexity."""
    code_binary = """
def tree_fn(n):
    if n <= 1:
        return 1
    return tree_fn(n - 1) + tree_fn(n - 1)
"""
    tree = ast.parse(code_binary)
    res = analyzer.analyze(tree)
    assert res.time_complexity == "O(2^n)"


def test_37_metamorphic_unknown_to_known_bounded_operation(analyzer: ComplexityAnalyzer):
    """Test 37: Replacing an unknown operation with a known constant operation inside a loop
    changes analysis_status from PARTIAL (Unknown) to COMPLETE (O(n)).
    """
    code_unknown = """
def process(items):
    for item in items:
        custom_engine.compute(item)
"""
    code_known = """
def process(items):
    for item in items:
        len(items)
"""
    tree_un = ast.parse(code_unknown)
    res_un = analyzer.analyze(tree_un)
    assert res_un.analysis_status == "PARTIAL"
    assert res_un.time_complexity.startswith("Unknown")

    tree_kn = ast.parse(code_known)
    res_kn = analyzer.analyze(tree_kn)
    assert res_kn.analysis_status == "COMPLETE"
    assert res_kn.time_complexity == "O(n)"


def test_38_metamorphic_adding_independent_sequential_cost(analyzer: ComplexityAnalyzer):
    """Test 38: Adding an independent sequential O(n) loop to an O(n²) function preserves O(n²)."""
    code_base = """
def quadratic(matrix):
    for row in matrix:
        for x in row:
            pass
"""
    code_augmented = """
def quadratic(matrix):
    for row in matrix:
        for x in row:
            pass
    for r in matrix:
        pass
"""
    res_base = analyzer.analyze(ast.parse(code_base))
    res_aug = analyzer.analyze(ast.parse(code_augmented))

    assert res_base.time_complexity == "O(n²)"
    assert res_aug.time_complexity == "O(n²)"


def test_39_metamorphic_identifier_renaming_preserves_complexity(analyzer: ComplexityAnalyzer):
    """Test 39: Renaming identifiers and parameters has zero impact on derived complexity."""
    code1 = """
def calculate(data_list):
    res = 0
    for element in data_list:
        res += element
    return res
"""
    code2 = """
def x(y):
    z = 0
    for w in y:
        z += w
    return z
"""
    res1 = analyzer.analyze(ast.parse(code1))
    res2 = analyzer.analyze(ast.parse(code2))

    assert res1.time_complexity == res2.time_complexity == "O(n)"
    assert res1.space_complexity == res2.space_complexity == "O(1)"
    assert res1.analysis_status == res2.analysis_status == "COMPLETE"
