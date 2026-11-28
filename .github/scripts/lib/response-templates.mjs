/**
 * Response templates for GitHub maintainer automation bot.
 * Standardizes all automated responses across issues and pull requests.
 */

export const MARKERS = {
  ISSUE_INTAKE: '<!-- pycode-workbench-issue-intake -->',
  PR_CI_SUMMARY: '<!-- pycode-pr-ci-summary -->'
};

/**
 * Welcome response for newly opened issues.
 * @param {string} username - Issue author login
 * @param {string} owner - Repository owner
 * @param {string} repo - Repository name
 * @returns {string} Markdown formatted comment body
 */
export function welcomeIssue(username, owner, repo) {
  const contributingUrl = `https://github.com/${owner}/${repo}/blob/main/CONTRIBUTING.md`;

  return `${MARKERS.ISSUE_INTAKE}
👋 Welcome @${username} to the **Python Code Intelligence & Performance Workbench**! Thank you for opening this issue.

### 📌 Issue Assignment Policy & How to Claim
- **Wait for formal assignment:** To ensure coordinated development, **do not begin implementation before an issue is formally assigned** to you. Pull requests submitted without an active assignment will not be reviewed.
- **Requesting assignment:** If you would like to work on this issue, please comment \`/claim\` or \`/assign\` below.
- **Eligibility:** Issues eligible for Winter of Code Social (WOCS) must carry the \`wocs\` label and exactly one difficulty level (\`level 1\`, \`level 2\`, or \`level 3\`). Each contributor may have at most **two active WOCS issues** assigned concurrently.

### 📋 Contribution Guidelines
- Please review our [Contribution Guidelines](${contributingUrl}) before starting.
- **Testing & Verification:** All changes require verifiable tests (backend pytest or frontend lint/typecheck/build) preserving our zero-execution static analysis boundary.
- **Responsible AI Usage:** Any use of AI tools must be disclosed in the pull request template, and contributors must personally understand and verify all submitted code.

Happy contributing! 🚀`;
}

/**
 * B3. Successful assignment message.
 * @param {string} username - Assigned user login
 * @param {string} owner - Repository owner
 * @param {string} repo - Repository name
 * @returns {string} Markdown formatted comment body
 */
export function successfulAssignment(username, owner, repo) {
  const contributingUrl = `https://github.com/${owner}/${repo}/blob/main/CONTRIBUTING.md`;

  return `Hi @${username}!

Your issue claim has been successfully approved.

You are now the assigned contributor for this issue.

Please review [CONTRIBUTING.md](${contributingUrl}), create a dedicated feature/fix branch from the latest main, and follow the repository's testing and pull-request requirements.

Please link this issue in your eventual pull request.

Happy contributing!`;
}

/**
 * B4. Existing assignee response.
 * @param {string} assignee - Current assignee login
 * @returns {string} Markdown formatted comment body
 */
export function alreadyAssigned(assignee) {
  return `This issue has already been assigned to @${assignee}.

To ensure fair contribution distribution, this issue is currently not accepting additional assignments.

Please explore other open issues.`;
}

/**
 * B5. Unassign response when successfully unassigned.
 * @param {string} username - User login unassigned
 * @returns {string} Markdown formatted comment body
 */
export function unassignSuccess(username) {
  return `Hi @${username}, you have been unassigned from this issue.

The issue is now available for other contributors to claim.`;
}

/**
 * B5. Unassign response when user is not the assignee.
 * @param {string} username - User login attempting unassign
 * @returns {string} Markdown formatted comment body
 */
export function unassignNotAssignee(username) {
  return `Hi @${username}, you cannot unclaim this issue because it is not currently assigned to you.`;
}

/**
 * Response when issue cannot be claimed due to WOCS eligibility rules.
 * @param {string} reason - Detailed explanation of why issue is ineligible
 * @returns {string} Markdown formatted comment body
 */
export function issueNotClaimable(reason) {
  return `This issue cannot be claimed at this time:

${reason}

Please consult [CONTRIBUTING.md](https://github.com/KartikeyG-world/pycode-intelligence-workbench/blob/main/CONTRIBUTING.md) for full WOCS eligibility guidelines.`;
}

