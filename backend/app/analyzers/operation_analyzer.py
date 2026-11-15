import ast
from typing import List, Dict, Any, Tuple, Set, Optional


class OperationReport:
    def __init__(self):
        self.operations: List[Dict[str, Any]] = []
        self.max_operation_cost: str = "O(1)"
        self.has_sorting: bool = False
        self.has_linear_search_in_loop: bool = False
        self.has_quadratic_insert: bool = False
        self.has_repeated_sort_in_loop: bool = False
        self.has_string_concat_in_loop: bool = False
        self.has_list_copy: bool = False
        self.has_slice_in_loop: bool = False
        self.has_copy_in_loop: bool = False
        self.detected_allocations: List[Dict[str, Any]] = []
        self.space_complexity_from_allocations: str = "O(1)"
        self.space_reasoning: List[str] = []
        self.optimization_hints: List[str] = []


class LocalTypeInference:
    """Conservative, scope-aware local type inference for operation diagnostics."""

    @staticmethod
    def infer_expr_type(node: Optional[ast.AST], env: Dict[str, str]) -> str:
        if node is None:
            return "unknown"
        if isinstance(node, ast.Constant):
            # Check bool before int because bool subclasses int in Python
            if isinstance(node.value, bool):
                return "bool"
            if isinstance(node.value, int):
                return "int"
            if isinstance(node.value, float):
                return "float"
            if isinstance(node.value, str):
                return "str"
            return "unknown"
        if isinstance(node, ast.JoinedStr):
            return "str"
        if isinstance(node, (ast.List, ast.ListComp)):
            return "list"
        if isinstance(node, (ast.Dict, ast.DictComp)):
            return "dict"
        if isinstance(node, (ast.Set, ast.SetComp)):
            return "set"
        if isinstance(node, ast.Tuple):
            return "tuple"
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                fname = node.func.id
                if fname in ("str", "repr", "chr", "format"):
                    return "str"
                if fname in ("int", "len", "ord"):
                    return "int"
                if fname in ("float",):
                    return "float"
                if fname in ("bool",):
                    return "bool"
                if fname in ("list",):
                    return "list"
                if fname in ("dict",):
                    return "dict"
                if fname in ("set",):
                    return "set"
            return "unknown"
        if isinstance(node, ast.Name):
            return env.get(node.id, "unknown")
        if isinstance(node, ast.BinOp):
            left_t = LocalTypeInference.infer_expr_type(node.left, env)
            right_t = LocalTypeInference.infer_expr_type(node.right, env)
            if isinstance(node.op, ast.Add):
                if left_t == "str" or right_t == "str":
                    return "str"
                if left_t == "int" and right_t == "int":
                    return "int"
                if left_t in ("int", "float") and right_t in ("int", "float"):
                    return "float"
            return "unknown"
        if isinstance(node, ast.UnaryOp):
            sub_t = LocalTypeInference.infer_expr_type(node.operand, env)
            if isinstance(node.op, (ast.UAdd, ast.USub)):
                return sub_t if sub_t in ("int", "float") else "unknown"
            if isinstance(node.op, ast.Not):
                return "bool"
        return "unknown"

    @staticmethod
    def infer_annotation_type(ann: Optional[ast.AST]) -> str:
        if ann is None:
            return "unknown"
        if isinstance(ann, ast.Name):
            if ann.id in ("str", "int", "float", "bool", "list", "dict", "set", "tuple"):
                return ann.id
        elif isinstance(ann, ast.Subscript):
            if isinstance(ann.value, ast.Name):
                if ann.value.id in ("List", "list"):
                    return "list"
                if ann.value.id in ("Dict", "dict"):
                    return "dict"
                if ann.value.id in ("Set", "set"):
                    return "set"
                if ann.value.id in ("Tuple", "tuple"):
                    return "tuple"
        return "unknown"


