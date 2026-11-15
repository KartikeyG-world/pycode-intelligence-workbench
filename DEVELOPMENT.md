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

## 6. Documented Engine Algorithmic Deficiencies (Phase -1 Audit)

The following behavioral limitations were verified and cataloged during the Phase -1 baseline audit without altering existing code:

1. **Interprocedural Complexity Loss**:
   Loops invoking external helper functions do not inline helper asymptotic cost, treating caller and callee as sequential blocks ($\mathcal{O}(\max(f(n), g(n)))$) rather than multiplying costs ($\mathcal{O}(f(n) \cdot g(n))$).
2. **Recursion Loop Preemption**:
   If any recursive function exists in the submitted AST, the analyzer branches exclusively to `recursions[0]`, ignoring all outer and independent loops in the AST.
3. **Single Recursion Tracking**:
   When multiple recursive procedures exist in the module, only `recursions[0]` is evaluated; subsequent recursive functions are ignored.
4. **Integer Accumulation Flagged as String Concatenation**:
   Any `+=` binary operation within a loop triggers `has_string_concat_in_loop = True` without type inference, emitting quadratic string copying warnings for integer accumulators (`total += x`).

These deficiencies will be addressed in future analysis engine redesign phases.
