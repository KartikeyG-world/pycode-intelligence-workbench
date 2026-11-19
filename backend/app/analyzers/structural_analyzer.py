"""
Structural AST Metrics Engine for Phase 1B.2.

Calculates AST structural metrics, statement counts, control nesting depths,
and syntax properties independently for every discovered ScopeDefinition.
Strictly implements the Stage 0.7 specification and Stage 1.0.2 architecture contract.
"""

from typing import Dict, List, Optional, Sequence, Tuple, Set, Iterator
import ast

from app.schemas.metrics import ScopeStructuralMetrics
from app.analyzers.scope_discovery import ScopeDefinition

# AST node types excluded from structural metrics and depth calculation
EXCLUDED_AST_CLASSES: Tuple[type, ...] = (
    ast.Load,
    ast.Store,
    ast.Del,
    getattr(ast, "TypeIgnore", ()),
)


class StructuralMetricsAnalyzer:
    """
    Analyzes AST structural metrics for discovered analysis scopes.

    Produces ScopeStructuralMetrics conforming to the Stage 0.7 specification:
    - Scope ownership enforcement (prunes child function/method/class bodies from parent scopes).
    - Iterative BFS traversal for AST node counting and maximum depth determination.
    - Statement counts (recursive owned statements and top-level statements).
    - Control nesting depth with elif source-coordinate discrimination.
    - Conditional, boolean operator, loop, comprehension, parameter, and return counts.
    - AST immutability guarantees.
    """

    def analyze(self, scope: ScopeDefinition) -> ScopeStructuralMetrics:
        """
        Calculates ScopeStructuralMetrics for a single ScopeDefinition.
        """
        return self._compute_scope_metrics(scope.node, scope.scope_type)

    def analyze_all(
        self, scopes: Sequence[ScopeDefinition]
    ) -> Dict[str, ScopeStructuralMetrics]:
        """
        Calculates ScopeStructuralMetrics for an ordered sequence of scopes.

        Returns a dictionary mapping scope_id -> ScopeStructuralMetrics.
        """
        result: Dict[str, ScopeStructuralMetrics] = {}
        for scope in scopes:
            result[scope.scope_id] = self.analyze(scope)
        return result

    def _get_scope_children(
        self, node: ast.AST, is_root: bool, scope_type: str
    ) -> Iterator[ast.AST]:
        """
        Yields the child AST nodes owned by the given scope.

        Enforces scope ownership boundaries:
        - Scope root at depth 1.
        - For module: owns root, statements in body; for nested function/class declarations,
          owns the declaration statement and decorators/bases, but prunes child signatures and bodies.
        - For class_body: owns ClassDef root and class type_params; prunes definition-site
          decorators/bases/keywords; owns statements in body, pruning child method/class bodies.
        - For function/method: owns FunctionDef root, type_params, arguments, returns, and body;
          prunes definition-site decorators; prunes child callable/class bodies.
        - Excludes ast.expr_context (Load, Store, Del) and ast.TypeIgnore.
        """
        if is_root:
            if scope_type == "module":
                for stmt in getattr(node, "body", []):
                    yield stmt
            elif scope_type == "class_body":
                for tp in getattr(node, "type_params", []):
                    yield tp
                for stmt in getattr(node, "body", []):
                    yield stmt
            elif scope_type in ("function", "method"):
                for tp in getattr(node, "type_params", []):
                    yield tp
                if getattr(node, "args", None) is not None:
                    yield node.args
                if getattr(node, "returns", None) is not None:
                    yield node.returns
                for stmt in getattr(node, "body", []):
                    yield stmt
        else:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Nested function declaration statement: enclosing scope owns decorators
                for dec in node.decorator_list:
                    yield dec
                # type_params, args, returns, and body are pruned (owned by child scope)
            elif isinstance(node, ast.ClassDef):
                # Nested class declaration statement: enclosing scope owns decorators, bases, keywords
                for dec in node.decorator_list:
                    yield dec
                for base in node.bases:
                    yield base
                for kw in node.keywords:
                    yield kw
                # type_params and body are pruned (owned by child class_body scope)
            else:
                for child in ast.iter_child_nodes(node):
                    if not isinstance(child, EXCLUDED_AST_CLASSES):
                        yield child

    def _compute_ast_node_count_and_depth(
        self, root: ast.AST, scope_type: str
    ) -> Tuple[int, int]:
        """
        Iterative BFS traversal to calculate total owned AST nodes and maximum AST depth.
        Avoids recursion to eliminate call-stack limits on deeply nested ASTs.
        """
        count = 0
        max_depth = 1
        queue: List[Tuple[ast.AST, int, bool]] = [(root, 1, True)]

        while queue:
            node, depth, is_root = queue.pop(0)
            count += 1
            if depth > max_depth:
                max_depth = depth
            for child in self._get_scope_children(node, is_root, scope_type):
                queue.append((child, depth + 1, False))

        return count, max_depth

    def _analyze_statements_and_nesting(
        self, root: ast.AST, scope_type: str
    ) -> Tuple[int, int, int, List[str]]:
        """
        Iterative traversal of statement suites to compute:
        - statement_count (total recursively encountered ast.stmt nodes owned by the scope)
        - top_level_statement_count (direct statements in scope body)
        - control_nesting_depth (maximum control nesting depth starting at 0)
        - diagnostics (e.g. MISSING_COORDINATES_FALLBACK_NESTED)
        """
        root_body = getattr(root, "body", [])
        top_level_stmts = [s for s in root_body if isinstance(s, ast.stmt)]
        top_level_statement_count = len(top_level_stmts)

        diagnostics: List[str] = []
        statement_count = 0
        max_nesting = 0

        # Iterative suite queue: (suite_statements, current_nesting_depth)
        queue: List[Tuple[List[ast.stmt], int]] = [(top_level_stmts, 0)]

        while queue:
            suite, current_nesting = queue.pop(0)
            for stmt in suite:
                statement_count += 1
                if current_nesting > max_nesting:
                    max_nesting = current_nesting

                # If stmt is a child scope declaration, its body belongs to that child scope
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue

                if isinstance(stmt, ast.If):
                    queue.append((stmt.body, current_nesting + 1))
                    if stmt.orelse:
                        if len(stmt.orelse) == 1 and isinstance(stmt.orelse[0], ast.If):
                            inner_if = stmt.orelse[0]
                            outer_col = getattr(stmt, "col_offset", None)
                            inner_col = getattr(inner_if, "col_offset", None)
                            if (
                                outer_col is None
                                or inner_col is None
                                or outer_col < 0
                                or inner_col < 0
                            ):
                                if (
                                    "MISSING_COORDINATES_FALLBACK_NESTED"
                                    not in diagnostics
                                ):
                                    diagnostics.append(
                                        "MISSING_COORDINATES_FALLBACK_NESTED"
                                    )
                                # Fallback: treat inner If as nested else: if
                                queue.append(([inner_if], current_nesting + 1))
                            elif inner_col == outer_col:
                                # Flat elif transition: preserves current nesting
                                queue.append(([inner_if], current_nesting))
                            else:
                                # Nested else: if: increment nesting
                                queue.append(([inner_if], current_nesting + 1))
                        else:
                            queue.append((stmt.orelse, current_nesting + 1))
                elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
                    queue.append((stmt.body, current_nesting + 1))
                    if stmt.orelse:
                        queue.append((stmt.orelse, current_nesting + 1))
                elif isinstance(stmt, (ast.With, ast.AsyncWith)):
                    queue.append((stmt.body, current_nesting + 1))
                elif isinstance(stmt, ast.Try):
                    queue.append((stmt.body, current_nesting + 1))
                    for handler in stmt.handlers:
                        queue.append((handler.body, current_nesting + 1))
                    if stmt.orelse:
                        queue.append((stmt.orelse, current_nesting + 1))
                    if stmt.finalbody:
                        queue.append((stmt.finalbody, current_nesting + 1))
                elif hasattr(ast, "TryStar") and isinstance(stmt, ast.TryStar):
                    queue.append((stmt.body, current_nesting + 1))
                    for handler in stmt.handlers:
                        queue.append((handler.body, current_nesting + 1))
                    if stmt.orelse:
                        queue.append((stmt.orelse, current_nesting + 1))
                    if stmt.finalbody:
                        queue.append((stmt.finalbody, current_nesting + 1))
                elif isinstance(stmt, ast.Match):
                    for case in stmt.cases:
                        queue.append((case.body, current_nesting + 1))

        return statement_count, top_level_statement_count, max_nesting, diagnostics

    def _compute_scope_metrics(
        self, root: ast.AST, scope_type: str
    ) -> ScopeStructuralMetrics:
        """
        Computes all ScopeStructuralMetrics fields for an individual scope root.
        """
        stmt_count, top_stmt_count, nesting, diags = (
            self._analyze_statements_and_nesting(root, scope_type)
        )
        ast_count, ast_depth = self._compute_ast_node_count_and_depth(
            root, scope_type
        )

        if_stmt_count = 0
        if_expr_count = 0
        bool_op_count = 0
        assert_count = 0
        loop_count = 0
        comp_count = 0
        return_count: Optional[int] = None
        param_count: Optional[int] = None

        if scope_type in ("function", "method"):
            return_count = 0
            param_count = 0
            if hasattr(root, "args") and root.args is not None:
                args = root.args
                param_count += len(getattr(args, "posonlyargs", []))
                param_count += len(getattr(args, "args", []))
                if getattr(args, "vararg", None) is not None:
                    param_count += 1
                param_count += len(getattr(args, "kwonlyargs", []))
                if getattr(args, "kwarg", None) is not None:
                    param_count += 1

        # Iterative traversal of owned nodes to compute specific constructs
        queue: List[Tuple[ast.AST, bool]] = [(root, True)]
        while queue:
            node, is_root = queue.pop(0)
            if not is_root:
                if isinstance(node, ast.If):
                    if_stmt_count += 1
                elif isinstance(node, ast.IfExp):
                    if_expr_count += 1
                elif isinstance(node, ast.BoolOp):
                    bool_op_count += len(node.values) - 1
                elif isinstance(node, ast.Assert):
                    assert_count += 1
                elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
                    loop_count += 1
                elif isinstance(
                    node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
                ):
                    comp_count += 1
                elif isinstance(node, ast.Return) and scope_type in ("function", "method"):
                    return_count += 1

            for child in self._get_scope_children(node, is_root, scope_type):
                queue.append((child, False))

        conditional_count = if_stmt_count + if_expr_count

        return ScopeStructuralMetrics(
            statement_count=stmt_count,
            top_level_statement_count=top_stmt_count,
            ast_node_count=ast_count,
            ast_depth=ast_depth,
            control_nesting_depth=nesting,
            if_statement_count=if_stmt_count,
            if_expression_count=if_expr_count,
            conditional_count=conditional_count,
            boolean_operator_count=bool_op_count,
            assertion_count=assert_count,
            loop_count=loop_count,
            comprehension_count=comp_count,
            parameter_count=param_count,
            return_count=return_count,
            diagnostics=diags,
        )
