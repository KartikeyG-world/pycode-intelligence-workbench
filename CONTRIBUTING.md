# Contributing

Thank you for considering a contribution to the Python Code Intelligence & Performance Workbench. Contributions must preserve the project's static-only analysis boundary and the accepted analyzer/data contracts.

## Before starting

1. Read the issue and confirm the intended behavior with the maintainers.
2. Inspect the current implementation and relevant tests before proposing changes.
3. Identify any accepted mathematical or architecture contract affected by the change.
4. Keep implementation scope narrow. Do not combine unrelated refactors with a feature or fix.

## Branching

Do not commit feature work directly to `main`. Use a focused branch based on the latest approved `main`:

- `feat/<short-description>` for features
- `fix/<short-description>` for bug fixes
- `test/<short-description>` for test-only changes
- `docs/<short-description>` for documentation
- `refactor/<short-description>` for behavior-preserving refactors

Avoid reusing a branch for unrelated work. Do not rewrite shared branch history or force-push without explicit maintainer authorization.

## Commit messages

Use Conventional Commit-style messages with an accurate scope where useful:

```text
feat(analyzer): add canonical scope diagnostic
fix(parser): reject oversized source before parsing
test(cfg): cover unreachable exit edge
refactor(metrics): simplify immutable result mapping
docs(architecture): clarify analyzer integration boundary
```

Prefer atomic commits that explain one coherent change. Do not claim a commit is tested unless the stated tests were actually run.

## Implementation requirements

- Preserve deterministic behavior and explicit status/coverage semantics.
- Do not execute submitted Python source. `eval`, `exec`, execution-oriented compilation, subprocess execution of supplied code and runtime tracing are outside the current product boundary.
- Do not mutate the original AST during analysis.
- Preserve canonical scope identity and ordering contracts.
- Do not conflate structural AST ownership with Halstead inventory ownership.
- Keep partial, unsupported and undefined results explicit; do not coerce them to successful zero values.
- Do not change accepted CFG behavior or mathematical formulas without an approved specification change.
- Treat correlations as descriptive, not causal or predictive.
- Do not introduce a new project-wide aggregate metric unless its mathematical definition, eligible population and denominator are approved.

## Testing expectations

Run the smallest relevant test module while iterating, then the appropriate regression set before opening a pull request. For backend changes, run from `backend/`:

```powershell
uv run pytest tests/<relevant_test_module>.py -v
```

For broader backend verification:

```powershell
uv run pytest tests/ -v
```

For frontend changes, run:

```powershell
npm run lint
npx tsc --noEmit
npm run build
```

Run frontend commands from `frontend/`. Record the branch, full commit SHA, commands, results and environment. If network/socket restrictions prevent an integration test from running, report that as an unverified test rather than a pass.

Before committing, inspect the full diff and run:

```powershell
git diff --check
git status --short
git diff --stat
```

Stage only intended files; avoid indiscriminate staging if the working tree contains unrelated changes.

## Pull request checklist

Include the following in the pull request description:

- Problem being solved and linked issue.
- Scope of the change and key design decisions.
- Files/modules changed.
- Tests added or updated.
- Exact verification commands and outcomes.
- Known limitations, partial behavior or environment-specific test gaps.
- API/schema or compatibility impact.
- Documentation updates where public behavior or architecture changed.

A pull request should not be marked ready while it contains unresolved correctness, security or contract questions. Do not merge until required review and checks have completed.

## Documentation changes

Technical documentation must identify the source paths and commit against which statements were verified. Distinguish:

- Implemented and exercised behavior.
- Implemented modules not yet wired into the request path.
- Schema fields that exist but are not populated by the current runtime path.
- Planned work.
- Unsupported behavior.

Trello is the project knowledge index; GitHub Markdown is the version-controlled technical documentation. When a documented statement conflicts with source code or an accepted specification, investigate and correct the document rather than silently changing the code contract.
