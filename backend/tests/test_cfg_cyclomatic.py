import ast
import pytest
from app.analyzers.cfg_builder import CFGBuilder


class TestCFGCyclomaticComplexity:
    """Verifies mathematical correctness of McCabe cyclomatic complexity and reachability."""

    def test_complete_parity_canonical_algorithms(self):
        # 1. Binary Search
        binary_search_code = """
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
        tree = ast.parse(binary_search_code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["binary_search@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        # while (+1), if (+1), elif (+1) -> Total 4
        assert cfg.cyclomatic_complexity == 4
        assert cfg.graph_cyclomatic == 4
        assert cfg.decision_cyclomatic == 4
        assert cfg.cyclomatic_discrepancy == 0
        assert cfg.risk_rank == "A"

    def test_dead_code_after_return(self):
        code = """
def early_exit(x):
    if x > 0:
        return 1
        a = 100  # dead code
        b = 200  # dead code
    return 0
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["early_exit@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 2  # if (+1)
        assert cfg.unreachable_basic_blocks == 1  # The dead block containing a=100, b=200
        assert cfg.total_nodes > cfg.reachable_nodes

        # Verify dead block is flagged is_unreachable
        dead_blocks = [n for n in cfg.nodes.values() if n.is_unreachable and n.block_type not in ("entry", "exit")]
        assert len(dead_blocks) == 1
        assert "a = 100" in dead_blocks[0].statement_snippets()[0]

    def test_dead_code_after_raise(self):
        code = """
def fatal(x):
    if x < 0:
        raise ValueError("negative")
        print("never reached")
    return x
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["fatal@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 2
        assert cfg.unreachable_basic_blocks == 1

    def test_dead_code_after_break(self):
        code = """
def loop_dead(items):
    for x in items:
        break
        dead_statement = True
    return "done"
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["loop_dead@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.unreachable_basic_blocks == 1

    def test_risk_rank_scale(self):
        # Function with 7 decision points -> CC = 8 -> Rank B
        code = """
def rank_b_fn(x):
    if x == 1: pass
    if x == 2: pass
    if x == 3: pass
    if x == 4: pass
    if x == 5: pass
    if x == 6: pass
    if x == 7: pass
    return x
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["rank_b_fn@2"]

        assert cfg.cyclomatic_complexity == 8
        assert cfg.risk_rank == "B"

    def test_partial_status_comprehension(self):
        code = """
def comp_fn(nums):
    evens = [x * 2 for x in nums if x % 2 == 0]
    return evens
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["comp_fn@2"]

        assert cfg.cyclomatic_status == "PARTIAL"
        assert "Comprehension loops and filters are summarized at basic-block level" in cfg.limitations
        # decision cyclomatic counts: 1 + for (+1) + if (+1) = 3
        assert cfg.decision_cyclomatic == 3
        assert cfg.graph_cyclomatic == 1  # basic block contains comprehension expression atomically
        assert cfg.cyclomatic_discrepancy == 2

    def test_partial_status_chained_comparison(self):
        code = """
def range_check(x):
    if 0 < x < 100:
        return True
    return False
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["range_check@2"]

        assert cfg.cyclomatic_status == "PARTIAL"
        assert "Chained comparison short-circuiting is summarized at basic-block level" in cfg.limitations
        # 1 + if(1) + chained(1) = 3
        assert cfg.decision_cyclomatic == 3
        assert cfg.graph_cyclomatic == 2  # atomic comparison test block

    def test_partial_status_try_except(self):
        code = """
def safe_div(a, b):
    try:
        res = a / b
    except ZeroDivisionError:
        res = 0
    except TypeError:
        res = -1
    finally:
        cleanup()
    return res
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["safe_div@2"]

        assert cfg.cyclomatic_status == "PARTIAL"
        assert "Exception flow does not represent all statement-level implicit exceptions" in cfg.limitations
        # 2 except handlers
        assert cfg.decision_points == {"except_handler": 2}
        assert cfg.decision_cyclomatic == 3

    def test_partial_status_generator_yield(self):
        code = """
def gen_numbers(n):
    for i in range(n):
        yield i
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["gen_numbers@2"]

        assert cfg.cyclomatic_status == "PARTIAL"
        assert "Generator yield/resume control flow is summarized" in cfg.limitations

    def test_partial_status_pep634_match(self):
        code = """
def match_test(status):
    match status:
        case 200:
            return "ok"
        case 404:
            return "not found"
        case _:
            return "other"
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["match_test@2"]

        assert cfg.cyclomatic_status == "PARTIAL"
        assert "PEP 634 match/case statements are deferred to Phase 1B.2" in cfg.limitations
        assert cfg.decision_points == {"match_case": 3}

    def test_unsupported_status_contract(self):
        builder = CFGBuilder(scope_id="unsupported_fn@1", name="unsupported_fn", scope_type="function")
        builder.mark_unsupported("Inline assembly or unsupported dynamic bytecode syntax")
        cfg = builder.build_from_body([])

        assert cfg.cyclomatic_status == "UNSUPPORTED"
        assert cfg.cyclomatic_complexity is None
        assert cfg.risk_rank is None
        assert cfg.is_provisional is False
        assert "Inline assembly or unsupported dynamic bytecode syntax" in cfg.limitations

    def test_partial_status_provisional_contract(self):
        code = """
def partial_comprehension(nums):
    return [x for x in nums if x > 0]
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["partial_comprehension@2"]

        assert cfg.cyclomatic_status == "PARTIAL"
        assert cfg.is_provisional is True
        assert cfg.risk_rank is None  # Unqualified risk rank must not be exposed for PARTIAL
        assert cfg.cyclomatic_complexity == cfg.decision_cyclomatic
        assert cfg.graph_cyclomatic is not None
        assert cfg.cyclomatic_discrepancy == cfg.decision_cyclomatic - cfg.graph_cyclomatic

    def test_try_finally_cleanup_limitations(self):
        code = """
def try_finally_check(x):
    try:
        if x < 0:
            raise ValueError("negative")
        return x
    finally:
        cleanup()
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["try_finally_check@2"]

        assert cfg.cyclomatic_status == "PARTIAL"
        assert "Finally cleanup transitions on abrupt control transfers (return/break/raise/continue) are summarized" in cfg.limitations
        assert "Exception flow does not represent all statement-level implicit exceptions" in cfg.limitations
        # Verify candidate dispatch edge exists
        edge_types = [e.edge_type for e in cfg.edges]
        assert "finally_cleanup" in edge_types or "raise" in edge_types

    def test_unsupported_status_lifecycle_robustness(self):
        builder = CFGBuilder(scope_id="unsupported_lifecycle@1", name="unsupported_lifecycle", scope_type="function")
        builder.mark_unsupported("Explicit syntax limitation")
        # Ensure _add_limitation does not overwrite UNSUPPORTED with PARTIAL
        builder._add_limitation("Secondary minor limitation")
        cfg = builder.build_from_body([])

        assert cfg.cyclomatic_status == "UNSUPPORTED"
        assert cfg.cyclomatic_complexity is None
        assert cfg.graph_cyclomatic is None
        assert cfg.decision_cyclomatic is None
        assert cfg.cyclomatic_discrepancy is None
        assert cfg.risk_rank is None
        assert cfg.is_provisional is False

        d = cfg.to_dict()
        assert d["cyclomatic_status"] == "UNSUPPORTED"
        assert d["cyclomatic_complexity"] is None
        assert d["risk_rank"] is None
        assert d["is_provisional"] is False

        summary = CFGBuilder.compute_project_summary({cfg.scope_id: cfg})
        assert summary["function_count"] == 1
        assert summary["unsupported_function_count"] == 1
        assert summary["complete_function_count"] == 0
        assert summary["average_cyclomatic_complexity"] is None
        assert summary["provisional_average_cyclomatic_complexity"] is None
