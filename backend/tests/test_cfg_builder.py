import ast
import pytest
from app.analyzers.cfg_builder import CFGBuilder, ControlFlowGraph, BasicBlock, CFGEdge


class TestCFGBuilderBasics:
    """Verifies fundamental CFG construction, basic blocks, IDs, sentinels, and scopes."""

    def test_empty_function_invariants(self):
        code = "def empty():\n    pass"
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)

        assert "empty@1" in cfgs
        cfg = cfgs["empty@1"]

        assert cfg.scope_id == "empty@1"
        assert cfg.name == "empty"
        assert cfg.scope_type in ("function", "module")
        assert cfg.reachable_nodes == 3  # entry, B0 (pass), exit
        assert cfg.reachable_edges == 2  # entry -> B0, B0 -> exit
        assert cfg.unreachable_basic_blocks == 0
        assert cfg.graph_cyclomatic == 1
        assert cfg.decision_cyclomatic == 1
        assert cfg.cyclomatic_status == "COMPLETE"
        assert cfg.risk_rank == "A"

    def test_empty_module(self):
        code = ""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)

        assert "<module>" in cfgs
        cfg = cfgs["<module>"]
        assert cfg.reachable_nodes == 2  # entry, exit
        assert cfg.reachable_edges == 1  # entry -> exit
        assert cfg.graph_cyclomatic == 1
        assert cfg.cyclomatic_complexity == 1
        assert cfg.cyclomatic_status == "COMPLETE"

    def test_straight_line_statements(self):
        code = """
def calc(a, b):
    x = a + 1
    y = b * 2
    z = x + y
    return z
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["calc@2"]

        assert cfg.reachable_nodes == 3  # entry, B0 (x=, y=, z=, return z), exit
        assert cfg.reachable_edges == 2  # entry -> B0, B0 -> exit
        assert cfg.unreachable_basic_blocks == 0
        assert cfg.cyclomatic_complexity == 1
        assert cfg.graph_cyclomatic == 1
        assert cfg.decision_cyclomatic == 1
        assert cfg.cyclomatic_status == "COMPLETE"

        # Verify statements are ordered inside the block
        b0 = [n for n in cfg.nodes.values() if n.block_type == "basic_block"][0]
        assert len(b0.statements) == 4
        snippets = b0.statement_snippets()
        assert "x = a + 1" in snippets[0]
        assert "return z" in snippets[-1]

    def test_stable_node_and_edge_ids(self):
        code = """
def foo(x):
    y = x + 1
    return y
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["foo@2"]

        assert cfg.entry_id == "foo@2_entry"
        assert cfg.exit_id == "foo@2_exit"
        for nid in cfg.nodes:
            assert nid.startswith("foo@2_")
        for edge in cfg.edges:
            assert edge.edge_id.startswith("edge_")
            assert edge.source in cfg.nodes
            assert edge.target in cfg.nodes

    def test_source_line_spans(self):
        code = """
def span_check():
    a = 1
    b = 2
    c = 3
    return a + b + c
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["span_check@2"]

        b0 = [n for n in cfg.nodes.values() if n.block_type == "basic_block"][0]
        assert b0.lineno == 3
        assert b0.end_lineno == 6

    def test_serialization_dict_safety(self):
        code = "def f(): return 42"
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["f@1"]
        d = cfg.to_dict()

        assert isinstance(d, dict)
        assert d["name"] == "f"
        assert d["cyclomatic_complexity"] == 1
        assert len(d["nodes"]) == 3
        assert len(d["edges"]) == 2
        # Check no ast.AST objects remain in serialization
        for n in d["nodes"]:
            assert isinstance(n["statements"], list)
            for stmt in n["statements"]:
                assert isinstance(stmt, str)

    def test_scope_isolation_nested_functions(self):
        code = """
def outer(x):
    a = x * 2
    def inner(y):
        b = y + 10
        return b
    c = inner(a)
    return c
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)

        assert "outer@2" in cfgs
        assert "outer.inner@4" in cfgs

        outer_cfg = cfgs["outer@2"]
        inner_cfg = cfgs["outer.inner@4"]

        # Outer CFG does not inline inner function's body
        # Outer has: a = x*2, def inner(y), c = inner(a), return c -> all in basic block
        assert outer_cfg.reachable_nodes == 3  # entry, B0, exit
        assert outer_cfg.cyclomatic_complexity == 1

        # Inner CFG has its own independent graph
        assert inner_cfg.reachable_nodes == 3  # entry, B0, exit
        assert inner_cfg.cyclomatic_complexity == 1

    def test_scope_isolation_class_and_methods(self):
        code = """
class Calculator:
    base_val = 100

    def add(self, x):
        return x + self.base_val

    def sub(self, x):
        return x - self.base_val
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)

        assert "class_body:Calculator@2" in cfgs
        assert "Calculator.add@5" in cfgs
        assert "Calculator.sub@8" in cfgs

        cb_cfg = cfgs["class_body:Calculator@2"]
        assert cb_cfg.scope_type == "class_body"
        assert cb_cfg.cyclomatic_complexity == 1

        add_cfg = cfgs["Calculator.add@5"]
        assert add_cfg.scope_type in ("method", "function")
        assert add_cfg.cyclomatic_complexity == 1

        sub_cfg = cfgs["Calculator.sub@8"]
        assert sub_cfg.scope_type in ("method", "function")
        assert sub_cfg.cyclomatic_complexity == 1

    def test_serialization_has_provisional_flag(self):
        code = "def f(): return 42"
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["f@1"]
        d = cfg.to_dict()

        assert "is_provisional" in d
        assert d["is_provisional"] is False

    def test_project_summary_aggregation(self):
        code = """
