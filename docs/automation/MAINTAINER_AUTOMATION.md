# GitHub Maintainer Automation & Repository Governance

This document describes the design, architecture, security model, and operational procedures for the GitHub Actions maintainer automation system implemented in `KartikeyG-world/pycode-intelligence-workbench`.

The automation system supports **Winter of Code Social (WOCS) 2026** participation, eliminates manual administration of contributor onboarding and issue assignment, enforces pull-request contribution policies, runs comprehensive multi-version CI, and isolates privileged reporting operations.

---

## 1. System Architecture

The automation system is constructed exclusively from native GitHub Actions, the GitHub REST API (v2022-11-28), and zero-dependency Node.js ES modules. It introduces no external bot servers, databases, webhooks, or personal access tokens (PATs).

```text
                                  GitHub Events
                                        |
       +--------------------+-----------+-----------+--------------------+
       |                    |                       |                    |
       v                    v                       v                    v
  issues.opened      issue_comment.created    pull_request.*       workflow_run.completed
       |                    |                       |                    |
       v                    v                       v                    v
 [issue-intake.yml]  [issue-commands.yml]   [pull-request-ci.yml]  [pull-request-summary.yml]
       |                    |               [pull-request-policy.yml]    |
       |                    |                       |                    |
       |                    +--- /claim             |                    |
       |                    +--- /assign            |                    |
       |                    +--- /unclaim           |                    |
       |                    +--- /status            |                    |
       |                    +--- /help              |                    |
       |                    +--- /level 1/2/3       |                    |
       |                            |               |                    |
       v                            v               v                    v
  Post Welcome               Assign / Label    CI & Policy Checks   Update Summary Comment
  Instructions               Idempotently      (Zero Secrets)       (Stable HTML Marker)
```

### Automation Workflows Overview

| Workflow | File | Trigger Event | Primary Purpose | Permissions |
|---|---|---|---|---|
| **Issue Intake** | `.github/workflows/issue-intake.yml` | `issues: [opened]` | Post welcoming comment with assignment & WOCS policies | `issues: write`, `contents: read` |
| **Issue Commands** | `.github/workflows/issue-commands.yml` | `issue_comment: [created]` | Process `/claim`, `/assign`, `/unclaim`, `/status`, `/help`, and maintainer `/level` | `issues: write`, `pull-requests: write`, `contents: read`, `actions: write` |
| **Pull Request CI** | `.github/workflows/pull-request-ci.yml` | `pull_request: [opened, synchronize, reopened, ready_for_review]` | Run backend test matrices (Python 3.11, 3.13) & frontend checks (lint, tsc, build) | `contents: read` |
| **Pull Request Policy** | `.github/workflows/pull-request-policy.yml` | `pull_request_target: [opened, synchronize, reopened, edited, ready_for_review]`, `workflow_dispatch: [pr_number]` | Enforce branch target, issue linkage, assignment, AI disclosure, and WOCS labels from trusted base ref | `contents: read`, `pull-requests: read`, `issues: read`, `statuses: write` |
| **Pull Request Summary** | `.github/workflows/pull-request-summary.yml` | `workflow_run: [completed]` on PR CI | Post/update a single consolidated CI summary comment on the pull request with hardened job validation | `pull-requests: write`, `issues: write`, `actions: read`, `contents: read` |

---

## 2. Supported Commands & Usage

Commands are parsed with strict token-level matching. Commands embedded in ordinary discussion text, blockquotes, or markdown code blocks are ignored.

### Contributor Commands (Issue Comments Only)

#### `/claim` or `/assign`
- **Action:** Requests formal assignment for the issue.
- **Pre-conditions Verified Before Assignment:**
  1. The issue is currently open and unlocked.
  2. The issue has the exact `wocs` label.
  3. The issue has exactly one approved difficulty label (`level 1`, `level 2`, or `level 3`).
  4. The issue has no current assignee.
  5. The requesting contributor does not already hold **more than two active assigned WOCS issues** in this repository.
  6. The user is assignable via GitHub API.
- **Single-Contributor Concurrency Guarantee:** Uses a per-issue GitHub Actions concurrency group with `queue: max` and `cancel-in-progress: false`. This configures GitHub Actions' FIFO run queue (retaining up to 100 queued assignment requests without dropping intermediate requests). The latest issue state is re-fetched before assignment, the assignment API call is executed, and the updated issue state is re-fetched and verified. If another contributor won an assignment race while a request was queued, the second claim is politely rejected without overwriting the assignment.
- **Paginated Active Issue Limit Check:** Queries the GitHub REST API across all pages (100 items per page) to count active open WOCS issues assigned to the requester, strictly excluding pull requests and non-WOCS tasks.

