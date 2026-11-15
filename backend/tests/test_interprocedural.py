import pytest
from app.analyzers.ast_parser import SafeASTParser
from app.analyzers.complexity_analyzer import ComplexityAnalyzer


@pytest.fixture
def analyzer():
    return ComplexityAnalyzer()


@pytest.fixture
def parser():
    return SafeASTParser()


# ==============================================================================
# TEST GROUP A: INTERPROCEDURAL CALLS
# ==============================================================================

def test_helper_called_once_linear(analyzer, parser):
    """1. O(n) helper called once sequentially in caller yields O(n)."""
    code = """
def helper(arr):
    total = 0
    for x in arr:
        total += x
    return total

def main_func(arr):
    result = helper(arr)
    return result
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert res.time_complexity == "O(n)"
    assert res.analysis_scope == "function"
    assert res.analysis_target == "main_func"


def test_helper_called_n_times_quadratic(analyzer, parser):
    """2. O(n) helper called inside an O(n) loop multiplies to O(n²)."""
    code = """
def helper(arr):
    total = 0
    for x in arr:
        total += x
    return total

def main_func(arr):
    result = 0
    for i in range(len(arr)):
        result += helper(arr)
    return result
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert res.time_complexity == "O(n²)"
    assert "Two nested loops" in res.complexity_reasoning or "multiplies iteration cost" in res.complexity_reasoning or "scaling" in res.complexity_reasoning


def test_linearithmic_helper_called_n_times(analyzer, parser):
    """3. O(n log n) sorting helper called n times scales to O(n² log n)."""
    code = """
def sort_helper(arr):
    return sorted(arr)

def process_all(matrix):
    n = len(matrix)
    for i in range(n):
        sort_helper(matrix[i])
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert "log" in res.time_complexity and ("n²" in res.time_complexity or "n^2" in res.time_complexity)


def test_two_sequential_helpers(analyzer, parser):
    """4. Two sequential O(n) function calls yield O(max(n, n)) = O(n)."""
    code = """
def step_one(arr):
    for x in arr:
        pass

def step_two(arr):
    for x in arr:
        pass

def run(arr):
    step_one(arr)
    step_two(arr)
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert res.time_complexity == "O(n)"


def test_multiple_callers_of_shared_helper(analyzer, parser):
    """5. Multiple callers invoke a shared helper function."""
    code = """
def shared_helper(arr):
    for x in arr:
        pass

def caller_a(arr):
    shared_helper(arr)

def caller_b(arr):
    for i in range(len(arr)):
        shared_helper(arr)
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert res.analysis_scope == "function_collection"
    # Dominant is caller_b with O(n²)
    assert res.time_complexity == "O(n²)"
    # Both callers analyzed in function_analyses
    analyses = {f["name"]: f for f in res.function_analyses}
    assert analyses["caller_a"]["time_complexity"] == "O(n)"
    assert analyses["caller_b"]["time_complexity"] == "O(n²)"


def test_unreachable_helper_not_executed(analyzer, parser):
    """6. An uncalled helper function does not inflate top-level module execution cost."""
    code = """
def dead_exponential_helper(n):
    if n <= 1:
        return 1
    return dead_exponential_helper(n - 1) + dead_exponential_helper(n - 1)

total = 0
for i in range(n):
    total += i
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert res.analysis_scope == "module"
    assert res.time_complexity == "O(n)"


def test_nested_helper_invocation(analyzer, parser):
    """7. Caller invokes helper_a, which in turn invokes helper_b."""
    code = """
def helper_b(arr):
    for x in arr:
        pass

def helper_a(arr):
    for y in arr:
        helper_b(arr)

def top_func(arr):
    helper_a(arr)
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert res.time_complexity == "O(n²)"
    assert res.analysis_target == "top_func"


def test_shadowed_function_name(analyzer, parser):
    """8. A local variable shadows a function name; caller executes as O(1) without resolving helper."""
    code = """
def helper(x):
    for i in range(x):
        pass

def caller(n):
    helper = 123
    return helper
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    analyses = {f["name"]: f for f in res.function_analyses}
    assert analyses["caller"]["time_complexity"] == "O(1)"


def test_unresolved_external_call(analyzer, parser):
    """9. Unresolved external call lowers confidence and documents limitation."""
    code = """
def process(data):
    result = external_unresolved_service(data)
    return result
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert res.confidence in ("MEDIUM", "LOW")
    assert len(res.unresolved_calls) > 0
    assert res.analysis_complete is False


def test_multiple_independent_function_targets(analyzer, parser):
    """10. Multiple independent functions without callers are identified as collection."""
    code = """
