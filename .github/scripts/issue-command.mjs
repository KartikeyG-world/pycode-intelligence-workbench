/**
 * Main issue and pull request command processor for GitHub Actions.
 * Handles /claim, /assign, /unclaim, /help, /status, and maintainer /level commands.
 *
 * Implements hardened pagination, single-contributor concurrency verification,
 * and reliable policy re-evaluation dispatch.
 */

import { parseCommand, extractLinkedIssueNumber } from './lib/command-parser.mjs';
import * as templates from './lib/response-templates.mjs';

const AUTHORIZED_ROLES = ['admin', 'maintain', 'write', 'triage'];
const VALID_LEVELS = ['1', '2', '3'];

/**
 * Creates an authenticated GitHub REST API client using fetch.
 *
 * @param {string} token - GITHUB_TOKEN
 * @param {string} repoFull - 'owner/repo'
 * @param {typeof fetch} [fetchFn] - Optional fetch implementation for testing
 * @returns {object} API helper methods
 */
export function createGitHubClient(token, repoFull, fetchFn = globalThis.fetch) {
  const [owner, repo] = repoFull.split('/');
  const baseUrl = 'https://api.github.com';
  const headers = {
    'Accept': 'application/vnd.github+json',
    'Authorization': `Bearer ${token}`,
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'pycode-maintainer-automation'
  };

  async function request(path, options = {}) {
    const url = path.startsWith('http') ? path : `${baseUrl}${path}`;
    const res = await fetchFn(url, {
      ...options,
      headers: {
        ...headers,
        ...(options.headers || {})
      }
    });

    if (res.status === 204) {
      return null;
    }

    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const error = new Error(`GitHub API error ${res.status}: ${JSON.stringify(data)}`);
      error.status = res.status;
      error.data = data;
      throw error;
    }
    return data;
  }

  return {
    owner,
    repo,
    async getIssue(issueNumber) {
      return request(`/repos/${owner}/${repo}/issues/${issueNumber}`);
    },
    async createComment(issueNumber, body) {
      return request(`/repos/${owner}/${repo}/issues/${issueNumber}/comments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ body })
      });
    },
    async addAssignees(issueNumber, assignees) {
      return request(`/repos/${owner}/${repo}/issues/${issueNumber}/assignees`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assignees })
      });
    },
    async removeAssignees(issueNumber, assignees) {
      return request(`/repos/${owner}/${repo}/issues/${issueNumber}/assignees`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assignees })
      });
    },
    /**
     * Paginates through all open issues assigned to a username to count active WOCS issues.
     * Excludes pull requests and non-WOCS issues.
     */
    async listOpenWocsIssuesForAssignee(username) {
      const allWocsIssues = [];
      let page = 1;
      const perPage = 100;

      while (true) {
        let issues;
        try {
          issues = await request(`/repos/${owner}/${repo}/issues?state=open&assignee=${encodeURIComponent(username)}&per_page=${perPage}&page=${page}`);
        } catch (err) {
          throw new Error(`Failed to query open issues for @${username} on page ${page}: ${err.message}`);
        }

        if (!Array.isArray(issues) || issues.length === 0) {
          break;
        }

        for (const item of issues) {
          if (item.pull_request) continue;
          const labels = item.labels || [];
          const hasWocs = labels.some(l => (typeof l === 'string' ? l : l.name) === 'wocs');
          if (hasWocs) {
            allWocsIssues.push(item);
          }
        }

        if (issues.length < perPage) {
          break;
        }
        page++;
      }

      return allWocsIssues;
    },
    async getCollaboratorPermission(username) {
      try {
        const data = await request(`/repos/${owner}/${repo}/collaborators/${encodeURIComponent(username)}/permission`);
        return data.permission || data.role_name || 'none';
      } catch (err) {
        if (err.status === 404) return 'none';
        throw err;
      }
    },
    async getPullRequest(prNumber) {
      return request(`/repos/${owner}/${repo}/pulls/${prNumber}`);
    },
    async addLabels(issueNumber, labels) {
      return request(`/repos/${owner}/${repo}/issues/${issueNumber}/labels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ labels })
      });
    },
    async removeLabel(issueNumber, labelName) {
      try {
        return await request(`/repos/${owner}/${repo}/issues/${issueNumber}/labels/${encodeURIComponent(labelName)}`, {
          method: 'DELETE'
        });
      } catch (err) {
        if (err.status === 404) return null; // Label already not present
        throw err;
      }
    },
    async dispatchWorkflow(workflowId, ref, inputs = {}) {
      return request(`/repos/${owner}/${repo}/actions/workflows/${encodeURIComponent(workflowId)}/dispatches`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ref, inputs })
      });
    }
  };
}