#### `/unclaim`
- **Action:** Releases the assignment of the currently assigned contributor.
- **Rules:**
  - Only the currently assigned contributor can unclaim themselves.
  - Unclaim attempts by non-assignees are rejected.
  - Re-fetches state before and after unassignment to confirm completion.

#### `/status`
- **Action:** Reports issue state, lock status, current assignee, WOCS label presence, difficulty level, and whether the issue is open for claiming (with reasons if blocked).
- **Requester Eligibility Reporting:** Separately reports the requester's personal claim eligibility under the 2-active-WOCS-issue limit, clearly distinguishing issue availability from personal quota status.

#### `/help`
- **Action:** Displays command usage instructions and policy reminders.

### Maintainer-Only Commands (Pull Request Comments Only)

#### `/level 1`, `/level 2`, `/level 3`
- **Action:** Sets the WOCS difficulty label on an eligible pull request.
- **Permission Verification:** The command author's actual repository permission is verified via the GitHub Collaborators API (`admin`, `maintain`, `write`, or authorized `triage`). Unprivileged users are rejected.
- **Label Synchronization:**
  1. Identifies the linked issue from the PR body (e.g. `Closes #123`).
  2. Verifies the linked issue has `wocs` and is assigned to the PR author.
  3. Adds the exact `wocs` label and `level <X>` to the PR.
  4. Removes conflicting difficulty labels (`level 1`, `level 2`, or `level 3` if different).
  5. **Automated Policy Re-Evaluation:** Triggers a `workflow_dispatch` of `pull-request-policy.yml` targeting the PR number so the policy check is automatically re-evaluated without requiring an empty commit or manual workflow re-run.
  6. Publishes a confirmation comment indicating label update and policy dispatch status.

---

## 3. Pull Request Policy Rules

The `Pull Request Policy` workflow (`.github/workflows/pull-request-policy.yml`) enforces repository invariants and WOCS compliance:

1. **Target Branch:** Pull requests must target `main`.
2. **Draft PR Handling:** Draft pull requests skip strict body and label validation until marked "Ready for review".
3. **Linked Issue:** Must contain a standard GitHub closing keyword linking an open issue (`Closes #123`, `Fixes #123`, `Resolves #123`).
4. **Assignment Verification:** The linked issue must currently be assigned to the pull request author.
5. **Issue Assignment Confirmation:** The PR template checkbox `- [x] I confirm that this issue was formally assigned to me...` must be checked.
6. **AI Assistance Disclosure:**
   - Exactly one of `- [x] No` or `- [x] Yes` must be selected.
   - Both ownership sub-confirmations must be checked.
7. **Technical Description:** Non-empty `Problem Addressed` and `Summary of Changes` sections (placeholder comments stripped).
8. **Verification Evidence:** Non-empty `Verification Commands & Environment` code block.
9. **WOCS Labels:** For PRs linked to WOCS issues, the PR must have `wocs` and exactly one of `level 1`, `level 2`, or `level 3`. If missing, an actionable check failure directs maintainers to comment `/level <1|2|3>`.
10. **Owner-Authored Maintenance Exemption:** A narrow, deliberate exception exists exclusively for the repository owner (`author_association === 'OWNER'`) when submitting non-WOCS administrative or infrastructure maintenance PRs. Under this exemption:
    - Target branch (`main`), AI disclosure, technical description, and verification sections remain strictly enforced.
    - Linked issue reference and contributor assignment confirmation checkboxes are waived with informative workflow annotations.
    - Full policy enforcement remains strictly non-negotiable for all external contributors, collaborators, and any WOCS-labeled pull request.

---

## 4. Security Model & Invariants

1. **Token Principle:** All workflows use the short-lived, repository-scoped `GITHUB_TOKEN` secret. No personal access tokens (PATs) or long-lived credentials are used.
2. **Read-Only Fork PRs:** Pull request CI runs under the safe `pull_request` event. Fork PRs receive a read-only token with zero repository secrets exposed.
3. **Hardened Policy Execution (`pull_request_target`):** The `Pull Request Policy` workflow runs under `pull_request_target` to ensure policy definitions and verification scripts execute exclusively from the trusted base branch (`ref: ${{ github.base_ref || github.event.repository.default_branch }}`). Security invariants:
   - Untrusted PR head code is **never** checked out.
   - Contributor-controlled scripts, packages, or binaries are never executed.
   - PR metadata is ingested strictly via trusted GitHub API endpoints.
   - The workflow uses explicit least-privilege permissions (`contents: read`, `pull-requests: read`, `issues: read`, `statuses: write`).
