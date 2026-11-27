# Workbench Frontend

The interactive web user interface for the **Python Code Intelligence & Performance Workbench**.

Built with Next.js 16 (App Router), React 19, TypeScript 5, and Tailwind CSS v4.

---

## Capabilities & Architecture

The frontend provides an interactive, dual-column analysis workspace:

- **Monaco Code Editor (`components/CodeEditor.tsx`):** In-browser Python source code editor with syntax highlighting, line numbers, template selectors, and toolbar actions (Analyze, Reset, Export).
- **Asymptotic Complexity Overview (`components/ComplexityOverview.tsx`):** Displays deduced time/space complexity, tight bounds, confidence levels, and space breakdown.
- **AST Control Flow & Hierarchy (`components/StructureFlow.tsx`):** Interactive React Flow diagram (`@xyflow/react`) visualizing AST basic-block control flow, parent-child hierarchy, and basic-block topologies with dark-themed controls.
- **Project Metrics Overview (`components/metrics/MetricsOverview.tsx`):** Project-wide summary cards aggregating procedural scope counts, structural averages, cyclomatic complexity averages, Halstead volume/effort averages, and diagnostic populations.
- **Per-Scope Metrics Explorer (`components/metrics/ScopeMetricsTable.tsx`):** Sortable, responsive data table presenting all canonical AST scopes with sticky identifier column pinning, multi-column sorting, and canonical preorder reset.
- **Detailed Scope Inspector (`components/metrics/ScopeInspector.tsx`):** Deep-dive modal/drawer detailing scope-level cyclomatic complexity, CFG reachability, decision-point breakdown, structural AST distributions, Halstead token inventories, and syntax coverage diagnostics.
- **Project Correlation Analysis (`components/metrics/ProjectCorrelationSection.tsx`):** Statistical co-variation analysis (Pearson $r$ and Spearman $\rho$) across 5 dimensions with status diagnostics and an interactive scatter plot rendered directly from backend observation pairs.

---

## Directory Structure

```text
frontend/
├── app/
│   ├── globals.css          # Tailwind CSS v4 imports and dark scrollbar rules
│   ├── layout.tsx           # Root HTML layout, font setup, and document metadata
│   └── page.tsx             # Main dual-column analysis workspace and state management
├── components/
│   ├── CodeEditor.tsx       # Monaco Editor wrapper and toolbar controls
│   ├── ComplexityOverview.tsx# Algorithmic time/space complexity summary
│   ├── StructureFlow.tsx    # React Flow AST hierarchy diagram
│   └── metrics/             # Phase 1C static metrics components
│       ├── MetricsOverview.tsx
│       ├── ScopeMetricsTable.tsx
│       ├── ScopeInspector.tsx
│       └── ProjectCorrelationSection.tsx
├── lib/
│   ├── api.ts               # HTTP client communication with FastAPI backend
│   └── utils.ts             # Tailwind class merging utilities
├── types/
│   └── analysis.ts          # TypeScript type definitions matching backend Pydantic schemas
├── package.json
└── tsconfig.json
```

---

## Prerequisites & Installation

- **Node.js:** Requires Node.js `>=20.0.0` (as defined in `package.json` engines).
- **Package Installation:** Use `npm ci` for deterministic clean installation of locked dependencies:

```bash
cd frontend
npm ci
```

---

## Available Scripts

From the `frontend/` directory:

| Script | Command | Purpose |
|---|---|---|
| `dev` | `npm run dev` | Start Next.js development server on `http://localhost:3000` |
| `lint` | `npm run lint` | Run ESLint validation across all pages and components |
| `typecheck` | `npx tsc --noEmit` | Execute TypeScript strict compiler validation without emitting files |
| `build` | `npm run build` | Produce optimized Next.js production build (`next build --webpack`) |
| `start` | `npm run start` | Start Next.js production server from built assets |

---

## Environment & API Configuration

The frontend communicates with the FastAPI backend over HTTP JSON APIs configured in `frontend/lib/api.ts`:

- **Environment Variable:** `NEXT_PUBLIC_API_URL`
- **Default Value:** `http://localhost:8000/api` (falls back automatically when unset)

### Endpoint Routes

- Static analysis: `POST ${NEXT_PUBLIC_API_URL}/analyze`
- Persisted history list: `GET ${NEXT_PUBLIC_API_URL}/history`
- History item detail: `GET ${NEXT_PUBLIC_API_URL}/history/:submissionId`
- Backend health check: `GET ${NEXT_PUBLIC_API_URL}/health`

For full end-to-end setup and operations, consult the root [DEVELOPMENT.md](../DEVELOPMENT.md).
