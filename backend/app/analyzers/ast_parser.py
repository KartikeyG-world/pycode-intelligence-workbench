import ast
from typing import Optional, Tuple
from app.schemas.analysis import SyntaxErrorInfo
from app.core.config import settings


class SafeASTParser:
    """Safely parses Python source code into an AST without execution, enforcing strict resource boundaries."""

    MAX_AST_NODES: int = 10_000
    MAX_AST_DEPTH: int = 200

    @staticmethod
    def parse_code(code: str) -> Tuple[Optional[ast.AST], Optional[SyntaxErrorInfo]]:
        # Size limit check
        if len(code.encode("utf-8")) > settings.MAX_CODE_LENGTH_BYTES:
            return None, SyntaxErrorInfo(
                line=1,
                column=1,
                message=f"Source code exceeds maximum allowed size ({settings.MAX_CODE_LENGTH_BYTES} bytes).",
                snippet=code[:100] + "..."
            )

        line_count = len(code.splitlines())
        if line_count > settings.MAX_CODE_LINES:
            return None, SyntaxErrorInfo(
                line=1,
                column=1,
                message=f"Source code exceeds maximum allowed line count ({settings.MAX_CODE_LINES} lines).",
                snippet=f"{line_count} lines"
            )

        try:
            tree = ast.parse(code)
            
            # Check AST node count and maximum depth to protect against deeply nested attacks
            node_count = 0
            max_depth = 0
            
            def check_limits(node: ast.AST, current_depth: int):
                nonlocal node_count, max_depth
                node_count += 1
                if current_depth > max_depth:
                    max_depth = current_depth
                if node_count > SafeASTParser.MAX_AST_NODES:
                    raise ValueError(f"AST node count exceeded limit ({SafeASTParser.MAX_AST_NODES} nodes).")
                if current_depth > SafeASTParser.MAX_AST_DEPTH:
                    raise RecursionError(f"AST nesting depth exceeded limit ({SafeASTParser.MAX_AST_DEPTH} levels).")
                
                for child in ast.iter_child_nodes(node):
                    check_limits(child, current_depth + 1)
            
            check_limits(tree, 1)
            return tree, None

        except (ValueError, RecursionError) as e:
            return None, SyntaxErrorInfo(
                line=1,
                column=1,
                message=f"Static analysis resource limit reached: {str(e)}",
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