4. **Privileged Summary Isolation:** The automated summary comment workflow uses `workflow_run` (which runs in the default branch context). It:
   - Does not check out PR code.
   - Does not run PR scripts or commands.
   - Does not download or execute untrusted workflow artifacts.
   - Relies strictly on trusted GitHub API metadata and hardened job conclusion verification.
5. **Action Pinning & Node 24 Runtime:** All external GitHub Actions are pinned to full-length 40-character commit SHAs with semantic tag comments. Actions are upgraded to Node 24-compatible releases (`actions/checkout@v7.0.1`, `actions/setup-node@v7.1.0`, `actions/setup-python@v7.1.0`, `astral-sh/setup-uv@v10.4.0`) ahead of GitHub's scheduled Node 20 runner deprecation.
6. **No Shell Code Interpolation:** Untrusted comment text and issue bodies are never interpolated into shell scripts (`run: ... ${{ github.event... }}`). All dynamic payloads are accessed via Node.js parsing `process.env.GITHUB_EVENT_PATH`.

---

## 5. Recommended GitHub Repository Configuration

After deploying these workflows, configure the following settings in GitHub:

### A. Workflow Permissions
Navigate to **Settings > Actions > General > Workflow permissions**:
- Select **Read and write permissions** (required for `GITHUB_TOKEN` to assign issues, manage labels, and post comments).
- Ensure **Allow GitHub Actions to create and approve pull requests** remains unchecked (maintains manual maintainer approval boundary).

### B. Branch Protection Rules for `main`
Navigate to **Settings > Branches** (or **Rulesets > New ruleset**) for `main`:
1. **Require a pull request before merging:**
   - Require 1 approving review.
   - Dismiss stale pull request approvals when new commits are pushed.
   - Require review from Code Owners (if applicable).
2. **Require status checks to pass before merging:**
   - Require branches to be up to date before merging.
   - Required status checks (wait until initial run completes on GitHub):
     - `Backend Validation (Python 3.11)`
     - `Backend Validation (Python 3.13)`
     - `Frontend Validation (Lint, Typecheck, Build)`
     - `Validate Contribution & WOCS Policy`
3. **Block force pushes:** Enabled.
4. **Prevent branch deletion:** Enabled.
5. **Require conversation resolution before merging:** Enabled.

---

## 6. Maintainer Review & WOCS Scoring Procedure

1. **Review Issue Assignment:** Verify that the PR contributor claimed and was assigned to the linked issue before submitting code.
2. **Review Static Boundaries:** Confirm that submitted code preserves the zero-execution static analysis boundary (no `eval`, `exec`, runtime profiling, or process spawning).
3. **Verify CI Status:** Confirm that backend tests (Python 3.11 & 3.13) and frontend lint/tsc/build checks passed.
4. **Evaluate Difficulty:** Inspect the actual complexity and scope of the contribution.
5. **Apply Level:** Comment `/level 1`, `/level 2`, or `/level 3` on the PR. The bot will apply labels and resolve the policy gate.
6. **Merge:** Merge the pull request using GitHub's merge interface (Squash and Merge recommended for atomic feature history).

---

## 7. Frontend Dependency Security Audit & Maintenance Pathway

A security audit of the repository's frontend dependencies (`frontend/package.json`) identified 13 known vulnerabilities (2 low, 7 moderate, 3 high, 1 critical):

| Package | Severity | Issue / Advisory | Direct vs Transitive | Root Cause & Context |
|---|---|---|---|---|
| `next` (`16.3.6`) | Critical / High | CVE-2024-34351, GHSA-fr5h-rqp8-gw9v (SSRF in Image Optimization, RCE in Image Optimization / SVG, cache poisoning) | Direct | Pinned Next.js version in `package.json` |
| `dompurify` | Moderate | Nested DOM clobbering | Transitive | Introduced via `@xyflow/react` |
| `minimatch` | High | ReDoS in path globbing | Transitive | Introduced via `eslint` / `glob` |
| `sharp` | Moderate | Memory exhaustion on malformed buffers | Transitive | Introduced via Next.js image optimization |
| `source-map-js` | Moderate | Prototype pollution in parser | Transitive | Introduced via `postcss` / `tailwindcss` |
| `zod` | Low | ReDoS in regex schema validation | Transitive | Internal Next.js dependency |

### Remediation Guidance & Boundary
- **Separation of Concerns:** Remediating application dependencies is decoupled from maintainer workflow automation to prevent regression in production bundle semantics.
- **Recommended Action:** Upgrade Next.js to `>= 16.4.5` (or latest stable) and run `npm audit fix` in a dedicated, isolated pull request following PR #29 merge.
- **Verification:** Any future dependency bump must run `npm run lint`, `npx tsc --noEmit`, and `npm run build` across all 4 viewports.
