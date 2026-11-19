"""
AST-Normalized Halstead Complexity Engine for Phase 1B.2.

Computes semantic operator and operand inventories, Halstead metrics,
mathematical availability statuses, and tripartite syntax coverage independently
for every canonical analysis scope. Strictly implements the Stage 0.7 specification
and Stage 1.0.2 architecture contract.
"""

from typing import Dict, List, Optional, Sequence, Tuple, Set, Any
import ast
import math

from app.schemas.metrics import ScopeHalsteadMetrics, UnclassifiedSyntaxRecord
from app.analyzers.scope_discovery import ScopeDefinition

# Mappings for AST operators to semantic Halstead identifiers
BINOP_MAP: Dict[type, str] = {
    ast.Add: "op:add",
    ast.Sub: "op:sub",
    ast.Mult: "op:mult",
    ast.Div: "op:div",
    ast.FloorDiv: "op:floordiv",
    ast.Mod: "op:mod",
    ast.Pow: "op:pow",
    ast.LShift: "op:lshift",
    ast.RShift: "op:rshift",
    ast.BitOr: "op:bitor",
    ast.BitAnd: "op:bitand",
    ast.BitXor: "op:bitxor",
    ast.MatMult: "op:matmul",
}

UNARYOP_MAP: Dict[type, str] = {
    ast.UAdd: "op:uadd",
    ast.USub: "op:usub",
    ast.Not: "op:not",
    ast.Invert: "op:invert",
}

CMPOP_MAP: Dict[type, str] = {
    ast.Eq: "op:eq",
    ast.NotEq: "op:noteq",
    ast.Lt: "op:lt",
    ast.LtE: "op:lte",
    ast.Gt: "op:gt",
    ast.GtE: "op:gte",
    ast.Is: "op:is",
    ast.IsNot: "op:is_not",
    ast.In: "op:in",
    ast.NotIn: "op:not_in",
}

AUGOP_MAP: Dict[type, str] = {
    ast.Add: "op:aug_add",
    ast.Sub: "op:aug_sub",
    ast.Mult: "op:aug_mult",
    ast.Div: "op:aug_div",
    ast.FloorDiv: "op:aug_floordiv",
    ast.Mod: "op:aug_mod",
    ast.Pow: "op:aug_pow",
    ast.LShift: "op:aug_lshift",
    ast.RShift: "op:aug_rshift",
    ast.BitOr: "op:aug_bitor",
    ast.BitAnd: "op:aug_bitand",
    ast.BitXor: "op:aug_bitxor",
    ast.MatMult: "op:aug_matmul",
}


