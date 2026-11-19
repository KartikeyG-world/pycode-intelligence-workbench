import ast
import copy
from collections import deque
from typing import Dict, Any, List, Optional, Set, Tuple, Literal

CFGBlockType = Literal[
    "entry",
    "basic_block",
    "branch_header",
    "loop_header",
    "short_circuit_header",
    "return_block",
    "raise_block",
    "except_handler",
    "finally_block",
    "exit",
]

CFGEdgeType = Literal[
    "entry",
    "fallthrough",
    "branch_true",
    "branch_false",
    "loop_body",
    "loop_back",
    "loop_exit",
    "break",
    "continue",
    "return",
    "raise",
    "except_dispatch",
    "finally_cleanup",
]


def _is_atomic(node: ast.AST) -> bool:
    """Returns True if the AST node is an atomic literal or variable reference without side-effects."""
    return isinstance(node, (ast.Name, ast.Constant))


class BasicBlock:
    """Represents a maximal sequence of straight-line AST statements without intervening control-flow transfers."""

    def __init__(
        self,
        block_id: str,
        scope_id: str,
        block_type: CFGBlockType = "basic_block",
        label: str = "",
        lineno: Optional[int] = None,
        end_lineno: Optional[int] = None,
        is_unreachable: bool = False,
    ):
        self.block_id = block_id
        self.scope_id = scope_id
        self.block_type: CFGBlockType = block_type
        self.label = label
        self.statements: List[ast.AST] = []
        self.lineno = lineno
        self.end_lineno = end_lineno
        self.is_unreachable = is_unreachable
        self.terminator_type: str = "fallthrough"

    def add_statement(self, stmt: ast.AST):
        self.statements.append(stmt)
        s_lineno = getattr(stmt, "lineno", None)
        s_end_lineno = getattr(stmt, "end_lineno", s_lineno)
        if s_lineno is not None:
            if self.lineno is None or s_lineno < self.lineno:
                self.lineno = s_lineno
        if s_end_lineno is not None:
            if self.end_lineno is None or s_end_lineno > self.end_lineno:
                self.end_lineno = s_end_lineno

    def statement_snippets(self) -> List[str]:
        snippets: List[str] = []
        for s in self.statements:
            try:
                code = ast.unparse(s)
                if len(code) > 60:
                    code = code[:57] + "..."
                snippets.append(code)
            except Exception:
                snippets.append(type(s).__name__)
        return snippets

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.block_id,
            "scope_id": self.scope_id,
            "block_type": self.block_type,
            "label": self.label or (self.statement_snippets()[0] if self.statement_snippets() else self.block_type),
            "statements": self.statement_snippets(),
            "lineno": self.lineno,
            "end_lineno": self.end_lineno,
            "is_unreachable": self.is_unreachable,
            "terminator_type": self.terminator_type,
        }


class CFGEdge:
    """Represents a directed transfer of control between basic blocks."""

    def __init__(
        self,
        edge_id: str,
        source: str,
        target: str,
        edge_type: CFGEdgeType,
        label: Optional[str] = None,
    ):
        self.edge_id = edge_id
        self.source = source
        self.target = target
        self.edge_type: CFGEdgeType = edge_type
        self.label = label

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.edge_id,
            "source": self.source,
            "target": self.target,
            "edge_type": self.edge_type,
            "label": self.label,
        }


class ControlFlowGraph:
    """Represents a complete, validated control flow graph for a procedural or module scope."""

    def __init__(
        self,
        scope_id: str,
        name: str,
        scope_type: str,
        entry_id: str,
        exit_id: str,
        lineno: Optional[int] = None,
        end_lineno: Optional[int] = None,
    ):
        self.scope_id = scope_id
        self.name = name
        self.scope_type = scope_type
        self.entry_id = entry_id
        self.exit_id = exit_id
        self.lineno = lineno
        self.end_lineno = end_lineno
        self.nodes: Dict[str, BasicBlock] = {}
        self.edges: List[CFGEdge] = []
        self.cyclomatic_status: Literal["COMPLETE", "PARTIAL", "UNSUPPORTED"] = "COMPLETE"
        self.cyclomatic_complexity: Optional[int] = None
        self.graph_cyclomatic: Optional[int] = None
        self.decision_cyclomatic: Optional[int] = None
        self.cyclomatic_discrepancy: Optional[int] = None
        self.risk_rank: Optional[Literal["A", "B", "C", "D", "E", "F"]] = None
        self.is_provisional: bool = False
        self.total_nodes: int = 0
        self.total_edges: int = 0
        self.reachable_nodes: int = 0
        self.reachable_edges: int = 0
        self.unreachable_basic_blocks: int = 0
        self.decision_points: Dict[str, int] = {}
        self.limitations: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "func_id": self.scope_id,
            "name": self.name,
            "qualified_name": self.name,
            "scope_type": self.scope_type,
            "cyclomatic_status": self.cyclomatic_status,
            "cyclomatic_complexity": self.cyclomatic_complexity,
            "graph_cyclomatic": self.graph_cyclomatic,
            "decision_cyclomatic": self.decision_cyclomatic,
            "cyclomatic_discrepancy": self.cyclomatic_discrepancy,
            "risk_rank": self.risk_rank,
            "is_provisional": self.is_provisional,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "reachable_nodes": self.reachable_nodes,
            "reachable_edges": self.reachable_edges,
            "unreachable_basic_blocks": self.unreachable_basic_blocks,
            "decision_points": self.decision_points,
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
            "limitations": self.limitations,
        }


class _LoopContext:
    def __init__(self, header_id: str, exit_id: str, else_id: Optional[str] = None):
        self.header_id = header_id
        self.exit_id = exit_id
        self.else_id = else_id


