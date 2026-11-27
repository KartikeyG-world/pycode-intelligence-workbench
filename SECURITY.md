# Security Policy

## Supported security boundary

The workbench is designed for **static analysis** of submitted Python source. It parses source into an AST and inspects that representation. Submitted code must not be executed by the analysis pipeline.

The current static-analysis path must not use:

- `eval()` or `exec()` on submitted source.
- Execution-oriented compilation of submitted source.
- A subprocess to run submitted source.
- Runtime tracing/profiling of the submitted program.
- Fabricated runtime measurements or dynamic branch-coverage claims.

A request to add runtime execution changes the product's threat model and requires a separate architecture and security review; it must not be implemented as a shortcut inside the static analyzer.

## Parser resource controls

The inspected `SafeASTParser` enforces the following limits:

| Input / structure | Limit | Enforcement point |
|---|---:|---|
| UTF-8 source size | 100,000 bytes | Before parsing |
| Source line count | 3,000 lines | Before parsing |
| AST node count | 10,000 nodes | After `ast.parse` returns |
| AST nesting depth | 200 levels | After `ast.parse` returns |

The parser uses iterative traversal for its post-parse AST validation and returns structured error information for handled parsing/resource failures.

## Residual parser risk

The node-count and depth guards run only after the Python parser has constructed the AST. They cannot limit all CPU, memory or native parser-stack resources consumed before `ast.parse` returns. A pathological input may therefore stress the interpreter's parser before Python-level validation can reject the result. Application-level limits must not be represented as a complete denial-of-service guarantee.

For deployments that accept untrusted or hostile source, use defense in depth:

- Isolate parsing and analysis in a worker process or container.
- Apply operating-system CPU and memory limits.
- Apply request deadlines and worker lifecycle controls.
- Limit concurrency and request body sizes at the edge.
- Keep runtime execution of submitted code disabled.
- Monitor resource exhaustion and worker restarts.

## Authentication and history authorization boundaries

The current repository architecture does not implement authentication or authorization:

- **Unauthenticated History Operations:** The endpoints `GET /api/history`, `GET /api/history/{submission_id}`, and `DELETE /api/history/{submission_id}` operate without authentication (`Depends(get_current_user)` is absent).
- **No Ownership Enforcement:** Although `User` and `Project` database models exist in `backend/app/models/models.py`, the analysis and history routes do not bind submissions to authenticated user identities, nor do they verify project or record-level ownership.
- **Unrestricted Access:** Any client with HTTP access to the backend can retrieve all historical analysis snippets, inspect full past analysis graphs, or delete past submissions.
- **Deployment Guidance:** Do not expose the current history API to untrusted clients or operate it as a multi-user service in its present state. An authenticating reverse proxy can provide a perimeter access gate for a controlled single-tenant deployment, but it does not establish per-user data isolation. Multi-user deployments require application-enforced authentication and authorization that propagates a trusted user identity and enforces submission and project ownership on every relevant read and delete operation.

## Internal exception disclosure risks

- **Analysis Endpoint:** In `backend/app/api/routes/analyze.py`, unexpected errors during analysis return raw exception messages directly to the client (`detail=f"...: {str(e)}"` with HTTP 500).
- **Health Check Endpoint:** In `backend/app/api/routes/health.py`, database connection errors return unredacted driver exceptions via `database.error` in the JSON response payload.
- **Risk Assessment:** These exception strings can disclose internal library versions, host paths, or database connectivity specifics to unauthenticated callers. Sanitization is tracked for Phase 1D remediation.

## Database deployment and migration boundaries

- **SQLite Schema Provisioning:** When using SQLite local fallback (`DATABASE_URL` starts with `sqlite`), `backend/app/main.py` executes `Base.metadata.create_all(bind=engine)` automatically during application lifespan startup.
- **PostgreSQL Migration Barrier:** When targeting PostgreSQL, automatic schema creation is not performed. While Alembic migration scripts exist under `backend/alembic/versions/`, the repository currently does not include a published `alembic.ini` configuration file. Direct execution of `alembic upgrade head` is blocked unless `alembic.ini` is manually provided.
- **Process Isolation:** The application does not enforce OS containerization or process sandboxing internally; deployment configurations must supply external containment boundaries.

## Static-analysis limitations

The application does not measure actual execution time, peak runtime memory, dynamic branch coverage or input-specific path execution. Static CFG reachability describes the analyzer's graph model; it is not evidence that a path executes for a given input. Correlation outputs are descriptive and do not prove causality or predict runtime performance.

## Reporting a vulnerability

Do not publish exploit details, credentials, private source data or a working denial-of-service payload in a public issue.

Use GitHub's private vulnerability reporting mechanism for this repository if it is enabled. If it is not enabled, contact the repository owner through a private channel listed in the repository owner's GitHub profile and request a secure reporting route. No dedicated security email address is asserted by this document.

A useful report includes:

- Affected commit, branch and deployment context.
- Impact and affected component.
- Minimal reproduction steps that avoid exposing real user data.
- Required input size, environment and resource constraints.
- Logs or traces with secrets and personal data removed.

Allow maintainers a reasonable opportunity to investigate and coordinate a fix before public disclosure.

## Scope and source references

This policy reflects the source inspected on canonical `main` at merge commit `e298ebba14b69a5c494e4b07308d3bd40aae1cd5` (post-Phase 1C integration), particularly `backend/app/analyzers/ast_parser.py`, `backend/app/core/config.py` and the analysis service. Reassess it when parser behavior, deployment isolation or the product execution boundary changes.
