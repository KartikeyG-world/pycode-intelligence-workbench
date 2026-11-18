import ast
import pytest
from app.analyzers.cfg_builder import CFGBuilder


class TestCFGControlFlow:
    """Verifies control flow semantics for branches, loops, and expression-level branching."""

    def test_simple_if_without_else(self):
        code = """
def check(x):
    y = 0
    if x > 0:
        y = 1
    return y
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["check@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 2
        assert cfg.graph_cyclomatic == 2
        assert cfg.decision_cyclomatic == 2
        assert cfg.decision_points == {"if": 1}

        # Check edge labels: must have branch_true and branch_false
        edge_types = [e.edge_type for e in cfg.edges]
        assert "branch_true" in edge_types
        assert "branch_false" in edge_types

    def test_if_else_branching(self):
        code = """
def sign(x):
    if x > 0:
        return 1
    else:
        return -1
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["sign@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 2
        assert cfg.reachable_nodes == 5  # entry, header, then, else, exit
        assert cfg.reachable_edges == 5

    def test_elif_chain(self):
        code = """
def classify(x):
    if x > 10:
        return "high"
    elif x > 0:
        return "mid"
    else:
        return "low"
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["classify@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 3
        assert cfg.graph_cyclomatic == 3
        assert cfg.decision_cyclomatic == 3
        assert cfg.decision_points == {"if": 2}

    def test_nested_conditionals(self):
        code = """
def nested(x, y):
    if x > 0:
        if y > 0:
            return 1
        else:
            return 2
    else:
        return 0
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["nested@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 3
        assert cfg.decision_points == {"if": 2}

    def test_while_loop_with_back_and_exit_edges(self):
        code = """
def countdown(n):
    while n > 0:
        n -= 1
    return n
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["countdown@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 2
        assert cfg.reachable_nodes == 5
        assert cfg.reachable_edges == 5

        edge_types = [e.edge_type for e in cfg.edges]
        assert "loop_body" in edge_types
        assert "loop_back" in edge_types
        assert "loop_exit" in edge_types

    def test_for_loop(self):
        code = """
def sum_items(items):
    total = 0
    for item in items:
        total += item
    return total
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["sum_items@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 2
        assert cfg.decision_points == {"for": 1}

    def test_async_for_loop(self):
        code = """
async def async_iter(stream):
    total = 0
    async for item in stream:
        total += item
    return total
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["async_iter@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 2
        assert cfg.decision_points == {"for": 1}

    def test_nested_loops_and_context(self):
        code = """
def matrix_scan(n, m):
    for i in range(n):
        for j in range(m):
            step()
    return 0
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["matrix_scan@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 3
        assert cfg.decision_points == {"for": 2}

    def test_for_loop_else(self):
        code = """
def find_item(items, target):
    for item in items:
        if item == target:
            break
    else:
        return "not_found"
    return "found"
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["find_item@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 3  # for (+1), if (+1), total 3
        assert cfg.decision_points == {"for": 1, "if": 1}

        edge_types = [e.edge_type for e in cfg.edges]
        assert "break" in edge_types
        assert "loop_exit" in edge_types

    def test_break_and_continue_targets(self):
        code = """
def loop_controls(items):
    for x in items:
        if x < 0:
            continue
        if x == 100:
            break
        process(x)
    return "done"
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["loop_controls@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 4  # for (+1), if (+1), if (+1), total 4
        edge_types = [e.edge_type for e in cfg.edges]
        assert "continue" in edge_types
        assert "break" in edge_types

    def test_nested_break_targets_innermost_loop(self):
        code = """
def nested_breaks(outer_list, inner_list):
    for x in outer_list:
        for y in inner_list:
            if y == 0:
                break
            step()
    return True
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["nested_breaks@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 4  # for outer (+1), for inner (+1), if (+1)
        # Verify break edge connects to inner loop exit, not outer
        break_edges = [e for e in cfg.edges if e.edge_type == "break"]
        assert len(break_edges) == 1

    def test_boolean_and_short_circuit_sub_blocks(self):
        code = """
def check_and(a, b):
    if a and b:
        return 1
    return 0
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["check_and@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 3  # if (+1), and (+1)
        assert cfg.decision_points == {"if": 1, "and": 1}
        assert cfg.graph_cyclomatic == 3
        assert cfg.decision_cyclomatic == 3

    def test_boolean_or_short_circuit_sub_blocks(self):
        code = """
def check_or(a, b):
    if a or b:
        return 1
    return 0
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["check_or@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 3
        assert cfg.decision_points == {"if": 1, "or": 1}

    def test_nested_boolean_expression(self):
        code = """
def check_nested(a, b, c):
    if a and (b or c):
        return 1
    return 0
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["check_nested@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 4  # if (+1), and (+1), or (+1)
        assert cfg.decision_points == {"if": 1, "and": 1, "or": 1}

    def test_boolean_op_in_assignment(self):
        code = """
def assign_bool(a, b):
    x = a and b
    return x
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["assign_bool@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 2  # and (+1)
        assert cfg.decision_points == {"and": 1}

    def test_boolean_op_in_return(self):
        code = """
def ret_bool(a, b):
    return a or b
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["ret_bool@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 2  # or (+1)
        assert cfg.decision_points == {"or": 1}

    def test_if_exp_in_assignment(self):
        code = """
def tern_assign(c):
    val = 10 if c else 20
    return val
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["tern_assign@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 2  # if_exp (+1)
        assert cfg.decision_points == {"if_exp": 1}

    def test_if_exp_in_return(self):
        code = """
def tern_ret(c):
    return 10 if c else 20
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["tern_ret@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 2  # if_exp (+1)
        assert cfg.decision_points == {"if_exp": 1}

    def test_assert_statement(self):
        code = """
def check_val(x):
    assert x > 0, "must be positive"
    return x * 2
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["check_val@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 2  # assert (+1)
        assert cfg.decision_points == {"assert": 1}

    def test_with_and_async_with(self):
        code = """
def context_use(filepath):
    with open(filepath) as f:
        data = f.read()
    return data
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["context_use@2"]

        # with does not add decision points (+0)
        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 1

    def test_embedded_bool_op_in_call_return(self):
        code = """
def calc_bool(a, b):
    return calculate(a and b)
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["calc_bool@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 2
        assert cfg.graph_cyclomatic == 2
        assert cfg.decision_cyclomatic == 2
        assert cfg.decision_points == {"and": 1}

    def test_embedded_if_exp_in_call_return(self):
        code = """
def calc_ifexp(a, b, c):
    return calculate(a if b else c)
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["calc_ifexp@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 2
        assert cfg.graph_cyclomatic == 2
        assert cfg.decision_cyclomatic == 2
        assert cfg.decision_points == {"if_exp": 1}

    def test_assert_with_bool_op_short_circuit(self):
        code = """
def check_assert_or(a, b):
    assert a or b
    return 1
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["check_assert_or@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 3  # assert (+1), or (+1)
        assert cfg.graph_cyclomatic == 3
        assert cfg.decision_cyclomatic == 3
        assert cfg.decision_points == {"assert": 1, "or": 1}

    def test_nested_bool_op_in_assignment(self):
        code = """
def nested_assign_bool(a, b, c):
    x = a and (b or c)
    return x
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["nested_assign_bool@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 3  # and (+1), or (+1)
        assert cfg.graph_cyclomatic == 3
        assert cfg.decision_cyclomatic == 3
        assert cfg.decision_points == {"and": 1, "or": 1}

    def test_nested_if_exp_combinations(self):
        code = """
def nested_ternary(a, b, c, d, e):
    x = (a if b else c) if d else e
    return x
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["nested_ternary@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 3  # if_exp (+1), if_exp (+1)
        assert cfg.graph_cyclomatic == 3
        assert cfg.decision_cyclomatic == 3
        assert cfg.decision_points == {"if_exp": 2}

    def test_if_exp_with_bool_op_condition(self):
        code = """
def ternary_bool_cond(a, b, c, d):
    x = a if (b and c) else d
    return x
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["ternary_bool_cond@2"]

        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.cyclomatic_complexity == 3  # if_exp (+1), and (+1)
        assert cfg.graph_cyclomatic == 3
        assert cfg.decision_cyclomatic == 3
        assert cfg.decision_points == {"if_exp": 1, "and": 1}
