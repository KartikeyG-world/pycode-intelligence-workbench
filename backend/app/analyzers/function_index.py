import ast
from typing import Dict, Any, List, Optional, Set, Tuple


class FunctionInfo:
    """Represents a statically indexed Python function, method, or module entrypoint."""

    def __init__(
        self,
        func_id: str,
        name: str,
        qualified_name: str,
        func_type: str,  # "module", "function", "async_function", "method", "static_method", "class_method"
        node: ast.AST,
        lineno: int = 1,
        end_lineno: int = 1,
        col_offset: int = 0,
        parent_scope_id: Optional[str] = None,
        scope_type: str = "module",  # "module", "class", "function"
        parameters: Optional[List[str]] = None,
        param_annotations: Optional[Dict[str, str]] = None,
        decorators: Optional[List[str]] = None,
    ):
        self.func_id = func_id
        self.name = name
        self.qualified_name = qualified_name
        self.func_type = func_type
        self.node = node
        self.lineno = lineno
        self.end_lineno = end_lineno
        self.col_offset = col_offset
        self.parent_scope_id = parent_scope_id
        self.scope_type = scope_type
        self.parameters = parameters or []
        self.param_annotations = param_annotations or {}
        self.decorators = decorators or []
        self.local_variables: Set[str] = set()
        self.shadowed_names: Set[str] = set()
        self.is_recursive: bool = False
        self.call_sites: List[Any] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "func_id": self.func_id,
            "name": self.name,
            "qualified_name": self.qualified_name,
            "func_type": self.func_type,
            "lineno": self.lineno,
            "end_lineno": self.end_lineno,
            "parent_scope_id": self.parent_scope_id,
            "parameters": self.parameters,
            "decorators": self.decorators,
            "is_recursive": self.is_recursive,
        }