/**
 * Response when contributor has reached maximum active WOCS issues limit.
 * @param {string} username - Contributor login
 * @param {number} activeCount - Current active WOCS issues count
 * @returns {string} Markdown formatted comment body
 */
export function maxIssuesReached(username, activeCount) {
  return `Hi @${username}, you currently have ${activeCount} active WOCS issue(s) assigned in this repository.

To ensure equitable distribution of contributions across all participants, contributors may have at most **two active WOCS issues** assigned simultaneously.

Please complete or release your existing assigned issue(s) before requesting a new assignment.`;
}

/**
 * B6. Help command response.
 * @returns {string} Markdown formatted comment body
 */
export function helpResponse() {
  return `### 🤖 Workbench Maintainer Bot Commands

**Contributor Commands (Issue Comments):**
- \`/claim\` or \`/assign\` — Request assignment for an open, unassigned WOCS issue.
- \`/unclaim\` — Release your current assignment on this issue.
- \`/status\` — View the current assignment status and WOCS eligibility of this issue.
- \`/help\` — Display this help message.

**Maintainer-Only Commands (Pull Request Comments):**
- \`/level 1\` — Assign WOCS difficulty Level 1 to the pull request.
- \`/level 2\` — Assign WOCS difficulty Level 2 to the pull request.
- \`/level 3\` — Assign WOCS difficulty Level 3 to the pull request.

*Note: Work must not begin before formal assignment confirmation.*`;
}

/**
 * B7. Status command response.
 * @param {object} status - Status details object
 * @returns {string} Markdown formatted comment body
 */
export function statusResponse({ state, locked, assignees, isWocs, difficultyLevels, canClaim, claimBlockReason }) {
  const assigneeStr = assignees && assignees.length > 0 
    ? assignees.map(a => `@${a}`).join(', ') 
    : '_None (Unassigned)_';

  const wocsBadge = isWocs ? '✅ Yes (`wocs`)' : '❌ No (Missing `wocs` label)';
  const levelsBadge = difficultyLevels.length === 1 
    ? `✅ \`${difficultyLevels[0]}\`` 
    : (difficultyLevels.length === 0 ? '❌ None' : `⚠️ Multiple (\`${difficultyLevels.join(', ')}\`)`);

  const availabilityStr = canClaim 
    ? '✅ **Available for claiming** (\`/claim\` or \`/assign\`)' 
    : `❌ **Not available for claiming** (${claimBlockReason || 'Requirements not met'})`;

  return `### 📊 Issue Status & WOCS Eligibility

- **State:** \`${state}\`${locked ? ' *(Locked)*' : ''}
- **Current Assignee(s):** ${assigneeStr}
- **WOCS Label:** ${wocsBadge}
- **Difficulty Level:** ${levelsBadge}
- **Assignment Availability:** ${availabilityStr}`;
}

/**
 * Module C. Level assignment success response.
 * @param {string} maintainer - Maintainer login
 * @param {string} level - Level applied (e.g., '1', '2', '3')
 * @returns {string} Markdown formatted comment body
 */
export function levelSuccess(maintainer, level) {
  return `✅ WOCS difficulty level successfully set to **level ${level}** by @${maintainer}.

Labels updated: \`wocs\`, \`level ${level}\`.`;
}

/**
 * Module C. Unauthorized level command attempt response.
 * @param {string} username - User login
 * @returns {string} Markdown formatted comment body
 */
export function levelUnauthorized(username) {
  return `Hi @${username}, you do not have permission to set WOCS difficulty levels.

The \`/level\` command is restricted to repository maintainers and authorized mentors.`;
}

/**
 * Module C. Level command run on issue rather than PR.
 * @returns {string} Markdown formatted comment body
 */
export function levelNotPr() {
  return `The \`/level\` command can only be used on pull request conversations by authorized maintainers.`;
}

/**
 * Module C. Level command invalid syntax.
 * @returns {string} Markdown formatted comment body
 */
export function levelInvalidSyntax() {
  return `Invalid command syntax. Please use \`/level 1\`, \`/level 2\`, or \`/level 3\`.`;
}

/**
 * Module C. Level command rejected due to linked issue problem.
 * @param {string} reason - Detailed explanation
 * @returns {string} Markdown formatted comment body
 */
export function levelInvalidIssue(reason) {
  return `⚠️ Cannot apply WOCS level to this pull request:

${reason}`;
}
