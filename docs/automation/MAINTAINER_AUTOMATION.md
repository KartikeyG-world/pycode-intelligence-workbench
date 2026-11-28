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
| **Pull Request CI** | `.github/workflows/pull-request-ci.yml` | `pull_request: [opened, synchronize, reopened, ready_for_review]` | Run backend test matrices (Python 3.11, 3.13), frontend checks (lint, tsc, build), and maintainer automation tests | `contents: read` |
| **Pull Request Policy** | `.github/workflows/pull-request-policy.yml` | `pull_request_target: [opened, synchronize, reopened, edited, ready_for_review]`, `workflow_dispatch: [pr_number]` | Enforce branch target, issue linkage, assignment, AI disclosure, and WOCS labels from trusted base ref (fails closed on API error) | `contents: read`, `pull-requests: read`, `issues: read`, `statuses: write` |
| **Pull Request Summary** | `.github/workflows/pull-request-summary.yml` | `workflow_run: [completed]` on PR CI | Post/update a single consolidated CI summary comment on the pull request with strict 4-job validation and paginated comment search | `pull-requests: write`, `issues: write`, `actions: read`, `contents: read` |

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
- **Cross-Issue & Single-Contributor Concurrency Guarantee:** Uses a single repository-wide GitHub Actions concurrency group (`group: issue-commands-${{ github.repository }}`) configured with `queue: max` and `cancel-in-progress: false`.
  - **Cross-Issue Protection:** Because the queue is serialized at the repository level rather than per-issue, simultaneous claims submitted by the same contributor on different issues (e.g. `/claim` on #40 and `/claim` on #41) cannot race or bypass the 2-active-WOCS-issue limit. The second request is queued until the first completes its assignment and database update, ensuring the second request re-evaluates the fresh quota and is rejected.
  - **Verification Flow:** The bot re-fetches the issue state, verifies that no assignee exists, queries the contributor's paginated active WOCS issue list across all pages (100 items per page, excluding PRs), executes the assignment API call, and verifies the final updated assignee list.
  - **Operational Trade-Offs & Queue Limits:**
    - GitHub Actions queues up to 100 pending workflow runs in FIFO order. If high burst traffic exceeds 100 pending runs, additional runs may be dropped or cancelled by GitHub.
    - All command traffic across the repository (claims, unclaims, status queries, level assignments) is processed sequentially. Given the project's scale, per-command execution takes ~10–15 seconds, providing responsive sequential throughput.
    - **Not an Atomic Database Transaction:** GitHub Actions runs independently of GitHub's internal database locks. If a maintainer manually assigns a contributor via the GitHub web UI while a bot claim is in flight, the bot detects this during post-assignment verification and gracefully fails with an informative rejection message without overwriting the assignment.
- **Paginated Active Issue Limit Check:** Queries the GitHub REST API across all pages (`per_page=100`) to count active open WOCS issues assigned to the requester, strictly excluding pull requests and non-WOCS tasks.

#### `/unclaim`
- **Action:** Releases the assignment of the currently assigned contributor.
- **Rules:**
  - Only the currently assigned contributor can unclaim themselves.
  - Unclaim attempts by non-assignees are rejected.
  - Serialized via the same repository-wide concurrency queue so simultaneous claims and unclaims cannot invalidate quota checks.
  - Re-fetches state before and after unassignment to confirm completion.

#### `/status`
- **Action:** Reports issue state, lock status, current assignee, WOCS label presence, difficulty level, and whether the issue is open for claiming (with reasons if blocked).
- **Requester Eligibility Reporting:** Separately reports the requester's personal claim eligibility under the 2-active-WOCS-issue limit, clearly distinguishing issue availability from personal quota status.

#### `/help`
- **Action:** Displays command usage instructions and policy reminders.

### Maintainer-Only Commands (Pull Request Comments Only)

#### `/level 1`, `/level 2`, `/level 3`
- **Action:** Sets the WOCS difficulty label on an eligible pull request.
- **Permission Verification:** The command author's actual repository permission is verified via the GitHub Collaborators API.
  - Default authorized roles: `admin`, `maintain`, and `write`.
  - Collaborators with `triage` permissions are **not** authorized by default to assign WOCS levels, preventing unauthorized scoring. Triage authorization requires explicit repository configuration (`allowTriageRole: true` or environment variable `ALLOW_TRIAGE_WOCS_LEVEL=true`).
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
   - Relies strictly on trusted GitHub API metadata and hardened job conclusion verification across all 4 expected jobs.
   - Implements paginated comment searching across all pages and fails closed if comment retrieval fails (preventing duplicate comment spam).
5. **Action Pinning & Node 24 Runtime:** All external GitHub Actions are pinned to full-length 40-character commit SHAs with semantic tag comments. Actions are upgraded to Node 24-compatible releases (`actions/checkout@v7.0.1`, `actions/setup-node@v7.1.0`, `actions/setup-python@v7.1.0`, `astral-sh/setup-uv@v10.4.0`) ahead of GitHub's scheduled Node 20 runner deprecation.
6. **No Shell Code Interpolation:** Untrusted comment text and issue bodies are never interpolated into shell scripts (`run: ... ${{ github.event... }}`). All dynamic payloads are accessed via Node.js parsing `process.env.GITHUB_EVENT_PATH`.

### Token Permissions Audit Across Workflows

Every workflow enforces explicit least-privilege permissions without repository administration privileges or personal access tokens (PATs):

| Workflow | Explicit Permissions Declared | Privilege Justification |
|---|---|---|
| `issue-intake.yml` | `contents: read`, `issues: write` | Post welcoming comment on new issues. |
| `issue-commands.yml` | `contents: read`, `issues: write`, `pull-requests: write`, `actions: write` | Assign issues, update PR labels, and dispatch `pull-request-policy.yml` upon `/level` command. `actions: write` is strictly required by the GitHub Actions API for `workflow_dispatch`. |
| `pull-request-ci.yml` | `contents: read` | Read-only matrix CI execution across Python 3.11/3.13, frontend, and maintainer automation tests. |
| `pull-request-policy.yml` | `contents: read`, `pull-requests: read`, `issues: read`, `statuses: write` | Read-only policy validation of PR metadata; `statuses: write` allows posting commit status check outcomes. |
| `pull-request-summary.yml` | `contents: read`, `pull-requests: write`, `issues: write`, `actions: read` | Read CI run job conclusions from Actions API and post/update the pinned summary comment. |

---

## 5. Recommended GitHub Repository Configuration & Operational Invariants

After deploying these workflows, configure the following settings in GitHub:

### A. Workflow Permissions & Event Policy
Navigate to **Settings > Actions > General > Workflow permissions**:
- Select **Read and write permissions** (required for `GITHUB_TOKEN` to assign issues, manage labels, and post comments).
- Ensure **Allow GitHub Actions to create and approve pull requests** remains unchecked (maintains manual maintainer approval boundary).
- **GitHub Event Policy Note for `pull_request_target`:** The repository administrator must explicitly check the Actions event-policy configuration in repository Settings before **December 2, 2026** (to verify that `pull_request_target` workflows from default branch are permitted under your organization's policy).

### B. Branch Protection Rules for `main`
Navigate to **Settings > Branches** (or **Rulesets > New ruleset**) for `main`:
1. **Require a pull request before merging:**
   - Require 1 approving review.
   - Dismiss stale pull request approvals when new commits are pushed.
   - Require review from Code Owners (if applicable).
2. **Require status checks to pass before merging:**
   - Require branches to be up to date before merging.
   - Required status checks:
     - `Backend Validation (Python 3.11)`
     - `Backend Validation (Python 3.13)`
     - `Frontend Validation (Lint, Typecheck, Build)`
     - `Maintainer Automation Tests`
     - `Validate Contribution & WOCS Policy`
3. **Block force pushes:** Enabled.
4. **Prevent branch deletion:** Enabled.
5. **Require conversation resolution before merging:** Enabled.

### C. Post-Merge Verification Procedure

Because `pull_request_target` (for policy) and `workflow_run` (for PR summary) execute exclusively from the default branch (`main`), they cannot be triggered by PR events until PR #29 is merged to `main`. After merging PR #29, execute this verification runbook:

1. **Test Policy Workflow Dispatch:**
   Trigger policy evaluation on an existing pull request using the GitHub Actions web UI or CLI:
   ```bash
   gh workflow run pull-request-policy.yml -f pr_number=<PR_NUMBER>
   ```
   Verify that the run completes with green check status.
2. **Test Issue Intake:**
   Open a new test issue. Verify that `issue-intake.yml` automatically posts the welcome comment within 15 seconds.
3. **Test Serialized Claim:**
   Comment `/claim` on an open WOCS test issue. Verify that `issue-commands.yml` processes the request via the repository-wide FIFO queue and assigns the issue.
4. **Test PR Level Assignment & Policy Dispatch:**
   Comment `/level 1` on an eligible pull request. Verify that labels `wocs` and `level 1` are applied and automated policy re-evaluation is dispatched.

---

## 6. Maintainer Review & WOCS Scoring Procedure

1. **Review Issue Assignment:** Verify that the PR contributor claimed and was assigned to the linked issue before submitting code.
2. **Review Static Boundaries:** Confirm that submitted code preserves the zero-execution static analysis boundary (no `eval`, `exec`, runtime profiling, or process spawning).
3. **Verify CI Status:** Confirm that all 4 CI jobs passed (`Backend Validation (Python 3.11)`, `Backend Validation (Python 3.13)`, `Frontend Validation (Lint, Typecheck, Build)`, and `Maintainer Automation Tests`).
4. **Evaluate Difficulty:** Inspect the actual complexity and scope of the contribution.
5. **Apply Level:** Comment `/level 1`, `/level 2`, or `/level 3` on the PR. The bot will apply labels and resolve the policy gate.
6. **Merge:** Merge the pull request using GitHub's merge interface (Squash and Merge recommended for atomic feature history).

---

## 7. Frontend Dependency Security Audit & Maintenance Pathway

A comprehensive security audit of `frontend/package.json` (`npm audit --json`) identified **13 known vulnerabilities** (0 info, 2 low, 7 moderate, 3 high, 1 critical):

> [!WARNING]
> The frontend application is **not vulnerability-free**. Production dependency remediation is intentionally isolated from this maintainer automation PR to preserve frontend build stability and avoid regressions in AST visualization components.

### Verified Vulnerability & Advisory Inventory

| Package | Severity | Exact GHSA / CVE Identifier | Direct vs Transitive | Summary & Impact |
|---|---|---|---|---|
| `next` (`16.3.6`) | **Critical** | [GHSA-8g9c-4865-x492](https://github.com/advisories/GHSA-8g9c-4865-x492) | Direct | SSRF in Next.js Image Optimization (*Note: previous attribution to CVE-2024-34351 was an older Next.js 14 CVE; the actual advisory is GHSA-8g9c-4865-x492*). |
| `next` (`16.3.6`) | **High** | [GHSA-3x5f-x526-w85f](https://github.com/advisories/GHSA-3x5f-x526-w85f) | Direct | RCE in Image Optimization component parsing external SVG files. |
| `next` (`16.3.6`) | **High** | [GHSA-958v-mg94-f2m7](https://github.com/advisories/GHSA-958v-mg94-f2m7) | Direct | RCE in Image Optimization via crafted image payload. |
| `next` (`16.3.6`) | **Moderate** | [GHSA-f3mh-rxg3-f5g2](https://github.com/advisories/GHSA-f3mh-rxg3-f5g2) | Direct | HttpOnly cookie exposure through internal response header on Next.js Edge runtime routes. |
| `next` (`16.3.6`) | **Moderate** | [GHSA-pc58-hwjq-p385](https://github.com/advisories/GHSA-pc58-hwjq-p385) | Direct | Cross-client response injection and disclosure in self-hosted Next.js applications. |
| `next` (`16.3.6`) | **Moderate** | [GHSA-rhh4-g77r-r9qj](https://github.com/advisories/GHSA-rhh4-g77r-r9qj) | Direct | Cross-user cache disclosure and poisoning in Next.js `use cache` with binary arguments. |
| `sharp` (`<0.35.5`) | **High** | [GHSA-wq5f-xc86-pv6w](https://github.com/advisories/GHSA-wq5f-xc86-pv6w) | Transitive (via `next`) | Vulnerability in librsvg dependency (CVE-2026-96889). |
| `source-map-js` (`1.0.0 - 1.2.1`) | **High** | [GHSA-68fv-2mgg-jv7q](https://github.com/advisories/GHSA-68fv-2mgg-jv7q) | Transitive (via `tailwindcss` / `postcss`) | Event-loop denial of service through indexed source-map section offsets (CVSS 7.5). |
| `zod` (`<4.6.6`) | **High** | [GHSA-mrhx-c7xc-m3w5](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5) | Transitive (via `next`) | Memory exhaustion while validating oversized constrained collections (CVSS 7.5). |
| `dompurify` (`<=3.4.16`) | **Low** | [GHSA-p98j-92pf-mc4p](https://github.com/advisories/GHSA-p98j-92pf-mc4p), [GHSA-6688-9rhm-gjv2](https://github.com/advisories/GHSA-6688-9rhm-gjv2), [GHSA-c6gr-qvv4-5v3f](https://github.com/advisories/GHSA-c6gr-qvv4-5v3f), [GHSA-cg2g-xh64-v4q7](https://github.com/advisories/GHSA-cg2g-xh64-v4q7), [GHSA-mrv2-3pqr-j5jr](https://github.com/advisories/GHSA-mrv2-3pqr-j5jr) | Transitive (via `@xyflow/react`) | Detached DOM hooks, force-removed rawtext roots, and SMIL attribute bypasses. |
| `minimatch` / `@typescript-eslint` | **Moderate** | [GHSA-f8q6-p94x-37v3](https://github.com/advisories/GHSA-f8q6-p94x-37v3) | Transitive (dev) | Regular expression denial of service in path glob matching. |

### Remediation Guidance & Dedicated Maintenance PR
- **Recommended Action:** Upgrade Next.js to `>= 16.4.6` in `frontend/package.json` (resolving all direct Next.js advisories and updating transitive `sharp` and `zod`) and run `npm audit fix` in an isolated pull request following the merge of PR #29.
- **Verification Criteria:** The follow-up PR must execute `npm run lint`, `npx tsc --noEmit`, and `npm run build`, and confirm layout rendering across desktop and mobile viewports.