class Calculator:
    base_val = 100

    def add(self, x):
        if x > 0:
            return x + self.base_val
        return self.base_val

    def sub(self, x):
        return x - self.base_val
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        summary = CFGBuilder.compute_project_summary(cfgs)

        # Calculator.add: CC=2, Calculator.sub: CC=1 -> avg = (2 + 1) / 2 = 1.5
        # Excludes module and class_body:Calculator@2 from denominator
        assert summary["function_count"] == 2
        assert summary["average_cyclomatic_complexity"] == 1.5
        assert summary["total_scopes"] >= 4  # module, class_body, add, sub

    def test_empty_function_population_summary(self):
        code = "a = 1; b = 2; c = a + b"
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        summary = CFGBuilder.compute_project_summary(cfgs)

        assert summary["function_count"] == 0
        assert summary["average_cyclomatic_complexity"] is None
        assert summary["provisional_average_cyclomatic_complexity"] is None
        assert summary["complete_function_count"] == 0
        assert summary["partial_function_count"] == 0

    def test_project_summary_provisional_segregation(self):
        code = """
def normal_fn(x):
    if x > 0:
        return x
    return 0

def partial_fn(nums):
    return [x for x in nums if x > 0]
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        summary = CFGBuilder.compute_project_summary(cfgs)

        assert summary["function_count"] == 2
        assert summary["complete_function_count"] == 1
        assert summary["partial_function_count"] == 1
        assert summary["average_cyclomatic_complexity"] == 2.0  # normal_fn only
        assert summary["provisional_average_cyclomatic_complexity"] == 3.0  # partial_fn only


class TestCFGClosureAudit:
    """Verifies Phase 1B.1 closure audit requirements: temporary isolation, scope types, and error boundaries."""

    def test_temporary_value_isolation_and_no_collision(self):
        code = """
def f(_t0, _t1, __cfg_tmp_0__):
    _t2 = calculate()
    res = consume(_t0 and _t1)
    return _t0, _t1, _t2, res, __cfg_tmp_0__
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        assert "f@2" in cfgs
        cfg = cfgs["f@2"]

        # User's identifier __cfg_tmp_0__ was in scope, so the generated temp must be __cfg_tmp_1__
        # Ensure generated temp (__cfg_tmp_1__) is NOT leaked into any user-facing snippets
        for node in cfg.nodes.values():
            snippets = node.statement_snippets()
            for s in snippets:
                assert "__cfg_tmp_1__" not in s

        # User's statements and variables remain intact
        return_block = [n for n in cfg.nodes.values() if n.terminator_type == "return"][0]
        assert any("_t0" in s and "__cfg_tmp_0__" in s for s in return_block.statement_snippets())

        # Verify statement_count is not inflated by synthetic assignments
        # f has: _t2 = calculate(), res = consume(...), return (...) -> 3 user statements
        user_stmt_count = sum(node.statement_count for node in cfg.nodes.values())
        assert user_stmt_count == 3

        # Verify dictionary serialization
        d = cfg.to_dict()
        for n in d["nodes"]:
            assert "statement_count" in n
            for stmt in n["statements"]:
                assert "__cfg_tmp_1__" not in stmt

    def test_scope_type_conformance_with_stage_012(self):
        code = """
async def standalone_async(x):
    return x + 1

class Service:
    def sync_method(self, y):
        return y * 2

    async def async_method(self, z):
        return z * 3

def outer_sync():
    async def nested_async(w):
        return w - 1
    return nested_async
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)

        # Validate every CFG scope type is in the approved Stage 0.1.2 vocabulary
        VALID_SCOPE_TYPES = {"module", "function", "method", "class_body"}
        for scope_id, cfg in cfgs.items():
            assert cfg.scope_type in VALID_SCOPE_TYPES, f"{scope_id} has invalid scope_type: {cfg.scope_type}"
            # Ensure async_function is never emitted
            assert cfg.scope_type != "async_function"

        # Check specific mappings
        assert cfgs["<module>"].scope_type == "module"
        assert cfgs["standalone_async@2"].scope_type == "function"
        assert cfgs["class_body:Service@5"].scope_type == "class_body"
        assert cfgs["Service.sync_method@6"].scope_type == "method"
        assert cfgs["Service.async_method@9"].scope_type == "method"
        assert cfgs["outer_sync@12"].scope_type == "function"
        assert cfgs["outer_sync.nested_async@13"].scope_type == "function"

        # Verify project summary aggregates all procedural scopes (functions + methods)
        summary = CFGBuilder.compute_project_summary(cfgs)
        # 5 procedural scopes: standalone_async, sync_method, async_method, outer_sync, nested_async
        assert summary["function_count"] == 5
        assert summary["total_scopes"] == 7

    def test_error_boundary_unsupported_vs_internal_failure(self):
        # Known unsupported construct: PEP 634 match statement records limitation and status
        code = """
def match_handler(val):
    match val:
        case 1:
            return "one"
        case _:
            return "other"
"""
        tree = ast.parse(code)
        cfgs = CFGBuilder.build_all(tree)
        cfg = cfgs["match_handler@2"]
        assert cfg.cyclomatic_status == "PARTIAL"
        assert any("match" in lim.lower() for lim in cfg.limitations)

        # Unexpected internal analyzer defect raises diagnosably
        class MalformedBuilder(CFGBuilder):
            def _build_statements(self, stmts, current_block):
                raise TypeError("Unexpected internal analyzer corruption")

        with pytest.raises(TypeError, match="Unexpected internal analyzer corruption"):
            MalformedBuilder.build_all(tree)