class FunctionIndex:
    """Indexes functions, classes, and scopes from a Python AST and resolves call targets."""

    def __init__(self):
        self.functions: Dict[str, FunctionInfo] = {}
        self.name_to_funcs: Dict[str, List[FunctionInfo]] = {}
        self.module_statements: List[ast.stmt] = []
        self.has_executable_module_code: bool = False
        self.module_func: Optional[FunctionInfo] = None

    @classmethod
    def from_ast(cls, tree: ast.AST) -> "FunctionIndex":
        indexer = cls()
        indexer._build(tree)
        return indexer

    def _build(self, tree: ast.AST):
        if not isinstance(tree, ast.Module):
            return

        # 1. Create top-level module pseudo-function
        module_id = "<module>"
        self.module_func = FunctionInfo(
            func_id=module_id,
            name="<module>",
            qualified_name="<module>",
            func_type="module",
            node=tree,
            lineno=1,
            end_lineno=getattr(tree, "end_lineno", 1),
            parent_scope_id=None,
            scope_type="module",
        )
        self.functions[module_id] = self.module_func

        # 2. Extract module-level executable statements (excluding defs)
        executable_stmts: List[ast.stmt] = []
        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            executable_stmts.append(stmt)
            # Check if this statement is meaningful execution (loops, calls, expressions)
            if self._is_meaningful_execution(stmt):
                self.has_executable_module_code = True

        self.module_statements = executable_stmts

        # 3. Recursively index all function and class definitions
        self._index_scope(
            body=tree.body,
            parent_id=module_id,
            parent_qualname="",
            parent_scope_type="module"
        )

        # 4. Map short names to function infos for scope lookups
        for func_info in self.functions.values():
            if func_info.func_id == "<module>":
                continue
            self.name_to_funcs.setdefault(func_info.name, []).append(func_info)

        # 5. Detect local variables and shadowed function names
        self._detect_locals_and_shadowing()

    def _is_meaningful_execution(self, stmt: ast.stmt) -> bool:
        """Determines whether a module-level statement represents actual execution vs trivial docstrings/imports."""
        # Docstrings
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
            return False
        # Imports only without execution are not execution targets
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            return False
        # Loops, calls, expressions, conditionals with calls/loops are meaningful
        if isinstance(stmt, (ast.For, ast.While, ast.Try, ast.With)):
            return True
        if isinstance(stmt, ast.Expr):
            # Function calls like helper(arr), print(...), etc.
            if isinstance(stmt.value, ast.Call):
                return True
        if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            # Assignments with function calls or comprehension
            val = getattr(stmt, "value", None)
            if isinstance(val, (ast.Call, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                return True
        if isinstance(stmt, ast.If):
            # Check for if __name__ == '__main__': or executable body
            return True
        return False

    def _index_scope(
        self,
        body: List[ast.stmt],
        parent_id: str,
        parent_qualname: str,
        parent_scope_type: str,
    ):
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_name = stmt.name
                qualname = f"{parent_qualname}.{func_name}" if parent_qualname else func_name
                func_id = f"{qualname}@{stmt.lineno}"

                # Determine function type
                func_type = "async_function" if isinstance(stmt, ast.AsyncFunctionDef) else "function"
                decorators: List[str] = []
                for dec in stmt.decorator_list:
                    if isinstance(dec, ast.Name):
                        decorators.append(dec.id)
                    elif isinstance(dec, ast.Attribute):
                        decorators.append(dec.attr)
                    elif isinstance(dec, ast.Call):
                        if isinstance(dec.func, ast.Name):
                            decorators.append(dec.func.id)
                        elif isinstance(dec.func, ast.Attribute):
                            decorators.append(dec.func.attr)

                if parent_scope_type == "class":
                    if "staticmethod" in decorators:
                        func_type = "static_method"
                    elif "classmethod" in decorators:
                        func_type = "class_method"
                    else:
                        func_type = "method"

                params = [arg.arg for arg in stmt.args.args]
                param_annotations: Dict[str, str] = {}
                for arg in stmt.args.args:
                    if arg.annotation and hasattr(ast, "unparse"):
                        param_annotations[arg.arg] = ast.unparse(arg.annotation)

                func_info = FunctionInfo(
                    func_id=func_id,
                    name=func_name,
                    qualified_name=qualname,
                    func_type=func_type,
                    node=stmt,
                    lineno=stmt.lineno,
                    end_lineno=getattr(stmt, "end_lineno", stmt.lineno),
                    col_offset=stmt.col_offset,
                    parent_scope_id=parent_id,
                    scope_type="function",
                    parameters=params,
                    param_annotations=param_annotations,
                    decorators=decorators,
                )
                self.functions[func_id] = func_info

                # Recurse for nested functions inside this function
                self._index_scope(
                    body=stmt.body,
                    parent_id=func_id,
                    parent_qualname=qualname,
                    parent_scope_type="function"
                )

            elif isinstance(stmt, ast.ClassDef):
                class_name = stmt.name
                class_qualname = f"{parent_qualname}.{class_name}" if parent_qualname else class_name
                class_id = f"class:{class_qualname}@{stmt.lineno}"
                # Recurse for methods inside class
                self._index_scope(
                    body=stmt.body,
                    parent_id=class_id,
                    parent_qualname=class_qualname,
                    parent_scope_type="class"
                )

    def _detect_locals_and_shadowing(self):
        """Walks each function body to discover local variable assignments and detect name shadowing."""
        known_function_names = set(self.name_to_funcs.keys())

        for func_info in self.functions.values():
            if func_info.func_id == "<module>":
                # For module level, assignments create module-level variables
                for stmt in self.module_statements:
                    for target in self._extract_assignment_targets(stmt):
                        func_info.local_variables.add(target)
                        if target in known_function_names:
                            func_info.shadowed_names.add(target)
                continue

            node = func_info.node
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Parameters are local variables
            for p in func_info.parameters:
                func_info.local_variables.add(p)
                if p in known_function_names:
                    func_info.shadowed_names.add(p)

            # Discover assigned variables within function body (not in nested defs)
            for stmt in node.body:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                for child in ast.walk(stmt):
                    if isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.For)):
                        for target in self._extract_assignment_targets(child):
                            func_info.local_variables.add(target)
                            if target in known_function_names:
                                func_info.shadowed_names.add(target)

    def _extract_assignment_targets(self, node: ast.AST) -> List[str]:
        targets: List[str] = []
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    targets.append(t.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                targets.append(node.target.id)
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name):
                targets.append(node.target.id)
        elif isinstance(node, ast.For):
            if isinstance(node.target, ast.Name):
                targets.append(node.target.id)
        return targets

    def resolve_call(
        self, caller_id: str, call_node: ast.Call
    ) -> Tuple[Optional[FunctionInfo], Optional[str]]:
        """Resolves an ast.Call node from the caller's context to a target FunctionInfo or returns an unresolved reason."""
        caller = self.functions.get(caller_id)
        if caller is None:
            return None, "unknown_caller"

        # Case 1: Direct name call: func(...)
        if isinstance(call_node.func, ast.Name):
            callee_name = call_node.func.id

            # Check if name is shadowed by a local variable or parameter
            if callee_name in caller.shadowed_names:
                return None, f"shadowed_name:{callee_name}"

            # Check for direct self recursion
            if caller.name == callee_name and caller.func_id != "<module>":
                return caller, None

            # Check for nested functions defined directly inside caller
            for child_func in self.functions.values():
                if child_func.parent_scope_id == caller_id and child_func.name == callee_name:
                    return child_func, None

            # Look up in module level functions
            candidates = self.name_to_funcs.get(callee_name, [])
            if len(candidates) == 1:
                return candidates[0], None
            elif len(candidates) > 1:
                # Disambiguate if one is a sibling in same scope
                same_scope = [c for c in candidates if c.parent_scope_id == caller.parent_scope_id]
                if len(same_scope) == 1:
                    return same_scope[0], None
                return None, f"ambiguous_candidates:{callee_name}"

            # Known Python built-ins
            if callee_name in BUILTIN_OPERATIONS:
                return None, f"builtin:{callee_name}"

            return None, f"unresolved_external:{callee_name}"

        # Case 2: Method call: self.method(...) or cls.method(...)
        elif isinstance(call_node.func, ast.Attribute):
            attr_name = call_node.func.attr
            if isinstance(call_node.func.value, ast.Name) and call_node.func.value.id in ("self", "cls"):
                # Method call within class
                if caller.parent_scope_id and caller.parent_scope_id.startswith("class:"):
                    for candidate in self.functions.values():
                        if candidate.parent_scope_id == caller.parent_scope_id and candidate.name == attr_name:
                            return candidate, None
                return None, f"unresolved_method:{attr_name}"

            return None, f"dynamic_dispatch:{attr_name}"

        return None, "dynamic_call_expression"


BUILTIN_OPERATIONS: Set[str] = {
    "len", "range", "enumerate", "zip", "min", "max", "sum", "sorted",
    "reversed", "map", "filter", "any", "all", "abs", "round", "int",
    "float", "str", "bool", "list", "dict", "set", "tuple", "print"
}
