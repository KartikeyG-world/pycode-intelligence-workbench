# Frontend Development Guide

The `frontend/` directory contains the browser-based interface for the **Python Code Intelligence & Performance Workbench**. It provides a workspace for entering Python source code, requesting static analysis from the FastAPI backend, and exploring the returned complexity, statistics, structure, reasoning, and saved analysis history.

The frontend does not analyze or execute submitted Python itself. It sends source code to the backend API and renders the backend's response.

## Technology Stack

| Technology | Purpose |
|---|---|
| Next.js 16.3.6 (App Router) | Frontend application and development/production server |
| React 19.2.8 | UI components and client-side state |
| TypeScript | Typed component props and API data contracts |
| Tailwind CSS v4 | Utility-first styling |
| `@monaco-editor/react` | Python code editor |
| `@xyflow/react` | Interactive code-structure graph |
| Recharts | Theoretical complexity charts |
| `lucide-react` | Interface icons |

The exact dependency versions and ranges are maintained in `package.json` and `package-lock.json`.

## Prerequisites

- **Node.js:** version 20 or later (the minimum declared in `package.json` is `>=20.0.0`).
- **npm:** required to install dependencies and run the frontend scripts.
- **FastAPI backend:** required for analysis, history, and backend health requests. Follow the backend setup in the root [DEVELOPMENT.md](../DEVELOPMENT.md).

## Installation

From the repository root, install the locked dependencies:

```bash
cd frontend
npm ci
```

Use `npm ci` to install from the checked-in `package-lock.json`. It provides a clean, reproducible install and does not update the lockfile.

## Development

Start the Next.js development server from the `frontend/` directory:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser. Keep the FastAPI backend running separately so that analysis, history, and health-check requests can reach it.

## Backend Connection

The frontend communicates with the FastAPI backend through the HTTP helpers in `lib/api.ts`. The API base URL is read from the public environment variable:

- **Variable:** `NEXT_PUBLIC_API_URL`
- **Default:** `http://localhost:8000/api`

If the variable is not set, the frontend uses the default above. To point the frontend at a different backend, create a `.env.local` file in `frontend/` and set the variable, for example:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

Restart the development server after changing environment configuration. Because this variable is prefixed with `NEXT_PUBLIC_`, its value is exposed to the browser bundle; do not put secrets or private credentials in it.

The current API client uses these routes relative to the configured base URL:

| Request | Purpose |
|---|---|
| `POST /analyze` | Submit Python source code for static analysis |
| `GET /history` | Retrieve saved analysis history |
| `GET /history/{submissionId}` | Retrieve a saved analysis record |
| `GET /health` | Check backend and database health |

For the complete backend setup and repository-wide development workflow, see [DEVELOPMENT.md](../DEVELOPMENT.md).

## Available Scripts

Run these commands from `frontend/`:

| Command | Purpose |
|---|---|
| `npm run dev` | Start the Next.js development server |
| `npm run lint` | Run ESLint |
| `npm run build` | Create a production build using `next build --webpack` |
| `npm run start` | Start the production server from a completed build |
| `npx tsc --noEmit` | Run the TypeScript compiler without emitting files |

There is no separate `typecheck` script in `package.json`; use `npx tsc --noEmit` directly. Run linting, TypeScript checking, and the production build independently so that each result is clear.

To test the production server locally:

```bash
npm run build
npm run start
```

## Component Architecture

The main workspace is assembled in `app/page.tsx`. Its principal components are:

| Component | Responsibility |
|---|---|
| `CodeEditor` | Wraps Monaco Editor for Python source input. Provides example presets, line/character information, reset and analyze actions, and the Ctrl/Cmd+Enter shortcut. |
| `ComplexityOverview` | Presents the returned time and space complexity, tight bound when available, confidence, nesting information, and space breakdown. |
| `StatisticsGrid` | Summarizes code statistics such as function, loop, conditional, recursion, operation, and comprehension counts. |
| `ComplexityChart` | Uses Recharts to display the theoretical growth curves supplied by the backend. |
| `StructureFlow` | Uses React Flow to render the returned code-structure nodes and edges as an interactive diagram. |
| `ReasoningPanel` | Displays the complexity explanation, detected patterns, optimization suggestions, and available reasoning details such as recurrence information and limitations. |
| `HistoryDrawer` | Loads saved analysis entries and lets a user select a previous submission to restore its code and result. |
| `ReportModal` | Formats the current analysis as a Markdown report that can be copied or downloaded. |
| `Navbar` | Displays backend/database status and provides access to analysis history and report export. |

The page coordinates editor state, analysis requests, backend health polling, selected results, and the history/report overlays. Component files are located in `components/`.

## API Types

The frontend API contracts are defined in `types/analysis.ts`. This file contains the TypeScript interfaces used by the API client and UI components, including analysis responses, code statistics and structure, theoretical graph data, and history records.

These interfaces describe the JSON shapes expected by the frontend. Keep them synchronized with the corresponding backend Pydantic schemas and API responses: a mismatch can cause incorrect assumptions when rendering data even if the frontend compiles successfully. When changing an API field, review both sides of the contract.

The HTTP request and response handling is centralized in `lib/api.ts`; prefer using those helpers rather than duplicating API URLs and fetch logic in components.

## Verification

Run each frontend check from the `frontend/` directory:

**1. ESLint**

```bash
npm run lint
```

**2. TypeScript**

```bash
npx tsc --noEmit
```

**3. Production build**

```bash
npm run build
```

These checks are independent. A successful lint run does not establish that type checking or the production build succeeds. The production start command also requires a completed build.

## Related Documentation

- [Repository overview](../README.md)
- [Development and operations guide](../DEVELOPMENT.md)
- [Contribution guidelines](../CONTRIBUTING.md)