class OperationAnalyzer:
    """Analyzes built-in operations, container allocations, performance pitfalls, and Python cost model."""

    def analyze(self, tree: ast.AST) -> OperationReport:
        report = OperationReport()
        self._inspect_allocations(tree, report)
        self._inspect_calls_and_operations(tree, report)
        return report

    def _inspect_allocations(self, tree: ast.AST, report: OperationReport):
        """Detects data structure creations like [0]*n or [[0]*n for _ in range(n)]."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ListComp):
                is_matrix = False
                if isinstance(node.elt, ast.BinOp) and isinstance(node.elt.op, ast.Mult):
                    is_matrix = True
                elif isinstance(node.elt, ast.ListComp):
                    is_matrix = True

                if is_matrix:
                    report.detected_allocations.append({
                        "type": "2D Matrix / Grid",
                        "complexity": "O(n²)",
                        "line": getattr(node, "lineno", 0),
                        "snippet": "Nested list comprehension / matrix allocation"
                    })
                    report.space_complexity_from_allocations = "O(n²)"
                    report.space_reasoning.append(
                        "Allocates a 2D matrix / nested list proportional to n × n, requiring O(n²) auxiliary space."
                    )
                else:
                    if report.space_complexity_from_allocations != "O(n²)":
                        report.detected_allocations.append({
                            "type": "1D List Comprehension",
                            "complexity": "O(n)",
                            "line": getattr(node, "lineno", 0),
                            "snippet": "List comprehension allocation"
                        })
                        report.space_complexity_from_allocations = "O(n)"
                        report.space_reasoning.append(
                            "List comprehension creates a new collection sized proportionally to input, requiring O(n) auxiliary space."
                        )

            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
                is_list_mult = False
                var_operand = "n"

                if isinstance(node.left, ast.List) and isinstance(node.right, (ast.Name, ast.Call)):
                    is_list_mult = True
                    var_operand = ast.unparse(node.right) if hasattr(ast, "unparse") else "n"
                elif isinstance(node.right, ast.List) and isinstance(node.left, (ast.Name, ast.Call)):
                    is_list_mult = True
                    var_operand = ast.unparse(node.left) if hasattr(ast, "unparse") else "n"

                if is_list_mult and report.space_complexity_from_allocations != "O(n²)":
                    report.detected_allocations.append({
                        "type": "Linear Array Allocation",
                        "complexity": "O(n)",
                        "line": getattr(node, "lineno", 0),
                        "snippet": f"[...] * {var_operand}"
                    })
                    report.space_complexity_from_allocations = "O(n)"
                    report.space_reasoning.append(
                        f"List multiplication '[...] * {var_operand}' allocates an array proportional to {var_operand}, requiring O(n) auxiliary space."
                    )

    def _inspect_calls_and_operations(self, tree: ast.AST, report: OperationReport):
        # 1. Identify all nodes located inside loops
        loop_nodes: Set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.For, ast.While)):
                for descendant in ast.walk(node):
                    if descendant is not node:
                        loop_nodes.add(id(descendant))

        # 2. Perform local type inference per scope to track string vs non-string variables
        scopes: List[List[ast.stmt]] = []
        if isinstance(tree, ast.Module):
            scopes.append(tree.body)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scopes.append(node.body)

        for scope_stmts in scopes:
            self._analyze_scope_operations(scope_stmts, loop_nodes, report)

    def _analyze_scope_operations(
        self,
        statements: List[ast.stmt],
        loop_nodes: Set[int],
        report: OperationReport
    ):
        env: Dict[str, str] = {}

        def inspect_node_operations(node: ast.AST, env_map: Dict[str, str]):
            for child in ast.walk(node):
                in_loop = id(child) in loop_nodes
                lineno = getattr(child, "lineno", 0)

                # Slicing detection: lst[1:], s[:k]
                if isinstance(child, ast.Subscript) and isinstance(child.slice, ast.Slice):
                    report.operations.append({
                        "name": "slice",
                        "cost": "O(k)",
                        "line": lineno,
                        "in_loop": in_loop
                    })
                    if in_loop:
                        report.has_slice_in_loop = True

                # List copying & sorting & inserts
                elif isinstance(child, ast.Call):
                    func_name = ""
                    if isinstance(child.func, ast.Name):
                        func_name = child.func.id
                    elif isinstance(child.func, ast.Attribute):
                        func_name = child.func.attr

                    if func_name in ("list", "copy"):
                        report.has_list_copy = True
                        if in_loop:
                            report.has_copy_in_loop = True
                        report.operations.append({
                            "name": "list_copy",
                            "cost": "O(n)",
                            "line": lineno,
                            "in_loop": in_loop
                        })

                    elif func_name in ("sorted", "sort"):
                        report.has_sorting = True
                        report.operations.append({
                            "name": func_name,
                            "cost": "O(n log n)",
                            "line": lineno,
                            "in_loop": in_loop
                        })
                        if in_loop:
                            report.has_repeated_sort_in_loop = True
                            report.optimization_hints.append(
                                f"Repeated sorting '{func_name}' detected inside a loop on line {lineno}. "
                                "Sorting repeatedly inside an iteration can degrade performance to O(n² log n); "
                                "consider sorting once before the loop."
                            )

                    elif func_name == "insert" and isinstance(child.func, ast.Attribute):
                        if child.args and isinstance(child.args[0], ast.Constant) and child.args[0].value == 0:
                            report.has_quadratic_insert = True
                            if in_loop:
                                report.optimization_hints.append(
                                    f"List insert at index 0 ('insert(0, ...)') detected inside a loop on line {lineno}. "
                                    "Inserting at the beginning shifts all elements (O(n) per call); "
                                    "consider using 'collections.deque' for O(1) appends to the left."
                                )

                    elif func_name == "copy" and isinstance(child.func, ast.Attribute):
                        report.has_list_copy = True
                        if in_loop:
                            report.has_copy_in_loop = True

                    elif func_name in ("min", "max", "sum"):
                        report.operations.append({
                            "name": func_name,
                            "cost": "O(n)",
                            "line": lineno,
                            "in_loop": in_loop
                        })

                # Membership test: 'x in lst'
                elif isinstance(child, ast.Compare):
                    for idx, op in enumerate(child.ops):
                        if isinstance(op, (ast.In, ast.NotIn)):
                            comparator = child.comparators[idx] if idx < len(child.comparators) else None
                            comp_type = LocalTypeInference.infer_expr_type(comparator, env_map)
                            is_list_or_unknown = comp_type not in ("set", "dict")
                            if isinstance(comparator, ast.Name):
                                cname = comparator.id.lower()
                                if "set" in cname or "dict" in cname or "map" in cname:
                                    is_list_or_unknown = False

                            report.operations.append({
                                "name": "membership",
                                "cost": "O(1)" if not is_list_or_unknown else "O(n)",
                                "line": lineno,
                                "in_loop": in_loop
                            })
                            if in_loop and is_list_or_unknown:
                                report.has_linear_search_in_loop = True
                                report.optimization_hints.append(
                                    f"Membership check ('in' operator) detected inside a loop on line {lineno}. "
                                    "If the container is a list, each check takes O(n), creating an O(n²) bottleneck. "
                                    "Consider converting the container to a 'set' or 'dict' for average O(1) lookups."
                                )

        def process_statement(stmt: ast.stmt, current_env: Dict[str, str]):
            # Track variable types from assignments
            if isinstance(stmt, ast.AnnAssign):
                ann_type = LocalTypeInference.infer_annotation_type(stmt.annotation)
                val_type = LocalTypeInference.infer_expr_type(stmt.value, current_env)
                chosen = ann_type if ann_type != "unknown" else val_type
                if isinstance(stmt.target, ast.Name):
                    current_env[stmt.target.id] = chosen
                inspect_node_operations(stmt, current_env)

            elif isinstance(stmt, ast.Assign):
                val_type = LocalTypeInference.infer_expr_type(stmt.value, current_env)
                for t in stmt.targets:
                    if isinstance(t, ast.Name):
                        current_env[t.id] = val_type
                inspect_node_operations(stmt, current_env)

            elif isinstance(stmt, ast.AugAssign):
                in_loop = id(stmt) in loop_nodes
                lineno = getattr(stmt, "lineno", 0)

                if in_loop and isinstance(stmt.op, ast.Add):
                    target_name = stmt.target.id if isinstance(stmt.target, ast.Name) else None
                    target_type = current_env.get(target_name, "unknown") if target_name else "unknown"
                    val_type = LocalTypeInference.infer_expr_type(stmt.value, current_env)

                    # Only flag string concatenation if variable or value is confirmed str
                    if target_type == "str" or val_type == "str":
                        report.has_string_concat_in_loop = True
                        report.optimization_hints.append(
                            f"Potential repeated string concatenation ('+=') inside a loop on line {lineno}. "
                            "In Python, repeatedly appending to an immutable string can lead to repeated memory reallocation "
                            "and copying (O(n²)); consider accumulating parts in a list and using ''.join(...) for linear O(n) performance."
                        )
                inspect_node_operations(stmt, current_env)

            elif isinstance(stmt, ast.If):
                inspect_node_operations(stmt.test, current_env)
                # Process then and else branches with branching envs
                then_env = current_env.copy()
                for sub in stmt.body:
                    process_statement(sub, then_env)

                else_env = current_env.copy()
                for sub in stmt.orelse:
                    process_statement(sub, else_env)

                # Merge envs conservatively
                all_keys = set(then_env.keys()) | set(else_env.keys())
                for k in all_keys:
                    t1 = then_env.get(k, "unknown")
                    t2 = else_env.get(k, "unknown")
                    current_env[k] = t1 if t1 == t2 else "unknown"

            elif isinstance(stmt, (ast.For, ast.While)):
                if isinstance(stmt, ast.For):
                    inspect_node_operations(stmt.iter, current_env)
                elif isinstance(stmt, ast.While):
                    inspect_node_operations(stmt.test, current_env)
                for sub in stmt.body:
                    process_statement(sub, current_env)
                for sub in stmt.orelse:
                    process_statement(sub, current_env)

            else:
                inspect_node_operations(stmt, current_env)

        for stmt in statements:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            process_statement(stmt, env)
