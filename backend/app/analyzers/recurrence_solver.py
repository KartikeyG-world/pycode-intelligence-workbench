import math
from typing import Dict, Any, List, Optional
from app.analyzers.complexity_classes import ComplexityClass


class RecurrenceRelation:
    """Holds structural recurrence parameters, derivation steps, and solved complexities."""

    def __init__(
        self,
        func_name: str,
        branching_factor: int,
        total_call_sites: int,
        reduction_type: str,  # "linear_decrement", "divide_and_conquer", "multi_term", "in_loop", "memoized", "unknown"
        step_size: float = 1.0,
        local_work: Optional[ComplexityClass] = None,
        has_memoization: bool = False,
        state_space: Optional[str] = None,
        parameter_names: Optional[List[str]] = None,
        leaf_output_work: Optional[ComplexityClass] = None,
        retains_all_outputs: bool = False,
        recursion_inside_loop_size: Optional[str] = None,
        is_bounded_cache: bool = False,
        local_allocation_work: Optional[ComplexityClass] = None,
        allocation_released_before_recursion: bool = False,
        has_shared_argument: bool = False,
        has_unique_argument_allocation: bool = False,
        has_shared_return_object: bool = False,
        has_fresh_return_allocation: bool = False,
        argument_payload_class: Optional[ComplexityClass] = None,
        return_payload_class: Optional[ComplexityClass] = None,
    ):
        self.func_name = func_name
        self.branching_factor = branching_factor
        self.total_call_sites = total_call_sites
        self.reduction_type = reduction_type
        self.step_size = step_size
        self.local_work = local_work or ComplexityClass.constant()
        self.has_memoization = has_memoization
        self.state_space = state_space
        self.parameter_names = parameter_names or ["n"]
        self.leaf_output_work = leaf_output_work
        self.retains_all_outputs = retains_all_outputs
        self.recursion_inside_loop_size = recursion_inside_loop_size
        self.is_bounded_cache = is_bounded_cache
        self.local_allocation_work = local_allocation_work
        self.allocation_released_before_recursion = allocation_released_before_recursion
        self.has_shared_argument = has_shared_argument
        self.has_unique_argument_allocation = has_unique_argument_allocation
        self.has_shared_return_object = has_shared_return_object
        self.has_fresh_return_allocation = has_fresh_return_allocation
        self.argument_payload_class = argument_payload_class
        self.return_payload_class = return_payload_class

        # Output derivation artifacts
        self.is_solved: bool = False
        self.recurrence_str: str = ""
        self.traversal_complexity: ComplexityClass = ComplexityClass.constant()
        self.materialization_complexity: Optional[ComplexityClass] = None
        self.solved_complexity: ComplexityClass = ComplexityClass.constant()
        self.stack_depth_class: ComplexityClass = ComplexityClass.constant()
        self.auxiliary_space_class: ComplexityClass = ComplexityClass.constant()
        self.output_space_class: ComplexityClass = ComplexityClass.constant()
        self.total_retained_space_class: ComplexityClass = ComplexityClass.constant()
        self.peak_live_heap_class: ComplexityClass = ComplexityClass.constant()
        self.active_frames_class: ComplexityClass = ComplexityClass.constant()
        self.cache_retained_class: ComplexityClass = ComplexityClass.constant()
        self.derivation_steps: List[str] = []
        self.confidence: str = "HIGH"
        self.confidence_reasons: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "func_name": self.func_name,
            "branching_factor": self.branching_factor,
            "total_call_sites": self.total_call_sites,
            "reduction_type": self.reduction_type,
            "step_size": self.step_size,
            "recurrence_expression": self.recurrence_str,
            "is_solved": self.is_solved,
            "solved_time": self.solved_complexity.big_o,
            "tight_bound": self.solved_complexity.tight_bound,
            "stack_depth": self.stack_depth_class.big_o,
            "auxiliary_space": self.auxiliary_space_class.big_o,
            "output_space": self.output_space_class.big_o,
            "total_retained_space": self.total_retained_space_class.big_o,
            "peak_live_heap": self.peak_live_heap_class.big_o,
            "active_frames": self.active_frames_class.big_o,
            "cache_retained": self.cache_retained_class.big_o,
            "confidence": self.confidence,
            "derivation_steps": self.derivation_steps,
            "confidence_reasons": self.confidence_reasons,
        }


