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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "func_id": self.func_id,
            "name": self.name,
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

        # 1. Extract loops specific to this function/scope
        node_to_analyze = func_info.node
        loops = self.loop_analyzer.analyze(node_to_analyze, skip_nested_functions=True)
        cost.loops = loops

        # 2. Check if this function is recursive (self-recursion)
        recurrence_rel: Optional[RecurrenceRelation] = None
        if func_id != "<module>" and isinstance(func_info.node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            rel = self.recursion_analyzer._analyze_function(func_info.node, func_info.name)
            if rel is not None:
                cost.is_recursive = True
                recurrence_rel = RecurrenceSolver.solve(rel)

        # 3. Evaluate loop costs with enclosing helper calls
        loop_class = ComplexityClass.constant()
        loop_reasons: List[str] = []
        if loops:
            loop_class, loop_reason_str = self._evaluate_loops_with_calls(func_id, loops, cost)
            if loop_reason_str:
                loop_reasons.append(loop_reason_str)

        # 4. Evaluate sequential (non-loop) call costs
        sequential_call_class = ComplexityClass.constant()
        for site in self.call_graph.call_sites:
            if site.caller_id == func_id and not site.is_in_loop:
                call_cost, is_complete, reason = self._resolve_call_site_cost(site)
                if not is_complete:
                    cost.unresolved_calls.append(site)
                    cost.confidence = "MEDIUM" if cost.confidence != "LOW" else "LOW"
                    cost.limitations.append(reason)
                else:
                    sequential_call_class = ComplexityClass.dominant_of(sequential_call_class, call_cost)
                    if call_cost > ComplexityClass.constant():
                        cost.detected_patterns.append(f"Sequential call to '{site.callee_name}' ({call_cost.big_o})")

        # 5. Evaluate built-in operations (comprehensions, sorting) in this function
        op_report = self.operation_analyzer.analyze(func_info.node)
        builtin_class = ComplexityClass.constant()
        if op_report.has_sorting:
            builtin_class = ComplexityClass.dominant_of(builtin_class, ComplexityClass.linearithmic())
            cost.detected_patterns.append("Sorting operation (O(n log n))")

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

        # 7. Space Complexity
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
            space_class = ComplexityClass.constant()
            if op_report.space_complexity_from_allocations != "O(1)":
                space_class = ComplexityClass.from_big_o(op_report.space_complexity_from_allocations)
                cost.detected_patterns.append(f"Auxiliary memory allocation: {space_class.big_o}")

            rec_stack_class = ComplexityClass.constant()
            for callee_id in cost.reachable_callees:
                callee_cost = self.computed_costs.get(callee_id)
                if callee_cost and callee_cost.is_recursive:
                    rec_stack_class = ComplexityClass.dominant_of(rec_stack_class, ComplexityClass.linear())

            total_space = ComplexityClass.dominant_of(space_class, rec_stack_class)
            cost.space_complexity = total_space
            cost.space_breakdown = SpaceBreakdown(
                auxiliary=space_class.big_o,
                recursion_stack=rec_stack_class.big_o,
                output="O(1)",
                total_retained=total_space.big_o,
            )

        self.computed_costs[func_id] = cost

    def _compute_mutual_recursion_scc(self, scc: List[str]):
        """Evaluates an SCC containing multiple mutually recursive functions."""
        func_names = [self.index.functions[fid].name for fid in scc if fid in self.index.functions]
        # Inspect branching in the cycle
        total_cycle_calls = 0
        for fid in scc:
            for site in self.call_graph.call_sites:
                if site.caller_id == fid and site.callee_id in scc:
                    total_cycle_calls += 1

        is_linear_cycle = total_cycle_calls <= len(scc)
        if is_linear_cycle:
            cycle_time = ComplexityClass.linear()
            cycle_tight = "Θ(n)"
            cycle_reason = f"Mutual recursion cycle across ({', '.join(func_names)}) with linear state decrements: O(n)."
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
            self.computed_costs[fid] = cost

    def _evaluate_loops_with_calls(
        self,
        func_id: str,
        loops: List[LoopInfo],
        cost: FunctionCost
    ) -> Tuple[ComplexityClass, str]:
        """Evaluates loops within a function, multiplying loop bounds by enclosed helper call costs."""
        if self.loop_tree_evaluator is not None:
            base_class, base_reason, base_patterns, base_conf, base_evidence = self.loop_tree_evaluator(loops)
            cost.detected_patterns.extend(base_patterns)
            cost.confidence_reasons.extend(base_evidence)
            if base_conf != "HIGH" and cost.confidence == "HIGH":
                cost.confidence = base_conf

            max_combined = base_class
            reasoning_additions: List[str] = []
            for site in self.call_graph.call_sites:
                if site.caller_id == func_id and site.is_in_loop:
                    c_cost, is_complete, reason = self._resolve_call_site_cost(site)
                    if not is_complete:
                        cost.unresolved_calls.append(site)
                        cost.confidence = "LOW"
                        cost.limitations.append(f"Enclosed loop call: {reason}")
                    else:
                        if c_cost > ComplexityClass.constant():
                            loop_depth = max(1, site.loop_depth)
                            multiplier = ComplexityClass.polynomial(float(loop_depth))
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

    def _resolve_call_site_cost(
        self, site: CallSite
    ) -> Tuple[ComplexityClass, bool, str]:
        """Resolves the asymptotic cost of a single call site."""
        if site.is_resolved and site.callee_id:
            # Check if all arguments are static constants
            all_constants = bool(site.arg_descriptions and all(a.startswith("constant:") for a in site.arg_descriptions))
            if all_constants:
                return ComplexityClass.constant(), True, "Constant argument call evaluates in O(1)"

            callee_cost = self.computed_costs.get(site.callee_id)
            if callee_cost:
                return callee_cost.time_complexity, True, f"Resolved to user function '{site.callee_name}'"
            return ComplexityClass.constant(), True, f"Self or mutual recursive call to '{site.callee_name}'"

        # Check known built-ins
        if site.callee_name in BUILTIN_COST_MODEL:
            return BUILTIN_COST_MODEL[site.callee_name], True, f"Built-in function '{site.callee_name}'"

        # Check known standard container methods (append, pop, etc.)
        if site.callee_name in BUILTIN_METHOD_COST_MODEL:
            return BUILTIN_METHOD_COST_MODEL[site.callee_name], True, f"Standard container method '{site.callee_name}'"

        # Unresolved external call
        return ComplexityClass.constant(), False, f"unresolved external call '{site.callee_name}' on line {site.lineno}"
