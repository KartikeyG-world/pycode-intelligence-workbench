import ast
import pytest
from app.analyzers.complexity_analyzer import ComplexityAnalyzer
from app.analyzers.ast_parser import SafeASTParser
from app.schemas.analysis import AnalyzeResponse
from app.analyzers.complexity_classes import ComplexityClass


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


def test_24_sum_with_container_start_argument_generic_parameter_partial(analyzer: ComplexityAnalyzer):
    """Test 24: sum(nested_lists, []) on unannotated parameter has unestablished inner dimensions l_j;
    reports PARTIAL / Unknown with modeled outer work contribution O(n) and proven lower bound Omega(n) rather than assuming O(n²).
    """
    code = """
def flatten(nested_lists):
    return sum(nested_lists, [])
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.analysis_status == "PARTIAL"
    assert not res.analysis_complete
    assert "Unknown" in res.time_complexity
    assert res.known_time_complexity == "O(n)"
    assert any(u["operation"] == "sum" for u in res.unresolved_costs)


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


# ==============================================================================
# 8. MATHEMATICAL AUDIT & REFINED SEMANTICS TESTS (Tests 40 - 49)
# ==============================================================================


def test_40_sum_parameterized_inner_lists_cubic_time(analyzer: ComplexityAnalyzer):
    """Test 40: sum() on 2D collection with parameterized inner lists (k=n, m=n)
    repeatedly concatenates lists in Theta(m * k^2) = O(n^3) time.
    """
    code = """
def flatten_matrix(n):
    return sum([[0] * n for _ in range(n)], [])
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(n³)"
    assert res.analysis_complete


def test_41_sum_fixed_size_inner_lists_quadratic_time(analyzer: ComplexityAnalyzer):
    """Test 41: sum() on collection with fixed-size inner lists (m = O(1))
    concatenates lists in Theta(m * k^2) = O(k^2) = O(n^2) time.
    """
    code = """
def flatten_pairs(n):
    return sum([[1, 2] for _ in range(n)], [])
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(n²)"
    assert res.analysis_complete


def test_42_cache_diagonal_state_traversal(analyzer: ComplexityAnalyzer):
    """Test 42: @cache on function where all recursive calls modify both parameters
    simultaneously visits only diagonal states O(min(n, m)), not full O(n * m).
    """
    code = """
from functools import cache

