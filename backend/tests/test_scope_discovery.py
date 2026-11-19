"""
Comprehensive test suite for Phase 1B.2 Unit 2: Canonical Scope Discovery Adapter.

Validates fundamental scope discovery, nested scopes, callable normalization,
canonical metadata, 1:1 CFG compatibility, and AST immutability.
"""

import ast
import copy
import pytest

from app.analyzers.scope_discovery import ScopeDefinition, discover_scopes
from app.analyzers.cfg_builder import CFGBuilder


# ============================================================================
# Section A: Fundamental Discovery
# ============================================================================

def test_empty_module():
    """1. Empty module yields exactly one <module> scope."""
    tree = ast.parse("")
    scopes = discover_scopes(tree)
    assert len(scopes) == 1
    mod = scopes[0]
    assert mod.scope_id == "<module>"
    assert mod.name == "<module>"
    assert mod.scope_type == "module"
    assert mod.parent_scope_id is None
    assert mod.node is tree


def test_module_level_function():
    """2. Module-level function yields <module> and function scope."""
    code = "def foo():\n    return 42"
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    assert len(scopes) == 2
    assert [s.scope_id for s in scopes] == ["<module>", "foo@1"]
    assert scopes[1].scope_type == "function"
    assert scopes[1].parent_scope_id == "<module>"
    assert scopes[1].name == "foo"


def test_module_level_async_function():
    """3. Module-level async function yields <module> and function scope (not async_function)."""
    code = "async def fetch_data():\n    return 1"
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    assert len(scopes) == 2
    assert scopes[1].scope_id == "fetch_data@1"
    assert scopes[1].scope_type == "function"
    assert scopes[1].parent_scope_id == "<module>"


def test_module_level_class():
    """4. Module-level class without methods yields <module> and class_body scope."""
    code = "class EmptyClass:\n    pass"
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    assert len(scopes) == 2
    assert scopes[1].scope_id == "class_body:EmptyClass@1"
    assert scopes[1].scope_type == "class_body"
    assert scopes[1].parent_scope_id == "<module>"
    assert scopes[1].name == "EmptyClass"


def test_class_with_one_method():
    """5. Class with one method yields <module>, class_body, and method scope."""
    code = "class Greeter:\n    def greet(self):\n        return 'hello'"
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    assert len(scopes) == 3
    assert [s.scope_id for s in scopes] == ["<module>", "class_body:Greeter@1", "Greeter.greet@2"]
    assert scopes[1].scope_type == "class_body"
    assert scopes[1].parent_scope_id == "<module>"
    assert scopes[2].scope_type == "method"
    assert scopes[2].parent_scope_id == "class_body:Greeter@1"


def test_class_with_multiple_methods():
    """6. Class with multiple methods preserves ordering and parentage."""
    code = (
        "class Calculator:\n"
        "    def add(self, a, b):\n"
        "        return a + b\n"
        "    def sub(self, a, b):\n"
        "        return a - b\n"
    )
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    assert len(scopes) == 4
    assert [s.scope_id for s in scopes] == [
        "<module>",
        "class_body:Calculator@1",
        "Calculator.add@2",
        "Calculator.sub@4",
    ]
    assert scopes[2].scope_type == "method"
    assert scopes[2].parent_scope_id == "class_body:Calculator@1"
    assert scopes[3].scope_type == "method"
    assert scopes[3].parent_scope_id == "class_body:Calculator@1"


# ============================================================================
# Section B: Nested Scopes
# ============================================================================

def test_function_nested_inside_function():
    """7. Function nested inside function has parent pointing to outer function."""
    code = (
        "def outer():\n"
        "    def inner():\n"
        "        return 1\n"
        "    return inner()\n"
    )
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    assert len(scopes) == 3
    assert [s.scope_id for s in scopes] == ["<module>", "outer@1", "outer.inner@2"]
    assert scopes[1].scope_type == "function"
    assert scopes[1].parent_scope_id == "<module>"
    assert scopes[2].scope_type == "function"
    assert scopes[2].parent_scope_id == "outer@1"


def test_function_nested_inside_method():
    """8. Function nested inside method has scope_type='function' and parent pointing to method."""
    code = (
        "class Worker:\n"
        "    def run(self):\n"
        "        def helper():\n"
        "            return 10\n"
        "        return helper()\n"
    )
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    assert len(scopes) == 4
    assert [s.scope_id for s in scopes] == [
        "<module>",
        "class_body:Worker@1",
        "Worker.run@2",
        "Worker.run.helper@3",
    ]
    assert scopes[2].scope_type == "method"
    assert scopes[2].parent_scope_id == "class_body:Worker@1"
    assert scopes[3].scope_type == "function"
    assert scopes[3].parent_scope_id == "Worker.run@2"