class _HalsteadCollector:
    """Internal AST visitor collecting semantic operators, operands, and unclassified nodes."""

    def __init__(self) -> None:
        self.operators: Dict[str, int] = {}
        self.operands: Dict[str, int] = {}
        self.diagnostics: List[str] = []
        self.unclassified_nodes: List[UnclassifiedSyntaxRecord] = []
        self.has_unsupported_structure: bool = False

    def add_operator(self, op: str, count: int = 1) -> None:
        self.operators[op] = self.operators.get(op, 0) + count

    def add_operand(self, opnd: str, count: int = 1) -> None:
        self.operands[opnd] = self.operands.get(opnd, 0) + count

    def add_unclassified(self, node: ast.AST, reason: str) -> None:
        self.unclassified_nodes.append(
            UnclassifiedSyntaxRecord(
                node_class=type(node).__name__,
                lineno=getattr(node, "lineno", None),
                col_offset=getattr(node, "col_offset", None),
                reason=reason,
            )
        )

    @staticmethod
    def format_literal(val: Any) -> str:
        """Formats typed literal values with strict type segregation."""
        if isinstance(val, bool):
            return f"lit:bool:{val}"
        elif isinstance(val, int):
            return f"lit:int:{val}"
        elif isinstance(val, float):
            return f"lit:float:{val}"
        elif val is None:
            return "lit:none:None"
        elif isinstance(val, str):
            return f'lit:str:"{val}"'
        elif isinstance(val, bytes):
            return f"lit:bytes:{val!r}"
        elif isinstance(val, complex):
            return f"lit:complex:{val}"
        elif val is Ellipsis:
            return "lit:ellipsis:..."
        else:
            return f"lit:{type(val).__name__}:{val}"

    def visit_pattern(self, pattern: ast.AST) -> None:
        """Visits PEP 634 pattern constructs with dedicated pattern operators."""
        if isinstance(pattern, ast.MatchValue):
            self.visit_expr(pattern.value)
        elif isinstance(pattern, ast.MatchSingleton):
            self.add_operand(self.format_literal(pattern.value))
        elif isinstance(pattern, ast.MatchSequence):
            self.add_operator("op:match_sequence")
            for p in pattern.patterns:
                self.visit_pattern(p)
        elif isinstance(pattern, ast.MatchMapping):
            self.add_operator("op:match_mapping")
            for k in pattern.keys:
                self.visit_expr(k)
            for p in pattern.patterns:
                self.visit_pattern(p)
            if pattern.rest is not None:
                self.add_operand(f"id:{pattern.rest}")
        elif isinstance(pattern, ast.MatchClass):
            self.add_operator("op:match_class")
            self.visit_expr(pattern.cls)
            for p in pattern.patterns:
                self.visit_pattern(p)
            for attr, p in zip(
                getattr(pattern, "kwd_attrs", []), getattr(pattern, "kwd_patterns", [])
            ):
                self.add_operand(f"attr:{attr}")
                self.visit_pattern(p)
        elif isinstance(pattern, ast.MatchStar):
            self.add_operator("op:match_star")
            if pattern.name is not None:
                self.add_operand(f"id:{pattern.name}")
        elif isinstance(pattern, ast.MatchAs):
            if pattern.pattern is None and pattern.name is None:
                # Wildcard pattern _: 0 operators, 0 operands
                pass
            elif pattern.pattern is None and pattern.name is not None:
                # Direct capture pattern: 0 operators, id:name operand
                self.add_operand(f"id:{pattern.name}")
            else:
                # Pattern alias: op:match_as operator, visit subpattern, optional id:name
                self.add_operator("op:match_as")
                if pattern.pattern is not None:
                    self.visit_pattern(pattern.pattern)
                if pattern.name is not None:
                    self.add_operand(f"id:{pattern.name}")
        elif isinstance(pattern, ast.MatchOr):
            k = len(pattern.patterns)
            if k > 1:
                self.add_operator("op:match_or", k - 1)
            for p in pattern.patterns:
                self.visit_pattern(p)
        else:
            self.add_unclassified(
                pattern, f"Unrecognized pattern AST node: {type(pattern).__name__}"
            )

    def visit_expr(self, node: Optional[ast.AST]) -> None:
        """Visits expression AST nodes recursively."""
        if node is None:
            return

        if isinstance(node, ast.Name):
            self.add_operand(f"id:{node.id}")
        elif isinstance(node, ast.Constant):
            self.add_operand(self.format_literal(node.value))
        elif isinstance(node, ast.BinOp):
            op_cls = type(node.op)
            if op_cls in BINOP_MAP:
                self.add_operator(BINOP_MAP[op_cls])
            else:
                self.add_unclassified(
                    node.op, f"Unrecognized BinOp operator: {op_cls.__name__}"
                )
            self.visit_expr(node.left)
            self.visit_expr(node.right)
        elif isinstance(node, ast.UnaryOp):
            op_cls = type(node.op)
            if op_cls in UNARYOP_MAP:
                self.add_operator(UNARYOP_MAP[op_cls])
            else:
                self.add_unclassified(
                    node.op, f"Unrecognized UnaryOp operator: {op_cls.__name__}"
                )
            self.visit_expr(node.operand)
        elif isinstance(node, ast.BoolOp):
            k = len(node.values)
            if k > 1:
                if isinstance(node.op, ast.And):
                    self.add_operator("op:and", k - 1)
                elif isinstance(node.op, ast.Or):
                    self.add_operator("op:or", k - 1)
                else:
                    self.add_unclassified(
                        node.op, f"Unrecognized BoolOp operator: {type(node.op).__name__}"
                    )
            for v in node.values:
                self.visit_expr(v)
        elif isinstance(node, ast.Compare):
            for op in node.ops:
                op_cls = type(op)
                if op_cls in CMPOP_MAP:
                    self.add_operator(CMPOP_MAP[op_cls])
                else:
                    self.add_unclassified(
                        op, f"Unrecognized Compare operator: {op_cls.__name__}"
                    )
            self.visit_expr(node.left)
            for comp in node.comparators:
                self.visit_expr(comp)
        elif isinstance(node, ast.Call):
            self.add_operator("op:call")
            self.visit_expr(node.func)
            for a in node.args:
                if isinstance(a, ast.Starred):
                    self.add_operator("op:unpack_star")
                    self.visit_expr(a.value)
                else:
                    self.visit_expr(a)
            for kw in node.keywords:
                if kw.arg is not None:
                    self.add_operand(f"kw:{kw.arg}")
                    self.visit_expr(kw.value)
                else:
                    self.add_operator("op:unpack_dict_star")
                    self.visit_expr(kw.value)
        elif isinstance(node, ast.Attribute):
            self.add_operator("op:attr")
            self.add_operand(f"attr:{node.attr}")
            self.visit_expr(node.value)
        elif isinstance(node, ast.Subscript):
            self.add_operator("op:subscript")
            self.visit_expr(node.value)
            self.visit_expr(node.slice)
        elif isinstance(node, ast.Slice):
            self.add_operator("op:slice")
            if node.lower is not None:
                self.visit_expr(node.lower)
            if node.upper is not None:
                self.visit_expr(node.upper)
            if node.step is not None:
                self.visit_expr(node.step)
        elif isinstance(node, ast.NamedExpr):
            self.add_operator("op:walrus")
            self.visit_expr(node.target)
            self.visit_expr(node.value)
        elif isinstance(node, ast.IfExp):
            self.add_operator("op:if_exp")
            self.visit_expr(node.test)
            self.visit_expr(node.body)
            self.visit_expr(node.orelse)
        elif isinstance(node, ast.Lambda):
            self.add_operator("op:lambda")
            if node.args:
                for a in getattr(node.args, "posonlyargs", []):
                    self.add_operand(f"id:{a.arg}")
                for a in getattr(node.args, "args", []):
                    self.add_operand(f"id:{a.arg}")
                if getattr(node.args, "vararg", None) is not None:
                    self.add_operand(f"id:{node.args.vararg.arg}")
                for a in getattr(node.args, "kwonlyargs", []):
                    self.add_operand(f"id:{a.arg}")
                if getattr(node.args, "kwarg", None) is not None:
                    self.add_operand(f"id:{node.args.kwarg.arg}")
            self.visit_expr(node.body)
        elif isinstance(node, ast.List):
            self.add_operator("op:list_display")
            for elt in node.elts:
                self.visit_expr(elt)
        elif isinstance(node, ast.Tuple):
            self.add_operator("op:tuple_display")
            for elt in node.elts:
                self.visit_expr(elt)
        elif isinstance(node, ast.Set):
            self.add_operator("op:set_display")
            for elt in node.elts:
                self.visit_expr(elt)
        elif isinstance(node, ast.Dict):
            self.add_operator("op:dict_display")
            for k, v in zip(node.keys, node.values):
                if k is None:
                    self.add_operator("op:unpack_dict_star")
                    self.visit_expr(v)
                else:
                    self.visit_expr(k)
                    self.visit_expr(v)
        elif isinstance(node, ast.Starred):
            self.add_operator("op:unpack_star")
            self.visit_expr(node.value)
        elif isinstance(node, ast.ListComp):
            self.add_operator("op:list_comp")
            for gen in node.generators:
                self.visit_comprehension(gen)
            self.visit_expr(node.elt)
        elif isinstance(node, ast.SetComp):
            self.add_operator("op:set_comp")
            for gen in node.generators:
                self.visit_comprehension(gen)
            self.visit_expr(node.elt)
        elif isinstance(node, ast.DictComp):
            self.add_operator("op:dict_comp")
            for gen in node.generators:
                self.visit_comprehension(gen)
            self.visit_expr(node.key)
            self.visit_expr(node.value)
        elif isinstance(node, ast.GeneratorExp):
            self.add_operator("op:gen_exp")
            for gen in node.generators:
                self.visit_comprehension(gen)
            self.visit_expr(node.elt)
        elif isinstance(node, ast.Yield):
            self.add_operator("op:yield")
            if node.value is not None:
                self.visit_expr(node.value)
        elif isinstance(node, ast.YieldFrom):
            self.add_operator("op:yield_from")
            self.visit_expr(node.value)
        elif isinstance(node, ast.Await):
            self.add_operator("op:await")
            self.visit_expr(node.value)
        elif isinstance(node, ast.JoinedStr):
            self.add_operator("op:fstring")
            for v in node.values:
                if isinstance(v, ast.Constant):
                    self.add_operand(self.format_literal(v.value))
                elif isinstance(v, ast.FormattedValue):
                    self.visit_formatted_value(v)
                else:
                    self.visit_expr(v)
        elif isinstance(node, ast.FormattedValue):
            self.visit_formatted_value(node)
        else:
            self.add_unclassified(
                node, f"Unrecognized expression AST node: {type(node).__name__}"
            )

    def visit_comprehension(self, gen: ast.comprehension) -> None:
        """Visits generator/comprehension clauses."""
        self.add_operator("op:comp_for")
        self.visit_expr(gen.target)
        self.visit_expr(gen.iter)
        for if_expr in gen.ifs:
            self.add_operator("op:comp_if")
            self.visit_expr(if_expr)

    def visit_formatted_value(self, node: ast.FormattedValue) -> None:
        """Visits an interpolated field within an f-string JoinedStr."""
        self.add_operator("op:format_field")
        self.visit_expr(node.value)
        if node.conversion == 114:
            self.add_operator("op:conv_repr")
        elif node.conversion == 115:
            self.add_operator("op:conv_str")
        elif node.conversion == 97:
            self.add_operator("op:conv_ascii")
        if node.format_spec is not None:
            self.add_operator("op:format_spec")
            if isinstance(node.format_spec, ast.JoinedStr):
                for val in node.format_spec.values:
                    if isinstance(val, ast.Constant):
                        self.add_operand(self.format_literal(val.value))
                    elif isinstance(val, ast.FormattedValue):
                        self.visit_formatted_value(val)
                    else:
                        self.visit_expr(val)
            else:
                self.visit_expr(node.format_spec)

    def visit_stmt(self, stmt: ast.stmt, scope_type: str) -> None:
        """Visits a statement AST node owned by the scope."""
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Child function declaration statement owned by enclosing scope
            op_def = "op:async_def" if isinstance(stmt, ast.AsyncFunctionDef) else "op:def"
            self.add_operator(op_def)
            self.add_operand(f"id:{stmt.name}")
            for dec in stmt.decorator_list:
                self.add_operator("op:decorator")
                self.visit_expr(dec)
            if stmt.args:
                for def_val in stmt.args.defaults:
                    if def_val is not None:
                        self.add_operator("op:default_arg")
                        self.visit_expr(def_val)
                for def_val in stmt.args.kw_defaults:
                    if def_val is not None:
                        self.add_operator("op:default_arg")
                        self.visit_expr(def_val)
            # Parameters, annotations, and body pruned (owned by child scope)
        elif isinstance(stmt, ast.ClassDef):
            # Child class declaration statement owned by enclosing scope
            self.add_operator("op:class")
            self.add_operand(f"id:{stmt.name}")
            for dec in stmt.decorator_list:
                self.add_operator("op:decorator")
                self.visit_expr(dec)
            for base in stmt.bases:
                self.visit_expr(base)
            for kw in stmt.keywords:
                if kw.arg is not None:
                    self.add_operand(f"kw:{kw.arg}")
                self.visit_expr(kw.value)
            # type_params and body pruned (owned by child class_body scope)
        elif hasattr(ast, "TypeAlias") and isinstance(stmt, ast.TypeAlias):
            self.add_operator("op:type_alias")
            if isinstance(stmt.name, ast.Name):
                self.add_operand(f"id:{stmt.name.id}")
            elif isinstance(stmt.name, str):
                self.add_operand(f"id:{stmt.name}")
            # type_params and value are excluded from Halstead counting
        elif isinstance(stmt, ast.Return):
            self.add_operator("op:return")
            if stmt.value is not None:
                self.visit_expr(stmt.value)
        elif isinstance(stmt, ast.Pass):
            self.add_operator("op:pass")
        elif isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                self.add_operator("op:assign")
                self.visit_expr(t)
            self.visit_expr(stmt.value)
        elif isinstance(stmt, ast.AugAssign):
            op_cls = type(stmt.op)
            if op_cls in AUGOP_MAP:
                self.add_operator(AUGOP_MAP[op_cls])
            else:
                self.add_unclassified(
                    stmt.op, f"Unrecognized AugAssign operator: {op_cls.__name__}"
                )
            self.visit_expr(stmt.target)
            self.visit_expr(stmt.value)
        elif isinstance(stmt, ast.AnnAssign):
            if stmt.value is not None:
                self.add_operator("op:ann_assign")
                self.visit_expr(stmt.target)
                self.visit_expr(stmt.value)
            # Type-only annotation statement without value is excluded
        elif isinstance(stmt, ast.Assert):
            self.add_operator("op:assert")
            self.visit_expr(stmt.test)
            if stmt.msg is not None:
                self.visit_expr(stmt.msg)
        elif isinstance(stmt, ast.Raise):
            self.add_operator("op:raise")
            if stmt.exc is not None:
                self.visit_expr(stmt.exc)
            if stmt.cause is not None:
                self.visit_expr(stmt.cause)
        elif isinstance(stmt, ast.Delete):
            self.add_operator("op:del")
            for t in stmt.targets:
                self.visit_expr(t)
        elif isinstance(stmt, ast.Global):
            self.add_operator("op:global")
            for name in stmt.names:
                self.add_operand(f"id:{name}")
        elif isinstance(stmt, ast.Nonlocal):
            self.add_operator("op:nonlocal")
            for name in stmt.names:
                self.add_operand(f"id:{name}")
        elif isinstance(stmt, ast.Break):
            self.add_operator("op:break")
        elif isinstance(stmt, ast.Continue):
            self.add_operator("op:continue")
        elif isinstance(stmt, ast.Expr):
            self.visit_expr(stmt.value)
        elif isinstance(stmt, ast.If):
            self.visit_if(stmt, is_elif=False)
        elif isinstance(stmt, (ast.For, ast.AsyncFor)):
            self.add_operator(
                "op:async_for" if isinstance(stmt, ast.AsyncFor) else "op:for"
            )
            self.visit_expr(stmt.target)
            self.visit_expr(stmt.iter)
            for s in stmt.body:
                self.visit_stmt(s, scope_type)
            if stmt.orelse:
                self.add_operator("op:else")
                for s in stmt.orelse:
                    self.visit_stmt(s, scope_type)
        elif isinstance(stmt, ast.While):
            self.add_operator("op:while")
            self.visit_expr(stmt.test)
            for s in stmt.body:
                self.visit_stmt(s, scope_type)
            if stmt.orelse:
                self.add_operator("op:else")
                for s in stmt.orelse:
                    self.visit_stmt(s, scope_type)
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            self.add_operator(
                "op:async_with" if isinstance(stmt, ast.AsyncWith) else "op:with"
            )
            for item in stmt.items:
                self.visit_expr(item.context_expr)
                if item.optional_vars is not None:
                    self.add_operator("op:as")
                    self.visit_expr(item.optional_vars)
            for s in stmt.body:
                self.visit_stmt(s, scope_type)
        elif isinstance(stmt, ast.Try):
            self.add_operator("op:try")
            for s in stmt.body:
                self.visit_stmt(s, scope_type)
            for handler in stmt.handlers:
                self.add_operator("op:except")
                if handler.type is not None:
                    self.visit_expr(handler.type)
                if handler.name is not None:
                    self.add_operator("op:as")
                    self.add_operand(f"id:{handler.name}")
                for s in handler.body:
                    self.visit_stmt(s, scope_type)
            if stmt.orelse:
                self.add_operator("op:else")
                for s in stmt.orelse:
                    self.visit_stmt(s, scope_type)
            if stmt.finalbody:
                self.add_operator("op:finally")
                for s in stmt.finalbody:
                    self.visit_stmt(s, scope_type)
        elif hasattr(ast, "TryStar") and isinstance(stmt, ast.TryStar):
            self.add_operator("op:try")
            for s in stmt.body:
                self.visit_stmt(s, scope_type)
            for handler in stmt.handlers:
                self.add_operator("op:except_star")
                if handler.type is not None:
                    self.visit_expr(handler.type)
                if handler.name is not None:
                    self.add_operator("op:as")
                    self.add_operand(f"id:{handler.name}")
                for s in handler.body:
                    self.visit_stmt(s, scope_type)
            if stmt.orelse:
                self.add_operator("op:else")
                for s in stmt.orelse:
                    self.visit_stmt(s, scope_type)
            if stmt.finalbody:
                self.add_operator("op:finally")
                for s in stmt.finalbody:
                    self.visit_stmt(s, scope_type)
        elif isinstance(stmt, ast.Match):
            self.add_operator("op:match")
            self.visit_expr(stmt.subject)
            for case in stmt.cases:
                self.add_operator("op:case")
                self.visit_pattern(case.pattern)
                if case.guard is not None:
                    self.visit_expr(case.guard)
                for s in case.body:
                    self.visit_stmt(s, scope_type)
        elif isinstance(stmt, ast.Import):
            self.add_operator("op:import")
            for alias in stmt.names:
                self.add_operand(f"id:{alias.name}")
                if alias.asname is not None:
                    self.add_operator("op:as")
                    self.add_operand(f"id:{alias.asname}")
        elif isinstance(stmt, ast.ImportFrom):
            self.add_operator("op:from_import")
            if stmt.module:
                self.add_operand(f"id:{stmt.module}")
            for alias in stmt.names:
                self.add_operand(f"id:{alias.name}")
                if alias.asname is not None:
                    self.add_operator("op:as")
                    self.add_operand(f"id:{alias.asname}")
        else:
            self.add_unclassified(
                stmt, f"Unrecognized statement AST node: {type(stmt).__name__}"
            )

    def visit_if(self, node: ast.If, is_elif: bool) -> None:
        """Visits If and elif nodes with source-coordinate discrimination."""
        if is_elif:
            self.add_operator("op:elif")
        else:
            self.add_operator("op:if")

        self.visit_expr(node.test)
        for s in node.body:
            self.visit_stmt(s, "if_body")

        if node.orelse:
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                inner_if = node.orelse[0]
                outer_col = getattr(node, "col_offset", None)
                inner_col = getattr(inner_if, "col_offset", None)
                if (
                    outer_col is None
                    or inner_col is None
                    or outer_col < 0
                    or inner_col < 0
                ):
                    if (
                        "MISSING_COORDINATES_FALLBACK_NESTED"
                        not in self.diagnostics
                    ):
                        self.diagnostics.append(
                            "MISSING_COORDINATES_FALLBACK_NESTED"
                        )
                    self.add_operator("op:else")
                    self.visit_if(inner_if, is_elif=False)
                elif inner_col == outer_col:
                    # Flat elif transition
                    self.visit_if(inner_if, is_elif=True)
                else:
                    # Nested else: if
                    self.add_operator("op:else")
                    self.visit_if(inner_if, is_elif=False)
            else:
                self.add_operator("op:else")
                for s in node.orelse:
                    self.visit_stmt(s, "else_body")


