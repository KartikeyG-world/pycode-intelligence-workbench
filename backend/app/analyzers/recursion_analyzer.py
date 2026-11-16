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


class RecursionAnalyzer:
    """Extracts call sites, control-flow execution paths, argument transformations, and symbolic recurrences."""

    def analyze(self, tree: ast.AST) -> List[RecurrenceRelation]:
        results: List[RecurrenceRelation] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_name = node.name
                rel = self._analyze_function(node, func_name)
                if rel is not None:
                    # Solve the extracted recurrence relation
                    solved_rel = RecurrenceSolver.solve(rel)
                    results.append(solved_rel)

        return results

    def _analyze_function(self, func_node: ast.FunctionDef, func_name: str) -> Optional[RecurrenceRelation]:
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
        local_alloc, alloc_released = self._inspect_recursive_local_allocations(func_node, func_name)

        # 9. Check cache payload semantics (shared vs unique argument/return allocations)
        has_shared_arg, has_unique_arg, has_shared_ret, has_fresh_ret, arg_payload, ret_payload = (
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
                    "trail", "history", "shared", "arr", "lst", "items", "data", "nums", "seq", "values", "tuple", "list"
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
        self, func_node: ast.FunctionDef, func_name: str
    ) -> Tuple[Optional[ComplexityClass], bool]:
        """Detects whether this recursive function allocates heap structures per frame,
        and whether those allocations are deleted/released before recursive call(s) without surviving aliases or escaping.
        """
        allocations: Dict[int, ComplexityClass] = {}
        var_to_allocs: Dict[str, Set[int]] = {}
        escaped_allocs: Set[int] = set()
        next_alloc_id = 1

        # Check parameter inputs that represent large container payloads (e.g. items, arr, data, values)
        for param in func_node.args.args:
            pname = param.arg
            if any(kw in pname.lower() for kw in ("arr", "lst", "items", "data", "matrix", "grid", "nums", "seq", "values")):
                aid = next_alloc_id
                next_alloc_id += 1
                allocations[aid] = ComplexityClass.linear("n")
                var_to_allocs.setdefault(pname, set()).add(aid)

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
                    alloc_cost = self._evaluate_allocation_node(stmt.value)
                    if alloc_cost:
                        aid = next_alloc_id
                        next_alloc_id += 1
                        allocations[aid] = alloc_cost
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
                    alloc_cost = self._evaluate_allocation_node(stmt.value)
                    if alloc_cost and isinstance(stmt.target, ast.Name):
                        aid = next_alloc_id
                        next_alloc_id += 1
                        allocations[aid] = alloc_cost
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
                        # print() is non-escaping for stdout / stderr, but if a custom file/stream writer
                        # is passed (e.g. print(temp, file=custom_writer)), references escape into that writer.
                        has_custom_stream = False
                        for kw in child.keywords:
                            if kw.arg == "file":
                                if isinstance(kw.value, ast.Constant) and kw.value.value is None:
                                    continue
                                if isinstance(kw.value, ast.Attribute) and kw.value.attr in ("stdout", "stderr"):
                                    continue
                                has_custom_stream = True
                        if has_custom_stream:
                            for a in all_call_args:
                                for sub in ast.walk(a):
                                    if isinstance(sub, ast.Name) and sub.id in var_to_allocs:
                                        escaped_allocs.update(var_to_allocs[sub.id])
                    elif cname in ("len", "id", "type"):
                        # Whitelisted non-escaping operations under the assumption of unshadowed built-in
                        # functions operating on built-in collections (list, dict, set). These inspect
                        # internal metadata (e.g. ob_size, pointer address, ob_type) without retaining references.
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
                alloc_cost = self._evaluate_allocation_node(node.value)
                if alloc_cost:
                    aid = next_alloc_id
                    next_alloc_id += 1
                    allocations[aid] = alloc_cost
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

    def _evaluate_allocation_node(self, node: Optional[ast.AST]) -> Optional[ComplexityClass]:
        if node is None:
            return None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            if isinstance(node.left, ast.List) or isinstance(node.right, ast.List):
                mult_operand = node.right if isinstance(node.left, ast.List) else node.left
                if isinstance(mult_operand, ast.BinOp) and isinstance(mult_operand.op, ast.Mult):
                    return ComplexityClass.polynomial(2.0)
                return ComplexityClass.linear()
        elif isinstance(node, ast.ListComp):
            if isinstance(node.elt, (ast.ListComp, ast.BinOp)):
                return ComplexityClass.polynomial(2.0)
            return ComplexityClass.linear()
        elif isinstance(node, (ast.DictComp, ast.SetComp)):
            return ComplexityClass.linear()
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("list", "tuple", "dict", "set"):
            if node.args:
                return ComplexityClass.linear()
        return None

    def _inspect_cache_payload_semantics(
        self, func_node: ast.FunctionDef, param_names: List[str], func_name: str
    ) -> Tuple[bool, bool, bool, bool, Optional[ComplexityClass], Optional[ComplexityClass]]:
        """Inspects whether a memoized/cached function exhibits:
        - has_shared_argument: argument payload passed unmodified across recursive calls.
        - has_unique_argument_allocation: fresh argument payload allocated per recursive call/state.
        - has_shared_return_object: return value references a pre-existing/shared container payload.
        - has_fresh_return_allocation: return value allocates a fresh container per call/state.
        - argument_payload_class: complexity class of argument payload (if any).
        - return_payload_class: complexity class of return payload (if any).
        """
        local_alloc_vars: Set[str] = set()
        for stmt in func_node.body:
            if isinstance(stmt, ast.Assign):
                is_alloc = self._evaluate_allocation_node(stmt.value) is not None
                if not is_alloc and isinstance(stmt.value, ast.BinOp) and isinstance(stmt.value.op, (ast.Add, ast.Mult)):
                    is_alloc = True
                if is_alloc:
                    for t in stmt.targets:
                        if isinstance(t, ast.Name):
                            local_alloc_vars.add(t.id)
            elif isinstance(stmt, ast.AnnAssign) and stmt.value:
                is_alloc = self._evaluate_allocation_node(stmt.value) is not None
                if not is_alloc and isinstance(stmt.value, ast.BinOp) and isinstance(stmt.value.op, (ast.Add, ast.Mult)):
                    is_alloc = True
                if is_alloc and isinstance(stmt.target, ast.Name):
                    local_alloc_vars.add(stmt.target.id)

        has_unique_argument_allocation = False
        has_shared_argument = False
        argument_payload_class: Optional[ComplexityClass] = None

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
                if isinstance(a, ast.BinOp) and isinstance(a.op, (ast.Add, ast.Mult)):
                    has_unique_argument_allocation = True
                    argument_payload_class = ComplexityClass.linear("n")
                elif isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id in ("list", "tuple", "set", "dict"):
                    if a.args:
                        has_unique_argument_allocation = True
                        argument_payload_class = ComplexityClass.linear("n")
                elif isinstance(a, ast.Name) and a.id in local_alloc_vars:
                    has_unique_argument_allocation = True
                    argument_payload_class = ComplexityClass.linear("n")

        if not has_unique_argument_allocation and container_param_candidates:
            for rc in rec_calls:
                for a in rc.args:
                    if isinstance(a, ast.Name) and a.id in container_param_candidates:
                        has_shared_argument = True
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
                alloc_cost = self._evaluate_allocation_node(val)
                if alloc_cost:
                    has_fresh_return_allocation = True
                    return_payload_class = alloc_cost
                elif isinstance(val, ast.Name):
                    if val.id in local_alloc_vars:
                        has_fresh_return_allocation = True
                        return_payload_class = ComplexityClass.linear("n")
                    elif val.id in container_param_candidates or "shared" in val.id.lower() or any(kw in val.id.lower() for kw in ("result", "data", "table", "arr")):
                        has_shared_return_object = True
                        return_payload_class = ComplexityClass.linear("n")

        if has_fresh_return_allocation:
            has_shared_return_object = False

        return (
            has_shared_argument,
            has_unique_argument_allocation,
            has_shared_return_object,
            has_fresh_return_allocation,
            argument_payload_class,
            return_payload_class,
        )
