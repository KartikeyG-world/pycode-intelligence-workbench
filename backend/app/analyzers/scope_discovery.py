"""
Canonical Scope Discovery Adapter for Phase 1B.2.

Produces a deterministic, authoritative inventory of all analysis scopes
(module, function, method, class_body) from the parsed AST.
Reuses FunctionIndex for procedural scope indexing and aligns with CFGBuilder.
"""

from dataclasses import dataclass
from typing import Literal, Optional, List, Set, Dict
import ast

from app.analyzers.function_index import FunctionIndex, FunctionInfo

PublicScopeType = Literal[
    "module",
    "function",
    "method",
    "class_body",
]


@dataclass(frozen=True)
class ScopeDefinition:
    """Canonical representation of an analysis scope within a Python AST."""
    scope_id: str
    name: str
    scope_type: PublicScopeType
    node: ast.AST
    lineno: Optional[int]
    end_lineno: Optional[int]
    parent_scope_id: Optional[str]


def discover_scopes(tree: ast.Module) -> List[ScopeDefinition]:
    """
    Discovers and returns all analysis scopes within a parsed Python module AST.

    Returns scopes in deterministic lexical preorder:
    1. Module scope (<module>) first.
    2. Enclosing scopes before nested child scopes.
    3. Sibling scopes in source appearance order.

    Public scope types are strictly: 'module', 'function', 'method', 'class_body'.
    Async syntax does not introduce separate public scope categories.
    """
    if not isinstance(tree, ast.Module):
        raise TypeError(f"Expected ast.Module instance, got {type(tree).__name__}")

    # 1. Reuse existing FunctionIndex for procedural scope discovery
    func_index = FunctionIndex.from_ast(tree)

    # Map original AST nodes to FunctionInfo (excluding the <module> entrypoint)
    node_to_func: Dict[ast.AST, FunctionInfo] = {
        func_info.node: func_info
        for func_id, func_info in func_index.functions.items()
        if func_id != "<module>"
    }

    scopes: List[ScopeDefinition] = []
    seen_ids: Set[str] = set()

    # 2. Add top-level Module Scope
    module_lineno = getattr(tree, "lineno", 1) or 1
    module_end_lineno = getattr(tree, "end_lineno", 1) or 1
    module_scope = ScopeDefinition(
        scope_id="<module>",
        name="<module>",
        scope_type="module",
        node=tree,
        lineno=module_lineno,
        end_lineno=module_end_lineno,
        parent_scope_id=None,
    )
    scopes.append(module_scope)
    seen_ids.add("<module>")

    # 3. Recursive lexical preorder traversal
    def _traverse_stmts(
        stmts: List[ast.stmt],
        current_scope_id: str,
        current_scope_type: PublicScopeType,
    ) -> None:
        for stmt in stmts:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_info = node_to_func.get(stmt)
                if func_info is None:
                    continue

                # Procedural scope type normalization:
                # Callables declared directly within a class_body are 'method'.
                # All other callables (module-level, nested in functions, or nested in methods) are 'function'.
                scope_type: PublicScopeType = "method" if current_scope_type == "class_body" else "function"

                scope_id = func_info.func_id
                if scope_id in seen_ids:
                    raise ValueError(f"Duplicate scope ID detected: {scope_id}")
                seen_ids.add(scope_id)

                scope_def = ScopeDefinition(
                    scope_id=scope_id,
                    name=func_info.name,
                    scope_type=scope_type,
                    node=stmt,
                    lineno=func_info.lineno,
                    end_lineno=func_info.end_lineno,
                    parent_scope_id=current_scope_id,
                )
                scopes.append(scope_def)

                # Lexical preorder: traverse function body with this function as parent
                _traverse_stmts(stmt.body, scope_id, scope_type)

            elif isinstance(stmt, ast.ClassDef):
                class_scope_id = f"class_body:{stmt.name}@{stmt.lineno}"
                if class_scope_id in seen_ids:
                    raise ValueError(f"Duplicate scope ID detected: {class_scope_id}")
                seen_ids.add(class_scope_id)

                scope_def = ScopeDefinition(
                    scope_id=class_scope_id,
                    name=stmt.name,
                    scope_type="class_body",
                    node=stmt,
                    lineno=stmt.lineno,
                    end_lineno=getattr(stmt, "end_lineno", stmt.lineno),
                    parent_scope_id=current_scope_id,
                )
                scopes.append(scope_def)

                # Lexical preorder: traverse class body with class_body as parent
                _traverse_stmts(stmt.body, class_scope_id, "class_body")

            elif isinstance(stmt, (ast.If, ast.For, ast.AsyncFor, ast.While)):
                _traverse_stmts(stmt.body, current_scope_id, current_scope_type)
                _traverse_stmts(stmt.orelse, current_scope_id, current_scope_type)

            elif isinstance(stmt, (ast.With, ast.AsyncWith)):
                _traverse_stmts(stmt.body, current_scope_id, current_scope_type)

            elif isinstance(stmt, ast.Try):
                _traverse_stmts(stmt.body, current_scope_id, current_scope_type)
                for handler in stmt.handlers:
                    _traverse_stmts(handler.body, current_scope_id, current_scope_type)
                _traverse_stmts(stmt.orelse, current_scope_id, current_scope_type)
                _traverse_stmts(stmt.finalbody, current_scope_id, current_scope_type)

            elif isinstance(stmt, ast.Match):
                for case in stmt.cases:
                    _traverse_stmts(case.body, current_scope_id, current_scope_type)

    _traverse_stmts(tree.body, "<module>", "module")

    # 4. Final verification of parent-child integrity
    scope_id_set = {s.scope_id for s in scopes}
    for s in scopes:
        if s.parent_scope_id is not None and s.parent_scope_id not in scope_id_set:
            raise ValueError(
                f"Scope '{s.scope_id}' references non-existent parent scope '{s.parent_scope_id}'"
            )

    return scopes


__all__ = [
    "PublicScopeType",
    "ScopeDefinition",
    "discover_scopes",
]