class RecurrenceSolver:
    """Symbolic recurrence solver applying closed-form analysis, recursion trees, and Master Theorem."""

    @classmethod
    def solve(cls, rel: RecurrenceRelation) -> RecurrenceRelation:
        var = "n"
        if rel.parameter_names:
            first_p = rel.parameter_names[0]
            if first_p in ("m", "k", "W"):
                var = first_p
            elif first_p != "n" and len(rel.parameter_names) == 1 and first_p.lower() not in ("arr", "lst", "nums", "items", "data", "values"):
                var = first_p

        # 1. Memoized Recursion
        if rel.has_memoization:
            cls._solve_memoized(rel, var)
            return rel

        # 2. Recursive call inside a loop -> T(n) = n * T(n-1) => O(n!)
        if rel.reduction_type == "in_loop":
            cls._solve_in_loop(rel, var)
            return rel

        # 3. Multi-term decrement: T(n) = T(n-1) + T(n-2) + ...
        if rel.reduction_type == "multi_term":
            cls._solve_multi_term(rel, var)
            return rel

        # 4. Divide-and-Conquer: T(n) = a T(n / c) + f(n)
        if rel.reduction_type == "divide_and_conquer":
            cls._solve_divide_and_conquer(rel, var)
            return rel

        # 5. Linear decrement: T(n) = a T(n - b) + f(n)
        if rel.reduction_type == "linear_decrement":
            cls._solve_linear_decrement(rel, var)
            return rel

        # 6. Fallback / Unsupported recurrence
        rel.is_solved = False
        rel.recurrence_str = f"T({var}) = {rel.branching_factor}T(...) + f({var})"
        rel.solved_complexity = ComplexityClass.unsupported("Non-standard recurrence relation")
        rel.confidence = "UNSUPPORTED"
        rel.derivation_steps = [
            f"Recursive structure detected for function '{rel.func_name}'.",
            "Recurrence relation could not be safely mapped to a supported symbolic closed form.",
            "In accordance with rigorous static analysis principles, exact asymptotic bound is reported as Unsupported.",
        ]
        rel.confidence_reasons = ["Complex recurrence parameters cannot be proven statically without dynamic bounds."]
        return rel

    @classmethod
    def _solve_linear_decrement(cls, rel: RecurrenceRelation, var: str):
        a = rel.branching_factor
        b = int(rel.step_size) if rel.step_size.is_integer() else rel.step_size
        local_work_str = "Θ(1)" if rel.local_work.category == "constant" else rel.local_work.tight_bound
        rel.recurrence_str = f"T({var}) = {a if a > 1 else ''}T({var} - {b}) + {local_work_str}"

        # Stack depth is n / b -> O(n)
        rel.stack_depth_class = ComplexityClass.linear(var)
        rel.active_frames_class = ComplexityClass.linear(var)

        # Peak simultaneously live heap
        if rel.local_allocation_work is not None and rel.local_allocation_work > ComplexityClass.constant():
            alloc = rel.local_allocation_work
            if rel.allocation_released_before_recursion:
                rel.peak_live_heap_class = alloc
                rel.auxiliary_space_class = ComplexityClass.dominant_of(rel.active_frames_class, alloc)
                rel.derivation_steps.append(
                    f"Frame allocates {alloc.big_o} heap memory, verified released before recursive invocation with no surviving aliases or escaped references. "
                    f"Peak live heap is bounded by a single frame ({alloc.big_o}). "
                    "(Note: static analysis evaluates reachability of unique live heap objects, not process RSS or operating-system page reclamation)."
                )
            else:
                if alloc.category == "linear":
                    accumulated_heap = ComplexityClass.polynomial(2.0, var)
                elif alloc.category == "polynomial":
                    accumulated_heap = ComplexityClass.polynomial(alloc.poly_degree + 1.0, var)
                else:
                    accumulated_heap = ComplexityClass.multiply(ComplexityClass.linear(var), alloc)
                rel.peak_live_heap_class = accumulated_heap
                rel.auxiliary_space_class = accumulated_heap
                rel.derivation_steps.append(
                    f"Each active recursive frame retains {alloc.big_o} heap memory across {var} levels without prior deallocation. "
                    f"Simultaneously live heap memory accumulates to {accumulated_heap.big_o}. "
                    "(Note: static analysis evaluates reachability of unique live heap objects, not process RSS or operating-system page reclamation)."
                )
        else:
            rel.peak_live_heap_class = ComplexityClass.constant()
            rel.auxiliary_space_class = rel.active_frames_class

        if a == 1:
            # Single linear recurrence: T(n) = T(n-b) + f(n)
            # If f(n) is constant -> Θ(n)
            # If f(n) is O(n) -> Θ(n²)
            if rel.local_work.category == "constant":
                rel.solved_complexity = ComplexityClass.linear(var)
                rel.traversal_complexity = ComplexityClass.linear(var)
            elif rel.local_work.category in ("linear", "polynomial"):
                new_deg = rel.local_work.poly_degree + 1.0
                rel.solved_complexity = ComplexityClass.polynomial(new_deg, var)
                rel.traversal_complexity = rel.solved_complexity
            else:
                rel.solved_complexity = ComplexityClass.multiply(ComplexityClass.linear(var), rel.local_work)
                rel.traversal_complexity = rel.solved_complexity

            rel.is_solved = True
            rel.confidence = "HIGH"
            rel.derivation_steps = [
                f"Extracted linear recurrence: {rel.recurrence_str}.",
                f"Execution path invokes exactly 1 recursive subproblem of size ({var} - {b}).",
                f"Recursion depth reaches {var}/{b} levels.",
                f"Local non-recursive work per level is {local_work_str}.",
                f"Summing over {var} levels yields {rel.solved_complexity.tight_bound}.",
            ]
            rel.confidence_reasons = [
                "Single recursive invocation per path verified by control-flow analysis.",
                f"Consistent linear decrement of parameter by {b}.",
            ]
            rel.output_space_class = ComplexityClass.constant()
            rel.total_retained_space_class = rel.auxiliary_space_class
            return

        # a >= 2: Branching linear decrement (Exponential)
        # e.g., T(n) = 2T(n-1) + O(1) -> Θ(2^n)
        # e.g., T(n) = 3T(n-1) + O(1) -> Θ(3^n)
        base = float(a) ** (1.0 / b)
        rel.traversal_complexity = ComplexityClass.exponential(base=base)
        rel.solved_complexity = rel.traversal_complexity

        rel.derivation_steps = [
            f"Extracted branching linear recurrence: {rel.recurrence_str}.",
            f"Each invocation branches into {a} recursive subproblems executing sequentially on the worst-case path.",
            f"Call tree has depth {var}/{b} and branching factor {a}.",
            f"Number of recursive calls grows as {a}^({var}/{b}) = {rel.traversal_complexity.tight_bound}.",
        ]

        # Check leaf output construction / materialization
        # In Power Set, each of the 2^n leaves copies a subset of size up to n: Θ(n * 2^n)
        if rel.leaf_output_work and rel.leaf_output_work.category != "constant":
            rel.materialization_complexity = ComplexityClass.multiply(rel.traversal_complexity, rel.leaf_output_work)
            rel.derivation_steps.append(
                f"Leaf operations construct/copy output collections of size {rel.leaf_output_work.tight_bound}. "
                f"Total materialization complexity is {rel.materialization_complexity.tight_bound}."
            )
            # The headline time is the materialization cost if dominant
            rel.solved_complexity = rel.materialization_complexity

        if rel.retains_all_outputs:
            # Retaining all subsets in a list -> output space Θ(n * 2^n) or Θ(2^n)
            leaf_size = rel.leaf_output_work or ComplexityClass.linear(var)
            rel.output_space_class = ComplexityClass.multiply(rel.traversal_complexity, leaf_size)
            rel.total_retained_space_class = rel.output_space_class
            rel.derivation_steps.append(
                f"All {rel.traversal_complexity.tight_bound} generated results are accumulated in memory, "
                f"requiring {rel.output_space_class.tight_bound} output storage."
            )
        else:
            rel.output_space_class = ComplexityClass.constant()
            rel.total_retained_space_class = rel.auxiliary_space_class

        rel.is_solved = True
        rel.confidence = "HIGH"
        rel.confidence_reasons = [
            f"Verified {a} sequential recursive calls per invocation on the worst-case control-flow path.",
            f"Linear parameter reduction step of {b}.",
            f"Closed-form recursion-tree evaluation: sum_(i=0)^({var}/{b}) {a}^i = Θ({base}^{var}).",
        ]

    @classmethod
    def _solve_multi_term(cls, rel: RecurrenceRelation, var: str):
        # e.g., T(n) = T(n-1) + T(n-2) + Θ(1)
        rel.recurrence_str = f"T({var}) = T({var} - 1) + T({var} - 2) + Θ(1)"
        rel.stack_depth_class = ComplexityClass.linear(var)
        rel.auxiliary_space_class = ComplexityClass.linear(var)
        # Golden ratio base approx 1.618, canonical exponential class O(2^n)
        rel.solved_complexity = ComplexityClass.exponential(base=2.0)
        rel.traversal_complexity = rel.solved_complexity
        rel.output_space_class = ComplexityClass.constant()
        rel.total_retained_space_class = rel.auxiliary_space_class
        rel.is_solved = True
        rel.confidence = "HIGH"
        rel.derivation_steps = [
            f"Extracted multi-term linear recurrence: {rel.recurrence_str}.",
            "Characteristic equation r² - r - 1 = 0 yields dominant root r = (1 + √5)/2 ≈ 1.618.",
            "Asymptotic growth is exponential in the O(2^n) complexity family with O(n) call stack depth.",
        ]
        rel.confidence_reasons = [
            "Distinct recursive calls decrementing by 1 and 2 respectively.",
            "Closed-form solution via characteristic roots.",
        ]

    @classmethod
    def _solve_divide_and_conquer(cls, rel: RecurrenceRelation, var: str):
        a = rel.branching_factor
        c = rel.step_size or 2.0  # subproblem size divisor
        c_int = int(c) if c.is_integer() else c

        local_work_str = "Θ(1)" if rel.local_work.category == "constant" else rel.local_work.tight_bound
        rel.recurrence_str = f"T({var}) = {a if a > 1 else ''}T({var} / {c_int}) + {local_work_str}"

        # Stack depth for divide and conquer is log_c(n) -> O(log n)
        rel.stack_depth_class = ComplexityClass.logarithmic()
        rel.auxiliary_space_class = ComplexityClass.logarithmic()

        # Master Theorem: compare p = log_c(a) with local work f(n) = n^d
        p = math.log(a, c) if (a > 0 and c > 1) else 0.0

        if a == 1 and rel.local_work.category == "constant":
            # T(n) = T(n/2) + 1 -> O(log n) (Binary search)
            rel.solved_complexity = ComplexityClass.logarithmic()
            rel.traversal_complexity = rel.solved_complexity
            rel.is_solved = True
            rel.confidence = "HIGH"
            rel.derivation_steps = [
                f"Extracted divide-and-conquer recurrence: {rel.recurrence_str}.",
                f"Single subproblem with size halved each step ({var} / {c_int}).",
                "Master Theorem Case 2 (p = 0, f(n) = Θ(1)): yields Θ(log n) time and Θ(log n) stack space.",
            ]
            rel.confidence_reasons = ["Subproblem size is halved at each recursion step with O(1) merge work."]
            return

        if a == 2 and rel.local_work.category == "constant":
            # T(n) = 2T(n/2) + 1 -> O(n)
            rel.solved_complexity = ComplexityClass.linear(var)
            rel.traversal_complexity = rel.solved_complexity
            rel.is_solved = True
            rel.confidence = "HIGH"
            rel.derivation_steps = [
                f"Extracted divide-and-conquer recurrence: {rel.recurrence_str}.",
                f"Two subproblems of size {var}/2 with constant O(1) local work.",
                "Master Theorem Case 1: p = log_2(2) = 1 > 0 => total time is dominated by leaves: Θ(n).",
            ]
            rel.confidence_reasons = ["Master Theorem Case 1: p = 1 dominates constant merge work."]
            return

        if a == 2 and rel.local_work.category == "linear":
            # T(n) = 2T(n/2) + n -> O(n log n) (Merge Sort)
            rel.solved_complexity = ComplexityClass.linearithmic(var)
            rel.traversal_complexity = rel.solved_complexity
            rel.auxiliary_space_class = ComplexityClass.linear(var)  # Merge buffer
            rel.total_retained_space_class = rel.auxiliary_space_class
            rel.is_solved = True
            rel.confidence = "HIGH"
            rel.derivation_steps = [
                f"Extracted divide-and-conquer recurrence: {rel.recurrence_str}.",
                f"Two subproblems of size {var}/2 combined with linear Θ({var}) merge work.",
                "Master Theorem Case 2: p = log_2(2) = 1 matches f(n) = Θ(n) => Θ(n log n) time.",
            ]
            rel.confidence_reasons = ["Master Theorem Case 2: p = 1 equals linear work per tree level."]
            return

        if a == 4 and rel.local_work.category == "constant":
            # T(n) = 4T(n/2) + 1 -> O(n^2)
            rel.solved_complexity = ComplexityClass.polynomial(2.0, var)
            rel.traversal_complexity = rel.solved_complexity
            rel.is_solved = True
            rel.confidence = "HIGH"
            rel.derivation_steps = [
                f"Extracted divide-and-conquer recurrence: {rel.recurrence_str}.",
                f"Four subproblems of size {var}/2 with constant local work.",
                "Master Theorem Case 1: p = log_2(4) = 2 => leaves dominate: Θ(n²).",
            ]
            rel.confidence_reasons = ["Master Theorem Case 1: p = 2 dominates constant work."]
            return

        if a == 4 and rel.local_work.category == "linear":
            # T(n) = 4T(n/2) + n -> O(n^2)
            rel.solved_complexity = ComplexityClass.polynomial(2.0, var)
            rel.traversal_complexity = rel.solved_complexity
            rel.is_solved = True
            rel.confidence = "HIGH"
            rel.derivation_steps = [
                f"Extracted divide-and-conquer recurrence: {rel.recurrence_str}.",
                f"Four subproblems of size {var}/2 with linear local work.",
                "Master Theorem Case 1: p = log_2(4) = 2 > d = 1 => leaves dominate: Θ(n²).",
            ]
            rel.confidence_reasons = ["Master Theorem Case 1: p = 2 dominates linear work."]
            return

        # General Master Theorem evaluation
        d = rel.local_work.poly_degree
        if p > d:
            rel.solved_complexity = ComplexityClass.polynomial(p, var)
        elif abs(p - d) < 1e-6:
            rel.solved_complexity = ComplexityClass.linearithmic(var) if p == 1 else ComplexityClass.polynomial(p, var)
        else:
            rel.solved_complexity = ComplexityClass.polynomial(d, var)

        rel.traversal_complexity = rel.solved_complexity
        rel.is_solved = True
        rel.confidence = "HIGH"
        rel.derivation_steps = [
            f"Extracted divide-and-conquer recurrence: {rel.recurrence_str}.",
            f"Master Theorem evaluation with log_{c_int}({a}) = {p:.2f} and local work degree {d}.",
            f"Derived asymptotic solution: {rel.solved_complexity.tight_bound}.",
        ]
        rel.confidence_reasons = ["Master Theorem criteria verified."]

    @classmethod
    def _solve_in_loop(cls, rel: RecurrenceRelation, var: str):
        # Recursion inside a loop of size n: T(n) = n * T(n-1) + O(1) => O(n!)
        loop_var = rel.recursion_inside_loop_size or var
        rel.recurrence_str = f"T({var}) = {loop_var} * T({var} - 1) + Θ(1)"
        rel.stack_depth_class = ComplexityClass.linear(var)
        rel.auxiliary_space_class = ComplexityClass.linear(var)
        rel.solved_complexity = ComplexityClass.factorial(var)
        rel.traversal_complexity = rel.solved_complexity
        rel.output_space_class = ComplexityClass.constant()
        rel.total_retained_space_class = rel.auxiliary_space_class
        rel.is_solved = True
        rel.confidence = "HIGH"
        rel.derivation_steps = [
            f"Extracted factorial recurrence: {rel.recurrence_str}.",
            f"Loop of size {loop_var} invokes recursive subproblem with decremented input size ({var} - 1).",
            "At depth k, the branching factor is (n - k), generating n * (n - 1) * ... * 1 = n! total leaf calls.",
            "Asymptotic time complexity is Θ(n!) with Θ(n) stack depth.",
        ]
        rel.confidence_reasons = [
            f"Loop bounding variable '{loop_var}' encloses recursive call.",
            "Factorial product expansion across n levels.",
        ]

    @classmethod
    def _solve_memoized(cls, rel: RecurrenceRelation, var: str):
        state_desc = rel.state_space or f"Θ({var})"
        rel.recurrence_str = f"T({var}) = {rel.branching_factor}T(...) with Memoization/Cache"
        rel.stack_depth_class = ComplexityClass.linear(var)
        rel.active_frames_class = ComplexityClass.linear(var)

        # Check multi-dimensional state space
        if state_desc.startswith("Θ(") and state_desc.endswith(")"):
            inner_expr = state_desc[2:-1].strip()
        else:
            inner_expr = state_desc.strip()

        if "min(" in state_desc:
            state_class = ComplexityClass.multi_variable(inner_expr)
        elif "*" in state_desc:
            state_class = ComplexityClass.multi_variable(inner_expr)
        elif "W" in state_desc:
            state_class = ComplexityClass.multi_variable(f"{var}*W")
        elif len(rel.parameter_names) >= 1:
            state_class = ComplexityClass.linear(rel.parameter_names[0])
        else:
            state_class = ComplexityClass.linear(var)

        # Distinguish state space cardinality from total execution time:
        # T_total = sum_{s in R} T_local(s) + T_transition/cache overhead
        if rel.local_work and rel.local_work > ComplexityClass.constant():
            rel.solved_complexity = ComplexityClass.multiply(state_class, rel.local_work)
            rel.traversal_complexity = rel.solved_complexity
        else:
            rel.solved_complexity = state_class
            rel.traversal_complexity = state_class

        # Check cache memory accounting:
        # A cache entry retains a mapping: key -> value.
        # Key structures retain:
        # 1. Unique argument payloads allocated per state: |R| * arg_payload (unbounded) or O(arg_payload) (bounded)
        # 2. Shared argument payloads: single shared object of size arg_payload (deduplicated across entries)
        # Value structures retain:
        # 3. Unique return payloads allocated per state: |R| * ret_payload (unbounded) or O(ret_payload) (bounded)
        # 4. Shared return objects: single shared object of size ret_payload (deduplicated across entries)
        # Table structure retains:
        # 5. Entry table overhead: |R| * O(1) = O(|R|) (unbounded) or O(1) (bounded)
        has_fresh_ret = rel.has_fresh_return_allocation
        has_shared_ret = rel.has_shared_return_object
        has_unique_arg = rel.has_unique_argument_allocation
        has_shared_arg = rel.has_shared_argument

        ret_payload = rel.return_payload_class
        arg_payload = rel.argument_payload_class

        if not ret_payload and rel.local_allocation_work and rel.local_allocation_work > ComplexityClass.constant():
            ret_payload = rel.local_allocation_work
            if not has_fresh_ret and not has_shared_ret and not has_unique_arg and not has_shared_arg:
                has_fresh_ret = True

        if rel.is_bounded_cache:
            # Bounded cache (fixed LRU capacity K = O(1) entries):
            # Entry count is O(1). Retained byte-memory is bounded by K * (arg_payload + ret_payload) + shared objects.
            retained_components: List[ComplexityClass] = [ComplexityClass.constant()]
            if has_unique_arg and arg_payload and arg_payload > ComplexityClass.constant():
                retained_components.append(arg_payload)
            if has_fresh_ret and ret_payload and ret_payload > ComplexityClass.constant():
                retained_components.append(ret_payload)
            if has_shared_arg and arg_payload and arg_payload > ComplexityClass.constant():
                retained_components.append(arg_payload)
            if has_shared_ret and ret_payload and ret_payload > ComplexityClass.constant():
                retained_components.append(ret_payload)

            combined_cache_mem = ComplexityClass.dominant_of(*retained_components)
            rel.cache_retained_class = combined_cache_mem
            rel.auxiliary_space_class = ComplexityClass.dominant_of(rel.active_frames_class, combined_cache_mem)
            rel.total_retained_space_class = rel.auxiliary_space_class
            entry_count_desc = "Bounded by fixed LRU capacity (O(1) entries)"
            b_qualifications: List[str] = ["fixed LRU capacity bounds table entry count to O(1)"]
            if has_unique_arg:
                b_qualifications.append(f"unique freshly allocated argument payload of size {arg_payload.big_o if arg_payload else 'O(1)'}")
            if has_fresh_ret:
                b_qualifications.append(f"unique freshly allocated return payload of size {ret_payload.big_o if ret_payload else 'O(1)'}")
            if has_shared_arg:
                b_qualifications.append(f"share references to external/passed argument payload of size {arg_payload.big_o if arg_payload else 'O(1)'}")
            if has_shared_ret:
                b_qualifications.append(f"store references to a shared return object of size {ret_payload.big_o if ret_payload else 'O(1)'}")
            mem_note = (
                f"Retained byte-memory: {combined_cache_mem.big_o} "
                f"(Note: {'; '.join(b_qualifications)}; retained byte-memory combines payload sizes retained across cached entries)."
            )
        else:
            # Unbounded cache: entry count is |R| = state_class
            retained_components: List[ComplexityClass] = [state_class]  # Table entry overhead |R| * O(1)

            if has_unique_arg and arg_payload and arg_payload > ComplexityClass.constant():
                m_unique_arg = ComplexityClass.multiply(state_class, arg_payload)
                retained_components.append(m_unique_arg)
            if has_fresh_ret and ret_payload and ret_payload > ComplexityClass.constant():
                m_fresh_ret = ComplexityClass.multiply(state_class, ret_payload)
                retained_components.append(m_fresh_ret)
            if has_shared_arg and arg_payload and arg_payload > ComplexityClass.constant():
                retained_components.append(arg_payload)  # Deduplicated: counted once on heap
            if has_shared_ret and ret_payload and ret_payload > ComplexityClass.constant():
                retained_components.append(ret_payload)  # Deduplicated: counted once on heap

            combined_cache_mem = ComplexityClass.dominant_of(*retained_components)
            rel.cache_retained_class = combined_cache_mem
            rel.auxiliary_space_class = ComplexityClass.dominant_of(rel.active_frames_class, combined_cache_mem)
            rel.total_retained_space_class = combined_cache_mem
            entry_count_desc = f"Bounded by reachable state count |R| = {state_desc} entries"
            u_qualifications: List[str] = [f"table entry overhead {state_class.big_o}"]
            if has_unique_arg:
                u_qualifications.append(f"unique freshly allocated argument payload of size {arg_payload.big_o if arg_payload else 'O(1)'} per entry accumulating to {m_unique_arg.big_o if 'm_unique_arg' in locals() else 'O(1)'}")
            if has_fresh_ret:
                u_qualifications.append(f"unique freshly allocated return payload of size {ret_payload.big_o if ret_payload else 'O(1)'} per entry accumulating to {m_fresh_ret.big_o if 'm_fresh_ret' in locals() else 'O(1)'}")
            if has_shared_arg:
                u_qualifications.append(f"share references to external/passed argument payload of size {arg_payload.big_o if arg_payload else 'O(1)'} deduplicated across entries")
            if has_shared_ret:
                u_qualifications.append(f"store references to a shared return object of size {ret_payload.big_o if ret_payload else 'O(1)'} deduplicated across entries")
            if not has_unique_arg and not has_fresh_ret and not has_shared_arg and not has_shared_ret:
                u_qualifications.append("scalar argument and return values")
            mem_note = (
                f"Retained byte-memory: {combined_cache_mem.big_o} "
                f"(Note: combines {'; '.join(u_qualifications)})."
            )

        rel.is_solved = True
        rel.confidence = "HIGH"
        local_work_str = "Θ(1)" if rel.local_work.category == "constant" else (rel.local_work.tight_bound if rel.local_work.tight_bound != "Unknown" else rel.local_work.big_o)
        rel.derivation_steps = [
            "Memoization table / cache detected for recursive state transitions.",
            f"State space cardinality is bounded by distinct reachable states: |R| = {state_desc}.",
            f"Local non-recursive work per state: T_local(s) = {local_work_str}.",
            f"Cache entry count: {entry_count_desc}. Each entry retains references to argument keys and computed return values.",
            mem_note,
            (
                "Each reachable state is computed at most once on cache miss; repeated calls or transitions to previously "
                "cached states resolve in expected O(1) cache lookup overhead (conditional on standard hash-table "
                "collision-free assumptions and primitive scalar key hashing and equality comparison under the unit-cost assumption "
                "for primitive integer keys; in the presence of adversarial hash collisions, worst-case dictionary lookup degrades "
                "toward O(|R|); compound or sequence keys of dimension k require O(k) hashing and equality comparison overhead)."
            ),
            f"Total execution time: T_total = sum_{{s in R}} T_local(s) + T_overhead = {rel.solved_complexity.tight_bound}.",
        ]
        rel.confidence_reasons = [
            "Cache lookup / assignment verified in AST.",
            f"State space cardinality bounded by {state_desc}.",
        ]
