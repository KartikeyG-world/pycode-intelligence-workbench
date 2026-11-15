import ast
from typing import Dict, Any, List, Optional, Set, Tuple
from app.analyzers.function_index import FunctionIndex, FunctionInfo

BUILTIN_CONTAINER_METHODS: Set[str] = {
    "append", "extend", "pop", "insert", "remove", "clear",
    "index", "count", "sort", "reverse", "copy",
    "get", "keys", "values", "items", "update",
    "add", "discard"
}


class CallSite:
    """Represents a specific function invocation site in the AST."""

    def __init__(
        self,
        caller_id: str,
        callee_id: Optional[str],
        callee_name: str,
        lineno: int,
        col_offset: int,
        is_in_loop: bool = False,
        loop_depth: int = 0,
        enclosing_loop_id: Optional[str] = None,
        arg_descriptions: Optional[List[str]] = None,
        arg_classifications: Optional[List[Dict[str, Any]]] = None,
        is_resolved: bool = True,
        unresolved_reason: Optional[str] = None,
        call_node: Optional[ast.Call] = None,
        is_awaited: bool = False,
        is_consumed_generator: bool = False,
        is_builtin: bool = False,
    ):
        self.caller_id = caller_id
        self.callee_id = callee_id
        self.callee_name = callee_name
        self.lineno = lineno
        self.col_offset = col_offset
        self.is_in_loop = is_in_loop
        self.loop_depth = loop_depth
        self.enclosing_loop_id = enclosing_loop_id
        self.arg_descriptions = arg_descriptions or []
        self.arg_classifications = arg_classifications or []
        self.is_resolved = is_resolved
        self.unresolved_reason = unresolved_reason
        self.call_node = call_node
        self.is_awaited = is_awaited
        self.is_consumed_generator = is_consumed_generator
        self.is_builtin = is_builtin

    def to_dict(self) -> Dict[str, Any]:
        return {
            "caller_id": self.caller_id,
            "callee_id": self.callee_id,
            "callee_name": self.callee_name,
            "lineno": self.lineno,
            "col_offset": self.col_offset,
            "is_in_loop": self.is_in_loop,
            "loop_depth": self.loop_depth,
            "is_resolved": self.is_resolved,
            "unresolved_reason": self.unresolved_reason,
            "args": self.arg_descriptions,
            "arg_classifications": self.arg_classifications,
            "is_awaited": self.is_awaited,
            "is_consumed_generator": self.is_consumed_generator,
            "is_builtin": self.is_builtin,
        }


class RecursionComponent:
    """Represents a recursion strongly connected component (direct or mutual)."""

    def __init__(self, component_id: int, functions: List[str], is_mutual: bool = False):
        self.component_id = component_id
        self.functions = functions
        self.is_mutual = is_mutual
        self.is_solvable: bool = False
        self.solved_complexity: Optional[str] = None
        self.explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "functions": self.functions,
            "is_mutual": self.is_mutual,
            "is_solvable": self.is_solvable,
            "solved_complexity": self.solved_complexity,
            "explanation": self.explanation,
        }


