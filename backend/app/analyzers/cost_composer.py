import ast
from typing import Dict, Any, List, Optional, Set, Tuple

from app.analyzers.complexity_classes import ComplexityClass
from app.analyzers.function_index import FunctionInfo, FunctionIndex, BUILTIN_OPERATIONS
from app.analyzers.call_graph import CallGraph, CallSite, RecursionComponent
from app.analyzers.loop_analyzer import LoopAnalyzer, LoopInfo
from app.analyzers.recursion_analyzer import RecursionAnalyzer
from app.analyzers.recurrence_solver import RecurrenceRelation, RecurrenceSolver
from app.analyzers.operation_analyzer import OperationAnalyzer, OperationReport
from app.schemas.analysis import SpaceBreakdown, RecurrenceInfo


BUILTIN_COST_MODEL: Dict[str, ComplexityClass] = {
    "len": ComplexityClass.constant(),
    "range": ComplexityClass.constant(),
    "print": ComplexityClass.constant(),
    "abs": ComplexityClass.constant(),
    "round": ComplexityClass.constant(),
    "int": ComplexityClass.constant(),
    "float": ComplexityClass.constant(),
    "bool": ComplexityClass.constant(),
    "enumerate": ComplexityClass.constant(),
    "zip": ComplexityClass.constant(),
    "reversed": ComplexityClass.constant(),
    "min": ComplexityClass.linear(),
    "max": ComplexityClass.linear(),
    "sum": ComplexityClass.linear(),
    "all": ComplexityClass.linear(),
    "any": ComplexityClass.linear(),
    "sorted": ComplexityClass.linearithmic(),
    "list": ComplexityClass.linear(),
    "dict": ComplexityClass.linear(),
    "set": ComplexityClass.linear(),
    "tuple": ComplexityClass.linear(),
}

BUILTIN_METHOD_COST_MODEL: Dict[str, ComplexityClass] = {
    "append": ComplexityClass.constant(),
    "pop": ComplexityClass.constant(),
    "extend": ComplexityClass.linear(),
    "insert": ComplexityClass.linear(),
    "remove": ComplexityClass.linear(),
    "count": ComplexityClass.linear(),
    "index": ComplexityClass.linear(),
    "clear": ComplexityClass.constant(),
    "copy": ComplexityClass.linear(),
    "add": ComplexityClass.constant(),
    "discard": ComplexityClass.constant(),
    "update": ComplexityClass.linear(),
    "get": ComplexityClass.constant(),
    "keys": ComplexityClass.constant(),
    "values": ComplexityClass.constant(),
    "items": ComplexityClass.constant(),
}


class FunctionCost:
    """Detailed asymptotic cost breakdown for a single function or module scope."""

    def __init__(self, func_id: str, name: str):
        self.func_id = func_id
        self.name = name
        self.func_type: str = "function"
        self.time_complexity: ComplexityClass = ComplexityClass.constant()
        self.tight_bound: str = "Θ(1)"
        self.space_complexity: ComplexityClass = ComplexityClass.constant()
        self.space_breakdown: SpaceBreakdown = SpaceBreakdown()
        self.confidence: str = "HIGH"
        self.confidence_reasons: List[str] = []
        self.complexity_reasoning: str = ""
        self.detected_patterns: List[str] = []
        self.derivation_steps: List[str] = []
        self.loops: List[LoopInfo] = []
        self.recurrence_info: Optional[RecurrenceInfo] = None
        self.is_recursive: bool = False
        self.unresolved_calls: List[CallSite] = []
        self.limitations: List[str] = []
        self.reachable_callees: Set[str] = set()
        self.call_graph_complete: bool = True
        self.cost_model_complete: bool = True
        self.analysis_complete: bool = True
        self.analysis_status: str = "COMPLETE"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "func_id": self.func_id,
            "name": self.name,
            "func_type": self.func_type,
            "time_complexity": self.time_complexity.big_o,
            "tight_bound": self.tight_bound,
            "space_complexity": self.space_complexity.big_o,
            "confidence": self.confidence,
            "is_recursive": self.is_recursive,
            "reasoning": self.complexity_reasoning,
            "patterns": self.detected_patterns,
            "unresolved_calls": [c.to_dict() for c in self.unresolved_calls],
            "limitations": self.limitations,
            "loops_count": len(self.loops),
            "call_graph_complete": self.call_graph_complete,
            "cost_model_complete": self.cost_model_complete,
            "analysis_complete": self.analysis_complete,
            "analysis_status": self.analysis_status,
        }