def test_nested_class_inside_class():
    """9. Nested class inside class has parent pointing to outer class_body."""
    code = (
        "class Outer:\n"
        "    class Inner:\n"
        "        pass\n"
    )
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    assert len(scopes) == 3
    assert [s.scope_id for s in scopes] == [
        "<module>",
        "class_body:Outer@1",
        "class_body:Inner@2",
    ]
    assert scopes[1].scope_type == "class_body"
    assert scopes[1].parent_scope_id == "<module>"
    assert scopes[2].scope_type == "class_body"
    assert scopes[2].parent_scope_id == "class_body:Outer@1"


def test_class_nested_inside_function():
    """10. Class nested inside function has parent pointing to enclosing function."""
    code = (
        "def factory():\n"
        "    class LocalProduct:\n"
        "        pass\n"
        "    return LocalProduct()\n"
    )
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    assert len(scopes) == 3
    assert [s.scope_id for s in scopes] == [
        "<module>",
        "factory@1",
        "class_body:LocalProduct@2",
    ]
    assert scopes[1].scope_type == "function"
    assert scopes[1].parent_scope_id == "<module>"
    assert scopes[2].scope_type == "class_body"
    assert scopes[2].parent_scope_id == "factory@1"


def test_methods_in_nested_classes():
    """11. Methods in nested classes are methods and point to nested class_body."""
    code = (
        "class A:\n"
        "    class B:\n"
        "        def nested_m(self):\n"
        "            return 1\n"
    )
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    assert len(scopes) == 4
    assert [s.scope_id for s in scopes] == [
        "<module>",
        "class_body:A@1",
        "class_body:B@2",
        "A.B.nested_m@3",
    ]
    assert scopes[2].scope_type == "class_body"
    assert scopes[2].parent_scope_id == "class_body:A@1"
    assert scopes[3].scope_type == "method"
    assert scopes[3].parent_scope_id == "class_body:B@2"


def test_multiple_sibling_scopes_deterministic_order():
    """12. Multiple sibling scopes appear in deterministic source line order."""
    code = (
        "def first(): pass\n"
        "class Middle: pass\n"
        "def last(): pass\n"
    )
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    assert [s.scope_id for s in scopes] == [
        "<module>",
        "first@1",
        "class_body:Middle@2",
        "last@3",
    ]


# ============================================================================
# Section C: Callable Normalization
# ============================================================================

def test_normal_function_normalization():
    """13. Normal function is normalized to public scope_type='function'."""
    tree = ast.parse("def f(): pass")
    scopes = discover_scopes(tree)
    assert scopes[1].scope_type == "function"


def test_async_function_normalization():
    """14. Async function is normalized to public scope_type='function'."""
    tree = ast.parse("async def f(): pass")
    scopes = discover_scopes(tree)
    assert scopes[1].scope_type == "function"


def test_normal_method_normalization():
    """15. Method declared in class_body is normalized to public scope_type='method'."""
    tree = ast.parse("class C:\n    def m(self): pass")
    scopes = discover_scopes(tree)
    assert scopes[2].scope_type == "method"


def test_async_method_normalization():
    """16. Async method declared in class_body is normalized to public scope_type='method'."""
    tree = ast.parse("class C:\n    async def m(self): pass")
    scopes = discover_scopes(tree)
    assert scopes[2].scope_type == "method"


def test_static_method_normalization():
    """17. @staticmethod in class_body is normalized to public scope_type='method'."""
    code = "class C:\n    @staticmethod\n    def sm(): pass"
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    assert scopes[2].scope_type == "method"


def test_class_method_normalization():
    """18. @classmethod in class_body is normalized to public scope_type='method'."""
    code = "class C:\n    @classmethod\n    def cm(cls): pass"
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    assert scopes[2].scope_type == "method"


def test_nested_function_inside_method_remains_function():
    """19. Function nested inside a method remains 'function', not 'method'."""
    code = (
        "class Service:\n"
        "    def process(self):\n"
        "        def validate(): pass\n"
        "        return validate()\n"
    )
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    assert len(scopes) == 4
    method_scope = scopes[2]
    nested_scope = scopes[3]
    assert method_scope.scope_type == "method"
    assert nested_scope.scope_type == "function"
    assert nested_scope.parent_scope_id == method_scope.scope_id


# ============================================================================
# Section D: Canonical Metadata
# ============================================================================

