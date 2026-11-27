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

## Available Scripts

From the `frontend/` directory:

| Script | Command | Purpose |
|---|---|---|
| `dev` | `npm run dev` | Start Next.js development server (Turbopack) on `http://localhost:3000` |
| `lint` | `npm run lint` | Run ESLint validation across all pages and components |
| `typecheck` | `npx tsc --noEmit` | Execute TypeScript strict compiler validation without emitting files |
| `build` | `npm run build` | Produce optimized Next.js production build (`next build --webpack`) |
| `start` | `npm run start` | Start Next.js production server from built assets |

---

## Development & API Communication

The frontend expects the backend FastAPI server to run at `http://127.0.0.1:8000`.

- Static analysis requests are sent via `POST http://127.0.0.1:8000/api/analyze`.
- Persisted history queries are sent via `GET http://127.0.0.1:8000/api/history`.
- Health checks are verified via `GET http://127.0.0.1:8000/api/health`.

For full end-to-end setup and operations, consult the root [DEVELOPMENT.md](../DEVELOPMENT.md).