class HalsteadAnalyzer:
    """
    AST-Normalized Halstead Complexity Engine.

    Calculates Halstead metrics, operator/operand token inventories, mathematical
    availability statuses, and syntax coverage states independently for every
    canonical ScopeDefinition.
    """

    def analyze(self, scope: ScopeDefinition) -> ScopeHalsteadMetrics:
        """
        Analyzes an individual ScopeDefinition and returns its ScopeHalsteadMetrics.
        """
        collector = _HalsteadCollector()
        root = scope.node
        scope_type = scope.scope_type

        if scope_type == "module":
            if not hasattr(root, "body"):
                collector.add_unclassified(root, "Unsupported module scope root: missing body")
                collector.has_unsupported_structure = True
            else:
                for s in getattr(root, "body", []):
                    collector.visit_stmt(s, "module")
        elif scope_type == "class_body":
            if not hasattr(root, "body"):
                collector.add_unclassified(root, "Unsupported class scope root: missing body")
                collector.has_unsupported_structure = True
            else:
                for s in getattr(root, "body", []):
                    collector.visit_stmt(s, "class_body")
        elif scope_type in ("function", "method"):
            if not hasattr(root, "body"):
                collector.add_unclassified(root, f"Unsupported {scope_type} scope root: missing body")
                collector.has_unsupported_structure = True
            else:
                # Formal parameter bindings belong to child scope
                if hasattr(root, "args") and root.args is not None:
                    args = root.args
                    for a in getattr(args, "posonlyargs", []):
                        collector.add_operand(f"id:{a.arg}")
                    for a in getattr(args, "args", []):
                        collector.add_operand(f"id:{a.arg}")
                    if getattr(args, "vararg", None) is not None:
                        collector.add_operand(f"id:{args.vararg.arg}")
                    for a in getattr(args, "kwonlyargs", []):
                        collector.add_operand(f"id:{a.arg}")
                    if getattr(args, "kwarg", None) is not None:
                        collector.add_operand(f"id:{args.kwarg.arg}")
                # Executable body statements
                for s in getattr(root, "body", []):
                    collector.visit_stmt(s, scope_type)
        else:
            collector.add_unclassified(root, f"Unsupported scope_type '{scope_type}'")
            collector.has_unsupported_structure = True

        # Tripartite syntax coverage determination
        if len(collector.unclassified_nodes) == 0:
            cov_status = "FULL"
        elif collector.has_unsupported_structure:
            cov_status = "UNCLASSIFIED_SYNTAX"
        else:
            cov_status = "PARTIAL"

        math_res = self._compute_mathematical_metrics(
            collector.operators, collector.operands
        )
        if cov_status == "UNCLASSIFIED_SYNTAX":
            math_res["undefined_reasons"].insert(
                0, "Scope syntax classification is UNCLASSIFIED_SYNTAX: scope structure is unsupported"
            )
        # Combine undefined reasons with diagnostics if any
        math_res["undefined_reasons"].extend(collector.diagnostics)

        return ScopeHalsteadMetrics(
            distinct_operators=math_res["distinct_operators"],
            distinct_operands=math_res["distinct_operands"],
            total_operators=math_res["total_operators"],
            total_operands=math_res["total_operands"],
            vocabulary=math_res["vocabulary"],
            length=math_res["length"],
            volume=math_res["volume"],
            difficulty=math_res["difficulty"],
            effort=math_res["effort"],
            theoretical_time_seconds=math_res["theoretical_time_seconds"],
            theoretical_delivered_bugs=math_res["theoretical_delivered_bugs"],
            volume_status=math_res["volume_status"],
            difficulty_status=math_res["difficulty_status"],
            effort_status=math_res["effort_status"],
            undefined_reasons=math_res["undefined_reasons"],
            syntax_coverage_status=cov_status,
            unclassified_syntax_nodes=collector.unclassified_nodes,
            operator_inventory=collector.operators,
            operand_inventory=collector.operands,
        )

    def analyze_all(
        self, scopes: Sequence[ScopeDefinition]
    ) -> Dict[str, ScopeHalsteadMetrics]:
        """
        Analyzes an ordered sequence of scopes and returns a dictionary
        mapping canonical scope_id -> ScopeHalsteadMetrics.
        """
        results: Dict[str, ScopeHalsteadMetrics] = {}
        for scope in scopes:
            results[scope.scope_id] = self.analyze(scope)
        return results

    @staticmethod
    def _compute_mathematical_metrics(
        op_inv: Dict[str, int], opnd_inv: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        Derives all mathematical Halstead metrics and availability statuses
        strictly conforming to Stage 0.7 formulas and Unit 1 schemas.
        """
        eta1 = len(op_inv)
        N1 = sum(op_inv.values())
        eta2 = len(opnd_inv)
        N2 = sum(opnd_inv.values())
        eta = eta1 + eta2
        N = N1 + N2

        volume: Optional[float] = None
        difficulty: Optional[float] = None
        effort: Optional[float] = None
        time_sec: Optional[float] = None
        bugs: Optional[float] = None
        undefined_reasons: List[str] = []

        if eta == 0:
            vol_status = "UNDEFINED_EMPTY_VOCABULARY"
            undefined_reasons.append(
                "Empty vocabulary (eta=0): volume is mathematically undefined"
            )
        else:
            vol_status = "AVAILABLE"
            volume = float(N * math.log2(eta))

        if eta2 == 0:
            diff_status = "UNDEFINED_ZERO_OPERANDS"
            undefined_reasons.append(
                "Zero operands (eta2=0): difficulty is mathematically undefined"
            )
        else:
            diff_status = "AVAILABLE"
            difficulty = float((eta1 / 2.0) * (N2 / eta2))

        if vol_status == "AVAILABLE" and diff_status == "AVAILABLE":
            eff_status = "AVAILABLE"
            assert volume is not None and difficulty is not None
            effort = float(difficulty * volume)
            time_sec = float(effort / 18.0)
        else:
            eff_status = "UNDEFINED_DEPENDENCY"
            undefined_reasons.append(
                "Effort is undefined because volume or difficulty is undefined"
            )

        if vol_status == "AVAILABLE" and volume is not None:
            bugs = float(volume / 3000.0)

        return {
            "distinct_operators": eta1,
            "distinct_operands": eta2,
            "total_operators": N1,
            "total_operands": N2,
            "vocabulary": eta,
            "length": N,
            "volume": volume,
            "difficulty": difficulty,
            "effort": effort,
            "theoretical_time_seconds": time_sec,
            "theoretical_delivered_bugs": bugs,
            "volume_status": vol_status,
            "difficulty_status": diff_status,
            "effort_status": eff_status,
            "undefined_reasons": undefined_reasons,
        }