def test_canonical_metadata_exact_fields():
    """20-25. ScopeDefinition provides exact scope_id, name, type, parent, node, line spans."""
    code = (
        "@cache\n"
        "def compute(x: int) -> int:\n"
        "    return x * 2\n"
    )
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    fn = scopes[1]
    assert fn.scope_id == "compute@2"
    assert fn.name == "compute"
    assert fn.scope_type == "function"
    assert fn.parent_scope_id == "<module>"
    assert isinstance(fn.node, ast.FunctionDef)
    assert fn.lineno == 2
    assert fn.end_lineno == 3


def test_exactly_one_module_scope():
    """26. Exactly one module scope is present and located at index 0."""
    code = "def a(): pass\ndef b(): pass"
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    mod_scopes = [s for s in scopes if s.scope_type == "module"]
    assert len(mod_scopes) == 1
    assert scopes[0].scope_id == "<module>"


def test_no_duplicate_scope_ids():
    """27. All scope IDs within the returned inventory are unique."""
    code = (
        "class A:\n"
        "    def m(self): pass\n"
        "class B:\n"
        "    def m(self): pass\n"
        "def m(): pass\n"
    )
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    ids = [s.scope_id for s in scopes]
    assert len(ids) == len(set(ids))


# ============================================================================
# Section E: CFG Compatibility
# ============================================================================

def test_cfg_module_and_class_body_alignment():
    """28. Module and class-body identifiers align exactly with CFGBuilder.build_all()."""
    code = "class Container:\n    pass\nclass Helper:\n    pass"
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    cfgs = CFGBuilder.build_all(tree)
    for s in scopes:
        assert s.scope_id in cfgs, f"Scope {s.scope_id} missing in CFGs"


def test_cfg_function_and_method_alignment():
    """29. Function and method identifiers align exactly with CFGBuilder.build_all()."""
    code = (
        "def top_func(): pass\n"
        "class Foo:\n"
        "    def bar(self): pass\n"
    )
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    cfgs = CFGBuilder.build_all(tree)
    assert set(cfgs.keys()) == {s.scope_id for s in scopes}


def test_cfg_async_callable_alignment():
    """30. Async functions and async methods align exactly with CFGBuilder.build_all()."""
    code = (
        "async def async_fetch(): pass\n"
        "class AsyncWorker:\n"
        "    async def async_run(self): pass\n"
    )
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    cfgs = CFGBuilder.build_all(tree)
    assert set(cfgs.keys()) == {s.scope_id for s in scopes}


def test_cfg_nested_scope_alignment():
    """31. Nested functions and methods inside nested classes align with CFGBuilder.build_all()."""
    code = (
        "class Outer:\n"
        "    def outer_m(self):\n"
        "        def inner_f(): pass\n"
        "    class Inner:\n"
        "        def inner_m(self): pass\n"
    )
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    cfgs = CFGBuilder.build_all(tree)
    assert set(cfgs.keys()) == {s.scope_id for s in scopes}


def test_cfg_complete_inventory_consistency():
    """32. Complete 1:1 bidirectional key consistency with CFGBuilder.build_all()."""
    code = (
        "def calculate(n):\n"
        "    class Factorial:\n"
        "        def compute(self, k):\n"
        "            def helper(): return k\n"
        "            return helper()\n"
        "    return Factorial().compute(n)\n"
    )
    tree = ast.parse(code)
    scopes = discover_scopes(tree)
    cfgs = CFGBuilder.build_all(tree)
    scope_ids = {s.scope_id for s in scopes}
    cfg_ids = set(cfgs.keys())
    assert scope_ids == cfg_ids


# ============================================================================
# Section F: AST Immutability
# ============================================================================

def test_ast_not_mutated_by_discovery():
    """33. Source AST structure and dump are completely unchanged after discover_scopes()."""
    code = (
        "class Processor:\n"
        "    def process(self, data: list[int]) -> int:\n"
        "        return sum(data)\n"
    )
    tree = ast.parse(code)
    dump_before = ast.dump(tree, indent=2)
    _ = discover_scopes(tree)
    dump_after = ast.dump(tree, indent=2)
    assert dump_before == dump_after


def test_ast_nodes_are_original_references():
    """34. AST node references in ScopeDefinition are identity-equal to original parsed AST nodes."""
    code = (
        "class MyClass:\n"
        "    def my_method(self):\n"
        "        pass\n"
    )
    tree = ast.parse(code)
    scopes = discover_scopes(tree)

    # Original references from tree
    original_class_node = tree.body[0]
    original_method_node = tree.body[0].body[0]

    assert scopes[0].node is tree
    assert scopes[1].node is original_class_node
    assert scopes[2].node is original_method_node


def test_invalid_input_type_rejected():
    """discover_scopes raises TypeError if argument is not an ast.Module."""
    with pytest.raises(TypeError) as exc:
        discover_scopes(ast.Pass())  # type: ignore
    assert "Expected ast.Module instance" in str(exc.value)
