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
| **Issue Intake** | `.github/workflows/issue-intake.yml` | `issues: [opened]` | Post welcoming comment with assignment & WOCS policies | `issues: write` |
| **Issue Commands** | `.github/workflows/issue-commands.yml` | `issue_comment: [created]` | Process `/claim`, `/assign`, `/unclaim`, `/status`, `/help`, and maintainer `/level` | `issues: write`, `pull-requests: write` |
| **Pull Request CI** | `.github/workflows/pull-request-ci.yml` | `pull_request: [opened, synchronize, reopened, ready_for_review]` | Run backend test matrices (Python 3.11, 3.13) & frontend checks (lint, tsc, build) | `contents: read` |
| **Pull Request Policy** | `.github/workflows/pull-request-policy.yml` | `pull_request: [opened, synchronize, reopened, edited, ready_for_review]` | Enforce branch target, issue linkage, assignment, AI disclosure, and WOCS labels | `contents: read`, `pull-requests: read`, `issues: read` |
| **Pull Request Summary** | `.github/workflows/pull-request-summary.yml` | `workflow_run: [completed]` on PR CI | Post/update a single consolidated CI summary comment on the pull request | `pull-requests: write`, `issues: write`, `actions: read` |

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
- **Single-Contributor Concurrency Guarantee:** Uses a per-issue GitHub Actions concurrency group (`cancel-in-progress: false`). The latest issue state is fetched before assignment, the assignment API call is executed, and the updated issue state is re-fetched and verified. If another contributor won a race condition while the workflow was queued, the second claim is politely rejected without overwriting the assignment.

#### `/unclaim`
- **Action:** Releases the assignment of the currently assigned contributor.
- **Rules:**
  - Only the currently assigned contributor can unclaim themselves.
  - Unclaim attempts by non-assignees are rejected.
  - Re-fetches state before and after unassignment to confirm completion.

#### `/status`
- **Action:** Reports issue state, lock status, current assignee, WOCS label presence, difficulty level, and whether the issue is available for claiming (with reasons if blocked).

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
  5. Publishes a confirmation comment.

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

---

## 4. Security Model & Invariants

1. **Token Principle:** All workflows use the short-lived, repository-scoped `GITHUB_TOKEN` secret. No personal access tokens (PATs) or long-lived credentials are used.
2. **Read-Only Fork PRs:** Pull request CI and policy checks run under the safe `pull_request` event. Fork PRs receive a read-only token with zero repository secrets exposed.
3. **No `pull_request_target`:** The vulnerable `pull_request_target` trigger is deliberately omitted to prevent script injection and untrusted code execution in privileged contexts.
4. **Privileged Summary Isolation:** The automated summary comment workflow uses `workflow_run` (which runs in the default branch context). It:
   - Does not check out PR code.
   - Does not run PR scripts or commands.
   - Does not download or execute untrusted workflow artifacts.
   - Relies strictly on trusted GitHub API metadata.
5. **Action Pinning:** All external GitHub Actions are pinned to full-length, immutable commit SHAs with semantic tag comments (e.g., `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2`).
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