class _TryContext:
    def __init__(self, handler_ids: List[str], finally_id: Optional[str] = None):
        self.handler_ids = handler_ids
        self.finally_id = finally_id


class CFGBuilder:
    """Constructs control flow graphs with maximal straight-line basic block decomposition."""

    def __init__(self, scope_id: str, name: str, scope_type: str, lineno: Optional[int] = None, end_lineno: Optional[int] = None):
        self.scope_id = scope_id
        self.name = name
        self.scope_type = scope_type
        self.lineno = lineno
        self.end_lineno = end_lineno

        self.block_counter = 0
        self.edge_counter = 0

        self.entry_id = f"{scope_id}_entry"
        self.exit_id = f"{scope_id}_exit"

        self.cfg = ControlFlowGraph(
            scope_id=scope_id,
            name=name,
            scope_type=scope_type,
            entry_id=self.entry_id,
            exit_id=self.exit_id,
            lineno=lineno,
            end_lineno=end_lineno,
        )

        # Create entry and exit sentinels
        self.entry_block = self._create_block(block_type="entry", label="ENTRY", lineno=lineno, custom_id=self.entry_id)
        self.exit_block = self._create_block(block_type="exit", label="EXIT", lineno=end_lineno, custom_id=self.exit_id)

        self.loop_stack: List[_LoopContext] = []
        self.try_stack: List[_TryContext] = []
        self.decision_points: Dict[str, int] = {}
        self.limitations: List[str] = []
        self.expr_temp_counter = 0

    def _create_block(
        self,
        block_type: CFGBlockType = "basic_block",
        label: str = "",
        lineno: Optional[int] = None,
        custom_id: Optional[str] = None,
        is_unreachable: bool = False,
    ) -> BasicBlock:
        if custom_id:
            bid = custom_id
        else:
            bid = f"{self.scope_id}_b{self.block_counter}"
            self.block_counter += 1

        block = BasicBlock(
            block_id=bid,
            scope_id=self.scope_id,
            block_type=block_type,
            label=label,
            lineno=lineno,
            is_unreachable=is_unreachable,
        )
        self.cfg.nodes[bid] = block
        return block

    def _add_edge(
        self,
        source: str,
        target: str,
        edge_type: CFGEdgeType,
        label: Optional[str] = None,
    ) -> CFGEdge:
        eid = f"edge_{source}_to_{target}_{self.edge_counter}_{edge_type}"
        self.edge_counter += 1
        edge = CFGEdge(edge_id=eid, source=source, target=target, edge_type=edge_type, label=label)
        self.cfg.edges.append(edge)
        return edge

    def _record_decision(self, kind: str, count: int = 1):
        self.decision_points[kind] = self.decision_points.get(kind, 0) + count

    def _add_limitation(self, limitation: str):
        if limitation not in self.limitations:
            self.limitations.append(limitation)
        if self.cfg.cyclomatic_status != "UNSUPPORTED":
            self.cfg.cyclomatic_status = "PARTIAL"

    def mark_unsupported(self, reason: str):
        """Marks the scope cyclomatic status as UNSUPPORTED and records the diagnostic limitation."""
        self.cfg.cyclomatic_status = "UNSUPPORTED"
        if reason not in self.limitations:
            self.limitations.append(reason)

    def _next_expr_temp(self) -> str:
        tid = f"_t{self.expr_temp_counter}"
        self.expr_temp_counter += 1
        return tid

    def _get_eval_children(self, node: ast.AST):
        """Yields (child_node, setter_fn) for an AST expression node in Python's evaluation order."""
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.Lambda)):
            return

        if isinstance(node, ast.Call):
            yield (node.func, lambda v: setattr(node, 'func', v))
            for i, arg in enumerate(node.args):
                yield (arg, lambda v, idx=i: node.args.__setitem__(idx, v))
            for kw in node.keywords:
                yield (kw.value, lambda v, k=kw: setattr(k, 'value', v))

        elif isinstance(node, ast.Subscript):
            yield (node.value, lambda v: setattr(node, 'value', v))
            yield (node.slice, lambda v: setattr(node, 'slice', v))

        elif isinstance(node, ast.Attribute):
            yield (node.value, lambda v: setattr(node, 'value', v))

        elif isinstance(node, ast.BinOp):
            yield (node.left, lambda v: setattr(node, 'left', v))
            yield (node.right, lambda v: setattr(node, 'right', v))

        elif isinstance(node, ast.UnaryOp):
            yield (node.operand, lambda v: setattr(node, 'operand', v))

        elif isinstance(node, ast.Compare):
            yield (node.left, lambda v: setattr(node, 'left', v))
            for i, comp in enumerate(node.comparators):
                yield (comp, lambda v, idx=i: node.comparators.__setitem__(idx, v))

        elif isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            for i, elt in enumerate(node.elts):
                yield (elt, lambda v, idx=i: node.elts.__setitem__(idx, v))

        elif isinstance(node, ast.Dict):
            for i in range(len(node.keys)):
                k = node.keys[i]
                if k is not None:
                    yield (k, lambda v, idx=i: node.keys.__setitem__(idx, v))
                yield (node.values[i], lambda v, idx=i: node.values.__setitem__(idx, v))

        elif isinstance(node, ast.IfExp):
            yield (node.test, lambda v: setattr(node, 'test', v))

        elif isinstance(node, ast.BoolOp):
            yield (node.values[0], lambda v: node.values.__setitem__(0, v))

        elif isinstance(node, ast.NamedExpr):
            yield (node.value, lambda v: setattr(node, 'value', v))

        elif isinstance(node, ast.Starred):
            yield (node.value, lambda v: setattr(node, 'value', v))

        elif isinstance(node, ast.Return):
            if node.value is not None:
                yield (node.value, lambda v: setattr(node, 'value', v))

        elif isinstance(node, ast.Assign):
            yield (node.value, lambda v: setattr(node, 'value', v))

        elif isinstance(node, ast.AnnAssign):
            if node.value is not None:
                yield (node.value, lambda v: setattr(node, 'value', v))

        elif isinstance(node, ast.AugAssign):
            yield (node.target, lambda v: setattr(node, 'target', v))
            yield (node.value, lambda v: setattr(node, 'value', v))

        elif isinstance(node, ast.Expr):
            yield (node.value, lambda v: setattr(node, 'value', v))

        elif isinstance(node, ast.Assert):
            yield (node.test, lambda v: setattr(node, 'test', v))
            if node.msg is not None:
                yield (node.msg, lambda v: setattr(node, 'msg', v))

        elif isinstance(node, ast.If):
            yield (node.test, lambda v: setattr(node, 'test', v))

    def _contains_branch(self, node: ast.AST) -> bool:
        """Checks if an AST node contains an embedded BoolOp or IfExp branch."""
        for child in ast.walk(node):
            if child is not node and isinstance(child, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.Lambda)):
                continue
            if isinstance(child, (ast.BoolOp, ast.IfExp)):
                return True
        return False

    def _extract_first_branch(self, stmt: ast.stmt):
        """Walks stmt in Python evaluation order and extracts the first branching expression.

        Hoists any non-atomic prefix expressions evaluated before the branch into pre-statements.
        Replaces the branching expression with a temporary variable reference.
        Returns (pre_stmts, branch_node, branch_temp, post_stmt) or None if no branch is present.
        """
        if not self._contains_branch(stmt):
            return None

        # Do not decompose top-level BoolOp in Assert (handled directly by _handle_assert)
        if isinstance(stmt, ast.Assert) and isinstance(stmt.test, ast.BoolOp):
            return None
        # Also do not decompose top-level not(BoolOp) in Assert (handled directly by _handle_assert)
        if (isinstance(stmt, ast.Assert) and isinstance(stmt.test, ast.UnaryOp)
                and isinstance(stmt.test.op, ast.Not) and isinstance(stmt.test.operand, ast.BoolOp)):
            return None
        # Do not decompose top-level BoolOp or IfExp in If (handled directly by _handle_if)
        if isinstance(stmt, ast.If) and isinstance(stmt.test, (ast.BoolOp, ast.IfExp)):
            return None

        pre_stmts: List[ast.stmt] = []
        stmt_copy = copy.deepcopy(stmt)

        def visit(node, setter):
            if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.Lambda)):
                return None

            if isinstance(node, ast.IfExp):
                sub = visit(node.test, lambda v: setattr(node, 'test', v))
                if sub is not None:
                    return sub
                b_temp = self._next_expr_temp()
                temp_node = ast.Name(id=b_temp, ctx=ast.Load())
                ast.copy_location(temp_node, node)
                setter(temp_node)
                return (node, b_temp)

            if isinstance(node, ast.BoolOp):
                sub = visit(node.values[0], lambda v: node.values.__setitem__(0, v))
                if sub is not None:
                    return sub
                b_temp = self._next_expr_temp()
                temp_node = ast.Name(id=b_temp, ctx=ast.Load())
                ast.copy_location(temp_node, node)
                setter(temp_node)
                return (node, b_temp)

            for child, child_setter in self._get_eval_children(node):
                if self._contains_branch(child):
                    return visit(child, child_setter)
                else:
                    if not _is_atomic(child) and not isinstance(child, (ast.Name, ast.Constant)):
                        t_name = self._next_expr_temp()
                        assign = ast.Assign(
                            targets=[ast.Name(id=t_name, ctx=ast.Store())],
                            value=copy.deepcopy(child),
                        )
                        ast.copy_location(assign, child)
                        ast.fix_missing_locations(assign)
                        pre_stmts.append(assign)
                        t_ref = ast.Name(id=t_name, ctx=ast.Load())
                        ast.copy_location(t_ref, child)
                        child_setter(t_ref)

            return None

        branch_info = visit(stmt_copy, lambda v: None)
        if branch_info is None:
            return None

        branch_node, branch_temp = branch_info
        return pre_stmts, branch_node, branch_temp, stmt_copy

    def build_from_body(self, body: List[ast.stmt]) -> ControlFlowGraph:
        """Builds the CFG for the provided sequence of statements."""
        if not body:
            # Empty scope: Entry -> Exit
            self._add_edge(self.entry_id, self.exit_id, edge_type="fallthrough")
            self._validate_and_finalize()
            return self.cfg

        first_block = self._create_block(block_type="basic_block", label="Start")
        self._add_edge(self.entry_id, first_block.block_id, edge_type="entry")

        final_block = self._build_statements(body, current_block=first_block)

        if final_block and not final_block.is_unreachable:
            if final_block.terminator_type == "fallthrough":
                self._add_edge(final_block.block_id, self.exit_id, edge_type="fallthrough")

        self._validate_and_finalize()
        return self.cfg

    def _build_statements(
        self,
        stmts: List[ast.stmt],
        current_block: BasicBlock,
    ) -> Optional[BasicBlock]:
        curr = current_block

        for i, stmt in enumerate(stmts):
            if curr is None or curr.terminator_type in ("return", "raise", "break", "continue"):
                if curr is None or not curr.is_unreachable:
                    # Switch to dead code block for remaining statements
                    dead_block = self._create_block(block_type="basic_block", label="Unreachable Dead Code", is_unreachable=True)
                    curr = dead_block
                curr.add_statement(stmt)
                continue

            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # Declarations count as atomic statements in enclosing scope; bodies are not traversed here
                curr.add_statement(stmt)
                continue

            # Check if this statement has an embedded branching expression requiring lowering
            branch_info = self._extract_first_branch(stmt)
            if branch_info is not None:
                pre_stmts, branch_node, branch_temp, post_stmt = branch_info

                # 1. Execute pre-statements in curr
                for pre in pre_stmts:
                    self._inspect_statement_expressions(pre)
                    curr.add_statement(pre)

                # 2. Lower branch_node
                if isinstance(branch_node, ast.IfExp):
                    assign_true = ast.Assign(targets=[ast.Name(id=branch_temp, ctx=ast.Store())], value=copy.deepcopy(branch_node.body))
                    assign_false = ast.Assign(targets=[ast.Name(id=branch_temp, ctx=ast.Store())], value=copy.deepcopy(branch_node.orelse))
                    ast.copy_location(assign_true, branch_node.body)
                    ast.copy_location(assign_false, branch_node.orelse)
                    ast.fix_missing_locations(assign_true)
                    ast.fix_missing_locations(assign_false)

                    if_node = ast.If(test=copy.deepcopy(branch_node.test), body=[assign_true], orelse=[assign_false])
                    ast.copy_location(if_node, branch_node)
                    if_node._decision_kind = "if_exp"

                elif isinstance(branch_node, ast.BoolOp):
                    first = branch_node.values[0]
                    rest = branch_node.values[1] if len(branch_node.values) == 2 else ast.BoolOp(op=branch_node.op, values=branch_node.values[1:])
                    assign_init = ast.Assign(targets=[ast.Name(id=branch_temp, ctx=ast.Store())], value=copy.deepcopy(first))
                    ast.copy_location(assign_init, first)
                    ast.fix_missing_locations(assign_init)
                    self._inspect_statement_expressions(assign_init)
                    curr.add_statement(assign_init)

                    if isinstance(branch_node.op, ast.And):
                        assign_then = ast.Assign(targets=[ast.Name(id=branch_temp, ctx=ast.Store())], value=copy.deepcopy(rest))
                        ast.copy_location(assign_then, rest)
                        ast.fix_missing_locations(assign_then)
                        if_node = ast.If(test=ast.Name(id=branch_temp, ctx=ast.Load()), body=[assign_then], orelse=[])
                        ast.copy_location(if_node, branch_node)
                        if_node._decision_kind = "and"
                    else:
                        assign_else = ast.Assign(targets=[ast.Name(id=branch_temp, ctx=ast.Store())], value=copy.deepcopy(rest))
                        ast.copy_location(assign_else, rest)
                        ast.fix_missing_locations(assign_else)
                        if_node = ast.If(test=ast.Name(id=branch_temp, ctx=ast.Load()), body=[ast.Pass()], orelse=[assign_else])
                        ast.copy_location(if_node, branch_node)
                        if_node._decision_kind = "or"

                join_block = self._handle_if(if_node, curr)
                # Continue building remaining statements from join_block
                return self._build_statements([post_stmt] + stmts[i+1:], current_block=join_block)

            # Standard statement dispatch
            if isinstance(stmt, ast.Return):
                curr = self._handle_return(stmt, curr)

            elif isinstance(stmt, ast.Raise):
                curr = self._handle_raise(stmt, curr)

            elif isinstance(stmt, ast.Break):
                curr = self._handle_break(stmt, curr)

            elif isinstance(stmt, ast.Continue):
                curr = self._handle_continue(stmt, curr)

            elif isinstance(stmt, ast.If):
                curr = self._handle_if(stmt, curr)

            elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
                curr = self._handle_loop(stmt, curr)

            elif isinstance(stmt, ast.Assert):
                curr = self._handle_assert(stmt, curr)

            elif isinstance(stmt, (ast.With, ast.AsyncWith)):
                curr = self._handle_with(stmt, curr)

            elif isinstance(stmt, (ast.Try, getattr(ast, "TryStar", ast.Try))):
                curr = self._handle_try(stmt, curr)

            elif hasattr(ast, "Match") and isinstance(stmt, ast.Match):
                self._add_limitation("PEP 634 match/case statements are deferred to Phase 1B.2")
                self._record_decision("match_case", len(stmt.cases))
                curr.add_statement(stmt)

            else:
                self._inspect_statement_expressions(stmt)
                curr.add_statement(stmt)

        return curr

    def _inspect_statement_expressions(self, stmt: ast.stmt):
        """Scans for embedded comprehensions, chained comparisons, or yields within non-branching statements."""
        for node in ast.walk(stmt):
            if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                self._add_limitation("Comprehension loops and filters are summarized at basic-block level")
                self._record_decision("comprehension_for", len(node.generators))
                for gen in node.generators:
                    if gen.ifs:
                        self._record_decision("comprehension_if", len(gen.ifs))
            elif isinstance(node, ast.Compare) and len(node.ops) > 1:
                self._add_limitation("Chained comparison short-circuiting is summarized at basic-block level")
                self._record_decision("chained_comparison", len(node.ops) - 1)
            elif isinstance(node, (ast.Yield, ast.YieldFrom)):
                self._add_limitation("Generator yield/resume control flow is summarized")

    def _handle_return(self, stmt: ast.Return, curr: BasicBlock) -> BasicBlock:
        self._inspect_statement_expressions(stmt)
        curr.add_statement(stmt)
        curr.terminator_type = "return"
        self._add_edge(curr.block_id, self.exit_id, edge_type="return", label="return")
        return curr

    def _handle_raise(self, stmt: ast.Raise, curr: BasicBlock) -> BasicBlock:
        self._inspect_statement_expressions(stmt)
        curr.add_statement(stmt)
        curr.terminator_type = "raise"
        if self.try_stack:
            try_ctx = self.try_stack[-1]
            for h_id in try_ctx.handler_ids:
                self._add_edge(curr.block_id, h_id, edge_type="except_dispatch", label="except_dispatch (candidate)")
            if try_ctx.finally_id:
                self._add_edge(curr.block_id, try_ctx.finally_id, edge_type="finally_cleanup", label="raise (unhandled)")
            else:
                self._add_edge(curr.block_id, self.exit_id, edge_type="raise", label="raise (unhandled)")
            self._add_limitation("Exception flow does not represent all statement-level implicit exceptions")
        else:
            self._add_edge(curr.block_id, self.exit_id, edge_type="raise", label="raise")
        return curr

    def _handle_break(self, stmt: ast.Break, curr: BasicBlock) -> BasicBlock:
        curr.add_statement(stmt)
        curr.terminator_type = "break"
        if self.loop_stack:
            target_id = self.loop_stack[-1].exit_id
            self._add_edge(curr.block_id, target_id, edge_type="break", label="break")
        else:
            self._add_edge(curr.block_id, self.exit_id, edge_type="break", label="break")
        return curr

    def _handle_continue(self, stmt: ast.Continue, curr: BasicBlock) -> BasicBlock:
        curr.add_statement(stmt)
        curr.terminator_type = "continue"
        if self.loop_stack:
            target_id = self.loop_stack[-1].header_id
            self._add_edge(curr.block_id, target_id, edge_type="continue", label="continue")
        else:
            self._add_edge(curr.block_id, self.entry_id, edge_type="continue", label="continue")
        return curr

    def _handle_if(self, stmt: ast.If, curr: BasicBlock) -> BasicBlock:
        decision_kind = getattr(stmt, "_decision_kind", "if")
        self._record_decision(decision_kind, 1)

        then_start = self._create_block(block_type="basic_block", label="Then")
        has_else = bool(stmt.orelse)

        if isinstance(stmt.test, ast.BoolOp):
            else_start = self._create_block(block_type="basic_block", label="Else") if has_else else self._create_block(block_type="basic_block", label="Join")
            entry_test = self._build_boolean_expr(
                expr=stmt.test,
                true_target_id=then_start.block_id,
                false_target_id=else_start.block_id,
            )
            self._add_edge(curr.block_id, entry_test.block_id, edge_type="fallthrough")
        elif isinstance(stmt.test, ast.IfExp):
            if_exp = stmt.test
            s_true = ast.If(test=if_exp.body, body=stmt.body, orelse=stmt.orelse)
            s_false = ast.If(test=if_exp.orelse, body=stmt.body, orelse=stmt.orelse)
            lowered = ast.If(test=if_exp.test, body=[s_true], orelse=[s_false])
            ast.copy_location(lowered, stmt)
            lowered._decision_kind = "if_exp"
            return self._handle_if(lowered, curr)
        else:
            self._inspect_statement_expressions(stmt)
            label_prefix = "if_exp" if decision_kind == "if_exp" else ("test" if decision_kind in ("and", "or") else "if")
            if not curr.statements and curr.block_type == "basic_block":
                header_block = curr
                header_block.block_type = "branch_header"
                header_block.label = f"{label_prefix} {ast.unparse(stmt.test)}"
                header_block.lineno = stmt.lineno
            else:
                header_block = self._create_block(block_type="branch_header", label=f"{label_prefix} {ast.unparse(stmt.test)}", lineno=stmt.lineno)
                self._add_edge(curr.block_id, header_block.block_id, edge_type="fallthrough")
            header_block.statements.append(stmt.test)

            else_start = self._create_block(block_type="basic_block", label="Else") if has_else else None

            self._add_edge(header_block.block_id, then_start.block_id, edge_type="branch_true", label="True")
            if has_else and else_start:
                self._add_edge(header_block.block_id, else_start.block_id, edge_type="branch_false", label="False")

        then_final = self._build_statements(stmt.body, current_block=then_start)

        if has_else and else_start:
            else_final = self._build_statements(stmt.orelse, current_block=else_start)
        else:
            else_final = else_start  # In BoolOp case without else, else_start was join block

        then_falls_through = then_final and not then_final.is_unreachable and then_final.terminator_type == "fallthrough"
        else_falls_through = (not has_else and not isinstance(stmt.test, ast.BoolOp)) or (else_final and not else_final.is_unreachable and else_final.terminator_type == "fallthrough")

        if then_falls_through or else_falls_through:
            if not has_else and isinstance(stmt.test, ast.BoolOp) and else_start:
                join_block = else_start
            else:
                join_block = self._create_block(block_type="basic_block", label="Join")

            if then_falls_through and then_final:
                self._add_edge(then_final.block_id, join_block.block_id, edge_type="fallthrough")
            if has_else and else_falls_through and else_final:
                self._add_edge(else_final.block_id, join_block.block_id, edge_type="fallthrough")
            elif not has_else and not isinstance(stmt.test, ast.BoolOp):
                self._add_edge(header_block.block_id, join_block.block_id, edge_type="branch_false", label="False")

            return join_block
        else:
            return None

    def _build_boolean_expr(
        self,
        expr: ast.AST,
        true_target_id: str,
        false_target_id: str,
    ) -> BasicBlock:
        """Recursively decomposes boolean expressions (and / or) into explicit short-circuit decision sub-blocks."""
        if isinstance(expr, ast.BoolOp):
            op_count = len(expr.values) - 1
            op_name = "and" if isinstance(expr.op, ast.And) else "or"
            self._record_decision(op_name, op_count)

            # Last sub-expression branches directly to true_target_id and false_target_id
            current_entry = self._build_boolean_expr(
                expr=expr.values[-1],
                true_target_id=true_target_id,
                false_target_id=false_target_id,
            )

            for val in reversed(expr.values[:-1]):
                if isinstance(expr.op, ast.And):
                    # For AND: if true, go to next sub-expression entry; if false, short-circuit to false_target_id
                    current_entry = self._build_boolean_expr(
                        expr=val,
                        true_target_id=current_entry.block_id,
                        false_target_id=false_target_id,
                    )
                else:
                    # For OR: if true, short-circuit to true_target_id; if false, go to next sub-expression entry
                    current_entry = self._build_boolean_expr(
                        expr=val,
                        true_target_id=true_target_id,
                        false_target_id=current_entry.block_id,
                    )

            return current_entry
        else:
            code_label = ast.unparse(expr)
            sb = self._create_block(
                block_type="short_circuit_header",
                label=f"test {code_label}",
                lineno=getattr(expr, "lineno", None),
            )
            sb.statements.append(expr)
            self._add_edge(sb.block_id, true_target_id, edge_type="branch_true", label="True")
            self._add_edge(sb.block_id, false_target_id, edge_type="branch_false", label="False")
            return sb

    def _handle_loop(self, stmt: ast.stmt, curr: BasicBlock) -> BasicBlock:
        is_while = isinstance(stmt, ast.While)
        self._record_decision("while" if is_while else "for", 1)

        test_code = ast.unparse(stmt.test) if is_while else f"{ast.unparse(stmt.target)} in {ast.unparse(stmt.iter)}"
        
        if not curr.statements and curr.block_type == "basic_block":
            header_block = curr
            header_block.block_type = "loop_header"
            header_block.label = f"{'while' if is_while else 'for'} {test_code}"
            header_block.lineno = stmt.lineno
        else:
            header_block = self._create_block(
                block_type="loop_header",
                label=f"{'while' if is_while else 'for'} {test_code}",
                lineno=stmt.lineno,
            )
            self._add_edge(curr.block_id, header_block.block_id, edge_type="fallthrough")

        header_block.statements.append(stmt.test if is_while else stmt.iter)

        join_block = self._create_block(block_type="basic_block", label="Loop Exit Join")
        body_start = self._create_block(block_type="basic_block", label="Loop Body")
        self._add_edge(header_block.block_id, body_start.block_id, edge_type="loop_body", label="Loop")

        if stmt.orelse:
            else_start = self._create_block(block_type="basic_block", label="Loop Else")
            self._add_edge(header_block.block_id, else_start.block_id, edge_type="loop_exit", label="Exit")
            self.loop_stack.append(_LoopContext(header_block.block_id, join_block.block_id, else_start.block_id))

            body_final = self._build_statements(stmt.body, current_block=body_start)
            if body_final and not body_final.is_unreachable and body_final.terminator_type == "fallthrough":
                self._add_edge(body_final.block_id, header_block.block_id, edge_type="loop_back", label="Back")

            self.loop_stack.pop()

            else_final = self._build_statements(stmt.orelse, current_block=else_start)
            if else_final and not else_final.is_unreachable and else_final.terminator_type == "fallthrough":
                self._add_edge(else_final.block_id, join_block.block_id, edge_type="fallthrough")
        else:
            self._add_edge(header_block.block_id, join_block.block_id, edge_type="loop_exit", label="Exit")
            self.loop_stack.append(_LoopContext(header_block.block_id, join_block.block_id))

            body_final = self._build_statements(stmt.body, current_block=body_start)
            if body_final and not body_final.is_unreachable and body_final.terminator_type == "fallthrough":
                self._add_edge(body_final.block_id, header_block.block_id, edge_type="loop_back", label="Back")

            self.loop_stack.pop()

        return join_block

    def _handle_assert(self, stmt: ast.Assert, curr: BasicBlock) -> BasicBlock:
        """Handles assert statements in normal non-optimized Python execution.

        Contract: In normal Python execution (__debug__ is True), assert test constitutes
        a conditional branch where failure raises AssertionError. Python's optimized
        execution mode (-O), where assert statements are removed at compile time by the
        bytecode compiler, is outside the scope of this static analysis model.
        """
        self._record_decision("assert", 1)
        next_block = self._create_block(block_type="basic_block", label="Assert Pass")
        raise_block = self._create_block(block_type="raise_block", label="AssertionError", lineno=stmt.lineno)
        raise_block.statements.append(stmt)
        raise_block.terminator_type = "raise"
        self._add_edge(raise_block.block_id, self.exit_id, edge_type="raise", label="raise AssertionError")

        if isinstance(stmt.test, ast.BoolOp):
            entry_test = self._build_boolean_expr(
                expr=stmt.test,
                true_target_id=next_block.block_id,
                false_target_id=raise_block.block_id,
            )
            self._add_edge(curr.block_id, entry_test.block_id, edge_type="fallthrough")
        elif (isinstance(stmt.test, ast.UnaryOp) and isinstance(stmt.test.op, ast.Not) and isinstance(stmt.test.operand, ast.BoolOp)):
            entry_test = self._build_boolean_expr(
                expr=stmt.test.operand,
                true_target_id=raise_block.block_id,
                false_target_id=next_block.block_id,
            )
            self._add_edge(curr.block_id, entry_test.block_id, edge_type="fallthrough")
        elif isinstance(stmt.test, ast.IfExp):
            if_exp = stmt.test
            s_true = ast.Assert(test=if_exp.body, msg=stmt.msg)
            s_false = ast.Assert(test=if_exp.orelse, msg=stmt.msg)
            lowered = ast.If(test=if_exp.test, body=[s_true], orelse=[s_false])
            ast.copy_location(lowered, stmt)
            lowered._decision_kind = "if_exp"
            return self._handle_if(lowered, curr)
        else:
            self._inspect_statement_expressions(stmt)
            test_block = self._create_block(
                block_type="branch_header",
                label=f"assert {ast.unparse(stmt.test)}",
                lineno=stmt.lineno,
            )
            test_block.statements.append(stmt)
            self._add_edge(curr.block_id, test_block.block_id, edge_type="fallthrough")
            self._add_edge(test_block.block_id, next_block.block_id, edge_type="branch_true", label="Pass")
            self._add_edge(test_block.block_id, raise_block.block_id, edge_type="branch_false", label="Fail")

        return next_block

    def _handle_with(self, stmt: ast.stmt, curr: BasicBlock) -> BasicBlock:
        with_label = ast.unparse(stmt.items[0]) if hasattr(stmt, "items") and stmt.items else "with"
        with_header = self._create_block(block_type="basic_block", label=f"with {with_label}", lineno=stmt.lineno)
        with_header.statements.append(stmt)
        self._add_edge(curr.block_id, with_header.block_id, edge_type="fallthrough")

        body_final = self._build_statements(stmt.body, current_block=with_header)
        cleanup_block = self._create_block(block_type="basic_block", label="With Cleanup")
        if body_final and not body_final.is_unreachable and body_final.terminator_type == "fallthrough":
            self._add_edge(body_final.block_id, cleanup_block.block_id, edge_type="fallthrough")

        return cleanup_block

    def _handle_try(self, stmt: ast.stmt, curr: BasicBlock) -> BasicBlock:
        self._add_limitation("Exception flow does not represent all statement-level implicit exceptions")
        if getattr(stmt, "finalbody", None):
            self._add_limitation("Finally cleanup transitions on abrupt control transfers (return/break/raise/continue) are summarized")
        handler_count = len(stmt.handlers)
        self._record_decision("except_handler", handler_count)

        try_start = self._create_block(block_type="basic_block", label="Try Body", lineno=stmt.lineno)
        self._add_edge(curr.block_id, try_start.block_id, edge_type="fallthrough")

        join_block = self._create_block(block_type="basic_block", label="Try Join")
        finally_block = self._create_block(block_type="finally_block", label="Finally") if stmt.finalbody else join_block

        handler_blocks: List[BasicBlock] = []
        for h in stmt.handlers:
            h_type_str = ast.unparse(h.type) if h.type else "Exception"
            h_block = self._create_block(block_type="except_handler", label=f"except {h_type_str}", lineno=h.lineno)
            handler_blocks.append(h_block)
            self._add_edge(try_start.block_id, h_block.block_id, edge_type="except_dispatch", label="except")

        self.try_stack.append(_TryContext([h.block_id for h in handler_blocks], finally_block.block_id if stmt.finalbody else None))

        try_final = self._build_statements(stmt.body, current_block=try_start)
        if stmt.orelse:
            else_start = self._create_block(block_type="basic_block", label="Try Else")
            if try_final and not try_final.is_unreachable and try_final.terminator_type == "fallthrough":
                self._add_edge(try_final.block_id, else_start.block_id, edge_type="fallthrough", label="normal exit")
            else_final = self._build_statements(stmt.orelse, current_block=else_start)
            if else_final and not else_final.is_unreachable and else_final.terminator_type == "fallthrough":
                self._add_edge(else_final.block_id, finally_block.block_id, edge_type="fallthrough")
        else:
            if try_final and not try_final.is_unreachable and try_final.terminator_type == "fallthrough":
                self._add_edge(try_final.block_id, finally_block.block_id, edge_type="fallthrough")

        for h, h_block in zip(stmt.handlers, handler_blocks):
            h_final = self._build_statements(h.body, current_block=h_block)
            if h_final and not h_final.is_unreachable and h_final.terminator_type == "fallthrough":
                self._add_edge(h_final.block_id, finally_block.block_id, edge_type="fallthrough")

        self.try_stack.pop()

        if stmt.finalbody:
            fin_final = self._build_statements(stmt.finalbody, current_block=finally_block)
            if fin_final and not fin_final.is_unreachable and fin_final.terminator_type == "fallthrough":
                self._add_edge(fin_final.block_id, join_block.block_id, edge_type="fallthrough")

        return join_block

    def _validate_and_finalize(self):
        """Performs BFS reachability, validates invariants, and computes cyclomatic metrics."""
        reachable_ids: Set[str] = set()
        queue = deque([self.entry_id])
        reachable_ids.add(self.entry_id)

        adj: Dict[str, List[str]] = {nid: [] for nid in self.cfg.nodes}
        for e in self.cfg.edges:
            if e.source in adj:
                adj[e.source].append(e.target)

        while queue:
            curr = queue.popleft()
            for neighbor in adj.get(curr, []):
                if neighbor not in reachable_ids and neighbor in self.cfg.nodes:
                    reachable_ids.add(neighbor)
                    queue.append(neighbor)

        unreachable_blocks_count = 0
        for nid, block in self.cfg.nodes.items():
            if nid not in reachable_ids:
                block.is_unreachable = True
                if block.block_type not in ("entry", "exit"):
                    unreachable_blocks_count += 1
            else:
                block.is_unreachable = False

        reachable_edges_count = sum(
            1 for e in self.cfg.edges if e.source in reachable_ids and e.target in reachable_ids
        )

        self.cfg.total_nodes = len(self.cfg.nodes)
        self.cfg.total_edges = len(self.cfg.edges)
        self.cfg.reachable_nodes = len(reachable_ids)
        self.cfg.reachable_edges = reachable_edges_count
        self.cfg.unreachable_basic_blocks = unreachable_blocks_count
        self.cfg.decision_points = dict(self.decision_points)
        self.cfg.limitations = list(self.limitations)

        # M_graph = E_reach - N_reach + 2
        m_graph = reachable_edges_count - len(reachable_ids) + 2
        total_pi = sum(self.decision_points.values())
        m_decision = 1 + total_pi

        self.cfg.graph_cyclomatic = max(1, m_graph)
        self.cfg.decision_cyclomatic = max(1, m_decision)

        if self.cfg.cyclomatic_status == "COMPLETE":
            self.cfg.cyclomatic_complexity = self.cfg.graph_cyclomatic
            self.cfg.cyclomatic_discrepancy = 0
            self.cfg.risk_rank = self._compute_risk_rank(self.cfg.cyclomatic_complexity)
            self.cfg.is_provisional = False
        elif self.cfg.cyclomatic_status == "PARTIAL":
            self.cfg.cyclomatic_complexity = self.cfg.decision_cyclomatic
            self.cfg.cyclomatic_discrepancy = self.cfg.decision_cyclomatic - self.cfg.graph_cyclomatic
            self.cfg.risk_rank = None  # Do not expose an unqualified risk rank in partial analysis
            self.cfg.is_provisional = True
        else:
            self.cfg.cyclomatic_complexity = None
            self.cfg.graph_cyclomatic = None
            self.cfg.decision_cyclomatic = None
            self.cfg.cyclomatic_discrepancy = None
            self.cfg.risk_rank = None
            self.cfg.is_provisional = False

    @staticmethod
    def _compute_risk_rank(score: int) -> Literal["A", "B", "C", "D", "E", "F"]:
        if score <= 5:
            return "A"
        if score <= 10:
            return "B"
        if score <= 20:
            return "C"
        if score <= 30:
            return "D"
        if score <= 40:
            return "E"
        return "F"

    @staticmethod
    def compute_project_summary(cfgs: Dict[str, ControlFlowGraph]) -> Dict[str, Any]:
        """Aggregates metrics across standalone functions and methods, excluding modules and class bodies.

        Empty populations return None for average_cyclomatic_complexity and 0 for function_count.
        Complete and provisional scores are segregated into distinct fields.
        """
        procedural_cfgs = [
            cfg for cfg in cfgs.values()
            if cfg.scope_type in ("function", "method", "async_function")
        ]
        if not procedural_cfgs:
            return {
                "average_cyclomatic_complexity": None,
                "provisional_average_cyclomatic_complexity": None,
                "function_count": 0,
                "complete_function_count": 0,
                "partial_function_count": 0,
                "unsupported_function_count": 0,
                "total_scopes": len(cfgs),
            }

        complete_scores = [
            cfg.cyclomatic_complexity for cfg in procedural_cfgs
            if cfg.cyclomatic_status == "COMPLETE" and cfg.cyclomatic_complexity is not None
        ]
        partial_scores = [
            cfg.cyclomatic_complexity for cfg in procedural_cfgs
            if cfg.cyclomatic_status == "PARTIAL" and cfg.cyclomatic_complexity is not None
        ]
        unsupported_count = sum(1 for cfg in procedural_cfgs if cfg.cyclomatic_status == "UNSUPPORTED")

        avg_cc = round(sum(complete_scores) / len(complete_scores), 2) if complete_scores else None
        prov_avg_cc = round(sum(partial_scores) / len(partial_scores), 2) if partial_scores else None

        return {
            "average_cyclomatic_complexity": avg_cc,
            "provisional_average_cyclomatic_complexity": prov_avg_cc,
            "function_count": len(procedural_cfgs),
            "complete_function_count": len(complete_scores),
            "partial_function_count": len(partial_scores),
            "unsupported_function_count": unsupported_count,
            "total_scopes": len(cfgs),
        }

    @classmethod
    def build_all(cls, tree: ast.AST) -> Dict[str, ControlFlowGraph]:
        """Indexes all scopes and builds independent CFGs for module, functions, methods, and class bodies."""
        from app.analyzers.function_index import FunctionIndex

        cfgs: Dict[str, ControlFlowGraph] = {}
        index = FunctionIndex.from_ast(tree)

        # 1. Module-level CFG
        module_lineno = 1
        module_end_lineno = getattr(tree, "end_lineno", 1)
        mod_builder = cls(
            scope_id="<module>",
            name="<module>",
            scope_type="module",
            lineno=module_lineno,
            end_lineno=module_end_lineno,
        )
        try:
            cfgs["<module>"] = mod_builder.build_from_body(getattr(tree, "body", []))
        except Exception as exc:
            mod_builder.mark_unsupported(f"Module scope analysis failed: {exc}")
            cfgs["<module>"] = mod_builder.cfg

        # 2. Procedural Scopes (functions, methods, generators, async functions)
        for func_id, func_info in index.functions.items():
            if func_id == "<module>":
                continue
            f_node = func_info.node
            f_body = getattr(f_node, "body", [])
            f_builder = cls(
                scope_id=func_id,
                name=func_info.name,
                scope_type=func_info.func_type,
                lineno=func_info.lineno,
                end_lineno=func_info.end_lineno,
            )
            try:
                cfgs[func_id] = f_builder.build_from_body(f_body)
            except Exception as exc:
                f_builder.mark_unsupported(f"Scope analysis failed: {exc}")
                cfgs[func_id] = f_builder.cfg

        # 3. Class Bodies (statements directly inside class definition, excluding methods)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name = node.name
                class_scope_id = f"class_body:{class_name}@{node.lineno}"
                class_body_stmts = [
                    s for s in node.body if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                ]
                cb_builder = cls(
                    scope_id=class_scope_id,
                    name=class_name,
                    scope_type="class_body",
                    lineno=node.lineno,
                    end_lineno=getattr(node, "end_lineno", node.lineno),
                )
                try:
                    cfgs[class_scope_id] = cb_builder.build_from_body(class_body_stmts)
                except Exception as exc:
                    cb_builder.mark_unsupported(f"Class body analysis failed: {exc}")
                    cfgs[class_scope_id] = cb_builder.cfg

        return cfgs