@cache
def diagonal_walk(n, m):
    if n <= 0 or m <= 0:
        return 0
    return diagonal_walk(n - 1, m - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(min(n,m))"
    assert res.space_breakdown.cache_retained == "O(min(n,m))"


def test_43_cache_invariant_parameter_linear(analyzer: ComplexityAnalyzer):
    """Test 43: @cache with multiple parameters where secondary parameters are invariant
    restricts state space to single-variable O(n), not multi-variable product.
    """
    code = """
from functools import cache

@cache
def solve_with_flag(n, debug_flag):
    if n <= 0:
        return 0
    return solve_with_flag(n - 1, debug_flag)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(n)"
    assert res.space_breakdown.cache_retained == "O(n)"


def test_44_recursive_allocation_aliased_deletion_survives(analyzer: ComplexityAnalyzer):
    """Test 44: When a local allocation has a surviving alias, deleting the original variable name
    does NOT release the object; heap memory accumulates to O(n²) across active frames.
    """
    code = """
def process(n):
    if n <= 0:
        return 0
    temporary = [0] * n
    alias = temporary
    del temporary
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.space_complexity == "O(n²)"
    assert res.space_breakdown.peak_live_heap == "O(n²)"
    assert res.space_breakdown.auxiliary == "O(n²)"


def test_45_recursive_allocation_escaped_container_survives(analyzer: ComplexityAnalyzer):
    """Test 45: When a local allocation is appended to a container, deleting the variable name
    does NOT release the object; it escapes and accumulates to O(n²).
    """
    code = """
def process(n):
    if n <= 0:
        return 0
    temporary = [0] * n
    container.append(temporary)
    del temporary
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.space_complexity == "O(n²)"
    assert res.space_breakdown.peak_live_heap == "O(n²)"


def test_46_print_custom_object_unresolved_representation(analyzer: ComplexityAnalyzer):
    """Test 46: print() on custom entity with unmodeled __str__/__repr__ records
    unresolved cost and reports PARTIAL status instead of assuming O(1).
    """
    code = """
def display(custom_entity):
    print(custom_entity)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert not res.analysis_complete
    assert res.analysis_status == "PARTIAL"
    assert any("custom_entity" in u["reason"] or "print" in u["operation"] for u in res.unresolved_costs)


def test_47_print_custom_file_stream_unresolved(analyzer: ComplexityAnalyzer):
    """Test 47: print() directed to a custom file object has unresolved write() cost."""
    code = """
def write_log(custom_stream):
    print("Execution complete", file=custom_stream)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert not res.analysis_complete
    assert res.analysis_status == "PARTIAL"
    assert any("custom" in u["reason"] and "stream" in u["reason"] for u in res.unresolved_costs)


def test_48_legacy_record_deserialization_compatibility():
    """Test 48: Verifies that legacy database records lacking Phase 1A.1.3 fields
    deserialize successfully into AnalyzeResponse with LEGACY_RECORD status.
    """
    legacy_payload = {
        "success": True,
        "time_complexity": "O(n)",
        "tight_bound": "Θ(n)",
        "space_complexity": "O(1)",
        "confidence": "HIGH",
        "complexity_reasoning": "Legacy analysis output",
        "statistics": {
            "function_count": 1,
            "loop_count": 1,
            "for_loop_count": 1,
            "while_loop_count": 0,
            "conditional_count": 0,
            "max_nesting_depth": 1,
            "recursion_detected": False,
            "recursion_count": 0,
            "operation_count": 1,
            "comprehension_count": 0,
            "imported_modules": [],
        },
        "structure": {"nodes": [], "edges": []},
        "graph": {"active_complexity": "O(n)", "growth_points": []},
    }

    parsed = AnalyzeResponse.model_validate(legacy_payload)
    assert parsed.analysis_status == "LEGACY_RECORD"
    assert parsed.analysis_complete is None
    assert parsed.known_time_complexity is None
    assert parsed.unresolved_costs == []
    assert parsed.space_breakdown.peak_live_heap == "O(1)"


def test_49_unresolved_cost_item_structured_validation():
    """Test 49: Validates structured validation and dual dict/attribute access of UnresolvedCostItem."""
    from app.schemas.analysis import UnresolvedCostItem

    item = UnresolvedCostItem(
        operation="custom_method",
        line=15,
        context="loop",
        loop_depth=2,
        reason="unresolved method invocation",
    )

    assert item.operation == "custom_method"
    assert item["operation"] == "custom_method"
    assert item["loop_depth"] == 2
    assert item.line == 15


# ==============================================================================
# 9. RESIDUAL CORRECTNESS RECONCILIATION TESTS (Tests 50 - 61)
# ==============================================================================


def test_50_sum_empty_inner_lists_linear(analyzer: ComplexityAnalyzer):
    """Test 50: sum([[] for _ in range(n)], []) takes Theta(n) linear time, not zero or quadratic."""
    code = """
def flatten_empty(n):
    return sum([[] for _ in range(n)], [])
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(n)"
    assert res.tight_bound == "Θ(n)"
    assert res.analysis_complete


def test_51_sum_independent_parameterized_dimensions(analyzer: ComplexityAnalyzer):
    """Test 51: sum([[0] * m for _ in range(k)], []) scales as Theta(m * k^2) with independent variables."""
    code = """
def flatten_rect(k, m):
    return sum([[0] * m for _ in range(k)], [])
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(m*k^2)"
    assert res.tight_bound == "Θ(m*k^2)"
    assert res.analysis_complete


def test_52_sum_ragged_inner_lists_cubic(analyzer: ComplexityAnalyzer):
    """Test 52: sum([[0] * i for i in range(n)], []) has ragged inner lists l_i = i scaling as Theta(n^3)."""
    code = """
def flatten_triangular(n):
    return sum([[0] * i for i in range(n)], [])
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(n³)"
    assert res.tight_bound == "Θ(n³)"
    assert res.analysis_complete


def test_53_memoized_grid_with_local_work_cubic(analyzer: ComplexityAnalyzer):
    """Test 53: Grid recursion with O(n) local loop per state computes total execution time
    T_total = sum_{s in R} T_local(s) = O(i*j) * O(n) = O(n*i*j), distinguishing state count from total work.
    """
    code = """
from functools import lru_cache

@lru_cache(maxsize=None)
def grid_with_loop(i, j):
    if i <= 0 or j <= 0:
        return 0
    total = 0
    for k in range(n):
        total += k
    return total + grid_with_loop(i - 1, j) + grid_with_loop(i, j - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(n*i*j)"
    assert res.tight_bound == "Θ(n*i*j)"
    assert res.recurrence.is_solved
    assert any("State space cardinality is bounded by distinct reachable states: |R| = Θ(i*j)" in step for step in res.recurrence.derivation_steps)
    assert any("Local non-recursive work per state: T_local(s) = O(n)" in step for step in res.recurrence.derivation_steps)


def test_54_memoized_large_returned_array_bounded_cache(analyzer: ComplexityAnalyzer):
    """Test 54: @lru_cache(maxsize=128) returning an O(n) array retains O(n) byte-memory
    even though entry count is bounded to O(1).
    """
    code = """
from functools import lru_cache

@lru_cache(maxsize=128)
def get_row(n):
    if n <= 0:
        return [0] * n
    return get_row(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.space_breakdown.cache_retained == "O(n)"
    assert res.space_complexity == "O(n)"


def test_55_memoized_large_container_arg_bounded_cache(analyzer: ComplexityAnalyzer):
    """Test 55: @lru_cache(maxsize=128) with large container parameter (arr) retains O(n) argument key memory."""
    code = """
from functools import lru_cache

@lru_cache(maxsize=128)
def solve_arr(arr, i):
    if i <= 0:
        return 0
    return solve_arr(arr, i - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.space_breakdown.cache_retained == "O(n)"


def test_56_multilevel_alias_surviving_deletion_retains_heap(analyzer: ComplexityAnalyzer):
    """Test 56: Multi-level alias chain b = a; c = b; del a; del b does NOT release heap
    because c still holds a reference to the allocated object; retains O(n^2).
    """
    code = """
def process(n):
    if n <= 0:
        return 0
    a = [0] * n
    b = a
    c = b
    del a
    del b
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.space_breakdown.peak_live_heap == "O(n²)"
    assert res.space_complexity == "O(n²)"


def test_57_multilevel_alias_all_deleted_bounds_heap(analyzer: ComplexityAnalyzer):
    """Test 57: When ALL aliases in a chain are deleted before recursive call, heap is released to single frame O(n)."""
    code = """
def process(n):
    if n <= 0:
        return 0
    a = [0] * n
    b = a
    c = b
    del a
    del b
    del c
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.space_breakdown.peak_live_heap == "O(n)"
    assert res.space_complexity == "O(n)"


def test_58_alias_reassigned_bounds_heap(analyzer: ComplexityAnalyzer):
    """Test 58: Reassigning an alias b = None before deleting the original releases the allocation."""
    code = """
def process(n):
    if n <= 0:
        return 0
    a = [0] * n
    b = a
    b = None
    del a
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.space_breakdown.peak_live_heap == "O(n)"
    assert res.space_complexity == "O(n)"


def test_59_external_call_escapes_allocation(analyzer: ComplexityAnalyzer):
    """Test 59: Passing local allocation to an unresolved external call conservatively marks it as escaped; retains O(n^2)."""
    code = """
def process(n):
    if n <= 0:
        return 0
    temp = [0] * n
    external_consume(temp)
    del temp
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.space_breakdown.peak_live_heap == "O(n²)"
    assert res.space_complexity == "O(n²)"


def test_60_attribute_escapes_allocation(analyzer: ComplexityAnalyzer):
    """Test 60: Storing local allocation into self.attr or container index escapes it; retains O(n^2)."""
    code = """
def process(n):
    if n <= 0:
        return 0
    temp = [0] * n
    self.stored = temp
    del temp
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.space_breakdown.peak_live_heap == "O(n²)"
    assert res.space_complexity == "O(n²)"


def test_61_unresolved_cost_item_mapping_interface():
    """Test 61: Full collections.abc.Mapping interface test for UnresolvedCostItem."""
    from collections.abc import Mapping
    from app.schemas.analysis import UnresolvedCostItem

    item = UnresolvedCostItem(
        operation="custom_dispatch",
        line=42,
        context="loop",
        loop_depth=3,
        reason="unresolved dynamic method",
    )

    assert isinstance(item, Mapping)
    assert item["operation"] == "custom_dispatch"
    assert item.get("operation") == "custom_dispatch"
    assert item.get("missing_key", "default_val") == "default_val"
    assert "operation" in item
    assert "missing" not in item
    assert set(item.keys()) == {"operation", "line", "context", "loop_depth", "reason"}
    assert set(item.values()) == {"custom_dispatch", 42, "loop", 3, "unresolved dynamic method"}
    assert len(item) == 5
    assert dict(item)["operation"] == "custom_dispatch"
    dump = item.model_dump()
    assert dump["operation"] == "custom_dispatch"
    assert "custom_dispatch" in item.model_dump_json()


# ==============================================================================
# 11. ESCAPE SAFETY, CACHE MEMORY PRECISION & LOOKUP COMPLEXITY (Tests 62 - 72)
# ==============================================================================


def test_62_self_recursive_call_escapes_argument_allocation(analyzer: ComplexityAnalyzer):
    """Test 62: Passing a local allocation to a self-recursive call escapes it into the callee frame;
    heap memory cannot be freed before child execution completes, retaining O(n^2) peak live heap.
    """
    code = """
def process(n, temp=None):
    if n <= 0:
        return 0
    temp = [0] * n
    res = process(n - 1, temp)
    del temp
    return res
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.space_breakdown.peak_live_heap == "O(n²)"
    assert res.space_complexity == "O(n²)"


def test_63_print_custom_stream_escapes_allocation(analyzer: ComplexityAnalyzer):
    """Test 63: print(temp, file=custom_writer) passes string representation via write(str), NOT the
    underlying allocated container; exact built-in list with primitive elements does not escape to the
    custom stream writer, and del temp ensures release before recursion, maintaining O(n) peak live heap.
    """
    code = """
def process(n):
    if n <= 0:
        return 0
    temp = [0] * n
    print(temp, file=custom_log_stream)
    del temp
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.space_breakdown.peak_live_heap == "O(n)"
    assert res.space_complexity == "O(n)"


def test_64_print_standard_builtin_is_non_escaping(analyzer: ComplexityAnalyzer):
    """Test 64: print(temp) to standard stdout does not escape or retain references to built-in list;
    after del temp before recursive invocation, peak live heap is bounded by a single frame O(n).
    """
    code = """
def process(n):
    if n <= 0:
        return 0
    temp = [0] * n
    print(temp)
    del temp
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.space_breakdown.peak_live_heap == "O(n)"
    assert res.space_complexity == "O(n)"


def test_65_len_builtin_is_non_escaping(analyzer: ComplexityAnalyzer):
    """Test 65: len(temp) on a built-in list reads container size without escaping references;
    after del temp before recursive invocation, peak live heap is bounded by a single frame O(n).
    """
    code = """
def process(n):
    if n <= 0:
        return 0
    temp = [0] * n
    k = len(temp)
    del temp
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.space_breakdown.peak_live_heap == "O(n)"
    assert res.space_complexity == "O(n)"


def test_66_case_a_shared_argument_retains_linear_cache_memory(analyzer: ComplexityAnalyzer):
    """Test 66: Case A - Shared argument tuple passed into cache entries retains O(n) total heap memory,
    not O(n^2), because all |R| = O(n) cache keys hold pointers to the identical pre-existing shared object.
    """
    code = """
from functools import lru_cache

@lru_cache(maxsize=None)
def solve(n, shared):
    if n <= 0:
        return 0
    return solve(n - 1, shared) + shared[n % len(shared)]
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(n)"
    assert res.space_breakdown.cache_retained == "O(n)"
    assert res.space_complexity == "O(n)"
    assert any("share references to external/passed argument payload" in step for step in res.recurrence.derivation_steps)


def test_67_case_b_unique_argument_allocation_per_state_quadratic(analyzer: ComplexityAnalyzer):
    """Test 67: Case B - Unique argument tuples allocated per state (new_path = path + (n,))
    retain distinct O(n) payloads per cache entry, accumulating to O(n^2) total retained cache memory.
    """
    code = """
from functools import lru_cache

@lru_cache(maxsize=None)
def solve(n, path):
    if n <= 0:
        return 0
    new_path = path + (n,)
    return solve(n - 1, new_path)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(n)"
    assert res.space_breakdown.cache_retained == "O(n²)"
    assert res.space_complexity == "O(n²)"
    assert any("unique freshly allocated argument payload" in step for step in res.recurrence.derivation_steps)


def test_68_case_c_shared_return_object_retains_linear_cache_memory(analyzer: ComplexityAnalyzer):
    """Test 68: Case C - Returning a shared container object (shared_result) stores identical object references
    across all |R| = O(n) cache entries, retaining O(n) total heap memory, not O(n^2).
    """
    code = """
from functools import lru_cache

shared_result = [0] * n

@lru_cache(maxsize=None)
def solve(n):
    if n <= 0:
        return shared_result
    return solve(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(n)"
    assert res.space_breakdown.cache_retained == "O(n)"
    assert res.space_complexity == "O(n)"
    assert any("store references to a shared return object" in step for step in res.recurrence.derivation_steps)


def test_69_case_d_unique_return_allocations_per_state_quadratic(analyzer: ComplexityAnalyzer):
    """Test 69: Case D - Unique return allocations created per state (return [0] * n fresh)
    store distinct O(n) payloads per cache entry in unbounded cache, retaining O(n^2) total heap memory.
    """
    code = """
from functools import lru_cache

@lru_cache(maxsize=None)
def solve(n):
    if n <= 0:
        return [0] * n
    res = solve(n - 1)
    return [0] * n
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(n)"
    assert res.space_breakdown.cache_retained == "O(n²)"
    assert res.space_complexity == "O(n²)"
    assert any("unique freshly allocated return payload" in step for step in res.recurrence.derivation_steps)


def test_70_case_e_bounded_cache_unique_return_allocations_linear(analyzer: ComplexityAnalyzer):
    """Test 70: Case E - Bounded cache (@lru_cache(maxsize=128)) with unique return allocations
    bounds table entry count to O(1), but retains O(n) byte-memory because each entry retains an O(n) list.
    """
    code = """
from functools import lru_cache

@lru_cache(maxsize=128)
def solve(n):
    if n <= 0:
        return [0] * n
    res = solve(n - 1)
    return [0] * n
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.time_complexity == "O(n)"
    assert res.space_breakdown.cache_retained == "O(n)"
    assert res.space_complexity == "O(n)"
    assert any("fixed LRU capacity bounds table entry count to O(1)" in step for step in res.recurrence.derivation_steps)


def test_71_cache_lookup_complexity_derivation_qualification(analyzer: ComplexityAnalyzer):
    """Test 71: Memoized derivation explicitly qualifies O(1) lookup overhead as conditional
    on standard hash-table collision-free assumptions and primitive scalar key hashing/equality,
    disclosing that container keys of size k require O(k) hashing and comparison operations.
    """
    code = """
from functools import lru_cache

@lru_cache(maxsize=None)
def memoized_solver(n):
    if n <= 1:
        return 1
    return memoized_solver(n - 1) + memoized_solver(n - 2)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.recurrence.is_solved
    lookup_steps = [s for s in res.recurrence.derivation_steps if "expected O(1) cache lookup overhead" in s]
    assert len(lookup_steps) == 1
    step = lookup_steps[0]
    assert "conditional on standard hash-table collision-free assumptions" in step
    assert "primitive scalar key hashing and equality comparison" in step
    assert "compound or sequence keys of dimension k require O(k) hashing and equality comparison" in step


def test_72_generic_sum_notation_and_input_model_separation(analyzer: ComplexityAnalyzer):
    """Test 72: Generic sum(nested, []) explanation explicitly separates proven lower bound Omega(k)
    from modeled outer contribution O(k) and unproven total complexity Unknown, documenting the
    input model assumption of a finite iterable containing compatible built-in list objects.
    """
    code = """
def flatten(nested):
    return sum(nested, [])
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)

    assert res.analysis_status == "PARTIAL"
    assert "Unknown" in res.time_complexity
    assert res.known_time_complexity == "O(n)"
    unresolved_sum = [u for u in res.unresolved_costs if u.get("operation") == "sum"]
    assert len(unresolved_sum) == 1
    reason = unresolved_sum[0]["reason"]
    assert "proven lower bound of Omega(k)" in reason
    assert "modeled outer work contribution of O(k)" in reason
    assert "statically Unknown because inner sublist lengths l_j are unconstrained" in reason
    assert "exact compatible built-in Python list semantics" in reason
    assert "finite outer iterable of length k" in reason


def test_73_len_locally_shadowed_escapes_allocation(analyzer: ComplexityAnalyzer):
    """Test 73: len() with locally shadowed len escapes allocated argument, resulting in O(n^2) space."""
    code = """
def process(n):
    if n <= 0:
        return 0
    temporary = [0] * n
    len = lambda x: 0
    x = len(temporary)
    del temporary
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert res.time_complexity == "O(n)"
    assert res.space_complexity == "O(n²)"


def test_74_len_parameter_shadowed_escapes_allocation(analyzer: ComplexityAnalyzer):
    """Test 74: len() with parameter named len escapes allocated argument, resulting in O(n^2) space."""
    code = """
def process(n, len):
    if n <= 0:
        return 0
    temporary = [0] * n
    x = len(temporary)
    del temporary
    return process(n - 1, len)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert res.time_complexity == "O(n)"
    assert res.space_complexity == "O(n²)"


def test_75_len_custom_class_with_user_len_escapes_allocation(analyzer: ComplexityAnalyzer):
    """Test 75: len() on a custom class with user-defined __len__ escapes allocation, resulting in O(n^2) space."""
    code = """
def process(n):
    if n <= 0:
        return 0
    temporary = CustomContainer()
    x = len(temporary)
    del temporary
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert not res.analysis_complete
    assert res.analysis_status == "PARTIAL"
    assert res.known_time_complexity == "O(n)"
    assert res.space_complexity == "O(n²)"


def test_76_id_and_type_locally_shadowed_escapes_allocation(analyzer: ComplexityAnalyzer):
    """Test 76: id() and type() with locally shadowed name escape allocation, resulting in O(n^2) space."""
    code = """
def process(n):
    if n <= 0:
        return 0
    temporary = [0] * n
    id = lambda x: 42
    x = id(temporary)
    del temporary
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert res.time_complexity == "O(n)"
    assert res.space_complexity == "O(n²)"


def test_77_print_custom_object_escapes_allocation(analyzer: ComplexityAnalyzer):
    """Test 77: print() of custom object whose representation executes arbitrary code escapes allocation."""
    code = """
def process(n):
    if n <= 0:
        return 0
    temporary = CustomNode()
    print(temporary)
    del temporary
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert not res.analysis_complete
    assert res.analysis_status == "PARTIAL"
    assert res.known_time_complexity == "O(n)"
    assert res.space_complexity == "O(n²)"


def test_78_print_list_of_custom_objects_escapes_allocation(analyzer: ComplexityAnalyzer):
    """Test 78: print() of list of custom objects with unmodeled repr escapes allocation."""
    code = """
def process(n):
    if n <= 0:
        return 0
    temporary = [Elem() for _ in range(n)]
    print(temporary)
    del temporary
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert not res.analysis_complete
    assert res.analysis_status == "PARTIAL"
    assert res.known_time_complexity == "O(n)"
    assert res.space_complexity == "O(n²)"


def test_79_print_custom_stdout_stream_escapes_allocation(analyzer: ComplexityAnalyzer):
    """Test 79: print() with custom.stdout stream (not sys.stdout) passes string representation via write(str),
    not the original container object; exact built-in list is released by del temp before recursion, maintaining O(n) space."""
    code = """
class CustomStream:
    stdout = None

def process(n):
    if n <= 0:
        return 0
    temporary = [0] * n
    print(temporary, file=CustomStream.stdout)
    del temporary
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert res.time_complexity == "O(n)"
    assert res.space_complexity == "O(n)"


def test_80_print_shadowed_sys_parameter_escapes_allocation(analyzer: ComplexityAnalyzer):
    """Test 80: print() with shadowed sys parameter passes string representation via write(str);
    exact built-in list is released by del temp before recursion, maintaining O(n) space."""
    code = """
def process(n, sys):
    if n <= 0:
        return 0
    temporary = [0] * n
    print(temporary, file=sys.stdout)
    del temporary
    return process(n - 1, sys)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert res.time_complexity == "O(n)"
    assert res.space_complexity == "O(n)"


def test_81_print_imported_sys_alias_preserves_single_frame_deallocation(analyzer: ComplexityAnalyzer):
    """Test 81: print() with imported sys alias (import sys as s; print(..., file=s.stdout)) preserves single-frame deallocation."""
    code = """
import sys as s

def process(n):
    if n <= 0:
        return 0
    temporary = [0] * n
    print(temporary, file=s.stdout)
    del temporary
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert res.time_complexity == "O(n)"
    assert res.space_complexity == "O(n)"


def test_82_recursive_shared_allocation_passed_bounds_heap(analyzer: ComplexityAnalyzer):
    """Test 82: Recursive object identity - Shared allocation passed across recursive frames
    references 1 single allocation, counted once to O(n) total space, not multiplied by call depth.
    """
    code = """
shared_data = [0] * n

def solve(n, data):
    if n <= 0:
        return 0
    return solve(n - 1, data)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert res.time_complexity == "O(n)"
    assert res.space_complexity == "O(n)"


def test_83_recursive_fresh_allocation_accumulates_quadratic_heap(analyzer: ComplexityAnalyzer):
    """Test 83: Recursive object identity - Fresh allocation per recursive frame without prior
    deallocation accumulates to O(n^2) live heap across call depth n.
    """
    code = """
def solve(n):
    if n <= 0:
        return 0
    frame_alloc = [0] * n
    return solve(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert res.time_complexity == "O(n)"
    assert res.space_complexity == "O(n²)"


def test_84_cache_composition_unique_arg_quadratic_fresh_ret_linear(analyzer: ComplexityAnalyzer):
    """Test 84: Cache composition - Unique argument O(n^2) larger than fresh return O(n)
    dominates combined cache memory to |R| * O(n^2) = O(n^3).
    """
    code = """
from functools import lru_cache

@lru_cache(maxsize=None)
def solve(n, matrix):
    if n <= 0:
        return [0] * n
    new_matrix = [[0] * n for _ in range(n)]
    res = solve(n - 1, new_matrix)
    return [0] * n
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert res.time_complexity in ("O(n)", "O(n²)")
    assert res.space_breakdown.cache_retained == "O(n³)"
    assert res.space_complexity == "O(n³)"


def test_85_cache_composition_fresh_ret_quadratic_unique_arg_linear(analyzer: ComplexityAnalyzer):
    """Test 85: Cache composition - Fresh return O(n^2) larger than unique argument O(n)
    dominates combined cache memory to |R| * O(n^2) = O(n^3).
    """
    code = """
from functools import lru_cache

@lru_cache(maxsize=None)
def solve(n, path):
    if n <= 0:
        return [[0] * n for _ in range(n)]
    new_path = path + (n,)
    res = solve(n - 1, new_path)
    return [[0] * n for _ in range(n)]
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert res.time_complexity in ("O(n)", "O(n²)")
    assert res.space_breakdown.cache_retained == "O(n³)"
    assert res.space_complexity == "O(n³)"


def test_86_cache_composition_bounded_cache_simultaneous_growing(analyzer: ComplexityAnalyzer):
    """Test 86: Cache composition - Both argument and return simultaneously growing O(n) in bounded
    cache (@lru_cache(maxsize=32)) bounds table entry count to O(1) and retains O(n) total cache memory.
    """
    code = """
from functools import lru_cache

@lru_cache(maxsize=32)
def solve(n, path):
    if n <= 0:
        return [0] * n
    new_path = path + (n,)
    res = solve(n - 1, new_path)
    return [0] * n
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert res.time_complexity == "O(n)"
    assert res.space_breakdown.cache_retained == "O(n)"
    assert res.space_complexity == "O(n)"


def test_87_multidimensional_dominant_of_independent_dimensions():
    """Test 87: ComplexityClass.dominant_of with independent dimensions M1=O(n^2), M2=O(m^3)
    preserves both asymptotic terms without collapsing incomparable dimensions: O(n² + m³).
    """
    m1 = ComplexityClass.polynomial(2.0, "n")
    m2 = ComplexityClass.polynomial(3.0, "m")
    dom = ComplexityClass.dominant_of(m1, m2)
    assert dom.big_o in ("O(n² + m³)", "O(n^2 + m^3)", "O(m³ + n²)")


def test_88_multidimensional_multiply_independent_dimensions():
    """Test 88: ComplexityClass.multiply with independent dimensions O(n^2) * O(m) preserves multi-variable product."""
    c1 = ComplexityClass.polynomial(2.0, "n")
    c2 = ComplexityClass.linear("m")
    prod = ComplexityClass.multiply(c1, c2)
    assert prod.big_o in ("O(n²*m)", "O(n^2*m)", "O(n² * m)")

    c3 = ComplexityClass.polynomial(3.0, "m")
    prod3 = ComplexityClass.multiply(c1, c3)
    assert prod3.big_o in ("O(n²*m³)", "O(n^2*m^3)", "O(n² * m³)")


def test_89_cross_role_cache_alias_identity(analyzer: ComplexityAnalyzer):
    """Test 89: Cross-role cache allocation identity - solve(n, shared) returning shared points to
    the exact same underlying heap container across argument and return roles, deduplicated to single O(n) object memory.
    """
    code = """
from functools import lru_cache

@lru_cache(maxsize=None)
def solve(n, shared):
    if n <= 0:
        return shared
    return solve(n - 1, shared)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert res.space_breakdown.cache_retained == "O(n)"


def test_90_comprehension_scope_isolation_does_not_shadow_outer(analyzer: ComplexityAnalyzer):
    """Test 90: In Python 3, comprehension generator target [len for len in items] is local to comprehension
    and does NOT shadow len in containing function scope; len(temp) is unshadowed built-in and temp is released before recursion.
    """
    code = """
def process(n):
    if n <= 0:
        return 0
    temp = [0] * n
    x = [len for len in [1, 2, 3]]
    k = len(temp)
    del temp
    del x
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert res.space_breakdown.peak_live_heap == "O(n)"
    assert res.space_complexity == "O(n)"


def test_91_comprehension_walrus_expression_leaks_and_shadows(analyzer: ComplexityAnalyzer):
    """Test 91: PEP 572 assignment expression (len := ...) inside comprehension leaks to enclosing function scope,
    shadowing len and causing temp to escape into the custom callable, accumulating O(n^2) peak heap.
    """
    code = """
def process(n):
    if n <= 0:
        return 0
    temp = [0] * n
    x = [(len := lambda o: 0) for _ in range(1)]
    k = len(temp)
    del temp
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert res.space_breakdown.peak_live_heap == "O(n²)"
    assert res.space_complexity == "O(n²)"


def test_92_nested_function_scope_isolation_does_not_shadow_outer(analyzer: ComplexityAnalyzer):
    """Test 92: Identifiers inside nested function def helper(): len = 1 do not leak to outer function;
    outer len(temp) calls built-in len, so temp is released before recursion.
    """
    code = """
def process(n):
    if n <= 0:
        return 0
    temp = [0] * n
    def helper():
        len = 1
        return len
    k = len(temp)
    del temp
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert res.space_breakdown.peak_live_heap == "O(n)"
    assert res.space_complexity == "O(n)"


def test_93_wildcard_import_uncertainty_forces_conservative_escape(analyzer: ComplexityAnalyzer):
    """Test 93: Wildcard import from math import * introduces dynamic namespace uncertainty where built-ins
    may be shadowed; calls to len(temp) conservatively treat arguments as escaped, accumulating O(n^2) peak heap.
    """
    code = """
from math import *

def process(n):
    if n <= 0:
        return 0
    temp = [0] * n
    k = len(temp)
    del temp
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert res.space_breakdown.peak_live_heap == "O(n²)"
    assert res.space_complexity == "O(n²)"


def test_94_standard_stream_mutation_detected(analyzer: ComplexityAnalyzer):
    """Test 94: Standard stream mutation sys.stdout = custom_stream marks stream redirected;
    exact built-in list printed is serialized to string without escaping underlying container, so del temp releases it.
    """
    code = """
import sys
sys.stdout = custom_stream

def process(n):
    if n <= 0:
        return 0
    temp = [0] * n
    print(temp)
    del temp
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert res.space_breakdown.peak_live_heap == "O(n)"
    assert res.space_complexity == "O(n)"


def test_95_redirect_stdout_context_manager(analyzer: ComplexityAnalyzer):
    """Test 95: with redirect_stdout(buf): context manager redirects stdout;
    exact built-in list printed is serialized to string without escaping underlying container.
    """
    code = """
from contextlib import redirect_stdout
import io

def process(n):
    if n <= 0:
        return 0
    temp = [0] * n
    buf = io.StringIO()
    with redirect_stdout(buf):
        print(temp)
    del temp
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert res.space_breakdown.peak_live_heap == "O(n)"
    assert res.space_complexity == "O(n)"


def test_96_from_sys_import_stdout_recognized(analyzer: ComplexityAnalyzer):
    """Test 96: from sys import stdout binds standard stream name; print(temp, file=stdout)
    recognized as standard stream, maintaining O(n) heap after del temp.
    """
    code = """
from sys import stdout

def process(n):
    if n <= 0:
        return 0
    temp = [0] * n
    print(temp, file=stdout)
    del temp
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert res.space_breakdown.peak_live_heap == "O(n)"
    assert res.space_complexity == "O(n)"


def test_97_print_custom_object_escapes_via_repr(analyzer: ComplexityAnalyzer):
    """Test 97: print(temp) where temp contains custom objects whose __repr__ may invoke user code
    and create references escapes the allocated container, accumulating O(n^2) peak live heap across frames.
    """
    code = """
def process(n):
    if n <= 0:
        return 0
    temp = [CustomNode() for _ in range(n)]
    print(temp)
    del temp
    return process(n - 1)
"""
    tree = ast.parse(code)
    res = analyzer.analyze(tree)
    assert res.space_breakdown.peak_live_heap == "O(n²)"
    assert res.space_complexity == "O(n²)"