class CallGraph:
    """Constructs and analyzes the interprocedural static call graph."""

    def __init__(self, function_index: FunctionIndex):
        self.index = function_index
        self.call_sites: List[CallSite] = []
        self.adj_list: Dict[str, Set[str]] = {fid: set() for fid in self.index.functions}
        self.reverse_adj_list: Dict[str, Set[str]] = {fid: set() for fid in self.index.functions}
        self.unresolved_calls: List[CallSite] = []
        self.sccs: List[List[str]] = []
        self.recursion_components: List[RecursionComponent] = []
        self.func_to_scc: Dict[str, int] = {}
        self._build_graph()
        self._compute_sccs()

    def _build_graph(self):
        """Extracts call sites from each function (and module) body and links resolved edges."""
        # Process module-level statements
        self._extract_calls_from_scope(
            caller_id="<module>",
            statements=self.index.module_statements
        )

        # Process each indexed function body
        for func_id, func_info in self.index.functions.items():
            if func_id == "<module>":
                continue
            if isinstance(func_info.node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._extract_calls_from_scope(
                    caller_id=func_id,
                    statements=func_info.node.body
                )

    def _extract_calls_from_scope(self, caller_id: str, statements: List[ast.stmt]):
        """Walks statements within a function or module scope, tracking loop nesting and call sites."""
        loop_stack: List[ast.AST] = []
        parent_stack: List[ast.AST] = []

        caller_info = self.index.functions.get(caller_id)
        caller_params = set(caller_info.parameters) if caller_info else set()

        class ScopeCallVisitor(ast.NodeVisitor):
            def __init__(self, outer: "CallGraph"):
                self.outer = outer

            def visit(self, node: ast.AST):
                parent_stack.append(node)
                try:
                    super().visit(node)
                finally:
                    parent_stack.pop()

            def visit_For(self, node: ast.For):
                loop_stack.append(node)
                self.generic_visit(node)
                loop_stack.pop()

            def visit_While(self, node: ast.While):
                loop_stack.append(node)
                self.generic_visit(node)
                loop_stack.pop()

            def _visit_comprehension_construct(self, generators: List[ast.comprehension], inner_nodes: List[ast.AST]):
                pushed = 0
                try:
                    for gen in generators:
                        self.visit(gen.iter)
                        loop_stack.append(gen)
                        pushed += 1
                        self.visit(gen.target)
                        for if_expr in gen.ifs:
                            self.visit(if_expr)
                    for n in inner_nodes:
                        self.visit(n)
                finally:
                    for _ in range(pushed):
                        loop_stack.pop()

            def visit_GeneratorExp(self, node: ast.GeneratorExp):
                self._visit_comprehension_construct(node.generators, [node.elt])

            def visit_ListComp(self, node: ast.ListComp):
                self._visit_comprehension_construct(node.generators, [node.elt])

            def visit_SetComp(self, node: ast.SetComp):
                self._visit_comprehension_construct(node.generators, [node.elt])

            def visit_DictComp(self, node: ast.DictComp):
                self._visit_comprehension_construct(node.generators, [node.key, node.value])

            # Decorator expressions and default argument expressions evaluate at definition time in the enclosing scope
            def visit_FunctionDef(self, node: ast.FunctionDef):
                for dec in node.decorator_list:
                    self.visit(dec)
                for d in node.args.defaults + [kd for kd in node.args.kw_defaults if kd]:
                    self.visit(d)
                # Function body is deferred, so do not visit node.body here

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                for dec in node.decorator_list:
                    self.visit(dec)
                for d in node.args.defaults + [kd for kd in node.args.kw_defaults if kd]:
                    self.visit(d)
                # Async function body is deferred, so do not visit node.body here

            def visit_ClassDef(self, node: ast.ClassDef):
                pass

            def visit_Attribute(self, node: ast.Attribute):
                # Check if this attribute access is a property getter invocation (not a method call)
                is_call_func = len(parent_stack) >= 2 and isinstance(parent_stack[-2], ast.Call) and parent_stack[-2].func is node
                if not is_call_func:
                    prop_name = node.attr
                    for fid, finfo in self.outer.index.functions.items():
                        if finfo.func_type == "property" and finfo.name == prop_name:
                            is_in_loop = len(loop_stack) > 0
                            loop_depth = len(loop_stack)
                            site = CallSite(
                                caller_id=caller_id,
                                callee_id=fid,
                                callee_name=f"{finfo.name}",
                                lineno=node.lineno,
                                col_offset=node.col_offset,
                                is_in_loop=is_in_loop,
                                loop_depth=loop_depth,
                                enclosing_loop_id=f"loop@{loop_stack[-1].lineno}" if loop_stack else None,
                                arg_descriptions=[],
                                arg_classifications=[],
                                is_resolved=True,
                                call_node=None,
                                is_builtin=False,
                            )
                            self.outer.call_sites.append(site)
                            self.outer.adj_list.setdefault(caller_id, set()).add(fid)
                            self.outer.reverse_adj_list.setdefault(fid, set()).add(caller_id)
                            self.outer.index.functions[caller_id].call_sites.append(site)
                self.generic_visit(node)

            def visit_Call(self, node: ast.Call):
                callee_info, unresolved_reason = self.outer.index.resolve_call(caller_id, node)
                callee_name = self.outer._extract_callee_name(node.func)

                # Check if this call is the iterator expression of the innermost loop
                is_in_iter_header = False
                if loop_stack:
                    innermost = loop_stack[-1]
                    if isinstance(innermost, (ast.For, ast.comprehension)):
                        if innermost.iter is node or any(n is node for n in ast.walk(innermost.iter)):
                            is_in_iter_header = True

                effective_loop_stack = loop_stack[:-1] if is_in_iter_header else loop_stack
                is_in_loop = len(effective_loop_stack) > 0
                loop_depth = len(effective_loop_stack)
                enclosing_loop_id = (
                    f"loop@{getattr(effective_loop_stack[-1], 'lineno', node.lineno)}"
                    if effective_loop_stack
                    else None
                )

                # Extract loop iteration variables and bound variables
                active_loop_vars: Set[str] = set()
                enclosing_loop_bound_vars: Set[str] = set()
                for loop in effective_loop_stack:
                    if isinstance(loop, (ast.For, ast.comprehension)):
                        if isinstance(loop.target, ast.Name):
                            active_loop_vars.add(loop.target.id)
                        elif isinstance(loop.target, ast.Tuple):
                            for elt in loop.target.elts:
                                if isinstance(elt, ast.Name):
                                    active_loop_vars.add(elt.id)
                        for n in ast.walk(loop.iter):
                            if isinstance(n, ast.Name):
                                enclosing_loop_bound_vars.add(n.id)
                    elif isinstance(loop, ast.While):
                        for n in ast.walk(loop.test):
                            if isinstance(n, ast.Name):
                                enclosing_loop_bound_vars.add(n.id)

                arg_descs = [self.outer._describe_argument(a) for a in node.args]
                arg_classifications = self.outer._classify_call_arguments(
                    node.args, caller_params, active_loop_vars, enclosing_loop_bound_vars
                )

                # Check if call is directly awaited
                is_awaited = False
                if len(parent_stack) >= 2 and isinstance(parent_stack[-2], ast.Await):
                    is_awaited = True

                # Check if generator is consumed
                is_consumed = False
                if len(parent_stack) >= 2:
                    direct_p = parent_stack[-2]
                    if isinstance(direct_p, ast.For) and direct_p.iter is node:
                        is_consumed = True
                    elif isinstance(direct_p, ast.Call) and isinstance(direct_p.func, ast.Name):
                        if direct_p.func.id in ("list", "set", "tuple", "sum", "iter", "next", "sorted", "enumerate", "zip"):
                            is_consumed = True
                for p in parent_stack[:-1]:
                    if isinstance(p, ast.comprehension) and p.iter is node:
                        is_consumed = True

                is_builtin = bool(
                    (unresolved_reason and unresolved_reason.startswith("builtin:"))
                    or (
                        unresolved_reason
                        and unresolved_reason.startswith("dynamic_dispatch:")
                        and callee_name in BUILTIN_CONTAINER_METHODS
                    )
                )

                if callee_info is not None:
                    callee_id = callee_info.func_id
                    site = CallSite(
                        caller_id=caller_id,
                        callee_id=callee_id,
                        callee_name=callee_info.name,
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        is_in_loop=is_in_loop,
                        loop_depth=loop_depth,
                        enclosing_loop_id=enclosing_loop_id,
                        arg_descriptions=arg_descs,
                        arg_classifications=arg_classifications,
                        is_resolved=True,
                        call_node=node,
                        is_awaited=is_awaited,
                        is_consumed_generator=is_consumed,
                        is_builtin=False,
                    )
                    self.outer.call_sites.append(site)
                    self.outer.adj_list.setdefault(caller_id, set()).add(callee_id)
                    self.outer.reverse_adj_list.setdefault(callee_id, set()).add(caller_id)
                    self.outer.index.functions[caller_id].call_sites.append(site)
                else:
                    site = CallSite(
                        caller_id=caller_id,
                        callee_id=None,
                        callee_name=callee_name,
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        is_in_loop=is_in_loop,
                        loop_depth=loop_depth,
                        enclosing_loop_id=enclosing_loop_id,
                        arg_descriptions=arg_descs,
                        arg_classifications=arg_classifications,
                        is_resolved=False,
                        unresolved_reason=unresolved_reason,
                        call_node=node,
                        is_awaited=is_awaited,
                        is_consumed_generator=is_consumed,
                        is_builtin=is_builtin,
                    )
                    self.outer.call_sites.append(site)
                    # Only register true unresolved external calls without cost models
                    if not is_builtin:
                        self.outer.unresolved_calls.append(site)
                    self.outer.index.functions[caller_id].call_sites.append(site)

                self.generic_visit(node)

        visitor = ScopeCallVisitor(self)
        for stmt in statements:
            visitor.visit(stmt)

    def _classify_call_arguments(
        self,
        args: List[ast.AST],
        caller_params: Set[str],
        active_loop_vars: Set[str],
        enclosing_loop_bound_vars: Optional[Set[str]] = None,
    ) -> List[Dict[str, Any]]:
        enclosing_loop_bound_vars = enclosing_loop_bound_vars or set()
        classifications: List[Dict[str, Any]] = []
        for a in args:
            if isinstance(a, ast.Constant):
                classifications.append({"category": "CONSTANT", "detail": str(a.value)})
            elif isinstance(a, ast.Name):
                if a.id in active_loop_vars:
                    classifications.append({"category": "LOOP_VARIABLE_SIZE", "detail": a.id})
                elif a.id in caller_params:
                    if enclosing_loop_bound_vars and a.id not in enclosing_loop_bound_vars:
                        classifications.append({"category": "INDEPENDENT_INPUT_SIZE", "detail": a.id})
                    else:
                        classifications.append({"category": "SAME_INPUT_SIZE", "detail": a.id})
                else:
                    classifications.append({"category": "COLLECTION_ALIAS", "detail": a.id})
            elif isinstance(a, ast.Subscript) and isinstance(a.slice, ast.Slice):
                slice_vars = {n.id for n in ast.walk(a.slice) if isinstance(n, ast.Name)}
                if slice_vars & active_loop_vars:
                    classifications.append({"category": "LOOP_VARIABLE_SIZE", "detail": "slice_with_loop_var"})
                else:
                    classifications.append({"category": "COLLECTION_SLICE", "detail": "slice"})
            elif isinstance(a, ast.BinOp):
                bin_vars = {n.id for n in ast.walk(a) if isinstance(n, ast.Name)}
                if bin_vars & active_loop_vars:
                    classifications.append({"category": "LOOP_VARIABLE_SIZE", "detail": "binop_loop_var"})
                elif bin_vars & caller_params:
                    classifications.append({"category": "DERIVED_SYMBOLIC_SIZE", "detail": "binop_caller_param"})
                else:
                    classifications.append({"category": "UNKNOWN", "detail": "binop_unknown"})
            else:
                classifications.append({"category": "UNKNOWN", "detail": "complex_expr"})
        return classifications

    def _extract_callee_name(self, func_node: ast.AST) -> str:
        if isinstance(func_node, ast.Name):
            return func_node.id
        elif isinstance(func_node, ast.Attribute):
            return func_node.attr
        return "<dynamic>"

    def _describe_argument(self, arg_node: ast.AST) -> str:
        """Classifies an argument passed at a call site to evaluate input size scaling."""
        if isinstance(arg_node, ast.Constant):
            return f"constant:{arg_node.value}"
        if isinstance(arg_node, ast.Name):
            return f"var:{arg_node.id}"
        if isinstance(arg_node, ast.Subscript) and isinstance(arg_node.slice, ast.Slice):
            return "slice"
        if isinstance(arg_node, ast.BinOp):
            if isinstance(arg_node.op, (ast.Sub, ast.FloorDiv, ast.Div, ast.RShift)):
                return "reduced_expression"
            return "binary_op"
        if isinstance(arg_node, ast.Call):
            return "nested_call"
        return "unknown"

    def _compute_sccs(self):
        """Finds Strongly Connected Components using Tarjan's algorithm.

        Produces SCCs in topological order (callees before callers / bottom-up).
        """
        index_counter = 0
        stack: List[str] = []
        on_stack: Set[str] = set()
        indices: Dict[str, int] = {}
        lowlinks: Dict[str, int] = {}
        scc_list: List[List[str]] = []

        vertices = [fid for fid in self.index.functions.keys() if fid != "<module>"]

        def strongconnect(v: str):
            nonlocal index_counter
            indices[v] = index_counter
            lowlinks[v] = index_counter
            index_counter += 1
            stack.append(v)
            on_stack.add(v)

            for w in self.adj_list.get(v, set()):
                if w == "<module>":
                    continue
                if w not in indices:
                    strongconnect(w)
                    lowlinks[v] = min(lowlinks[v], lowlinks[w])
                elif w in on_stack:
                    lowlinks[v] = min(lowlinks[v], indices[w])

            if lowlinks[v] == indices[v]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    scc.append(w)
                    if w == v:
                        break
                scc_list.append(scc)

        for v in vertices:
            if v not in indices:
                strongconnect(v)

        self.sccs = scc_list
        # Map each function to its SCC index
        for scc_idx, scc in enumerate(self.sccs):
            for fid in scc:
                self.func_to_scc[fid] = scc_idx

            # Check if this SCC represents recursion
            if len(scc) > 1:
                # Mutual recursion
                for fid in scc:
                    if fid in self.index.functions:
                        self.index.functions[fid].is_recursive = True
                comp = RecursionComponent(
                    component_id=scc_idx,
                    functions=scc,
                    is_mutual=True
                )
                comp.explanation = f"Mutual recursion cycle detected across {len(scc)} functions: {', '.join(scc)}"
                self.recursion_components.append(comp)
            elif len(scc) == 1:
                fid = scc[0]
                # Direct recursion if self-loop exists
                if fid in self.adj_list.get(fid, set()):
                    if fid in self.index.functions:
                        self.index.functions[fid].is_recursive = True
                    comp = RecursionComponent(
                        component_id=scc_idx,
                        functions=scc,
                        is_mutual=False
                    )
                    comp.explanation = f"Direct recursive function '{self.index.functions[fid].name}'"
                    self.recursion_components.append(comp)

    def get_reachable_from(self, root_id: str) -> Set[str]:
        """Returns the set of all function IDs reachable from root_id in the call graph."""
        visited: Set[str] = set()
        queue = [root_id]
        while queue:
            curr = queue.pop(0)
            if curr not in visited:
                visited.add(curr)
                for callee in self.adj_list.get(curr, set()):
                    if callee not in visited:
                        queue.append(callee)
        return visited

    def get_root_functions(self) -> List[str]:
        """Identifies functions that are not called by any other user function (in-degree 0 from user functions)."""
        roots = []
        for fid in self.index.functions:
            if fid == "<module>":
                continue
            # Look at callers other than itself
            external_callers = {c for c in self.reverse_adj_list.get(fid, set()) if c != fid and c != "<module>"}
            if not external_callers:
                roots.append(fid)
        return roots

    def to_mermaid(self) -> str:
        """Generates a GitHub-flavored Mermaid flowchart diagram of the call graph."""
        lines = ["flowchart TD"]
        # Nodes
        for fid, finfo in self.index.functions.items():
            if fid == "<module>":
                lines.append('    module["&lt;module&gt; (Module Entry)"]')
            else:
                rec_label = " [Recursive]" if finfo.is_recursive else ""
                clean_id = fid.replace("@", "_").replace(":", "_").replace(".", "_")
                lines.append(f'    {clean_id}["{finfo.name} ({finfo.func_type}){rec_label}"]')

        # Edges
        for site in self.call_sites:
            if site.is_resolved and site.callee_id:
                src = "module" if site.caller_id == "<module>" else site.caller_id.replace("@", "_").replace(":", "_").replace(".", "_")
                tgt = "module" if site.callee_id == "<module>" else site.callee_id.replace("@", "_").replace(":", "_").replace(".", "_")
                label = f"line {site.lineno}"
                if site.is_in_loop:
                    label += f" (in loop d={site.loop_depth})"
                lines.append(f'    {src} -->|"{label}"| {tgt}')

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "functions": [f.to_dict() for f in self.index.functions.values()],
            "call_sites": [c.to_dict() for c in self.call_sites],
            "unresolved_calls": [c.to_dict() for c in self.unresolved_calls],
            "recursion_components": [r.to_dict() for r in self.recursion_components],
            "scc_count": len(self.sccs),
            "mermaid": self.to_mermaid(),
        }
