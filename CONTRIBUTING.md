# Contributing

Thank you for considering a contribution to the Python Code Intelligence & Performance Workbench. Contributions must preserve the project's static-only analysis boundary and the accepted analyzer/data contracts.

## Before starting

1. Read the issue and confirm the intended behavior with the maintainers.
2. Inspect the current implementation and relevant tests before proposing changes.
3. Identify any accepted mathematical or architecture contract affected by the change.
4. Keep implementation scope narrow. Do not combine unrelated refactors with a feature or fix.

## Winter of Code Social (WOCS) 2026 Workflow

This repository participates in **[Winter of Code Social (WOCS) 2026](https://woc.codesocial.tech/)**, an open-source mentorship initiative organised by Code Social. All WOCS participants must follow these specific procedures:

### Automated Issue Assignment Bot & Commands

To streamline contributor onboarding while preserving fair access to tasks, this repository operates an automated maintainer bot for issue assignment and governance:

| Command | Allowed On | Description |
|---|---|---|
| `/claim` | Issue Comments | Request assignment for an unassigned, open WOCS issue. |
| `/assign` | Issue Comments | Exact alias for `/claim`. |
| `/unclaim` | Issue Comments | Release your current assignment on the issue so others may claim it. |
| `/status` | Issue Comments | Display the current assignee, WOCS eligibility, and claim availability. |
| `/help` | Issue / PR Comments | Display the full list of available automation commands. |

#### Assignment Rules & Policies
1. **Single-Contributor Assignment Guarantee:** Every issue is assigned to **at most one** contributor. Concurrent claim requests are serialized via repository-wide concurrency; once a contributor is confirmed as the assignee, further claim requests are politely rejected.
2. **Two Active WOCS Issues Limit:** To prevent task hoarding and ensure fair distribution, contributors may have at most **two active WOCS issues** assigned simultaneously across the repository. If you currently hold two assigned open WOCS issues, your `/claim` command will be rejected until you complete or `/unclaim` one of them.
3. **WOCS Eligibility Pre-Conditions:** An issue can only be claimed via `/claim` or `/assign` if:
   - The issue is currently **open** and **unlocked**.
   - The issue has the exact `wocs` label.
   - The issue has **exactly one** approved difficulty level label (`level 1`, `level 2`, or `level 3`).
   - The issue has no current assignee.
4. **Wait for Formal Confirmation:** **Do not start coding before assignment confirmation.** You are not authorized to begin work until the automation bot replies with a confirmation comment confirming that your issue claim has been approved. Pull requests submitted without an active assignment will not be reviewed.
5. **Releasing an Issue (`/unclaim`):** If you are unable to complete an assigned issue within a reasonable timeframe, comment `/unclaim` on the issue to release it for other contributors. Only the currently assigned contributor or a repository maintainer can release an assignment.

### Issue Claiming and Assignment
- **Inspect discussions:** Review the open issue and any existing comments before requesting assignment.
- **Request assignment:** Comment on the issue with `/claim` or `/assign`, accompanied by a brief outline of your proposed technical approach or reproduction plan.
- **Wait for confirmation:** Wait for the bot's confirmation comment and GitHub's assignee list to reflect your assignment before creating your branch.
- **Issue limits:** Strictly observe the maximum limit of two active WOCS issues.
- **Releasing issues:** Use `/unclaim` promptly if you encounter blockers or cannot finish the task.

### Git and Branching Workflow
- **Do not work directly on `main`.**
- Each assigned issue must be handled on its own dedicated branch created from the latest `origin/main`.
- Use the standard branch prefixes:
  - `feat/<short-description>` for new features
  - `fix/<short-description>` for bug fixes
  - `test/<short-description>` for tests
  - `docs/<short-description>` for documentation
  - `refactor/<short-description>` for behavior-preserving refactors

### Pull Request Submission
Every pull request must:
- Link the assigned issue in the description (e.g., `Closes #123`).
- Clearly explain the problem addressed, changes introduced, and design decisions made.
- Provide the exact verification commands executed and recorded outcomes.
- Include unit, regression, or metamorphic tests verifying the change.
- List any known limitations, partial behaviors, or environment constraints.
- **UI Screenshots:** Any modification altering the frontend user interface, layout, or visual styling must include before/after screenshots or recordings.
- Update relevant documentation if public behavior or contracts changed.

### WOCS Issue and PR Labels
The project tracks and evaluates contributions using the following exact labels:
- `wocs`
- `level 1`
- `level 2`
- `level 3`

Every eligible pull request requires the `wocs` label and **exactly one** difficulty label (`level 1`, `level 2`, or `level 3`) applied before it is merged.

> **Important:**
> The difficulty level is evaluated and assigned **solely by the Project Admin or Mentor** upon code review based on the actual complexity, scope, and technical depth of the contribution.
> Contributors must **not** self-assign difficulty labels or promise/assume leaderboard points.

### Responsible AI Usage Policy
AI-assisted contributions (using tools such as Gemini, ChatGPT, Claude, Copilot, or Cursor) are permitted with restrictions:
- **Full Contributor Ownership:** Contributors remain solely responsible for every submitted line of code, comment, and documentation. You must thoroughly understand and be able to explain all submitted logic during review.
- **Human Verification & Testing:** AI-suggested code must be reviewed and tested locally. Do not submit unverified outputs.
- **Mandatory Disclosure:** Material AI assistance must be disclosed in the pull request description (via the PR template's AI disclosure section).
- **Prohibition on Low-Effort / Mass-Generated PRs:** Unverified, mass-generated, copied, or low-effort AI contributions are strictly prohibited and will be rejected.
- **Privacy & Secret Hygiene:** Never submit repository secrets, credentials, environment variables, or private data to external AI models.
- **Invariants Preservation:** All contributions must strictly preserve the workbench's zero-execution static analysis boundary (no `eval`, `exec`, or dynamic tracing) and mathematical immutability guarantees.

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

- Problem being solved and linked assigned issue.
- Confirmation of prior issue assignment.
- Scope of the change and key design decisions.
- Files/modules changed.
- Tests added or updated.
- Exact verification commands and outcomes.
- Known limitations, partial behavior or environment-specific test gaps.
- UI screenshots or recordings for any visual/frontend modifications.
- AI assistance disclosure, if applicable.
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

## License for Contributions

By intentionally submitting a contribution for inclusion in this repository, you agree that the contribution is made available under the same MIT License that applies to the project. You retain copyright ownership of your original contribution; this is not a copyright assignment.

Contributors must have the necessary rights and permissions to submit their work. You must not submit copied or third-party material without appropriate authorization and license compliance. Contributions must preserve applicable existing third-party copyright and license notices.
