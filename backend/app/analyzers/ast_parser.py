import ast
from typing import Optional, Tuple
from app.schemas.analysis import SyntaxErrorInfo
from app.core.config import settings


class SafeASTParser:
    """Safely parses Python source code into an AST without execution, enforcing strict resource boundaries."""

    MAX_CODE_BYTES: int = 100_000
    MAX_CODE_LENGTH_BYTES: int = 100_000
    MAX_CODE_LINES: int = 3_000
    MAX_AST_NODES: int = 10_000
    MAX_AST_DEPTH: int = 200

    @staticmethod
    def parse_code(code: str) -> Tuple[Optional[ast.AST], Optional[SyntaxErrorInfo]]:
        # Tier 1: Pre-parse source boundary checks
        encoded = code.encode("utf-8")
        max_bytes = getattr(settings, "MAX_CODE_LENGTH_BYTES", SafeASTParser.MAX_CODE_BYTES)
        if len(encoded) > max_bytes:
            return None, SyntaxErrorInfo(
                line=1,
                column=1,
                message=f"Source code exceeds maximum allowed size ({max_bytes} bytes).",
                snippet=code[:100] + "..."
            )

        line_count = len(code.splitlines())
        max_lines = getattr(settings, "MAX_CODE_LINES", SafeASTParser.MAX_CODE_LINES)
        if line_count > max_lines:
            return None, SyntaxErrorInfo(
                line=1,
                column=1,
                message=f"Source code exceeds maximum allowed line count ({max_lines} lines).",
                snippet=f"{line_count} lines"
            )

        # Tier 2: Parser-stage execution with recoverable exception handling
        try:
            tree = ast.parse(code)
            
            # Tier 3: Post-parse AST validation using strictly bounded iterative traversal
            # (Prevents recursive call stack exhaustion when inspecting deep trees)
            node_count = 0
            stack = [(tree, 1)]
            
            while stack:
                curr_node, curr_depth = stack.pop()
                node_count += 1
                
                if node_count > SafeASTParser.MAX_AST_NODES:
                    raise ValueError(f"AST node count exceeded limit ({SafeASTParser.MAX_AST_NODES} nodes).")
                if curr_depth > SafeASTParser.MAX_AST_DEPTH:
                    raise RecursionError(f"AST nesting depth exceeded limit ({SafeASTParser.MAX_AST_DEPTH} levels).")
                
                # Push children to iterative stack
                for child in ast.iter_child_nodes(curr_node):
                    stack.append((child, curr_depth + 1))
            
            return tree, None

        except (ValueError, RecursionError) as e:
            return None, SyntaxErrorInfo(
                line=1,
                column=1,
                message=f"Static analysis resource limit reached: {str(e)}",
                snippet=None
            )
        except (MemoryError, TypeError) as e:
            return None, SyntaxErrorInfo(
                line=1,
                column=1,
                message=f"Static analysis resource or type constraint failure: {str(e)}",
                snippet=None
            )
        except SyntaxError as e:
            # Extract line snippet safely
            snippet = None
            lines = code.splitlines()
            if e.lineno and 1 <= e.lineno <= len(lines):
                snippet = lines[e.lineno - 1]

            return None, SyntaxErrorInfo(
                line=e.lineno or 1,
                column=e.offset or 1,
                message=str(e.msg) if hasattr(e, 'msg') and e.msg else str(e),
                snippet=snippet
            )
        except Exception as e:
            return None, SyntaxErrorInfo(
                line=1,
                column=1,
                message=f"Failed to parse source: {str(e)}",
                snippet=None
            )
