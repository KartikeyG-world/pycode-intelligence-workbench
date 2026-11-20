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

This policy reflects the source inspected at published Unit 5 commit `84ae1574d567160dcb70f56d6ba745424607dcd9`, particularly `backend/app/analyzers/ast_parser.py`, `backend/app/core/config.py` and the analysis service. Reassess it when parser behavior, deployment isolation or the product execution boundary changes.
