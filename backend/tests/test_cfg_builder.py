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
        assert summary["average_cyclomatic_complexity"] == 1.0