def func_linear(arr):
    for x in arr:
        pass

def func_quadratic(arr):
    for i in range(len(arr)):
        for j in range(len(arr)):
            pass
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert res.analysis_scope == "function_collection"
    assert res.time_complexity == "O(n²)"
    assert "func_linear" in res.analysis_target and "func_quadratic" in res.analysis_target


# ==============================================================================
# TEST GROUP B: MIXED RECURSION AND ITERATION
# ==============================================================================

def test_recursion_plus_nested_loop_no_preemption(analyzer, parser):
    """1. Recursive function plus independent nested loop maintains O(n²), fixing preemption defect."""
    code = """
def recursive_step(n):
    if n <= 1:
        return 1
    return recursive_step(n - 1)

def loop_and_recurse(n):
    for i in range(n):
        for j in range(n):
            pass
    return recursive_step(n)
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    # Must be O(n²), NOT O(n)!
    assert res.time_complexity == "O(n²)"


def test_recursive_function_called_in_linear_loop(analyzer, parser):
    """2. O(n) recursive function called inside an O(n) loop multiplies to O(n²)."""
    code = """
def recursive_step(n):
    if n <= 1:
        return 1
    return recursive_step(n - 1)

def caller(n):
    total = 0
    for i in range(n):
        total += recursive_step(n)
    return total
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert res.time_complexity == "O(n²)"


def test_recursive_function_called_in_nested_loop(analyzer, parser):
    """3. O(n) recursive function called inside nested loops multiplies to O(n³)."""
    code = """
def rec_linear(n):
    if n <= 1:
        return 1
    return rec_linear(n - 1)

def outer(n):
    for i in range(n):
        for j in range(n):
            rec_linear(n)
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert res.time_complexity == "O(n³)"


def test_sequential_recursive_and_iterative(analyzer, parser):
    """4. Sequential O(n) loop and O(n) recursion sum to O(n)."""
    code = """
def rec(n):
    if n <= 1:
        return 1
    return rec(n - 1)

def both(n):
    for i in range(n):
        pass
    rec(n)
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert res.time_complexity == "O(n)"


def test_multiple_independent_recursions(analyzer, parser):
    """5. Multiple independent recursive functions are both analyzed; dominant determines headline."""
    code = """
def linear_rec(n):
    if n <= 1:
        return 1
    return linear_rec(n - 1)

def exp_rec(n):
    if n <= 1:
        return 1
    return exp_rec(n - 1) + exp_rec(n - 1)
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert res.analysis_scope == "function_collection"
    assert res.time_complexity == "O(2^n)"
    analyses = {f["name"]: f for f in res.function_analyses}
    assert analyses["linear_rec"]["time_complexity"] == "O(n)"
    assert analyses["exp_rec"]["time_complexity"] == "O(2^n)"


def test_mutual_recursion_cycle_detection(analyzer, parser):
    """8. Detects mutual recursion cycle across functions using Tarjan's SCC."""
    code = """
def is_even(n):
    if n == 0:
        return True
    return is_odd(n - 1)

def is_odd(n):
    if n == 0:
        return False
    return is_even(n - 1)
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert res.time_complexity == "O(n)"
    assert len(res.call_graph.get("recursion_components", [])) > 0
    rec_comp = res.call_graph["recursion_components"][0]
    assert rec_comp["is_mutual"] is True


def test_unreachable_recursive_function(analyzer, parser):
    """9. Unreachable recursive function does not affect reachable module execution."""
    code = """
def unused_exp(n):
    if n <= 1:
        return 1
    return unused_exp(n - 1) + unused_exp(n - 1)

def main_loop(n):
    for i in range(n):
        pass

main_loop(100)
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert res.analysis_scope == "module"
    assert res.time_complexity != "O(2^n)"


def test_memoized_fibonacci_linear(analyzer, parser):
    """10. Memoized recursive function achieves linear time."""
    code = """
def fib_memo(n, memo={}):
    if n in memo:
        return memo[n]
    if n <= 1:
        return n
    memo[n] = fib_memo(n - 1, memo) + fib_memo(n - 2, memo)
    return memo[n]
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert res.time_complexity == "O(n)"


# ==============================================================================
# TEST GROUP C: ANALYSIS TARGET SEMANTICS
# ==============================================================================

def test_single_function_no_invocation(analyzer, parser):
    """1. Single function without module calls is inferred as target."""
    code = """
