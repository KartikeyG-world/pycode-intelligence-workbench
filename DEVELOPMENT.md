# Development and Operations Guide

This guide provides instructions for setting up, verifying, testing, and running both the Python FastAPI backend and Next.js frontend of the Python Code Intelligence & Performance Workbench.

---

## 1. Prerequisites

Ensure the following runtimes and tools are installed on your system:

- **Python**: 3.13.x (or 3.11+) 64-bit
- **Node.js**: v20.x or v24.x
- **Package Managers**:
  - Python: `uv` (recommended, `pip install uv`) or standard `pip`
  - Node.js: `npm` (v10+ or v11+)
- **Git**: 2.40+

---

## 2. Environment Configuration

Copy the root `.env.example` file to create your local `.env`:

```bash
cp .env.example .env
```

Default configuration values:
- `PROJECT_NAME="Code Complexity Visualizer"`
- `VERSION="1.0.0"`
- `API_V1_PREFIX="/api"`
- `DATABASE_URL="sqlite+pysqlite:///./complexity.db"` (Defaults to zero-configuration SQLite fallback)
- `NEXT_PUBLIC_API_URL="http://127.0.0.1:8000"`

---

## 3. Backend Setup & Testing (Python / FastAPI)

The backend utilizes `uv` for reproducible, lockfile-backed dependency management.

### Installation

Navigate to `backend/` and synchronize the environment:

```powershell
cd backend

# Using uv (recommended - syncs exact uv.lock):
python -m uv sync --extra dev

# Alternative standard pip installation:
python -m pip install -r requirements.txt
```

### Running Tests

Execute the complete 36-test suite:

```powershell
# From the backend/ directory:
.\.venv\Scripts\pytest tests/ -v
```

All 36 tests cover:
- `tests/test_api.py` (5 API endpoint integration tests)
- `tests/test_complexity_analyzer.py` (12 AST loop/recursion/memory unit tests)
- `tests/test_recurrence_regression.py` (19 recurrence solver and metamorphic regression tests)

### Starting the Development Server

```powershell
# From the backend/ directory:
.\.venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API Documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health Check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

## 4. Frontend Setup & Build (Next.js 16 / React 19)

### Installation

Navigate to `frontend/` and install locked dependencies:

```powershell
cd frontend
npm ci
```

### Type Checking & Linting

```powershell
# TypeScript verification:
npx tsc --noEmit

# ESLint check:
npm run lint
```

### Production Build

On Windows systems, Next.js 16 Webpack mode is configured for `@xyflow/react` stylesheet evaluation:

```powershell
npm run build
```

### Starting the Development Server

```powershell
npm run dev
```

The application interface is served at: [http://localhost:3000](http://localhost:3000).

---

## 5. Architectural Notes & Baseline Verification

### SQLite Local Fallback
When no Supabase PostgreSQL connection string is configured in `DATABASE_URL`, the application automatically falls back to SQLite (`./complexity.db`). The schema tables (`analysis_results`, `code_submissions`, `users`, `projects`) are verified on application startup via FastAPI's lifespan event.

### Sandbox & Windows Loopback Socket Note
On Windows systems, Python's `asyncio.ProactorEventLoop` uses a TCP loopback socket (`127.0.0.1`) for thread-to-event-loop notifications (`call_soon_threadsafe`). If executed in a sandboxed shell with network isolation, thread-based test clients like Starlette's `TestClient` require network loopback access (`BypassSandbox: true` or unsandboxed execution) to prevent socket permissions blocking (`WinError 10013`).

---

## 6. Historical Algorithmic Deficiencies (Resolved in Phase 1A & Phase 1A.1)

The following deficiencies cataloged during Phase -1 were systematically resolved in Phase 1A and Phase 1A.1:

1. **Interprocedural Call Graph & Loop Composition**: Resolved via `FunctionIndex`, `CallGraph`, and `CostComposer`. Call sites inside loops multiply caller and callee asymptotic costs ($\mathcal{O}(f(n) \cdot g(n))$).
2. **Multi-Function & Recursion Composition**: Resolved via Tarjan's SCC decomposition, bottom-up topological evaluation, and additive composition across independent procedures.
3. **Local Type Inference**: Resolved via `LocalTypeInference`, preventing false string concatenation warnings on numeric and annotated variables.
4. **Parser Boundaries & Semantic Execution Safety**: Enforced strict input byte/line limits (100 KB, 3,000 lines), iterative bounded AST traversal, container method cost models, and eager argument evaluation.

---

## 7. Phase 1B Architectural Specification & Design Boundaries

As the engine advances to Control Flow Graph (CFG) analysis, Cyclomatic Complexity, and path-sensitive analysis in Phase 1B, the following architectural invariants and boundaries must be preserved:

### A. Non-Exact Path Enumeration Boundary
Control flow analysis must NOT claim or attempt to provide "exact path enumeration" for general Python programs. In the presence of arbitrary loops, recursion, dynamic dispatch, and input-dependent branch conditions, path feasibility and exhaustive execution path enumeration are undecidable (Rice's Theorem / Halting Problem). Instead, the CFG engine computes sound over-approximations, upper-bound path counts, branch condition coverage, and McCabe cyclomatic complexity $M = E - N + 2P$.

### B. Seven-Tier Architecture & Division of Responsibility
The analysis pipeline adheres to a strict 7-tier layered hierarchy with unidirectional data flow:

1. **AST Layer (`SafeASTParser`)**: Enforces input size boundaries (100 KB / 3,000 lines), AST node limits (50,000 nodes, depth $\le 200$), and parses source into Python standard AST representations without code execution.
2. **Function Index (`FunctionIndex`)**: Extracts lexical scopes, parameter lists, class/method definitions, decorators, and maps identifiers across scopes.
3. **Call Graph (`CallGraph`)**: Identifies interprocedural call sites, argument classifications, Tarjan Strongly Connected Components (SCCs), and mutual/direct recursion cycles.
4. **Control Flow Graph (`CFGBuilder`)**: Constructs basic blocks, control flow edges, entry/exit points, loop headers, and exception handling paths per function scope.
5. **Recurrence Solver (`RecurrenceSolver` & `RecursionAnalyzer`)**: Solves homogeneous and inhomogeneous recurrence relations extracted from recursive calls.
6. **Cyclomatic Analyzer (`CyclomaticAnalyzer`)**: Computes McCabe cyclomatic complexity, decision density, and branch counts directly from the CFG block structure.
7. **Cost Composer (`CostComposer`)**: Synthesizes time complexity, auxiliary/retained space complexity, built-in operation costs, and emits the unified `AnalysisResult` contract.

### C. Radon as Development-Time Validation Oracle
External cyclomatic complexity tools (e.g., `radon`) are restricted to development-time test harness oracles and validation baselines (`tests/`). They must NOT be imported, linked, or executed as runtime production dependencies in backend code. The production workbench relies exclusively on internal, verified AST/CFG traversal.