/**
 * Main execution handler for issue comment events.
 *
 * @param {object} params
 * @param {object} params.client - GitHub API client
 * @param {object} params.event - Webhook event payload
 * @returns {Promise<{ handled: boolean, action?: string, reason?: string }>}
 */
export async function handleIssueComment({ client, event }) {
  const { action, issue, comment } = event;

  // 1. Filter: Process only newly created comments
  if (action !== 'created') {
    return { handled: false, reason: `Ignored action: ${action}` };
  }

  // 2. Filter: Ignore bot comments
  const author = comment?.user;
  if (!author || author.type === 'Bot' || author.login.endsWith('[bot]')) {
    return { handled: false, reason: 'Ignored bot comment' };
  }

  // 3. Filter: Strict command parsing
  const parsed = parseCommand(comment.body);
  if (!parsed) {
    return { handled: false, reason: 'No valid command found in comment' };
  }

  const { command, args } = parsed;
  const isPullRequest = Boolean(issue.pull_request);
  const commentAuthor = author.login;
  const issueNumber = issue.number;

  // ==========================================
  // PULL REQUEST CONTEXT COMMANDS
  // ==========================================
  if (isPullRequest) {
    if (command === 'claim' || command === 'assign' || command === 'unclaim') {
      return { handled: false, reason: 'Assignment commands are not processed on pull requests' };
    }

    if (command === 'help') {
      await client.createComment(issueNumber, templates.helpResponse());
      return { handled: true, action: 'help' };
    }

    if (command === 'status') {
      await client.createComment(issueNumber, 'The `/status` command is only available on issues. For pull requests, review the GitHub Actions status checks.');
      return { handled: true, action: 'status_on_pr' };
    }

    if (command === 'level') {
      // Module C: Maintainer-only WOCS level commands
      const userPermission = await client.getCollaboratorPermission(commentAuthor);
      if (!AUTHORIZED_ROLES.includes(userPermission.toLowerCase())) {
        await client.createComment(issueNumber, templates.levelUnauthorized(commentAuthor));
        return { handled: true, action: 'level_unauthorized' };
      }

      const targetLevel = args[0];
      if (!targetLevel || !VALID_LEVELS.includes(targetLevel)) {
        await client.createComment(issueNumber, templates.levelInvalidSyntax());
        return { handled: true, action: 'level_invalid_syntax' };
      }

      // Fetch PR to inspect body and linked issue
      const pr = await client.getPullRequest(issueNumber);
      const linkedIssueNum = extractLinkedIssueNumber(pr.body);

      if (!linkedIssueNum) {
        await client.createComment(
          issueNumber,
          templates.levelInvalidIssue('No linked issue reference found in pull request description (e.g., `Closes #123`).')
        );
        return { handled: true, action: 'level_missing_linked_issue' };
      }

      let linkedIssue;
      try {
        linkedIssue = await client.getIssue(linkedIssueNum);
      } catch {
        await client.createComment(
          issueNumber,
          templates.levelInvalidIssue(`Linked issue #${linkedIssueNum} could not be retrieved.`)
        );
        return { handled: true, action: 'level_linked_issue_not_found' };
      }

      if (linkedIssue.pull_request) {
        await client.createComment(
          issueNumber,
          templates.levelInvalidIssue(`#${linkedIssueNum} is a pull request, not an issue.`)
        );
        return { handled: true, action: 'level_linked_issue_is_pr' };
      }

      const linkedLabels = (linkedIssue.labels || []).map(l => (typeof l === 'string' ? l : l.name));
      if (!linkedLabels.includes('wocs')) {
        await client.createComment(
          issueNumber,
          templates.levelInvalidIssue(`Linked issue #${linkedIssueNum} does not have the mandatory \`wocs\` label.`)
        );
        return { handled: true, action: 'level_linked_issue_not_wocs' };
      }

      const prAuthor = pr.user.login;
      const linkedAssignees = (linkedIssue.assignees || []).map(a => a.login);
      if (!linkedAssignees.includes(prAuthor)) {
        await client.createComment(
          issueNumber,
          templates.levelInvalidIssue(`Pull request author @${prAuthor} is not an assigned contributor on linked issue #${linkedIssueNum}.`)
        );
        return { handled: true, action: 'level_author_not_assigned' };
      }

      // Remove conflicting difficulty labels
      const existingPrLabels = (pr.labels || []).map(l => (typeof l === 'string' ? l : l.name));
      const conflictingLevels = VALID_LEVELS
        .map(lvl => `level ${lvl}`)
        .filter(lvlName => lvlName !== `level ${targetLevel}` && existingPrLabels.includes(lvlName));

      for (const conf of conflictingLevels) {
        await client.removeLabel(issueNumber, conf);
      }

      // Add exact wocs and target level
      await client.addLabels(issueNumber, ['wocs', `level ${targetLevel}`]);

      // Re-evaluate policy via workflow_dispatch
      let reevalStatus = 'initiated';
      try {
        await client.dispatchWorkflow('pull-request-policy.yml', pr.base?.ref || 'main', {
          pr_number: issueNumber
        });
      } catch (dispatchErr) {
        console.warn(`Could not dispatch pull-request-policy.yml: ${dispatchErr.message}`);
        reevalStatus = 'manual';
      }

      // Publish confirmation
      await client.createComment(issueNumber, templates.levelSuccess(commentAuthor, targetLevel, reevalStatus));
      return { handled: true, action: `level_${targetLevel}_applied` };
    }
  }

  // ==========================================
  // ISSUE CONTEXT COMMANDS
  // ==========================================
  if (command === 'level') {
    await client.createComment(issueNumber, templates.levelNotPr());
    return { handled: true, action: 'level_on_issue_rejected' };
  }

  if (command === 'help') {
    await client.createComment(issueNumber, templates.helpResponse());
    return { handled: true, action: 'help' };
  }

  if (command === 'status') {
    const currentIssue = await client.getIssue(issueNumber);
    const state = currentIssue.state;
    const locked = Boolean(currentIssue.locked);
    const assignees = (currentIssue.assignees || []).map(a => a.login);
    const labels = (currentIssue.labels || []).map(l => (typeof l === 'string' ? l : l.name));
    const isWocs = labels.includes('wocs');
    const difficultyLevels = labels.filter(l => ['level 1', 'level 2', 'level 3'].includes(l));

    let canClaim = true;
    let claimBlockReason = '';

    if (state !== 'open') {
      canClaim = false;
      claimBlockReason = 'Issue is closed';
    } else if (locked) {
      canClaim = false;
      claimBlockReason = 'Issue is locked';
    } else if (assignees.length > 0) {
      canClaim = false;
      claimBlockReason = `Already assigned to @${assignees[0]}`;
    } else if (!isWocs) {
      canClaim = false;
      claimBlockReason = 'Missing `wocs` label';
    } else if (difficultyLevels.length === 0) {
      canClaim = false;
      claimBlockReason = 'Missing difficulty level label';
    } else if (difficultyLevels.length > 1) {
      canClaim = false;
      claimBlockReason = 'Conflicting difficulty labels present';
    }

    // Evaluate requester-specific eligibility under two-active-issue limit
    let requesterActiveCount = 0;
    let requesterEligible = true;
    let requesterBlockReason = '';

    try {
      const activeWocs = await client.listOpenWocsIssuesForAssignee(commentAuthor);
      const otherActive = activeWocs.filter(i => i.number !== issueNumber);
      requesterActiveCount = otherActive.length;

      if (requesterActiveCount >= 2) {
        requesterEligible = false;
        requesterBlockReason = `You currently have ${requesterActiveCount} active WOCS issues assigned (maximum limit: 2)`;
      }
    } catch (err) {
      requesterEligible = false;
      requesterBlockReason = `Could not verify your active issue count (${err.message})`;
    }

    await client.createComment(
      issueNumber,
      templates.statusResponse({
        state,
        locked,
        assignees,
        isWocs,
        difficultyLevels,
        canClaim,
        claimBlockReason,
        requester: commentAuthor,
        requesterActiveCount,
        requesterEligible,
        requesterBlockReason
      })
    );
    return { handled: true, action: 'status' };
  }

  if (command === 'unclaim') {
    // Single-contributor guarantee: Fetch latest state before unclaim
    const currentIssue = await client.getIssue(issueNumber);
    const assignees = (currentIssue.assignees || []).map(a => a.login);

    if (!assignees.includes(commentAuthor)) {
      await client.createComment(issueNumber, templates.unassignNotAssignee(commentAuthor));
      return { handled: true, action: 'unclaim_not_assignee' };
    }

    // Remove assignment
    await client.removeAssignees(issueNumber, [commentAuthor]);

    // Verify contributor is no longer assigned
    const updatedIssue = await client.getIssue(issueNumber);
    const updatedAssignees = (updatedIssue.assignees || []).map(a => a.login);

    if (!updatedAssignees.includes(commentAuthor)) {
      await client.createComment(issueNumber, templates.unassignSuccess(commentAuthor));
      return { handled: true, action: 'unclaim_success' };
    } else {
      await client.createComment(issueNumber, `Could not complete unassignment for @${commentAuthor}. Please ask a maintainer for assistance.`);
      return { handled: true, action: 'unclaim_failed' };
    }
  }

  if (command === 'claim' || command === 'assign') {
    // 1. Fetch latest issue state from GitHub
    const currentIssue = await client.getIssue(issueNumber);

    // 2. Check issue state
    if (currentIssue.state !== 'open') {
      await client.createComment(issueNumber, templates.issueNotClaimable('This issue is closed and cannot be claimed.'));
      return { handled: true, action: 'claim_rejected_closed' };
    }

    if (currentIssue.locked) {
      await client.createComment(issueNumber, templates.issueNotClaimable('This issue is locked and cannot be claimed.'));
      return { handled: true, action: 'claim_rejected_locked' };
    }

    // 3. Check existing assignees (Single-contributor guarantee)
    const currentAssignees = (currentIssue.assignees || []).map(a => a.login);
    if (currentAssignees.length > 0) {
      if (currentAssignees.includes(commentAuthor)) {
        await client.createComment(issueNumber, `Hi @${commentAuthor}, you are already assigned to this issue.`);
        return { handled: true, action: 'claim_already_own_assignee' };
      }
      await client.createComment(issueNumber, templates.alreadyAssigned(currentAssignees[0]));
      return { handled: true, action: 'claim_rejected_already_assigned' };
    }

    // 4. Verify exact 'wocs' label
    const labels = (currentIssue.labels || []).map(l => (typeof l === 'string' ? l : l.name));
    if (!labels.includes('wocs')) {
      await client.createComment(
        issueNumber,
        templates.issueNotClaimable('This issue does not have the mandatory `wocs` label and is not open for automated claiming.')
      );
      return { handled: true, action: 'claim_rejected_missing_wocs' };
    }

    // 5. Verify exactly one difficulty level
    const difficultyLevels = labels.filter(l => ['level 1', 'level 2', 'level 3'].includes(l));
    if (difficultyLevels.length === 0) {
      await client.createComment(
        issueNumber,
        templates.issueNotClaimable('This issue does not have an approved difficulty label (`level 1`, `level 2`, or `level 3`). A project maintainer or mentor must assign a level before claiming.')
      );
      return { handled: true, action: 'claim_rejected_missing_level' };
    }

    if (difficultyLevels.length > 1) {
      await client.createComment(
        issueNumber,
        templates.issueNotClaimable(`This issue has multiple conflicting difficulty labels (\`${difficultyLevels.join(', ')}\`). A maintainer must resolve these before the issue can be claimed.`)
      );
      return { handled: true, action: 'claim_rejected_conflicting_levels' };
    }

    // 6. Verify 2-active-WOCS-issues limit with reliable pagination
    let activeWocsIssues;
    try {
      activeWocsIssues = await client.listOpenWocsIssuesForAssignee(commentAuthor);
    } catch (err) {
      await client.createComment(
        issueNumber,
        `Hi @${commentAuthor}, could not verify your active issue count due to a GitHub API error (${err.message}). Please try again shortly or contact a maintainer.`
      );
      return { handled: true, action: 'claim_failed_pagination_error' };
    }

    // Exclude current issue if somehow already returned
    const otherActiveIssues = activeWocsIssues.filter(i => i.number !== issueNumber);

    if (otherActiveIssues.length >= 2) {
      await client.createComment(issueNumber, templates.maxIssuesReached(commentAuthor, otherActiveIssues.length));
      return { handled: true, action: 'claim_rejected_max_issues' };
    }

    // 7. Perform assignment
    try {
      await client.addAssignees(issueNumber, [commentAuthor]);
    } catch (err) {
      await client.createComment(
        issueNumber,
        `Hi @${commentAuthor}, assignment could not be completed via GitHub API (${err.message || 'Unknown error'}). Please ensure you have accepted the repository invitation or interacted with the repository.`
      );
      return { handled: true, action: 'claim_failed_api_error' };
    }

    // 8. Single-contributor assignment guarantee: Re-fetch and confirm
    const updatedIssue = await client.getIssue(issueNumber);
    const updatedAssignees = (updatedIssue.assignees || []).map(a => a.login);

    if (updatedAssignees.includes(commentAuthor) && updatedAssignees.length === 1) {
      await client.createComment(issueNumber, templates.successfulAssignment(commentAuthor, client.owner, client.repo));
      return { handled: true, action: 'claim_approved' };
    } else if (updatedAssignees.length > 0 && !updatedAssignees.includes(commentAuthor)) {
      // Race condition lost
      await client.createComment(issueNumber, templates.alreadyAssigned(updatedAssignees[0]));
      return { handled: true, action: 'claim_lost_race' };
    } else {
      await client.createComment(
        issueNumber,
        `Hi @${commentAuthor}, assignment could not be confirmed. Please contact a maintainer to verify your assignment.`
      );
      return { handled: true, action: 'claim_unconfirmed' };
    }
  }

  return { handled: false, reason: `Unknown command: ${command}` };
}

// CLI runner for GitHub Actions workflow
if (process.env.GITHUB_EVENT_PATH && process.argv[1]?.endsWith('issue-command.mjs')) {
  import('node:fs').then(async fs => {
    try {
      const eventPath = process.env.GITHUB_EVENT_PATH;
      const event = JSON.parse(fs.readFileSync(eventPath, 'utf8'));
      const token = process.env.GITHUB_TOKEN;
      const repo = process.env.GITHUB_REPOSITORY;

      if (!token || !repo) {
        console.error('Missing GITHUB_TOKEN or GITHUB_REPOSITORY');
        process.exit(1);
      }

      const client = createGitHubClient(token, repo);
      const result = await handleIssueComment({ client, event });
      console.log('Result:', JSON.stringify(result));
    } catch (error) {
      console.error('Fatal error executing issue command:', error);
      process.exit(1);
    }
  });
}
