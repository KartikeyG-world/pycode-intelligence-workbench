import math
import re
from typing import Dict, Any, Optional, Tuple, Set, List


class ComplexityClass:
    """Mathematical representation of asymptotic growth classes.

    Supports polynomial, logarithmic, exponential, factorial, and multi-variable forms.
    Provides canonical normalization and asymptotic dominance comparisons.
    """

    def __init__(
        self,
        category: str,  # "constant", "logarithmic", "linear", "linearithmic", "polynomial", "exponential", "factorial", "unsupported", "custom"
        poly_degree: float = 0.0,
        log_degree: float = 0.0,
        exp_base: float = 1.0,
        variables: Optional[Tuple[str, ...]] = None,
        is_tight: bool = True,
        custom_str: Optional[str] = None,
    ):
        self.category = category
        self.poly_degree = poly_degree
        self.log_degree = log_degree
        self.exp_base = exp_base
        self.variables = variables or ("n",)
        self.is_tight = is_tight
        self.custom_str = custom_str

    @classmethod
    def constant(cls) -> "ComplexityClass":
        return cls("constant", poly_degree=0.0, log_degree=0.0)

    @classmethod
    def logarithmic(cls, log_degree: float = 1.0) -> "ComplexityClass":
        return cls("logarithmic", poly_degree=0.0, log_degree=log_degree)

    @classmethod
    def linear(cls, var: str = "n") -> "ComplexityClass":
        return cls("linear", poly_degree=1.0, log_degree=0.0, variables=(var,))

    @classmethod
    def linearithmic(cls, var: str = "n") -> "ComplexityClass":
        return cls("linearithmic", poly_degree=1.0, log_degree=1.0, variables=(var,))

    @classmethod
    def polynomial(cls, degree: float, var: str = "n") -> "ComplexityClass":
        if degree == 0:
            return cls.constant()
        if degree == 1:
            return cls.linear(var)
        return cls("polynomial", poly_degree=degree, log_degree=0.0, variables=(var,))

    @classmethod
    def exponential(cls, base: float = 2.0, poly_factor: float = 0.0) -> "ComplexityClass":
        # Normalizes bases: e.g. base=2, poly_factor=0 -> O(2^n)
        return cls("exponential", poly_degree=poly_factor, exp_base=base)

    @classmethod
    def factorial(cls, var: str = "n") -> "ComplexityClass":
        return cls("factorial", variables=(var,))

    @classmethod
    def multi_variable(cls, desc: str) -> "ComplexityClass":
        return cls("custom", custom_str=desc)

    @classmethod
    def unsupported(cls, reason: str = "Unsupported recurrence") -> "ComplexityClass":
        return cls("unsupported", custom_str=f"Unsupported ({reason})", is_tight=False)

    @classmethod
    def unknown(cls, reason: str = "Unresolved operation") -> "ComplexityClass":
        custom = f"Unknown ({reason})" if reason != "Unresolved operation" else "Unknown"
        return cls("unknown", custom_str=custom, is_tight=False)

    @classmethod
    def from_big_o(cls, notation: str, is_tight: Optional[bool] = None) -> "ComplexityClass":
        clean = notation.strip()
        is_explicit_theta = clean.startswith("Θ(") or clean.startswith("Theta(")
        if clean.startswith("O(") and clean.endswith(")"):
            inner = clean[2:-1].strip()
            tight = False if is_tight is None else is_tight
        elif is_explicit_theta and clean.endswith(")"):
            inner = clean[clean.index("(") + 1 : -1].strip()
            tight = True if is_tight is None else is_tight
        else:
            inner = clean
            tight = True if is_tight is None else is_tight

        if inner == "1":
            return cls("constant", poly_degree=0.0, log_degree=0.0, is_tight=tight)
        if inner in ("log n", "log(n)"):
            return cls("logarithmic", poly_degree=0.0, log_degree=1.0, is_tight=tight)
        if inner == "n":
            return cls("linear", poly_degree=1.0, is_tight=tight)
        if inner in ("n log n", "n log(n)", "n*log(n)", "n*log n"):
            return cls("linearithmic", poly_degree=1.0, log_degree=1.0, is_tight=tight)
        if inner in ("n²", "n^2"):
            return cls("polynomial", poly_degree=2.0, is_tight=tight)
        if "log" in inner and ("n²" in inner or "n^2" in inner):
            return cls("polynomial", poly_degree=2.0, log_degree=1.0, is_tight=tight)
        if inner in ("n³", "n^3"):
            return cls("polynomial", poly_degree=3.0, is_tight=tight)
        if "log" in inner and ("n³" in inner or "n^3" in inner):
            return cls("polynomial", poly_degree=3.0, log_degree=1.0, is_tight=tight)
        if inner in ("n⁴", "n^4"):
            return cls("polynomial", poly_degree=4.0, is_tight=tight)
        if " + " in inner:
            terms = [cls.from_big_o(f"O({t.strip()})", is_tight=tight) for t in inner.split("+")]
            all_v = tuple(sorted(set.union(*[set(cls._get_class_vars(t)) for t in terms])))
            return cls("custom", custom_str=inner, variables=all_v, is_tight=tight)
        m_poly = re.match(r"^([a-zA-Z])(?:\^(\d+)|([²³⁴⁵]))$", inner)
        if m_poly:
            var_name = m_poly.group(1)
            deg_val = float(m_poly.group(2)) if m_poly.group(2) else {"²": 2.0, "³": 3.0, "⁴": 4.0, "⁵": 5.0}[m_poly.group(3)]
            return cls("polynomial", poly_degree=deg_val, variables=(var_name,), is_tight=tight)
        if re.match(r"^[a-zA-Z]$", inner):
            return cls("linear", poly_degree=1.0, variables=(inner,), is_tight=tight)
        if inner in ("2^n", "2ⁿ"):
            return cls("exponential", exp_base=2.0, is_tight=tight)
        if inner in ("3^n", "3ⁿ"):
            return cls("exponential", exp_base=3.0, is_tight=tight)
        if inner in ("n!",):
            return cls("factorial", is_tight=tight)
        if "Unsupported" in inner:
            return cls.unsupported()
        if "Unknown" in inner:
            return cls.unknown(inner)
        all_v = tuple(sorted(cls._extract_monomial_exponents(inner).keys()))
        return cls("custom", custom_str=inner, variables=all_v or ("n",), is_tight=tight)

    @property
    def big_o(self) -> str:
        """Returns standard Big-O notation, e.g. O(2^n)."""
        expr = self._raw_expression()
        if expr.startswith("Unsupported"):
            return "Unsupported / Cannot Determine"
        if expr.startswith("Unknown"):
            return expr
        return f"O({expr})"

    @property
    def tight_bound(self) -> str:
        """Returns tight bound notation Θ(...) or 'Unknown' if loose/upper-bound only."""
        expr = self._raw_expression()
        if expr.startswith("Unsupported") or expr.startswith("Unknown"):
            return "Unknown"
        if not self.is_tight:
            return "Unknown"
        return f"Θ({expr})"

    def _raw_expression(self) -> str:
        if self.custom_str:
            return self.custom_str

        var = self.variables[0] if self.variables else "n"

        if self.category == "constant":
            return "1"

        if self.category == "logarithmic":
            if self.log_degree == 1.0:
                return f"log {var}"
            return f"log^{int(self.log_degree) if self.log_degree.is_integer() else self.log_degree} {var}"

        if self.category == "linear":
            return var

        if self.category == "linearithmic":
            return f"{var} log {var}"

        if self.category == "polynomial":
            deg = int(self.poly_degree) if self.poly_degree.is_integer() else self.poly_degree
            base = f"{var}²" if deg == 2 else (f"{var}³" if deg == 3 else f"{var}^{deg}")
            if self.log_degree > 0:
                log_str = f"log {var}" if self.log_degree == 1.0 else f"log^{int(self.log_degree)} {var}"
                return f"{base} {log_str}"
            return base

        if self.category == "exponential":
            b = int(self.exp_base) if self.exp_base.is_integer() else round(self.exp_base, 2)
            base_str = f"{b}^{var}"
            if self.poly_degree > 0:
                p_deg = int(self.poly_degree) if self.poly_degree.is_integer() else self.poly_degree
                p_str = var if p_deg == 1 else f"{var}^{p_deg}"
                return f"{p_str} * {base_str}"
            return base_str

        if self.category == "factorial":
            return f"{var}!"

        return "n"

    def rank_score(self) -> float:
        """Numerical ranking to evaluate dominance in sums max(f(n), g(n))."""
        if self.category == "unknown":
            return -1.0
        if self.category == "constant":
            return 0.0
        if self.category == "logarithmic":
            return 1.0 * self.log_degree
        if self.category == "linear":
            return 10.0
        if self.category == "linearithmic":
            return 15.0
        if self.category == "polynomial":
            return 10.0 * self.poly_degree + 2.0 * self.log_degree
        if self.category == "custom":
            raw = self._raw_expression()
            if "+" in raw:
                terms = raw.split("+")
                return max(ComplexityClass.from_big_o(f"O({t.strip()})").rank_score() for t in terms)
            deg = 1.0
            if "*" in raw:
                deg = float(len(raw.split("*")))
            if "³" in raw or "^3" in raw:
                deg += 2.0
            elif "²" in raw or "^2" in raw:
                deg += 1.0
            return 10.0 * max(1.0, deg)
        if self.category == "exponential":
            # 2^n -> 100, 3^n -> 150, etc.
            return 100.0 * math.log2(max(1.5, self.exp_base)) + 5.0 * self.poly_degree
        if self.category == "factorial":
            return 1000.0
        return 10.0

    def __lt__(self, other: "ComplexityClass") -> bool:
        return self.rank_score() < other.rank_score()

    def __le__(self, other: "ComplexityClass") -> bool:
        return self.rank_score() <= other.rank_score()

    def __gt__(self, other: "ComplexityClass") -> bool:
        return self.rank_score() > other.rank_score()

    def __ge__(self, other: "ComplexityClass") -> bool:
        return self.rank_score() >= other.rank_score()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ComplexityClass):
            return False
        return self.big_o == other.big_o

    @classmethod
    def _extract_monomial_exponents(cls, s: str) -> Dict[str, float]:
        sup_map = {"²": 2.0, "³": 3.0, "⁴": 4.0, "⁵": 5.0}
        clean = re.sub(r"\blog\b(?:\s*\([^\)]*\)|\s+[a-zA-Z])?", "", s).strip()
        exps: Dict[str, float] = {}
        for var, p_num, p_sup in re.findall(r"([a-zA-Z])(?:\^(\d+(?:\.\d+)?)|([²³⁴⁵⁶⁷⁸⁹]))?", clean):
            if var in ("O", "Θ", "Theta"):
                continue
            deg = float(p_num) if p_num else (sup_map.get(p_sup, 1.0) if p_sup else 1.0)
            exps[var] = exps.get(var, 0.0) + deg
        return exps

    @classmethod
    def _get_class_vars(cls, c: "ComplexityClass") -> Set[str]:
        if c.category == "constant":
            return set()
        raw = c._raw_expression()
        exps = cls._extract_monomial_exponents(raw)
        if exps:
            return set(exps.keys())
        if c.category != "custom" and c.variables:
            return set(c.variables)
        return set(c.variables) if c.variables else {"n"}

    @classmethod
    def _monomial_dominates(cls, c_b: "ComplexityClass", c_a: "ComplexityClass") -> bool:
        """Determines whether monomial/class B component-wise dominates monomial/class A
        over all independent variables v in vars(A) U vars(B).
        """
        if c_a.category == "constant":
            return True
        if c_b.category == "constant":
            return False

        hier = {"constant": 0, "logarithmic": 1, "linear": 2, "linearithmic": 3, "polynomial": 4, "exponential": 5, "factorial": 6}
        cat_a = c_a.category if c_a.category != "custom" else "polynomial"
        cat_b = c_b.category if c_b.category != "custom" else "polynomial"
        vars_a = cls._get_class_vars(c_a)
        vars_b = cls._get_class_vars(c_b)

        if hier.get(cat_b, 4) > hier.get(cat_a, 4) and (not vars_a or vars_a == vars_b or vars_a.issubset(vars_b)):
            return True
        if hier.get(cat_a, 4) > hier.get(cat_b, 4) and (not vars_b or vars_b == vars_a or vars_b.issubset(vars_a)):
            return False

        exp_a = cls._extract_monomial_exponents(c_a._raw_expression())
        exp_b = cls._extract_monomial_exponents(c_b._raw_expression())
        vars_all = set(exp_a.keys()) | set(exp_b.keys())
        if not vars_all:
            return c_b.rank_score() >= c_a.rank_score()

        # Unparameterized dummy placeholder 'n' subsumed by multi-variable expression of >= degree
        if set(exp_a.keys()) == {"n"} and len(exp_b.keys()) >= 2:
            if sum(exp_b.values()) >= sum(exp_a.values()):
                return True

        # Component-wise dominance: for every independent variable v, exp_b(v) >= exp_a(v)
        if all(exp_b.get(v, 0.0) >= exp_a.get(v, 0.0) for v in vars_all):
            if all(exp_b.get(v, 0.0) == exp_a.get(v, 0.0) for v in vars_all):
                return c_b.log_degree >= c_a.log_degree
            return True

        return False

    @classmethod
    def _scale_var_in_expression(cls, c: "ComplexityClass", var: str, add_deg: int) -> "ComplexityClass":
        raw = c._raw_expression()
        all_vars = tuple(sorted(set(cls._get_class_vars(c)) | {var}))
        m = re.search(rf"\b{var}(?:²|³|\^(\d+))?\b", raw)
        cur_deg = 1
        if m:
            matched = m.group(0)
            if "²" in matched:
                cur_deg = 2
            elif "³" in matched:
                cur_deg = 3
            elif m.group(1):
                cur_deg = int(m.group(1))
            new_deg = cur_deg + add_deg
            rep = f"{var}²" if new_deg == 2 else (f"{var}³" if new_deg == 3 else f"{var}^{new_deg}")
            new_raw = raw[:m.start()] + rep + raw[m.end():]
            return cls("custom", custom_str=new_raw, variables=all_vars)
        return cls.multi_variable(f"{var}*{raw}")

    @classmethod
    def dominant_of(cls, *classes: "ComplexityClass") -> "ComplexityClass":
        valid = [c for c in classes if c.category not in ("unsupported", "unknown")]
        if not valid:
            return classes[0] if classes else cls.unsupported()

        non_constants = [c for c in valid if c.category != "constant"]
        if not non_constants:
            return cls.constant()
        if len(non_constants) == 1:
            return non_constants[0]

        # Decompose any sum expressions into atomic constituent terms
        atomic_terms: List["ComplexityClass"] = []
        for c in non_constants:
            raw = c._raw_expression()
            if " + " in raw:
                for sub in raw.split("+"):
                    clean_sub = sub.strip()
                    if clean_sub:
                        atomic_terms.append(cls.from_big_o(f"O({clean_sub})", is_tight=c.is_tight))
            else:
                atomic_terms.append(c)

        # Component-wise Pareto dominance: eliminate any term dominated by another
        surviving: List["ComplexityClass"] = []
        for i, cand in enumerate(atomic_terms):
            subsumed = False
            for j, other in enumerate(atomic_terms):
                if i == j:
                    continue
                if cls._monomial_dominates(other, cand):
                    # If mutually dominant (equivalent), keep only one (smaller index)
                    if cls._monomial_dominates(cand, other):
                        if j < i:
                            subsumed = True
                            break
                    else:
                        subsumed = True
                        break
            if not subsumed:
                if not any(s.big_o == cand.big_o for s in surviving):
                    surviving.append(cand)

        if len(surviving) == 1:
            return surviving[0]

        # Incomparable independent dimensions: sort deterministically and join with " + "
        def _sort_key(c: "ComplexityClass") -> Tuple[float, float, str]:
            exp = cls._extract_monomial_exponents(c._raw_expression())
            n_deg = exp.get("n", -1.0)
            tot_deg = sum(exp.values())
            return (-n_deg, -tot_deg, c._raw_expression())

        sorted_survivors = sorted(surviving, key=_sort_key)
        expr_terms = [c._raw_expression() for c in sorted_survivors]
        all_vars = tuple(sorted(set.union(*[cls._get_class_vars(c) for c in sorted_survivors])))
        combined_expr = " + ".join(expr_terms)
        tight = all(c.is_tight for c in sorted_survivors)
        return cls("custom", custom_str=combined_expr, variables=all_vars, is_tight=tight)

    @classmethod
    def multiply(cls, c1: "ComplexityClass", c2: "ComplexityClass") -> "ComplexityClass":
        """Symbolically multiplies two complexities: e.g. O(n) * O(n) = O(n²), O(n) * O(2^n) = O(n * 2^n)."""
        if c1.category == "constant":
            return c2
        if c2.category == "constant":
            return c1

        vars1 = cls._get_class_vars(c1)
        vars2 = cls._get_class_vars(c2)

        # 1. Distinct independent variables:
        if vars1 and vars2 and vars1 != vars2:
            raw1 = c1._raw_expression()
            raw2 = c2._raw_expression()
            # If one is a single variable already present in the other:
            if len(vars2) == 1 and list(vars2)[0] in raw1 and not ("min(" in raw1 or "max(" in raw1):
                ovar = list(vars2)[0]
                p_deg = int(c2.poly_degree) if c2.category in ("linear", "polynomial") else 1
                return cls._scale_var_in_expression(c1, ovar, p_deg)
            if len(vars1) == 1 and list(vars1)[0] in raw2 and not ("min(" in raw2 or "max(" in raw2):
                ovar = list(vars1)[0]
                p_deg = int(c1.poly_degree) if c1.category in ("linear", "polynomial") else 1
                return cls._scale_var_in_expression(c2, ovar, p_deg)
            # Truly disjoint variables: e.g. {n} and {m}
            all_vars = tuple(sorted(vars1 | vars2))
            if len(vars2) == 1 and len(vars1) > 1:
                return cls.multi_variable(f"{raw2}*{raw1}")
            return cls.multi_variable(f"{raw1}*{raw2}")

        # 2. Same variables (e.g. both 'n'):
        # Exponential * Polynomial -> Exponential with poly factor
        if c1.category == "exponential" and c2.category in ("linear", "polynomial"):
            new_poly = c1.poly_degree + c2.poly_degree
            return cls.exponential(base=c1.exp_base, poly_factor=new_poly)
        if c2.category == "exponential" and c1.category in ("linear", "polynomial"):
            new_poly = c2.poly_degree + c1.poly_degree
            return cls.exponential(base=c2.exp_base, poly_factor=new_poly)

        # Linear/Polynomial * Linearithmic: O(n) * O(n log n) = O(n² log n)
        if c1.category in ("linear", "polynomial") and c2.category == "linearithmic":
            new_poly = c1.poly_degree + c2.poly_degree
            new_log = c1.log_degree + c2.log_degree
            return cls("polynomial", poly_degree=new_poly, log_degree=new_log, variables=c1.variables)
        if c2.category in ("linear", "polynomial") and c1.category == "linearithmic":
            new_poly = c2.poly_degree + c1.poly_degree
            new_log = c2.log_degree + c1.log_degree
            return cls("polynomial", poly_degree=new_poly, log_degree=new_log, variables=c2.variables)

        # Polynomial * Polynomial with same variable:
        if c1.category in ("linear", "polynomial") and c2.category in ("linear", "polynomial"):
            deg = c1.poly_degree + c2.poly_degree
            log_deg = c1.log_degree + c2.log_degree
            v = c1.variables[0] if c1.variables else "n"
            if log_deg > 0:
                return cls("polynomial", poly_degree=deg, log_degree=log_deg, variables=(v,))
            return cls.polynomial(deg, var=v)

        # Linear * Logarithmic -> Linearithmic
        if (c1.category == "linear" and c2.category == "logarithmic") or (c2.category == "linear" and c1.category == "logarithmic"):
            v = c1.variables[0] if c1.category == "linear" else (c2.variables[0] if c2.category == "linear" else "n")
            return cls.linearithmic(var=v)

        # Fallback to dominant or custom
        return cls.dominant_of(c1, c2)