class CostComposer:
    """Composes interprocedural computational costs across loops, helper calls, and recurrences."""

    def __init__(
        self,
        index: FunctionIndex,
        call_graph: CallGraph,
        loop_analyzer: LoopAnalyzer,
        recursion_analyzer: RecursionAnalyzer,
        operation_analyzer: OperationAnalyzer,
        loop_tree_evaluator: Optional[Any] = None,
    ):
        self.index = index
        self.call_graph = call_graph
        self.loop_analyzer = loop_analyzer
        self.recursion_analyzer = recursion_analyzer
        self.operation_analyzer = operation_analyzer
        self.loop_tree_evaluator = loop_tree_evaluator
        self.computed_costs: Dict[str, FunctionCost] = {}

    def compose_all(self):
        """Computes costs for all functions bottom-up through the call graph SCC DAG."""
        for scc in self.call_graph.sccs:
            if len(scc) == 1:
                func_id = scc[0]
                self._compute_single_function(func_id)
            else:
                self._compute_mutual_recursion_scc(scc)

        # Finally compute <module> level
        self._compute_single_function("<module>")

    def _compute_single_function(self, func_id: str):
        func_info = self.index.functions.get(func_id)
        if func_info is None:
            return

        cost = FunctionCost(func_id=func_id, name=func_info.name)
        cost.reachable_callees = self.call_graph.get_reachable_from(func_id) - {func_id}
        cost.func_type = (
            "async_generator"
            if func_info.is_async_generator
            else (
                "generator"
                if func_info.is_generator
                else ("async_function" if func_info.is_async else "function")
            )
        )

        # 1. Extract loops specific to this function/scope
        node_to_analyze = func_info.node
        loops = self.loop_analyzer.analyze(node_to_analyze, skip_nested_functions=True)
        cost.loops = loops

        # Analyze built-in operations, allocations, and loop-level patterns
        op_report = self.operation_analyzer.analyze(func_info.node)

        # 2. Check if this function is recursive (self-recursion)
        recurrence_rel: Optional[RecurrenceRelation] = None
        if func_id != "<module>" and isinstance(func_info.node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            rel = self.recursion_analyzer._analyze_function(func_info.node, func_info.name)
            if rel is not None:
                cost.is_recursive = True
                recurrence_rel = RecurrenceSolver.solve(rel)

        # 3. Evaluate loop costs with enclosing helper calls and built-in operations
        loop_class = ComplexityClass.constant()
        loop_reasons: List[str] = []
        if loops:
            loop_class, loop_reason_str = self._evaluate_loops_with_calls(func_id, loops, cost, op_report)
            if loop_reason_str:
                loop_reasons.append(loop_reason_str)
        else:
            # Check calls enclosed in comprehension loops even without ast.For/While
            for site in self.call_graph.call_sites:
                if site.caller_id == func_id and site.is_in_loop:
                    c_cost, is_complete, reason = self._resolve_call_site_cost(site)
                    if not is_complete:
                        cost.unresolved_calls.append(site)
                        cost.confidence = "LOW"
                        cost.cost_model_complete = False
                        cost.analysis_complete = False
                        cost.analysis_status = "PARTIAL"
                        cost.limitations.append(f"Enclosed loop call: {reason}")
                    else:
                        if c_cost > ComplexityClass.constant():
                            loop_depth = max(1, site.loop_depth)
                            multiplier = ComplexityClass.polynomial(float(loop_depth))
                            is_independent = any(ac.get("category") == "INDEPENDENT_INPUT_SIZE" for ac in site.arg_classifications)
                            if is_independent and c_cost.category == "linear":
                                scaled_cost = ComplexityClass.multi_variable("n*m")
                            else:
                                scaled_cost = ComplexityClass.multiply(multiplier, c_cost)
                            loop_class = ComplexityClass.dominant_of(loop_class, scaled_cost)
                            cost.detected_patterns.append(
                                f"Comprehension loop on line {site.lineno} invokes helper '{site.callee_name}' ({c_cost.big_o})"
                            )
                            loop_reasons.append(
                                f"Enclosed helper call '{site.callee_name}' ({c_cost.big_o}) inside comprehension of depth {loop_depth} "
                                f"scales total time to {scaled_cost.big_o}."
                            )

        # 4. Evaluate sequential (non-loop) call costs
        sequential_call_class = ComplexityClass.constant()
        for site in self.call_graph.call_sites:
            if site.caller_id == func_id and not site.is_in_loop:
                call_cost, is_complete, reason = self._resolve_call_site_cost(site)
                if not is_complete:
                    cost.unresolved_calls.append(site)
                    cost.confidence = "LOW"
                    cost.cost_model_complete = False
                    cost.analysis_complete = False
                    cost.analysis_status = "PARTIAL"
                    cost.limitations.append(reason)
                else:
                    sequential_call_class = ComplexityClass.dominant_of(sequential_call_class, call_cost)
                    if call_cost > ComplexityClass.constant():
                        cost.detected_patterns.append(f"Sequential call to '{site.callee_name}' ({call_cost.big_o})")

        # 5. Evaluate built-in operations (comprehensions, sorting, allocations) in this function
        builtin_class = ComplexityClass.constant()
        if op_report.has_sorting:
            builtin_class = ComplexityClass.dominant_of(builtin_class, ComplexityClass.linearithmic())
            cost.detected_patterns.append("Sorting operation (O(n log n))")

        if op_report.space_complexity_from_allocations in ("O(n)", "O(n²)"):
            alloc_time = ComplexityClass.from_big_o(op_report.space_complexity_from_allocations)
            builtin_class = ComplexityClass.dominant_of(builtin_class, alloc_time)
            cost.detected_patterns.append(f"Array allocation ({alloc_time.big_o})")

        # Check comprehensions directly in this function body
        comp_count = sum(1 for n in ast.walk(func_info.node) if isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp)))
        if comp_count > 0:
            builtin_class = ComplexityClass.dominant_of(builtin_class, ComplexityClass.linear())
            cost.detected_patterns.append(f"{comp_count} collection comprehension(s) (O(n))")

        # 6. Synthesize combined Time Complexity
        time_class = ComplexityClass.dominant_of(loop_class, sequential_call_class, builtin_class)
        reasoning_parts: List[str] = list(loop_reasons)

        # If recurrence exists, compose with iterative costs
        if recurrence_rel is not None:
            cost.recurrence_info = RecurrenceInfo(
                present=True,
                expression=recurrence_rel.recurrence_str,
                is_solved=recurrence_rel.is_solved,
                branching_factor=recurrence_rel.branching_factor,
                total_call_sites=recurrence_rel.total_call_sites,
                derivation_steps=recurrence_rel.derivation_steps,
            )
            rec_class = recurrence_rel.solved_complexity
            time_class = ComplexityClass.dominant_of(time_class, rec_class)
            cost.detected_patterns.append(f"Recursive function '{func_info.name}'")
            reasoning_parts.append(
                f"Extracted recurrence relation: {recurrence_rel.recurrence_str}. "
                + " ".join(recurrence_rel.derivation_steps)
            )

        if not reasoning_parts:
            if time_class.category == "constant":
                reasoning_parts.append(f"Scalar constant execution with no dominant loops or recursions ({time_class.big_o}).")
            else:
                reasoning_parts.append(f"Dominant computational cost derived as {time_class.big_o}.")

        cost.time_complexity = time_class
        cost.tight_bound = time_class.tight_bound
        cost.complexity_reasoning = " ".join(reasoning_parts)

        # Check unknown decorators
        if func_info.has_unknown_decorator:
            cost.confidence = "MEDIUM" if cost.confidence == "HIGH" else cost.confidence
            cost.limitations.append(
                f"Function '{func_info.name}' is wrapped with unknown decorator(s): {', '.join(func_info.decorators)}. "
                "Runtime execution wrapping cannot be statically determined without decorator source."
            )

        # 7. Space Complexity: Separation of auxiliary, retained output, and stack
        if recurrence_rel is not None:
            output_space = recurrence_rel.output_space_class.big_o
            aux_space = recurrence_rel.auxiliary_space_class.big_o
            stack_space = recurrence_rel.stack_depth_class.big_o
            total_retained = recurrence_rel.total_retained_space_class.big_o
            cost.space_complexity = ComplexityClass.from_big_o(total_retained)
            cost.space_breakdown = SpaceBreakdown(
                auxiliary=aux_space,
                recursion_stack=stack_space,
                output=output_space,
                total_retained=total_retained,
            )
            cost.confidence = recurrence_rel.confidence
            cost.confidence_reasons.extend(recurrence_rel.confidence_reasons)
        else:
            # 1. Local auxiliary space
            aux_class = ComplexityClass.constant()
            if op_report.space_complexity_from_allocations != "O(1)":
                aux_class = ComplexityClass.from_big_o(op_report.space_complexity_from_allocations)
                cost.detected_patterns.append(f"Auxiliary memory allocation: {aux_class.big_o}")

            # 2. Peak auxiliary space from callees (sequential calls do NOT multiply auxiliary space)
            for callee_id in cost.reachable_callees:
                callee_cost = self.computed_costs.get(callee_id)
                if callee_cost:
                    aux_class = ComplexityClass.dominant_of(aux_class, callee_cost.space_complexity)

            # 3. Retained output space (if caller collects callee results across loop iterations)
            retained_output_class = ComplexityClass.constant()
            if self._detect_retained_loop_appends(func_info.node) and loops:
                loop_multiplier = ComplexityClass.polynomial(float(len(loops)))
                for site in self.call_graph.call_sites:
                    if site.caller_id == func_id and site.is_in_loop and site.callee_id:
                        c_cost = self.computed_costs.get(site.callee_id)
                        if c_cost and c_cost.space_complexity > ComplexityClass.constant():
                            scaled_out = ComplexityClass.multiply(loop_multiplier, c_cost.space_complexity)
                            retained_output_class = ComplexityClass.dominant_of(retained_output_class, scaled_out)
                            cost.detected_patterns.append(f"Retained loop outputs: {retained_output_class.big_o}")

            # 4. Recursion stack from reachable callees
            rec_stack_class = ComplexityClass.constant()
            for callee_id in cost.reachable_callees:
                callee_cost = self.computed_costs.get(callee_id)
                if callee_cost and callee_cost.is_recursive:
                    rec_stack_class = ComplexityClass.dominant_of(rec_stack_class, ComplexityClass.linear())

            total_space = ComplexityClass.dominant_of(aux_class, retained_output_class, rec_stack_class)
            cost.space_complexity = total_space
            cost.space_breakdown = SpaceBreakdown(
                auxiliary=aux_class.big_o,
                recursion_stack=rec_stack_class.big_o,
                output=retained_output_class.big_o,
                total_retained=total_space.big_o,
            )

        self.computed_costs[func_id] = cost

    def _detect_retained_loop_appends(self, node: ast.AST) -> bool:
        """Detects if results from helper calls inside loops are collected into a persistent data structure."""
        for child in ast.walk(node):
            if isinstance(child, (ast.For, ast.While)):
                # Track variables assigned from calls inside loop to detect aliased outputs
                call_assigned_vars: Set[str] = set()
                for sub in ast.walk(child):
                    if isinstance(sub, ast.Assign) and isinstance(sub.value, ast.Call):
                        for t in sub.targets:
                            if isinstance(t, ast.Name):
                                call_assigned_vars.add(t.id)

                for sub in ast.walk(child):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                        if sub.func.attr in ("append", "extend", "add"):
                            for a in sub.args:
                                if isinstance(a, ast.Call):
                                    return True
                                if isinstance(a, ast.Name) and a.id in call_assigned_vars:
                                    return True
        return False

    def _compute_mutual_recursion_scc(self, scc: List[str]):
        """Evaluates an SCC containing multiple mutually recursive functions with argument and local work checking."""
        func_names = [self.index.functions[fid].name for fid in scc if fid in self.index.functions]

        # 1. Inspect cycle call sites and argument reductions
        total_cycle_calls = 0
        has_unknown_transformation = False
        step_total = 0.0

        for fid in scc:
            for site in self.call_graph.call_sites:
                if site.caller_id == fid and site.callee_id in scc:
                    total_cycle_calls += 1
                    if site.arg_classifications:
                        for ac in site.arg_classifications:
                            cat = ac.get("category")
                            if cat in ("DERIVED_SYMBOLIC_SIZE", "LOOP_VARIABLE_SIZE"):
                                step_total += 1.0
                            elif cat in ("SAME_INPUT_SIZE", "CONSTANT"):
                                pass
                            else:
                                has_unknown_transformation = True
                    else:
                        for desc in site.arg_descriptions:
                            if "reduced" in desc:
                                step_total += 1.0
                            elif "unknown" in desc:
                                has_unknown_transformation = True

        # 2. Check local work performed across functions in the cycle
        max_local_work = ComplexityClass.constant()
        for fid in scc:
            finfo = self.index.functions.get(fid)
            if finfo and isinstance(finfo.node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                loops = self.loop_analyzer.analyze(finfo.node, skip_nested_functions=True)
                for loop in loops:
                    tree_c = loop.compute_tree_complexity()
                    max_local_work = ComplexityClass.dominant_of(max_local_work, tree_c)

        if has_unknown_transformation or (step_total == 0 and total_cycle_calls > 0):
            # Cannot verify convergence or recurrence closed-form safely
            cycle_time = ComplexityClass.unsupported("Non-standard mutual recurrence")
            cycle_tight = "Unknown"
            cycle_reason = f"Mutual recursion cycle across ({', '.join(func_names)}) has unverified argument reduction; closed-form recurrence cannot be proven statically."
            cycle_conf = "UNSUPPORTED"
            is_solvable = False
        else:
            is_linear_cycle = total_cycle_calls <= len(scc)
            is_solvable = True
            if is_linear_cycle:
                if max_local_work.category == "constant":
                    cycle_time = ComplexityClass.linear()
                    cycle_tight = "Θ(n)"
                    cycle_reason = f"Mutual recursion cycle across ({', '.join(func_names)}) with linear state decrements: O(n)."
                    cycle_conf = "MEDIUM"
                elif max_local_work.category in ("linear", "polynomial"):
                    new_deg = max_local_work.poly_degree + 1.0
                    cycle_time = ComplexityClass.polynomial(new_deg)
                    cycle_tight = cycle_time.tight_bound
                    cycle_reason = f"Mutual recursion cycle across ({', '.join(func_names)}) with {max_local_work.big_o} local frame work: {cycle_time.big_o}."
                    cycle_conf = "MEDIUM"
                else:
                    cycle_time = ComplexityClass.multiply(ComplexityClass.linear(), max_local_work)
                    cycle_tight = cycle_time.tight_bound
                    cycle_reason = f"Mutual recursion cycle across ({', '.join(func_names)}) with {max_local_work.big_o} frame work: {cycle_time.big_o}."
                    cycle_conf = "MEDIUM"
            else:
                cycle_time = ComplexityClass.exponential(2.0)
                cycle_tight = "O(2^n)"
                cycle_reason = f"Mutual recursion cycle across ({', '.join(func_names)}) with multiple branching paths: worst-case O(2^n)."
                cycle_conf = "LOW"

        for fid in scc:
            finfo = self.index.functions.get(fid)
            if not finfo:
                continue
            cost = FunctionCost(func_id=fid, name=finfo.name)
            cost.is_recursive = True
            cost.time_complexity = cycle_time
            cost.tight_bound = cycle_tight
            cost.space_complexity = ComplexityClass.linear()
            cost.space_breakdown = SpaceBreakdown(
                auxiliary="O(1)",
                recursion_stack="O(n)",
                output="O(1)",
                total_retained="O(n)",
            )
            cost.confidence = cycle_conf
            cost.complexity_reasoning = cycle_reason
            cost.detected_patterns.append(f"Mutual recursion in component ({', '.join(func_names)})")
            if not is_solvable:
                cost.cost_model_complete = False
                cost.analysis_complete = False
                cost.analysis_status = "UNSUPPORTED"
                cost.limitations.append("Mutual recursion recurrence could not be mapped to supported closed form.")
            self.computed_costs[fid] = cost

    def _evaluate_loops_with_calls(
        self,
        func_id: str,
        loops: List[LoopInfo],
        cost: FunctionCost,
        op_report: Optional[OperationReport] = None,
    ) -> Tuple[ComplexityClass, str]:
        """Evaluates loops within a function, multiplying loop bounds by enclosed helper call costs."""
        if self.loop_tree_evaluator is not None:
            base_class, base_reason, base_patterns, base_conf, base_evidence = self.loop_tree_evaluator(loops)
            cost.detected_patterns.extend(base_patterns)
            cost.confidence_reasons.extend(base_evidence)
            if base_conf != "HIGH" and cost.confidence == "HIGH":
                cost.confidence = base_conf

            max_combined = base_class

            # Operations inside loop (linear search, quadratic insert, slicing, copying)
            if op_report is not None:
                if op_report.has_linear_search_in_loop:
                    max_combined = ComplexityClass.dominant_of(max_combined, ComplexityClass.polynomial(2.0))
                    cost.detected_patterns.append("Linear search / membership check inside loop (O(n²))")
                if op_report.has_slice_in_loop:
                    max_combined = ComplexityClass.dominant_of(max_combined, ComplexityClass.polynomial(2.0))
                    cost.detected_patterns.append("Container slicing inside loop (O(n²))")
                if op_report.has_copy_in_loop:
                    max_combined = ComplexityClass.dominant_of(max_combined, ComplexityClass.polynomial(2.0))
                    cost.detected_patterns.append("Container copy inside loop (O(n²))")
                if op_report.has_quadratic_insert:
                    max_combined = ComplexityClass.dominant_of(max_combined, ComplexityClass.polynomial(2.0))
                    cost.detected_patterns.append("List insert(0, ...) inside loop (O(n²))")
            reasoning_additions: List[str] = []
            for site in self.call_graph.call_sites:
                if site.caller_id == func_id and site.is_in_loop:
                    c_cost, is_complete, reason = self._resolve_call_site_cost(site)
                    if not is_complete:
                        cost.unresolved_calls.append(site)
                        cost.confidence = "LOW"
                        cost.cost_model_complete = False
                        cost.analysis_complete = False
                        cost.analysis_status = "PARTIAL"
                        cost.limitations.append(f"Enclosed loop call: {reason}")
                    else:
                        if c_cost > ComplexityClass.constant():
                            loop_depth = max(1, site.loop_depth)
                            multiplier = ComplexityClass.polynomial(float(loop_depth))

                            # Handle independent input sizes e.g. caller(n, items) calling helper(items)
                            is_independent = any(ac.get("category") == "INDEPENDENT_INPUT_SIZE" for ac in site.arg_classifications)
                            if is_independent and c_cost.category == "linear":
                                scaled_cost = ComplexityClass.multi_variable("n*m")
                            else:
                                scaled_cost = ComplexityClass.multiply(multiplier, c_cost)

                            max_combined = ComplexityClass.dominant_of(max_combined, scaled_cost)
                            cost.detected_patterns.append(
                                f"Loop on line {site.lineno} invokes helper '{site.callee_name}' ({c_cost.big_o})"
                            )
                            reasoning_additions.append(
                                f"Enclosed helper call '{site.callee_name}' ({c_cost.big_o}) inside loop of depth {loop_depth} "
                                f"multiplies iteration cost, scaling total time to {scaled_cost.big_o}."
                            )

            if reasoning_additions:
                overall_reason = f"{base_reason} " + " ".join(reasoning_additions)
            else:
                overall_reason = base_reason

            return max_combined, overall_reason

        # Fallback if loop_tree_evaluator is None
        loop_calls: Dict[int, List[CallSite]] = {}
        for site in self.call_graph.call_sites:
            if site.caller_id == func_id and site.is_in_loop:
                loop_calls.setdefault(site.lineno, []).append(site)

        max_loop_class = ComplexityClass.constant()
        reasoning_items: List[str] = []

        for loop in loops:
            l_class, l_reason = self._evaluate_single_loop_tree(loop, loop_calls, cost)
            max_loop_class = ComplexityClass.dominant_of(max_loop_class, l_class)
            if l_reason:
                reasoning_items.append(l_reason)

        if len(loops) > 1:
            cost.detected_patterns.append(f"{len(loops)} independent sequential loop blocks")
            overall_reason = (
                f"Detected {len(loops)} sequential loop blocks. In asymptotic analysis, "
                f"sequential blocks add: O(f(n)) + O(g(n)) = O(max(f(n), g(n))). "
                f"The dominant block determines the overall time complexity of {max_loop_class.big_o}. "
                + " ".join(reasoning_items)
            )
        else:
            overall_reason = " ".join(reasoning_items)

        return max_loop_class, overall_reason

    def _evaluate_single_loop_tree(
        self,
        loop: LoopInfo,
        loop_calls: Dict[int, List[CallSite]],
        cost: FunctionCost
    ) -> Tuple[ComplexityClass, str]:
        base_bound = ComplexityClass.from_big_o(loop.complexity_class)
        reasoning = loop.reasoning or f"Loop with bound {base_bound.big_o}."
        cost.detected_patterns.append(f"Loop bounded by {loop.bound_symbol}")

        # Check calls enclosed inside this loop level
        enclosed_call_class = ComplexityClass.constant()
        for lineno, sites in loop_calls.items():
            for site in sites:
                # Check if call is within this loop line range
                c_cost, is_complete, reason = self._resolve_call_site_cost(site)
                if not is_complete:
                    cost.unresolved_calls.append(site)
                    cost.confidence = "LOW"
                    cost.limitations.append(f"Loop on line {loop.lineno} contains {reason}")
                else:
                    if c_cost > ComplexityClass.constant():
                        enclosed_call_class = ComplexityClass.dominant_of(enclosed_call_class, c_cost)
                        cost.detected_patterns.append(
                            f"Loop on line {loop.lineno} invokes helper '{site.callee_name}' ({c_cost.big_o})"
                        )
                        reasoning += (
                            f" Enclosed helper call '{site.callee_name}' adds {c_cost.big_o} per iteration, "
                            f"scaling total loop cost to {ComplexityClass.multiply(base_bound, c_cost).big_o}."
                        )

        # Child loops (nested loops)
        nested_class = ComplexityClass.constant()
        for child in loop.children:
            ch_class, ch_reason = self._evaluate_single_loop_tree(child, loop_calls, cost)
            nested_class = ComplexityClass.dominant_of(nested_class, ch_class)

        # Multiply loop bound by inner body work (either nested loop or enclosed call)
        inner_work = ComplexityClass.dominant_of(nested_class, enclosed_call_class)
        if inner_work > ComplexityClass.constant():
            total_loop_cost = ComplexityClass.multiply(base_bound, inner_work)
        else:
            total_loop_cost = base_bound

        return total_loop_cost, reasoning

    def _evaluate_nested_call_args(
        self, call_node: Optional[ast.Call]
    ) -> Tuple[ComplexityClass, bool, str]:
        """Evaluates computational cost of evaluating argument expressions at call site."""
        if not call_node or not call_node.args:
            return ComplexityClass.constant(), True, ""

        max_arg_cost = ComplexityClass.constant()
        for arg in call_node.args:
            for child in ast.walk(arg):
                if isinstance(child, ast.Call):
                    cname = ""
                    if isinstance(child.func, ast.Name):
                        cname = child.func.id
                    elif isinstance(child.func, ast.Attribute):
                        cname = child.func.attr

                    # Look up user function
                    found_cost = None
                    for fid, fcost in self.computed_costs.items():
                        if fcost.name == cname and fid != "<module>":
                            found_cost = fcost.time_complexity
                            break

                    if found_cost is not None:
                        max_arg_cost = ComplexityClass.dominant_of(max_arg_cost, found_cost)
                    elif cname in BUILTIN_COST_MODEL:
                        max_arg_cost = ComplexityClass.dominant_of(max_arg_cost, BUILTIN_COST_MODEL[cname])

        return max_arg_cost, True, f"Call arguments evaluated in {max_arg_cost.big_o}"

    @staticmethod
    def _extract_int_constant(node: ast.AST) -> Optional[int]:
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            if isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, int):
                return -node.operand.value
        return None

    def _resolve_container_method_cost(
        self, call_node: ast.Call, method_name: str
    ) -> Tuple[ComplexityClass, bool, str]:
        receiver_name = ""
        if isinstance(call_node.func, ast.Attribute) and isinstance(call_node.func.value, ast.Name):
            receiver_name = call_node.func.value.id

        if method_name == "pop":
            if call_node.args:
                val = self._extract_int_constant(call_node.args[0])
                if val == 0:
                    return ComplexityClass.linear(), True, f"list.pop(0) shifts elements requiring O(n) linear time on '{receiver_name}'"
                elif val == -1:
                    return ComplexityClass.constant(), True, f"list.pop(-1) removes last element in O(1) constant time on '{receiver_name}'"
                elif val is not None and val > 0:
                    return ComplexityClass.linear(), True, f"list.pop(k) shifts n-k elements requiring O(n-k) time on '{receiver_name}'"
                return ComplexityClass.linear(), True, f"list.pop(k) shifts following elements requiring O(n-k) time on '{receiver_name}'"
            return ComplexityClass.constant(), True, f"list.pop() removes last element in O(1) amortized time on '{receiver_name}'"

        if method_name == "insert":
            if call_node.args:
                idx = self._extract_int_constant(call_node.args[0])
                if idx == 0:
                    return ComplexityClass.linear(), True, f"list.insert(0, ...) shifts elements requiring O(n) time on '{receiver_name}'"
                elif idx == -1:
                    return ComplexityClass.constant(), True, f"list.insert(-1, ...) appends to end in O(1) amortized time on '{receiver_name}'"
                elif idx is not None:
                    return ComplexityClass.linear(), True, f"list.insert(k, ...) shifts n-k elements in O(n-k) time on '{receiver_name}'"
            return ComplexityClass.linear(), True, f"list.insert() shifts subsequent elements requiring O(n) time on '{receiver_name}'"

        if method_name in ("extend", "copy", "remove", "count", "index", "update"):
            return ComplexityClass.linear(), True, f"Container method '{method_name}' traverses elements in O(n) time on '{receiver_name}' (assuming standard built-in type)"

        if method_name in ("append", "add", "discard", "clear", "get", "keys", "values", "items"):
            return ComplexityClass.constant(), True, f"Container method '{method_name}' executes in O(1) amortized/average time on '{receiver_name}' (assuming standard hash/array distribution)"

        return ComplexityClass.constant(), False, f"Unknown method '{method_name}' on '{receiver_name}'"

    def _resolve_builtin_function_cost(
        self, site: CallSite
    ) -> Tuple[ComplexityClass, bool, str]:
        """Resolves built-in function calls under explicit, documented assumptions."""
        fname = site.callee_name
        call = site.call_node

        if fname == "print":
            has_container_arg = False
            if call and call.args:
                for arg in call.args:
                    if isinstance(arg, (ast.List, ast.Dict, ast.Set, ast.Tuple, ast.ListComp)):
                        has_container_arg = True
                    elif isinstance(arg, ast.Name):
                        if any(kw in arg.id.lower() for kw in ("arr", "list", "items", "matrix", "grid", "data")):
                            has_container_arg = True
            if has_container_arg:
                return ComplexityClass.linear(), True, "print() formatting and stream write proportional to container size O(n)"
            return ComplexityClass.constant(), True, "print() with scalar/constant arguments evaluates in O(1)"

        if fname == "len":
            return ComplexityClass.constant(), True, "len() on established built-in sized container is O(1) (assuming standard __len__)"

        if fname == "range":
            return ComplexityClass.constant(), True, "range() constructor returns iterator object in O(1) time and space"

        if fname in ("min", "max", "sum"):
            if call and call.args:
                arg = call.args[0]
                if isinstance(arg, (ast.GeneratorExp, ast.ListComp)):
                    elt_cost = ComplexityClass.constant()
                    for n in ast.walk(arg.elt):
                        if isinstance(n, ast.Call):
                            cname = n.func.id if isinstance(n.func, ast.Name) else (n.func.attr if isinstance(n.func, ast.Attribute) else "")
                            for fid, fcost in self.computed_costs.items():
                                if fcost.name == cname and fid != "<module>":
                                    elt_cost = ComplexityClass.dominant_of(elt_cost, fcost.time_complexity)
                    if elt_cost > ComplexityClass.constant():
                        total_cost = ComplexityClass.multiply(ComplexityClass.linear(), elt_cost)
                        return total_cost, True, f"{fname}() consuming generator yielding '{elt_cost.big_o}' elements in {total_cost.big_o}"
                    return ComplexityClass.linear(), True, f"{fname}() consuming comprehension/generator iterable in O(n)"
                if isinstance(arg, ast.Call):
                    nested_cname = arg.func.id if isinstance(arg.func, ast.Name) else "nested"
                    found_cost = None
                    for fid, fcost in self.computed_costs.items():
                        if fcost.name == nested_cname and fid != "<module>":
                            found_cost = fcost.time_complexity
                            break
                    if found_cost:
                        return ComplexityClass.dominant_of(ComplexityClass.linear(), found_cost), True, f"{fname}() over '{nested_cname}()' result"
            return ComplexityClass.linear(), True, f"Built-in '{fname}()' iterates over collection in O(n) time"

        if fname == "sorted":
            key_kw = None
            if call:
                for kw in call.keywords:
                    if kw.arg == "key":
                        key_kw = kw.value
            if key_kw is not None:
                key_name = ast.unparse(key_kw) if hasattr(ast, "unparse") else "key"
                if isinstance(key_kw, ast.Name):
                    found_cost = None
                    for fid, fcost in self.computed_costs.items():
                        if fcost.name == key_kw.id and fid != "<module>":
                            found_cost = fcost.time_complexity
                            break
                    if found_cost:
                        total = ComplexityClass.dominant_of(ComplexityClass.linearithmic(), ComplexityClass.multiply(ComplexityClass.linear(), found_cost))
                        return total, True, f"sorted() with key function '{key_name}' ({total.big_o})"
                    elif key_kw.id in BUILTIN_COST_MODEL:
                        return ComplexityClass.linearithmic(), True, f"sorted() with built-in key '{key_name}' in O(n log n)"
                    else:
                        return ComplexityClass.linearithmic(), False, f"sorted() with unresolved key function '{key_name}'"
            return ComplexityClass.linearithmic(), True, "sorted() Timsort worst-case O(n log n)"

        if fname in BUILTIN_COST_MODEL:
            return BUILTIN_COST_MODEL[fname], True, f"Built-in function '{fname}'"

        return ComplexityClass.constant(), False, f"Unknown built-in '{fname}'"

    def _resolve_call_site_cost(
        self, site: CallSite
    ) -> Tuple[ComplexityClass, bool, str]:
        """Resolves the asymptotic cost of a single call site."""
        if site.is_resolved and site.callee_id:
            callee_info = self.index.functions.get(site.callee_id)

            # Check generator deferred execution: creating a generator without consuming it is O(1)
            # BUT its call arguments are evaluated eagerly at call site!
            if callee_info and callee_info.is_generator:
                arg_work, _, _ = self._evaluate_nested_call_args(site.call_node)
                if not site.is_consumed_generator:
                    if arg_work > ComplexityClass.constant():
                        return arg_work, True, f"Generator '{site.callee_name}' unconsumed (body deferred), but call arguments evaluated in {arg_work.big_o}"
                    return ComplexityClass.constant(), True, f"Generator '{site.callee_name}' instantiated in O(1) without consumption (body execution deferred)"

            # Check coroutine unawaited creation: creating a coroutine object without awaiting it is O(1)
            # BUT its call arguments are evaluated eagerly at call site!
            if callee_info and callee_info.is_async:
                arg_work, _, _ = self._evaluate_nested_call_args(site.call_node)
                if not site.is_awaited:
                    if arg_work > ComplexityClass.constant():
                        return arg_work, True, f"Coroutine '{site.callee_name}' unawaited (body deferred), but call arguments evaluated in {arg_work.big_o}"
                    return ComplexityClass.constant(), True, f"Coroutine '{site.callee_name}' created in O(1) without await (asynchronous execution deferred)"

            # Check if all arguments are static constants
            if site.arg_classifications and all(a.get("category") == "CONSTANT" for a in site.arg_classifications):
                return ComplexityClass.constant(), True, "Constant argument call evaluates in O(1)"

            callee_cost = self.computed_costs.get(site.callee_id)
            if callee_cost:
                return callee_cost.time_complexity, True, f"Resolved to user function '{site.callee_name}'"
            return ComplexityClass.constant(), True, f"Self or mutual recursive call to '{site.callee_name}'"

        # Check known built-in functions
        if site.callee_name in BUILTIN_OPERATIONS or site.callee_name in BUILTIN_COST_MODEL:
            return self._resolve_builtin_function_cost(site)

        # Check known standard container methods (append, pop, insert, etc.)
        if site.call_node and isinstance(site.call_node.func, ast.Attribute):
            method_name = site.call_node.func.attr
            c_cost, is_valid, desc = self._resolve_container_method_cost(site.call_node, method_name)
            if is_valid:
                return c_cost, True, desc

        if site.callee_name in BUILTIN_METHOD_COST_MODEL:
            return BUILTIN_METHOD_COST_MODEL[site.callee_name], True, f"Standard container method '{site.callee_name}'"

        # Unresolved external call
        return ComplexityClass.constant(), False, f"unresolved external call '{site.callee_name}' on line {site.lineno}"
