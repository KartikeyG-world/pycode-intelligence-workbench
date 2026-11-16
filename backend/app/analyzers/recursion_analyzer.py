import ast
from typing import Dict, Any, List, Optional, Tuple, Set
from app.analyzers.complexity_classes import ComplexityClass
from app.analyzers.recurrence_solver import RecurrenceRelation, RecurrenceSolver


class RecursionCallSite:
    """Detailed record of a single recursive call site in the AST."""

    def __init__(
        self,
        call_id: str,
        lineno: int,
        arg_snippets: List[str],
        is_in_loop: bool = False,
        loop_bound: Optional[str] = None,
        branch_context: str = "main",
    ):
        self.call_id = call_id
        self.lineno = lineno
        self.arg_snippets = arg_snippets
        self.is_in_loop = is_in_loop
        self.loop_bound = loop_bound
        self.branch_context = branch_context


class AllocationInfo:
    """Holds cost and structural type invariants for heap allocations."""

    def __init__(self, cost: ComplexityClass, is_exact_builtin: bool = True, has_primitive_elements: bool = True):
        self.cost = cost
        self.is_exact_builtin = is_exact_builtin
        self.has_primitive_elements = has_primitive_elements


class RecursionAnalyzer:
    """Extracts call sites, control-flow execution paths, argument transformations, and symbolic recurrences."""

    def analyze(self, tree: ast.AST) -> List[RecurrenceRelation]:
        results: List[RecurrenceRelation] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_name = node.name
                rel = self._analyze_function(node, func_name, tree)
                if rel is not None:
                    # Solve the extracted recurrence relation
                    solved_rel = RecurrenceSolver.solve(rel)
                    results.append(solved_rel)

        return results

    def _analyze_function(
        self, func_node: ast.FunctionDef, func_name: str, module_node: Optional[ast.AST] = None
    ) -> Optional[RecurrenceRelation]:
        # 1. Collect all recursive calls
        recursive_calls: List[ast.Call] = []
        for child in ast.walk(func_node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name) and child.func.id == func_name:
                    recursive_calls.append(child)

        if not recursive_calls:
            return None

        param_names = [arg.arg for arg in func_node.args.args]
        total_call_sites = len(recursive_calls)

        # 2. Calculate worst-case branching factor along any single execution path
        worst_case_branches = self._calculate_worst_case_branches(func_node.body, func_name)
        if worst_case_branches == 0:
            worst_case_branches = total_call_sites

        # 3. Check for memoization (e.g. @cache, @lru_cache, or memo[key] dictionary usage)
        has_memoization, state_space, is_bounded_cache = self._detect_memoization(
            func_node, param_names, worst_case_branches
        )

        # 4. Check if any recursive call is enclosed inside a loop (e.g. for i in range(n): f(n-1))
        in_loop, loop_bound = self._check_recursion_in_loop(func_node, func_name)

        # 5. Analyze argument transformations across recursive calls
        reduction_type, step_size = self._analyze_argument_transformations(
            func_node, recursive_calls, param_names, worst_case_branches
        )

        if in_loop:
            reduction_type = "in_loop"

        # 6. Check for leaf output materialization and full output retention
        # e.g. result.append(list(current)) -> leaf output work O(n), retains all outputs
        leaf_output_work, retains_all = self._inspect_leaf_and_output(func_node, param_names)

        # 7. Check local non-recursive work per frame (e.g. slicing, loop, etc.)
        local_work = self._inspect_local_work(func_node)

        # 8. Check local allocations per frame and whether they are released before recursive calls
        local_alloc, alloc_released = self._inspect_recursive_local_allocations(func_node, func_name, module_node)

        # 9. Check cache payload semantics (shared vs unique argument/return allocations)
        has_shared_arg, has_unique_arg, has_shared_ret, has_fresh_ret, has_cross_role_alias, arg_payload, ret_payload = (
            self._inspect_cache_payload_semantics(func_node, param_names, func_name)
        )

        # Canonical input size variable
        canonical_var = "n"
        if param_names:
            first_p = param_names[0]
            if first_p in ("m", "k", "W"):
                canonical_var = first_p

        cache_params = {"memo", "cache", "dp", "visited", "seen", "table", "store"}
        input_params = [p for p in param_names if p.lower() not in cache_params]
        if not input_params:
            input_params = [canonical_var]
        elif len(input_params) == 1 and input_params[0].lower() in ("arr", "lst", "nums", "items", "data", "values"):
            input_params = [canonical_var]

        rel = RecurrenceRelation(
            func_name=func_name,
            branching_factor=worst_case_branches,
            total_call_sites=total_call_sites,
            reduction_type=reduction_type,
            step_size=step_size,
            local_work=local_work,
            has_memoization=has_memoization,
            state_space=state_space,
            parameter_names=input_params,
            leaf_output_work=leaf_output_work,
            retains_all_outputs=retains_all,
            recursion_inside_loop_size=loop_bound,
            is_bounded_cache=is_bounded_cache,
            local_allocation_work=local_alloc,
            allocation_released_before_recursion=alloc_released,
            has_shared_argument=has_shared_arg,
            has_unique_argument_allocation=has_unique_arg,
            has_shared_return_object=has_shared_ret,
            has_fresh_return_allocation=has_fresh_ret,
            argument_payload_class=arg_payload,
            return_payload_class=ret_payload,
            has_cross_role_alias=has_cross_role_alias,
        )

        return rel

    def _calculate_worst_case_branches(self, stmts: List[ast.stmt], func_name: str) -> int:
        """Computes the maximum number of recursive calls that execute along any single control-flow path."""
        calls_on_path = 0

        for stmt in stmts:
            if isinstance(stmt, ast.If):
                # Count calls in the test condition (always evaluated)
                test_calls = self._count_calls_in_expr(stmt.test, func_name)
                # Either body executes OR orelse executes
                body_calls = self._calculate_worst_case_branches(stmt.body, func_name)
                orelse_calls = self._calculate_worst_case_branches(stmt.orelse, func_name) if stmt.orelse else 0
                calls_on_path += test_calls + max(body_calls, orelse_calls)

            elif isinstance(stmt, (ast.For, ast.While)):
                # If a loop has a recursive call, it will execute repeatedly per frame
                loop_calls = self._calculate_worst_case_branches(stmt.body, func_name)
                if loop_calls > 0:
                    # Enclosed in loop, will be handled by in_loop flag
                    calls_on_path += loop_calls
                else:
                    calls_on_path += 0

            elif isinstance(stmt, (ast.Assign, ast.AugAssign)):
                calls_on_path += self._count_calls_in_expr(stmt.value, func_name)

            elif isinstance(stmt, ast.Expr):
                calls_on_path += self._count_calls_in_expr(stmt.value, func_name)

            elif isinstance(stmt, ast.Return):
                if stmt.value:
                    calls_on_path += self._count_calls_in_expr(stmt.value, func_name)

        return calls_on_path

    def _count_calls_in_expr(self, node: ast.AST, func_name: str) -> int:
        count = 0
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == func_name:
                count += 1
        return count

    def _check_recursion_in_loop(self, func_node: ast.AST, func_name: str) -> Tuple[bool, Optional[str]]:
        for node in ast.walk(func_node):
            if isinstance(node, (ast.For, ast.While)):
                for child in ast.walk(node):
                    if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == func_name:
                        # Extract loop bound
                        bound = "n"
                        if isinstance(node, ast.For) and isinstance(node.iter, ast.Call):
                            if isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range" and node.iter.args:
                                bound = ast.unparse(node.iter.args[-1]) if hasattr(ast, "unparse") else "n"
                        return True, bound
        return False, None

    def _detect_memoization(
        self, func_node: ast.FunctionDef, param_names: List[str], worst_case_branches: int = 1
    ) -> Tuple[bool, Optional[str], bool]:
        # Check decorators: @cache, @lru_cache
        for dec in func_node.decorator_list:
            dec_id = ""
            maxsize_val: Optional[int] = None
            if isinstance(dec, ast.Name):
                dec_id = dec.id
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    dec_id = dec.func.id
                elif isinstance(dec.func, ast.Attribute):
                    dec_id = dec.func.attr
                for kw in dec.keywords:
                    if kw.arg == "maxsize" and isinstance(kw.value, ast.Constant):
                        maxsize_val = kw.value.value
                if dec.args and isinstance(dec.args[0], ast.Constant):
                    maxsize_val = dec.args[0].value
            elif isinstance(dec, ast.Attribute):
                dec_id = dec.attr

            if "cache" in dec_id.lower():
                # If bounded cache with maxsize <= 1 and branching factor > 1 (e.g. fibonacci):
                # cache thrashing prevents memoization from reducing exponential branching
                if "lru" in dec_id.lower() and maxsize_val is not None and maxsize_val <= 1:
                    if worst_case_branches > 1:
                        return False, None, True
                    return True, "Θ(n)", True

                cache_params = {"memo", "cache", "dp", "visited", "seen", "table", "store"}
                input_params = [p for p in param_names if p.lower() not in cache_params]
                is_bounded = bool("lru" in dec_id.lower() and maxsize_val is not None)

                container_payload_names = {
                    "path", "acc", "accumulator", "prefix", "suffix", "curr", "current",
                    "trail", "history", "shared", "arr", "lst", "items", "data", "nums",
                    "seq", "values", "tuple", "list", "matrix", "grid", "board", "table",
                    "graph", "payload"
                }

                if len(input_params) >= 2:
                    p1, p2 = input_params[:2]
                    if p2.lower() in container_payload_names:
                        state = f"Θ({p1})"
                    elif p1.lower() in container_payload_names:
                        state = f"Θ({p2})"
                    else:
                        rec_calls = [
                            n for n in ast.walk(func_node)
                            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == func_node.name
                        ]
                        p1_modified = False
                        p2_modified = False
                        all_calls_modify_both = bool(rec_calls)
                        any_call_modifies_only_one = False

                        for rc in rec_calls:
                            c_p1_mod = False
                            c_p2_mod = False
                            if rc.args and len(rc.args) > 0:
                                a0 = rc.args[0]
                                if not (isinstance(a0, ast.Name) and a0.id == p1):
                                    c_p1_mod = True
                            if rc.args and len(rc.args) > 1:
                                a1 = rc.args[1]
                                if not (isinstance(a1, ast.Name) and a1.id == p2):
                                    c_p2_mod = True

                            if c_p1_mod:
                                p1_modified = True
                            if c_p2_mod:
                                p2_modified = True

                            if c_p1_mod and c_p2_mod:
                                pass
                            elif c_p1_mod or c_p2_mod:
                                all_calls_modify_both = False
                                any_call_modifies_only_one = True
                            else:
                                all_calls_modify_both = False

                        if not p2_modified:
                            state = f"Θ({p1})"
                        elif all_calls_modify_both and not any_call_modifies_only_one:
                            state = f"Θ(min({p1},{p2}))"
                        else:
                            state = f"Θ({p1}*{p2})"
                else:
                    state = "Θ(n)"
                return True, state, is_bounded

        # Check in-body cache access: memo[key], cache[key]
        has_dict_lookup = False
        has_dict_store = False
        has_key_tuple = False

        for node in ast.walk(func_node):
            if isinstance(node, ast.Subscript):
                if isinstance(node.value, ast.Name) and any(kw in node.value.id.lower() for kw in ("memo", "cache", "dp")):
                    has_dict_lookup = True
                    if isinstance(node.slice, ast.Tuple):
                        has_key_tuple = True
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
                        if any(kw in target.value.id.lower() for kw in ("memo", "cache", "dp")):
                            has_dict_store = True

        if has_dict_lookup and has_dict_store:
            if has_key_tuple and any("cap" in p.lower() or "weight" in p.lower() for p in param_names):
                return True, "Θ(n*W)", False
            return True, "Θ(n)", False

        return False, None, False

    def _analyze_argument_transformations(
        self, func_node: ast.FunctionDef, recursive_calls: List[ast.Call], param_names: List[str], worst_case_branches: int = 1
    ) -> Tuple[str, float]:
        is_halving = False
        is_subtraction = False
        is_addition_to_bound = False
        step = 1.0

        # Detect local variables assigned from halving expressions (e.g. mid = (low + high) // 2)
        halving_vars: Set[str] = set()
        for node in ast.walk(func_node):
            if isinstance(node, ast.Assign):
                if isinstance(node.value, ast.BinOp) and isinstance(node.value.op, (ast.FloorDiv, ast.Div, ast.RShift)):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            halving_vars.add(t.id)
                elif isinstance(node.value, ast.Name) and "mid" in node.value.id.lower():
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            halving_vars.add(t.id)

        for call in recursive_calls:
            for idx, arg in enumerate(call.args):
                # Check for halving variable in argument (e.g. mid - 1, mid + 1, mid)
                for n in ast.walk(arg):
                    if isinstance(n, ast.Name) and (n.id in halving_vars or "mid" in n.id.lower()):
                        is_halving = True
                        step = 2.0

                # Halving: n // 2, n / 2, mid - 1
                if isinstance(arg, ast.BinOp):
                    if isinstance(arg.op, (ast.FloorDiv, ast.Div, ast.RShift)):
                        is_halving = True
                        step = 2.0
                    elif isinstance(arg.op, ast.Sub):
                        is_subtraction = True
                        if isinstance(arg.right, ast.Constant) and isinstance(arg.right.value, (int, float)):
                            step = max(step, float(arg.right.value))
                    elif isinstance(arg.op, ast.Add):
                        is_addition_to_bound = True
                        if isinstance(arg.right, ast.Constant) and isinstance(arg.right.value, (int, float)):
                            step = max(step, float(arg.right.value))

                # Slicing: arr[:mid], arr[mid:] -> halving; arr[1:] -> linear decrement
                elif isinstance(arg, ast.Subscript) and isinstance(arg.slice, ast.Slice):
                    sl = arg.slice
                    is_slice_half = False
                    for slice_bound in (sl.lower, sl.upper):
                        if slice_bound is not None:
                            if isinstance(slice_bound, ast.Name) and ("mid" in slice_bound.id.lower() or slice_bound.id in halving_vars):
                                is_slice_half = True
                            elif isinstance(slice_bound, ast.BinOp) and isinstance(slice_bound.op, (ast.FloorDiv, ast.Div, ast.RShift)):
                                is_slice_half = True

                    if is_slice_half:
                        is_halving = True
                        step = 2.0
                    elif sl.lower is not None:
                        is_subtraction = True
                        step = 1.0

        # Check for multi-term decrement like fib(n-1) + fib(n-2) along the SAME execution path
        distinct_steps: Set[float] = set()
        for call in recursive_calls:
            for arg in call.args:
                if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Sub):
                    if isinstance(arg.right, ast.Constant) and isinstance(arg.right.value, (int, float)):
                        distinct_steps.add(float(arg.right.value))

        if worst_case_branches > 1 and len(distinct_steps) >= 2 and 1.0 in distinct_steps and 2.0 in distinct_steps:
            return "multi_term", 1.0

        if is_halving:
            return "divide_and_conquer", 2.0

        if is_subtraction or is_addition_to_bound:
            return "linear_decrement", step

        # Default linear decrement
        return "linear_decrement", 1.0

    def _inspect_leaf_and_output(
        self, func_node: ast.FunctionDef, param_names: List[str]
    ) -> Tuple[Optional[ComplexityClass], bool]:
        """Detects if base case or body copies/materializes output items (e.g. list(current))."""
        has_list_copy = False
        retains_all = False

        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                # Check list(current) or copy.copy(current)
                if isinstance(node.func, ast.Name) and node.func.id == "list":
                    has_list_copy = True
                elif isinstance(node.func, ast.Attribute) and node.func.attr == "copy":
                    has_list_copy = True
                elif isinstance(node.func, ast.Attribute) and node.func.attr == "append":
                    # result.append(...)
                    if isinstance(node.func.value, ast.Name) and "result" in node.func.value.id.lower():
                        retains_all = True
            elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
                # current[:] full slice copy
                if node.slice.lower is None and node.slice.upper is None:
                    has_list_copy = True

        leaf_work = ComplexityClass.linear("n") if has_list_copy else None
        return leaf_work, retains_all

    def _inspect_local_work(self, func_node: ast.FunctionDef) -> ComplexityClass:
        """Inspects non-recursive work per execution frame (e.g. loops or slicing)."""
        from app.analyzers.loop_analyzer import LoopAnalyzer
        loops = LoopAnalyzer().analyze(func_node, skip_nested_functions=True)
        if not loops:
            return ComplexityClass.constant()

        max_class = ComplexityClass.constant()
        for loop in loops:
            c = loop.compute_tree_complexity()
            max_class = ComplexityClass.dominant_of(max_class, c)
        return max_class

    def _inspect_recursive_local_allocations(
        self, func_node: ast.FunctionDef, func_name: str, module_node: Optional[ast.AST] = None
    ) -> Tuple[Optional[ComplexityClass], bool]:
        """Detects whether this recursive function allocates heap structures per frame,
        and whether those allocations are deleted/released before recursive call(s) without surviving aliases or escaping.
        """
        allocations: Dict[int, ComplexityClass] = {}
        alloc_metadata: Dict[int, AllocationInfo] = {}
        var_to_allocs: Dict[str, Set[int]] = {}
        escaped_allocs: Set[int] = set()
        next_alloc_id = 1

        shadowed_builtins, valid_sys, valid_sys_streams, is_redirected, is_uncertain = (
            self._collect_shadowed_builtins_and_sys(func_node, module_node)
        )

        for stmt in func_node.body:
            # 1. Explicit deletion: del x, y
            if isinstance(stmt, ast.Delete):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        var_to_allocs.pop(target.id, None)

            # 2. Assignment: target = value
            elif isinstance(stmt, ast.Assign):
                # Heap store: obj.attr = x or container[i] = x
                is_heap_store = any(isinstance(t, (ast.Attribute, ast.Subscript)) for t in stmt.targets)
                if is_heap_store:
                    for child in ast.walk(stmt.value):
                        if isinstance(child, ast.Name) and child.id in var_to_allocs:
                            escaped_allocs.update(var_to_allocs[child.id])
                else:
                    alloc_info = self._evaluate_allocation_node(stmt.value, func_name=func_name)
                    if alloc_info:
                        aid = next_alloc_id
                        next_alloc_id += 1
                        allocations[aid] = alloc_info.cost
                        alloc_metadata[aid] = alloc_info
                        for t in stmt.targets:
                            if isinstance(t, ast.Name):
                                var_to_allocs[t.id] = {aid}
                    elif isinstance(stmt.value, ast.Name) and stmt.value.id in var_to_allocs:
                        # Direct or chained aliasing: alias = source
                        src_allocs = set(var_to_allocs[stmt.value.id])
                        for t in stmt.targets:
                            if isinstance(t, ast.Name):
                                var_to_allocs[t.id] = set(src_allocs)
                    else:
                        # Reassignment to other value / None / literal
                        for t in stmt.targets:
                            if isinstance(t, ast.Name):
                                var_to_allocs.pop(t.id, None)

            # 3. Annotated assignment: target: Type = value
            elif isinstance(stmt, ast.AnnAssign) and stmt.value:
                if isinstance(stmt.target, (ast.Attribute, ast.Subscript)):
                    for child in ast.walk(stmt.value):
                        if isinstance(child, ast.Name) and child.id in var_to_allocs:
                            escaped_allocs.update(var_to_allocs[child.id])
                else:
                    alloc_info = self._evaluate_allocation_node(stmt.value, func_name=func_name)
                    if alloc_info and isinstance(stmt.target, ast.Name):
                        aid = next_alloc_id
                        next_alloc_id += 1
                        allocations[aid] = alloc_info.cost
                        alloc_metadata[aid] = alloc_info
                        var_to_allocs[stmt.target.id] = {aid}
                    elif isinstance(stmt.value, ast.Name) and stmt.value.id in var_to_allocs and isinstance(stmt.target, ast.Name):
                        var_to_allocs[stmt.target.id] = set(var_to_allocs[stmt.value.id])
                    elif isinstance(stmt.target, ast.Name):
                        var_to_allocs.pop(stmt.target.id, None)

            # 4. Global / Nonlocal
            elif isinstance(stmt, (ast.Global, ast.Nonlocal)):
                for name in stmt.names:
                    if name in var_to_allocs:
                        escaped_allocs.update(var_to_allocs[name])

            # 5. Method and external calls: container appends or unknown function invocations
            for child in ast.walk(stmt):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Attribute) and child.func.attr in ("append", "extend", "insert", "add", "update"):
                        for a in child.args:
                            if isinstance(a, ast.Name) and a.id in var_to_allocs:
                                escaped_allocs.update(var_to_allocs[a.id])
                    cname = ""
                    if isinstance(child.func, ast.Name):
                        cname = child.func.id
                    elif isinstance(child.func, ast.Attribute):
                        cname = child.func.attr

                    all_call_args = list(child.args) + [kw.value for kw in child.keywords if kw.arg != "file"]
                    if cname == func_name:
                        # Self-recursive call: passing an allocated object into the callee frame escapes
                        # the caller's local scope, retaining the object across the child frame's lifetime.
                        for a in all_call_args:
                            for sub in ast.walk(a):
                                if isinstance(sub, ast.Name) and sub.id in var_to_allocs:
                                    escaped_allocs.update(var_to_allocs[sub.id])
                    elif cname == "print":
                        if "print" in shadowed_builtins or is_uncertain:
                            # Locally or module-shadowed print function or uncertain built-ins escapes arguments
                            for a in all_call_args:
                                for sub in ast.walk(a):
                                    if isinstance(sub, ast.Name) and sub.id in var_to_allocs:
                                        escaped_allocs.update(var_to_allocs[sub.id])
                        else:
                            # Unshadowed built-in print:
                            # In Python, print(*args, file=stream) serializes objects to strings via str() / repr()
                            # and passes the resulting string to stream.write(s). The original container object itself
                            # is NOT passed to the stream writer and does not escape to the stream buffer.
                            # The original object ONLY escapes if evaluating __str__ / __repr__ executes arbitrary
                            # user code (i.e. not an exact built-in collection or contains non-primitive scalar elements).
                            for a in all_call_args:
                                for sub in ast.walk(a):
                                    if isinstance(sub, ast.Name) and sub.id in var_to_allocs:
                                        aids = var_to_allocs[sub.id]
                                        if any(
                                            not alloc_metadata[aid].is_exact_builtin
                                            or not alloc_metadata[aid].has_primitive_elements
                                            for aid in aids if aid in alloc_metadata
                                        ):
                                            escaped_allocs.update(aids)
                    elif cname in ("len", "id", "type"):
                        if cname in shadowed_builtins or is_uncertain:
                            # Locally or module-shadowed callable or uncertain built-ins escapes arguments
                            for a in all_call_args:
                                for sub in ast.walk(a):
                                    if isinstance(sub, ast.Name) and sub.id in var_to_allocs:
                                        escaped_allocs.update(var_to_allocs[sub.id])
                        elif cname == "len":
                            # Built-in len() is non-escaping ONLY on exact supported built-in collections
                            for a in all_call_args:
                                for sub in ast.walk(a):
                                    if isinstance(sub, ast.Name) and sub.id in var_to_allocs:
                                        aids = var_to_allocs[sub.id]
                                        if any(
                                            not alloc_metadata[aid].is_exact_builtin
                                            for aid in aids if aid in alloc_metadata
                                        ):
                                            escaped_allocs.update(aids)
                        else:
                            # id() and type() on unshadowed built-in are strictly non-escaping
                            pass
                    else:
                        # External or unresolved function/method invocation: conservatively treat arguments as escaped.
                        for a in all_call_args:
                            for sub in ast.walk(a):
                                if isinstance(sub, ast.Name) and sub.id in var_to_allocs:
                                    escaped_allocs.update(var_to_allocs[sub.id])

        # 6. Check all return and yield statements across branches for returned allocations (which escape into caller/cache)
        for node in ast.walk(func_node):
            if isinstance(node, ast.Return) and node.value:
                alloc_info = self._evaluate_allocation_node(node.value, func_name=func_name)
                if alloc_info:
                    aid = next_alloc_id
                    next_alloc_id += 1
                    allocations[aid] = alloc_info.cost
                    alloc_metadata[aid] = alloc_info
                    escaped_allocs.add(aid)
                for child in ast.walk(node.value):
                    if isinstance(child, ast.Name) and child.id in var_to_allocs:
                        escaped_allocs.update(var_to_allocs[child.id])
            elif isinstance(node, (ast.Yield, ast.YieldFrom)) and node.value:
                for child in ast.walk(node.value):
                    if isinstance(child, ast.Name) and child.id in var_to_allocs:
                        escaped_allocs.update(var_to_allocs[child.id])

        if not allocations:
            return None, False

        max_alloc = max(allocations.values(), key=lambda c: c.rank_score())

        # An allocation is released if and only if it has not escaped and no live variable references it
        all_released = True
        for aid in allocations:
            if aid in escaped_allocs:
                all_released = False
                break
            surviving = [v for v, aids in var_to_allocs.items() if aid in aids]
            if surviving:
                all_released = False
                break

        return max_alloc, all_released

    def _walk_local_scope(self, node: ast.AST):
        """Walks AST nodes in the current local scope without descending into nested function or class bodies.
        Comprehension generator targets are not yielded as local scope targets, but PEP 572 walrus
        expressions (NamedExpr) inside comprehensions are yielded as they bind in the enclosing scope.
        """
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node
            return

        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            yield node
            for gen in node.generators:
                yield from self._walk_local_scope(gen.iter)
                for if_clause in gen.ifs:
                    yield from self._walk_local_scope(if_clause)
            if isinstance(node, ast.DictComp):
                yield from self._walk_local_scope(node.key)
                yield from self._walk_local_scope(node.value)
            else:
                yield from self._walk_local_scope(node.elt)
            return

        yield node
        for child in ast.iter_child_nodes(node):
            yield from self._walk_local_scope(child)

    def _extract_all_target_names(self, node: Optional[ast.AST]) -> List[str]:
        names: List[str] = []
        if node is None:
            return names
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for elt in node.elts:
                names.extend(self._extract_all_target_names(elt))
        elif isinstance(node, ast.Starred):
            names.extend(self._extract_all_target_names(node.value))
        return names

    def _extract_pattern_targets(self, pattern: Optional[ast.AST]) -> List[str]:
        names: List[str] = []
        if pattern is None:
            return names
        pname = getattr(pattern, "name", None)
        if pname and isinstance(pname, str):
            names.append(pname)
        prest = getattr(pattern, "rest", None)
        if prest and isinstance(prest, str):
            names.append(prest)
        for child in ast.iter_child_nodes(pattern):
            names.extend(self._extract_pattern_targets(child))
        return names

    def _extract_targets_from_node(self, node: ast.AST) -> List[str]:
        targets: List[str] = []
        if isinstance(node, ast.Assign):
            for t in node.targets:
                targets.extend(self._extract_all_target_names(t))
        elif isinstance(node, ast.AnnAssign):
            targets.extend(self._extract_all_target_names(node.target))
        elif isinstance(node, ast.AugAssign):
            targets.extend(self._extract_all_target_names(node.target))
        elif isinstance(node, ast.For):
            targets.extend(self._extract_all_target_names(node.target))
        elif isinstance(node, ast.NamedExpr):
            targets.extend(self._extract_all_target_names(node.target))
        elif isinstance(node, ast.With):
            for item in node.items:
                if item.optional_vars:
                    targets.extend(self._extract_all_target_names(item.optional_vars))
        elif isinstance(node, ast.ExceptHandler):
            if node.name:
                targets.append(node.name)
        elif hasattr(ast, "Match") and isinstance(node, ast.Match):
            for case in node.cases:
                targets.extend(self._extract_pattern_targets(case.pattern))
        return targets

    def _collect_shadowed_builtins_and_sys(
        self, func_node: ast.FunctionDef, module_node: Optional[ast.AST] = None
    ) -> Tuple[Set[str], Set[str], Set[str], bool, bool]:
        """Collects shadowed built-in names (len, id, type, print), valid sys module aliases,
        valid directly imported stream bindings, stream redirection status, and environment uncertainty.
        """
        shadowed: Set[str] = set()
        valid_sys: Set[str] = {"sys"}
        valid_sys_streams: Set[str] = set()
        is_redirected: bool = False
        is_uncertain: bool = False

        builtins_tracked = ("len", "id", "type", "print")

        # 1. Inspect module-level imports and assignments if module AST is available
        if module_node and isinstance(module_node, ast.Module):
            for stmt in module_node.body:
                if isinstance(stmt, ast.Import):
                    for alias in stmt.names:
                        if alias.name == "sys":
                            if alias.asname:
                                valid_sys.add(alias.asname)
                                valid_sys.discard("sys")
                            else:
                                valid_sys.add("sys")
                        elif alias.asname == "sys":
                            valid_sys.discard("sys")
                        if alias.asname in builtins_tracked:
                            shadowed.add(alias.asname)
                        elif alias.name in builtins_tracked and not alias.asname:
                            shadowed.add(alias.name)
                elif isinstance(stmt, ast.ImportFrom):
                    if any(alias.name == "*" for alias in stmt.names):
                        is_uncertain = True
                    if stmt.module == "sys":
                        for alias in stmt.names:
                            bound = alias.asname or alias.name
                            if alias.name in ("stdout", "stderr"):
                                valid_sys_streams.add(bound)
                    for alias in stmt.names:
                        name_bound = alias.asname or alias.name
                        if name_bound in builtins_tracked:
                            shadowed.add(name_bound)
                        if name_bound in valid_sys:
                            valid_sys.discard(name_bound)
                        if name_bound in valid_sys_streams and (stmt.module != "sys" or alias.name not in ("stdout", "stderr")):
                            valid_sys_streams.discard(name_bound)
                elif isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                    targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                    for t in targets:
                        if (
                            isinstance(t, ast.Attribute)
                            and t.attr in ("stdout", "stderr")
                            and isinstance(t.value, ast.Name)
                            and t.value.id in valid_sys
                        ):
                            is_redirected = True
                            valid_sys_streams.discard(t.attr)
                    for target in self._extract_targets_from_node(stmt):
                        if target in builtins_tracked:
                            shadowed.add(target)
                        if target in valid_sys:
                            valid_sys.discard(target)
                        if target in valid_sys_streams:
                            valid_sys_streams.discard(target)
                elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if stmt.name in builtins_tracked:
                        shadowed.add(stmt.name)
                    if stmt.name in valid_sys:
                        valid_sys.discard(stmt.name)
                    if stmt.name in valid_sys_streams:
                        valid_sys_streams.discard(stmt.name)
                elif isinstance(stmt, ast.With):
                    for item in stmt.items:
                        if isinstance(item.context_expr, ast.Call):
                            call = item.context_expr
                            if (isinstance(call.func, ast.Name) and call.func.id in ("redirect_stdout", "redirect_stderr")) or (
                                isinstance(call.func, ast.Attribute) and call.func.attr in ("redirect_stdout", "redirect_stderr")
                            ):
                                is_redirected = True
                elif isinstance(stmt, ast.Delete):
                    for t in stmt.targets:
                        for name in self._extract_all_target_names(t):
                            valid_sys.discard(name)
                            valid_sys_streams.discard(name)

                # Dynamic mutations: setattr(sys, "stdout", ...) or globals()/locals() calls
                for node in ast.walk(stmt):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name):
                            if node.func.id in ("globals", "locals"):
                                is_uncertain = True
                            elif node.func.id == "setattr" and len(node.args) >= 2:
                                first, second = node.args[0], node.args[1]
                                if isinstance(first, ast.Name) and first.id in valid_sys:
                                    if isinstance(second, ast.Constant) and second.value in ("stdout", "stderr"):
                                        is_redirected = True
                                        valid_sys_streams.discard(str(second.value))

        # 2. Inspect function parameters
        for arg in (
            func_node.args.posonlyargs
            + func_node.args.args
            + ([func_node.args.vararg] if func_node.args.vararg else [])
            + func_node.args.kwonlyargs
            + ([func_node.args.kwarg] if func_node.args.kwarg else [])
        ):
            if arg and arg.arg:
                if arg.arg in builtins_tracked:
                    shadowed.add(arg.arg)
                if arg.arg in valid_sys:
                    valid_sys.discard(arg.arg)
                if arg.arg in valid_sys_streams:
                    valid_sys_streams.discard(arg.arg)

        # 3. Inspect local statements inside function body adhering strictly to lexical scoping
        for stmt in func_node.body:
            for child in self._walk_local_scope(stmt):
                if isinstance(child, ast.Import):
                    for alias in child.names:
                        if alias.name == "sys":
                            if alias.asname:
                                valid_sys.add(alias.asname)
                                valid_sys.discard("sys")
                            else:
                                valid_sys.add("sys")
                        elif alias.asname == "sys":
                            valid_sys.discard("sys")
                        if alias.asname in builtins_tracked:
                            shadowed.add(alias.asname)
                        elif alias.name in builtins_tracked and not alias.asname:
                            shadowed.add(alias.name)
                elif isinstance(child, ast.ImportFrom):
                    if any(alias.name == "*" for alias in child.names):
                        is_uncertain = True
                    if child.module == "sys":
                        for alias in child.names:
                            bound = alias.asname or alias.name
                            if alias.name in ("stdout", "stderr"):
                                valid_sys_streams.add(bound)
                    for alias in child.names:
                        name_bound = alias.asname or alias.name
                        if name_bound in builtins_tracked:
                            shadowed.add(name_bound)
                        if name_bound in valid_sys:
                            valid_sys.discard(name_bound)
                        if name_bound in valid_sys_streams and (child.module != "sys" or alias.name not in ("stdout", "stderr")):
                            valid_sys_streams.discard(name_bound)
                elif isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.For, ast.NamedExpr, ast.With, ast.ExceptHandler)) or (
                    hasattr(ast, "Match") and isinstance(child, ast.Match)
                ):
                    if isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                        targets = child.targets if isinstance(child, ast.Assign) else [child.target]
                        for t in targets:
                            if (
                                isinstance(t, ast.Attribute)
                                and t.attr in ("stdout", "stderr")
                                and isinstance(t.value, ast.Name)
                                and t.value.id in valid_sys
                            ):
                                is_redirected = True
                                valid_sys_streams.discard(t.attr)
                    for target in self._extract_targets_from_node(child):
                        if target in builtins_tracked:
                            shadowed.add(target)
                        if target in valid_sys:
                            valid_sys.discard(target)
                        if target in valid_sys_streams:
                            valid_sys_streams.discard(target)
                elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if child.name in builtins_tracked:
                        shadowed.add(child.name)
                    if child.name in valid_sys:
                        valid_sys.discard(child.name)
                    if child.name in valid_sys_streams:
                        valid_sys_streams.discard(child.name)
                elif isinstance(child, ast.With):
                    for item in child.items:
                        if isinstance(item.context_expr, ast.Call):
                            call = item.context_expr
                            if (isinstance(call.func, ast.Name) and call.func.id in ("redirect_stdout", "redirect_stderr")) or (
                                isinstance(call.func, ast.Attribute) and call.func.attr in ("redirect_stdout", "redirect_stderr")
                            ):
                                is_redirected = True
                elif isinstance(child, ast.Delete):
                    for t in child.targets:
                        for name in self._extract_all_target_names(t):
                            valid_sys.discard(name)
                            valid_sys_streams.discard(name)

                # Dynamic mutations: setattr or globals()/locals() calls inside function
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Name):
                        if child.func.id in ("globals", "locals"):
                            is_uncertain = True
                        elif child.func.id == "setattr" and len(child.args) >= 2:
                            first, second = child.args[0], child.args[1]
                            if isinstance(first, ast.Name) and first.id in valid_sys:
                                if isinstance(second, ast.Constant) and second.value in ("stdout", "stderr"):
                                    is_redirected = True
                                    valid_sys_streams.discard(str(second.value))

        if is_uncertain:
            shadowed.update(builtins_tracked)

        return shadowed, valid_sys, valid_sys_streams, is_redirected, is_uncertain

    def _evaluate_allocation_node(
        self, node: Optional[ast.AST], func_name: Optional[str] = None
    ) -> Optional[AllocationInfo]:
        if node is None:
            return None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            if isinstance(node.left, ast.List) or isinstance(node.right, ast.List):
                list_op = node.left if isinstance(node.left, ast.List) else node.right
                mult_operand = node.right if isinstance(node.left, ast.List) else node.left
                all_prims = all(isinstance(elt, ast.Constant) for elt in list_op.elts)
                if isinstance(mult_operand, ast.BinOp) and isinstance(mult_operand.op, ast.Mult):
                    return AllocationInfo(ComplexityClass.polynomial(2.0), is_exact_builtin=True, has_primitive_elements=all_prims)
                if isinstance(mult_operand, ast.Name):
                    return AllocationInfo(ComplexityClass.linear(mult_operand.id), is_exact_builtin=True, has_primitive_elements=all_prims)
                return AllocationInfo(ComplexityClass.linear(), is_exact_builtin=True, has_primitive_elements=all_prims)
        elif isinstance(node, ast.ListComp):
            has_custom_elt = isinstance(node.elt, ast.Call)
            if isinstance(node.elt, (ast.ListComp, ast.BinOp)):
                cost = ComplexityClass.polynomial(2.0)
            else:
                cost = ComplexityClass.linear()
            return AllocationInfo(cost, is_exact_builtin=True, has_primitive_elements=not has_custom_elt)
        elif isinstance(node, (ast.DictComp, ast.SetComp)):
            has_custom_elt = isinstance(node.value if isinstance(node, ast.DictComp) else node.elt, ast.Call)
            return AllocationInfo(ComplexityClass.linear(), is_exact_builtin=True, has_primitive_elements=not has_custom_elt)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if func_name and node.func.id == func_name:
                return None
            if node.func.id in ("list", "tuple", "dict", "set"):
                if node.args:
                    return AllocationInfo(ComplexityClass.linear(), is_exact_builtin=True, has_primitive_elements=True)
            elif node.func.id and node.func.id[0].isupper():
                # Custom object instantiation (e.g. CustomClass(), CustomList())
                return AllocationInfo(ComplexityClass.linear(), is_exact_builtin=False, has_primitive_elements=False)
        return None

    def _inspect_cache_payload_semantics(
        self, func_node: ast.FunctionDef, param_names: List[str], func_name: str
    ) -> Tuple[bool, bool, bool, bool, bool, Optional[ComplexityClass], Optional[ComplexityClass]]:
        """Inspects whether a memoized/cached function exhibits:
        - has_shared_argument: argument payload passed unmodified across recursive calls.
        - has_unique_argument_allocation: fresh argument payload allocated per recursive call/state.
        - has_shared_return_object: return value references a pre-existing/shared container payload.
        - has_fresh_return_allocation: return value allocates a fresh container per call/state.
        - has_cross_role_alias: argument and return payload reference the exact same underlying shared allocation.
        - argument_payload_class: complexity class of argument payload (if any).
        - return_payload_class: complexity class of return payload (if any).
        """
        local_alloc_vars: Dict[str, ComplexityClass] = {}
        for stmt in func_node.body:
            if isinstance(stmt, ast.Assign):
                alloc_info = self._evaluate_allocation_node(stmt.value, func_name=func_name)
                if alloc_info:
                    for t in stmt.targets:
                        if isinstance(t, ast.Name):
                            local_alloc_vars[t.id] = alloc_info.cost
                elif isinstance(stmt.value, ast.BinOp) and isinstance(stmt.value.op, (ast.Add, ast.Mult)):
                    for t in stmt.targets:
                        if isinstance(t, ast.Name):
                            local_alloc_vars[t.id] = ComplexityClass.linear("n")
            elif isinstance(stmt, ast.AnnAssign) and stmt.value:
                alloc_info = self._evaluate_allocation_node(stmt.value, func_name=func_name)
                if alloc_info and isinstance(stmt.target, ast.Name):
                    local_alloc_vars[stmt.target.id] = alloc_info.cost
                elif isinstance(stmt.value, ast.BinOp) and isinstance(stmt.value.op, (ast.Add, ast.Mult)) and isinstance(stmt.target, ast.Name):
                    local_alloc_vars[stmt.target.id] = ComplexityClass.linear("n")

        has_unique_argument_allocation = False
        has_shared_argument = False
        argument_payload_class: Optional[ComplexityClass] = None
        shared_arg_names: Set[str] = set()
        shared_ret_names: Set[str] = set()

        rec_calls = [
            n for n in ast.walk(func_node)
            if isinstance(n, ast.Call) and (
                (isinstance(n.func, ast.Name) and n.func.id == func_name)
                or (isinstance(n.func, ast.Attribute) and n.func.attr == func_name)
            )
        ]

        container_param_candidates = {
            p for p in param_names
            if any(kw in p.lower() for kw in ("shared", "arr", "lst", "items", "data", "nums", "seq", "values", "path", "grid", "matrix", "table", "tuple", "list"))
        }

        for rc in rec_calls:
            for a in rc.args:
                alloc_info = self._evaluate_allocation_node(a, func_name=func_name)
                if alloc_info:
                    has_unique_argument_allocation = True
                    argument_payload_class = ComplexityClass.dominant_of(argument_payload_class or ComplexityClass.constant(), alloc_info.cost)
                elif isinstance(a, ast.BinOp) and isinstance(a.op, (ast.Add, ast.Mult)):
                    has_unique_argument_allocation = True
                    argument_payload_class = ComplexityClass.dominant_of(argument_payload_class or ComplexityClass.constant(), ComplexityClass.linear("n"))
                elif isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id in ("list", "tuple", "set", "dict"):
                    if a.args:
                        has_unique_argument_allocation = True
                        argument_payload_class = ComplexityClass.dominant_of(argument_payload_class or ComplexityClass.constant(), ComplexityClass.linear("n"))
                elif isinstance(a, ast.Name) and a.id in local_alloc_vars:
                    has_unique_argument_allocation = True
                    cost = local_alloc_vars[a.id]
                    argument_payload_class = ComplexityClass.dominant_of(argument_payload_class or ComplexityClass.constant(), cost)

        if not has_unique_argument_allocation and container_param_candidates:
            for rc in rec_calls:
                for a in rc.args:
                    if isinstance(a, ast.Name) and a.id in container_param_candidates:
                        has_shared_argument = True
                        shared_arg_names.add(a.id)
                        argument_payload_class = ComplexityClass.linear("n")
                        break
                if has_shared_argument:
                    break

        has_fresh_return_allocation = False
        has_shared_return_object = False
        return_payload_class: Optional[ComplexityClass] = None

        for node in ast.walk(func_node):
            if isinstance(node, ast.Return) and node.value:
                val = node.value
                alloc_info = self._evaluate_allocation_node(val, func_name=func_name)
                if alloc_info:
                    has_fresh_return_allocation = True
                    return_payload_class = ComplexityClass.dominant_of(return_payload_class or ComplexityClass.constant(), alloc_info.cost)
                elif isinstance(val, ast.Name):
                    if val.id in local_alloc_vars:
                        has_fresh_return_allocation = True
                        cost = local_alloc_vars[val.id]
                        return_payload_class = ComplexityClass.dominant_of(return_payload_class or ComplexityClass.constant(), cost)
                    elif val.id in container_param_candidates or "shared" in val.id.lower() or any(kw in val.id.lower() for kw in ("result", "data", "table", "arr")):
                        has_shared_return_object = True
                        shared_ret_names.add(val.id)
                        return_payload_class = ComplexityClass.dominant_of(return_payload_class or ComplexityClass.constant(), ComplexityClass.linear("n"))

        has_cross_role_alias = bool(
            has_shared_argument and has_shared_return_object and (shared_arg_names & shared_ret_names)
        )

        return (
            has_shared_argument,
            has_unique_argument_allocation,
            has_shared_return_object,
            has_fresh_return_allocation,
            has_cross_role_alias,
            argument_payload_class,
            return_payload_class,
        )