def binary_search(arr, target):
    low = 0
    high = len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert res.analysis_scope == "function"
    assert res.analysis_target == "binary_search"
    assert res.time_complexity == "O(log n)"


def test_top_level_executable_calling_function(analyzer, parser):
    """4. Executable top-level code calling a function has module scope."""
    code = """
def compute(n):
    for i in range(n):
        pass

compute(100)
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert res.analysis_scope == "module"
    assert res.analysis_target == "<module>"


def test_main_guard_entrypoint(analyzer, parser):
    """5. if __name__ == '__main__': entrypoint is evaluated under module scope."""
    code = """
def main_task(n):
    for i in range(n):
        for j in range(n):
            pass

if __name__ == '__main__':
    main_task(10)
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert res.analysis_scope == "module"
    assert res.analysis_target == "<module>"


def test_linear_and_exp_rec_semantic_verification(analyzer, parser):
    """7. Verifies Section 16 Group C exact requirement:
    - Module execution: O(1)
    - linear_rec: O(n)
    - exp_rec: O(2ⁿ)
    - Function collection: correctly labelled, not falsely presented as module execution.
    """
    code = """
def linear_rec(n):
    if n <= 1:
        return 1
    return linear_rec(n - 1)

def exp_rec(n):
    if n <= 1:
        return 1
    return exp_rec(n - 1) + exp_rec(n - 1)
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)

    # 1. Function collection correctly labelled
    assert res.analysis_scope == "function_collection"
    assert "linear_rec" in res.analysis_target
    assert "exp_rec" in res.analysis_target

    # 2. Per-function analyses verified
    analyses = {f["name"]: f for f in res.function_analyses}
    assert analyses["linear_rec"]["time_complexity"] == "O(n)"
    assert analyses["exp_rec"]["time_complexity"] == "O(2^n)"

    # 3. Explicit disclosure that module level execution without calls is O(1)
    assert "Module-level execution without invocations is O(1)" in res.complexity_reasoning


# ==============================================================================
# TEST GROUP D: OPERATION DIAGNOSTICS & TYPE AWARENESS
# ==============================================================================

def test_integer_accumulation_no_warning(analyzer, parser):
    """1. Integer addition += in loop must NOT trigger string concatenation warning."""
    code = """
def sum_numbers(n):
    total = 0
    for i in range(n):
        total += i
    return total
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    # Zero string concatenation warnings
    assert not any("string" in hint.lower() and "concat" in hint.lower() for hint in res.optimization_suggestions)


def test_annotated_int_accumulation_no_warning(analyzer, parser):
    """2. Explicitly annotated int accumulation does NOT trigger warning."""
    code = """
def sum_values(values):
    result: int = 0
    for x in values:
        result += x
    return result
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert not any("string" in hint.lower() and "concat" in hint.lower() for hint in res.optimization_suggestions)


def test_float_accumulation_no_warning(analyzer, parser):
    """3. Float accumulation does NOT trigger warning."""
    code = """
def sum_floats(arr):
    val = 0.0
    for x in arr:
        val += x
    return val
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert not any("string" in hint.lower() and "concat" in hint.lower() for hint in res.optimization_suggestions)


def test_string_accumulation_triggers_diagnostic(analyzer, parser):
    """4. String concatenation += in loop DOES trigger optimization diagnostic."""
    code = """
def build_string(parts):
    text = ""
    for part in parts:
        text += part
    return text
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert any("string concatenation" in hint.lower() for hint in res.optimization_suggestions)
    assert any("join" in hint.lower() for hint in res.optimization_suggestions)


def test_annotated_string_accumulation_triggers_diagnostic(analyzer, parser):
    """5. Explicitly annotated str accumulation DOES trigger optimization diagnostic."""
    code = """
def build_annotated(parts):
    text: str = ""
    for part in parts:
        text += part
    return text
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert any("string concatenation" in hint.lower() for hint in res.optimization_suggestions)


def test_unknown_type_accumulation_no_false_claim(analyzer, parser):
    """6. Unknown dynamic value does NOT assert string concatenation."""
    code = """
def process_dynamic(values):
    result = fetch_unknown_data()
    for x in values:
        result += x
    return result
"""
    tree, err = parser.parse_code(code)
    assert err is None
    res = analyzer.analyze(tree)
    assert not any("string concatenation" in hint.lower() for hint in res.optimization_suggestions)
