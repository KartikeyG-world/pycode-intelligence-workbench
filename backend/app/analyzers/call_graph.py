import ast
from typing import Dict, Any, List, Optional, Set, Tuple
from app.analyzers.function_index import FunctionIndex, FunctionInfo


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
        is_resolved: bool = True,
        unresolved_reason: Optional[str] = None,
        call_node: Optional[ast.Call] = None,
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
        self.is_resolved = is_resolved
        self.unresolved_reason = unresolved_reason
        self.call_node = call_node

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

        class ScopeCallVisitor(ast.NodeVisitor):
            def __init__(self, outer: "CallGraph"):
                self.outer = outer

            def visit_For(self, node: ast.For):
                loop_stack.append(node)
                self.generic_visit(node)
                loop_stack.pop()

            def visit_While(self, node: ast.While):
                loop_stack.append(node)
                self.generic_visit(node)
                loop_stack.pop()

            # Stop walking into nested function or class definitions (they have their own scope)
            def visit_FunctionDef(self, node: ast.FunctionDef):
                pass

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                pass

            def visit_ClassDef(self, node: ast.ClassDef):
                pass

            def visit_Call(self, node: ast.Call):
                callee_info, unresolved_reason = self.outer.index.resolve_call(caller_id, node)
                callee_name = self.outer._extract_callee_name(node.func)

                is_in_loop = len(loop_stack) > 0
                loop_depth = len(loop_stack)
                enclosing_loop_id = f"loop@{loop_stack[-1].lineno}" if loop_stack else None
                arg_descs = [self.outer._describe_argument(a) for a in node.args]

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
                        is_resolved=True,
                        call_node=node,
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
                        is_resolved=False,
                        unresolved_reason=unresolved_reason,
                        call_node=node,
                    )
                    self.outer.call_sites.append(site)
                    self.outer.unresolved_calls.append(site)
                    self.outer.index.functions[caller_id].call_sites.append(site)

                self.generic_visit(node)

        visitor = ScopeCallVisitor(self)
        for stmt in statements:
            visitor.visit(stmt)

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
