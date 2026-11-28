/**
 * Pull request policy validator.
 * Validates PR target branch, linked issue assignment, PR template completion,
 * AI disclosures, and WOCS labels.
 *
 * Implements hardened security checks and narrow owner-authored maintenance exemption.
 */

import { extractLinkedIssueNumber } from './lib/command-parser.mjs';

const VALID_WOCS_LEVELS = ['level 1', 'level 2', 'level 3'];

/**
 * Removes markdown comments (<!-- ... -->) and trims text.
 * @param {string} text
 * @returns {string}
 */
function stripMarkdownComments(text) {
  if (!text) return '';
  return text.replace(/<!--[\s\S]*?-->/g, '').trim();
}

/**
 * Validates a pull request against repository contribution and WOCS governance policies.
 *
 * @param {object} params
 * @param {object} params.pr - Pull request object (from GitHub API)
 * @param {object | null} params.linkedIssue - Linked issue object (from GitHub API)
 * @param {string[]} [params.prLabels] - Array of label names on PR
 * @returns {{ valid: boolean, errors: string[], warnings: string[], isDraft: boolean }}
 */
export function validatePullRequestPolicy({ pr, linkedIssue, prLabels = [] }) {
  const errors = [];
  const warnings = [];

  // 1. Target Branch: Must target 'main'
  const targetBranch = pr.base?.ref;
  if (targetBranch !== 'main') {
    errors.push(`Pull request targets \`${targetBranch || 'unknown'}\` branch instead of \`main\`. All contributions must target the default branch.`);
  }

  // 2. Draft PR Handling: Do not enforce final checks on drafts
  if (pr.draft) {
    return {
      valid: errors.length === 0,
      errors,
      warnings: ['Pull request is currently a draft. Full policy validation will run when marked ready for review.'],
      isDraft: true
    };
  }

  const body = pr.body || '';

  // Determine WOCS context
  const activePrLabels = prLabels.map(l => (typeof l === 'string' ? l : l.name));
  const hasWocsLabel = activePrLabels.includes('wocs');
  const issueLabels = linkedIssue ? (linkedIssue.labels || []).map(l => (typeof l === 'string' ? l : l.name)) : [];
  const isWocsIssue = issueLabels.includes('wocs');
  const isWocs = hasWocsLabel || isWocsIssue;

  // Narrow Owner-Authored Non-WOCS Maintenance Exemption
  // Relies exclusively on GitHub-provided trusted author_association
  const isOwner = pr.author_association === 'OWNER';
  const isOwnerMaintenance = isOwner && !isWocs;

  // 3. Linked Issue Reference
  const linkedIssueNumber = extractLinkedIssueNumber(body);
  if (!linkedIssueNumber) {
    if (isOwnerMaintenance) {
      warnings.push('Owner-authored non-WOCS maintenance PR: linked issue reference is exempt.');
    } else {
      errors.push('No linked issue reference found in PR description. PR must reference an issue using `Closes #<number>`, `Fixes #<number>`, or `Resolves #<number>`.');
    }
  } else if (!linkedIssue) {
    errors.push(`Linked issue #${linkedIssueNumber} could not be found or verified.`);
  } else {
    // 4. Linked Issue Validity
    if (linkedIssue.pull_request) {
      errors.push(`Linked reference #${linkedIssueNumber} is a pull request, not an issue.`);
    }

    if (linkedIssue.state === 'closed') {
      errors.push(`Linked issue #${linkedIssueNumber} is closed. Contributions must link to an open assigned issue.`);
    }

    // 5. Linked Issue Assignment
    const prAuthor = pr.user?.login;
    const assignees = (linkedIssue.assignees || []).map(a => a.login);
    if (!assignees.includes(prAuthor)) {
      if (isOwnerMaintenance) {
        warnings.push(`Owner-authored non-WOCS maintenance PR: issue assignment requirement on #${linkedIssueNumber} is exempt.`);
      } else {
        if (assignees.length === 0) {
          errors.push(`Linked issue #${linkedIssueNumber} is unassigned. PR author @${prAuthor} must be formally assigned before submitting a PR.`);
        } else {
          errors.push(`Linked issue #${linkedIssueNumber} is assigned to @${assignees.join(', @')}, not PR author @${prAuthor}.`);
        }
      }
    }
  }

  // 6. Template Section: Issue Assignment Confirmation Checkbox
  // Pattern: - [x] I confirm that this issue was formally assigned to me
  const assignmentConfirmed = /- \[[xX]\]\s*I confirm that this issue was formally assigned to me/i.test(body);
  if (!assignmentConfirmed) {
    if (isOwnerMaintenance) {
      warnings.push('Owner-authored non-WOCS maintenance PR: issue assignment confirmation checkbox is exempt.');
    } else {
      errors.push('Issue Assignment Confirmation checkbox is not checked. Please check the confirmation in the PR description.');
    }
  }

  // 7. Template Section: AI Assistance Disclosure (ALWAYS ENFORCED FOR ALL CONTRIBUTORS AND OWNER)
  // Section-scoped matching strictly within ## AI Assistance Disclosure
  const aiSectionMatch = body.match(/(?:^|\r?\n)##\s*AI Assistance Disclosure[^\r\n]*(?:\r?\n([\s\S]*?)(?=(?:\r?\n##\s)|$)|$)/i);
  if (!aiSectionMatch) {
    errors.push('AI Assistance Disclosure section is missing from the PR description.');
    errors.push('AI Disclosure confirmation missing: "I confirm that I understand, have personally verified, and can explain every line of code..." must be checked.');
    errors.push('AI Disclosure confirmation missing: "I confirm that this contribution contains no mass-generated, copied, or unverified code" must be checked.');
  } else {
    const aiSectionText = aiSectionMatch[1] || '';

    // Match No checkboxes within the AI section
    // Examples: - [x] No, - [ ] No, * [X] No.
    const noMatches = [...aiSectionText.matchAll(/^[ \t]*[-*]\s*\[([ xX])\]\s*No\b/gim)];
    // Match Yes checkboxes within the AI section
    // Examples: - [x] Yes, - [ ] Yes (please disclose...)
    const yesMatches = [...aiSectionText.matchAll(/^[ \t]*[-*]\s*\[([ xX])\]\s*Yes\b/gim)];

    const noCheckedCount = noMatches.filter(m => m[1].toLowerCase() === 'x').length;
    const yesCheckedCount = yesMatches.filter(m => m[1].toLowerCase() === 'x').length;

    if (noMatches.length === 0 && yesMatches.length === 0) {
      errors.push('AI Assistance Disclosure is malformed: no `No` or `Yes` options found in the section.');
    } else if (noMatches.length > 1 || yesMatches.length > 1) {
      errors.push('AI Assistance Disclosure is ambiguous: duplicate AI disclosure options found in the section.');
    } else if (noCheckedCount === 0 && yesCheckedCount === 0) {
      errors.push('AI Assistance Disclosure is incomplete: neither `No` nor `Yes` is checked.');
    } else if (noCheckedCount > 0 && yesCheckedCount > 0) {
      errors.push('AI Assistance Disclosure is ambiguous: both `No` and `Yes` are checked. Please select exactly one.');
    }

    // When Yes is checked, require meaningful disclosure details
    if (yesCheckedCount === 1 && noCheckedCount === 0) {
      const lines = aiSectionText.split(/\r?\n/);
      let yesLineIndex = -1;
      for (let i = 0; i < lines.length; i++) {
        if (/^[ \t]*[-*]\s*\[[ xX]\]\s*Yes\b/i.test(lines[i])) {
          yesLineIndex = i;
          break;
        }
      }

      const detailsParts = [];
      if (yesLineIndex !== -1) {
        const match = lines[yesLineIndex].match(/^[ \t]*[-*]\s*\[[ xX]\]\s*Yes\b(.*)$/i);
        if (match && match[1]) {
          detailsParts.push(match[1]);
        }

        for (let i = yesLineIndex + 1; i < lines.length; i++) {
          const line = lines[i];
          // Stop at next checkbox, header, or horizontal rule
          if (/^[ \t]*[-*]\s*\[[ xX\s]\]/i.test(line)) break;
          if (/^[ \t]*(?:#{1,6}\s|---|___|\*\*\*)/.test(line)) break;
          detailsParts.push(line);
        }
      }

      const rawDetails = stripMarkdownComments(detailsParts.join('\n'));
      // Remove template instructions and placeholder text
      const cleanDetails = rawDetails
        .replace(/\(?\s*please disclose tools used and extent of assistance below:?\s*\)?/gi, '')
        .replace(/^[\s:;,-]+|[\s:;,-]+$/g, '')
        .trim();

      if (cleanDetails.length < 5) {
        errors.push('AI Assistance Disclosure is incomplete: `Yes` is checked but no meaningful disclosure details were provided. Please specify the AI tools used and the extent of assistance.');
      }
    }

    // Sub-confirmations for AI disclosure (ALWAYS ENFORCED)
    const understandConfirmed = /[-*]\s*\[[xX]\]\s*I confirm that I understand, have personally verified, and can explain every line/i.test(aiSectionText);
    if (!understandConfirmed) {
      errors.push('AI Disclosure confirmation missing: "I confirm that I understand, have personally verified, and can explain every line of code..." must be checked.');
    }

    const noCopiedConfirmed = /[-*]\s*\[[xX]\]\s*I confirm that this contribution contains no mass-generated, copied, or unverified code/i.test(aiSectionText);
    if (!noCopiedConfirmed) {
      errors.push('AI Disclosure confirmation missing: "I confirm that this contribution contains no mass-generated, copied, or unverified code" must be checked.');
    }
  }

  // 8. Description content validation: Problem Addressed & Summary of Changes (ALWAYS ENFORCED)
  const problemMatch = body.match(/### Problem Addressed\s*([\s\S]*?)(?=### Summary of Changes|$)/i);
  const problemText = problemMatch ? stripMarkdownComments(problemMatch[1]) : '';
  if (problemText.length < 10) {
    errors.push('Problem Addressed section is empty or contains only template placeholder text. Please provide a clear description.');
  }

  const summaryMatch = body.match(/### Summary of Changes\s*([\s\S]*?)(?=### Files \/ Modules Changed|$)/i);
  const summaryText = summaryMatch ? stripMarkdownComments(summaryMatch[1]) : '';
  if (summaryText.length < 10) {
    errors.push('Summary of Changes section is empty or contains only template placeholder text. Please summarize your changes.');
  }

  // 9. Verification Info (ALWAYS ENFORCED)
  const verificationMatch = body.match(/### Verification Commands & Environment\s*([\s\S]*?)(?=### Verification Outcome|$)/i);
  let verificationText = verificationMatch ? stripMarkdownComments(verificationMatch[1]) : '';
  // Strip code block backticks (e.g. ```powershell ... ```) to inspect actual commands
  verificationText = verificationText.replace(/```[a-zA-Z0-9_-]*|```/g, '').trim();
  if (verificationText.length < 5) {
    errors.push('Verification Commands & Environment section is empty. Please provide the commands used to test your contribution.');
  }

  // 10. WOCS Label Validation (if linked issue is a WOCS issue, or PR has WOCS label)
  if (isWocs) {
    if (!hasWocsLabel) {
      errors.push('PR is missing the mandatory `wocs` label. An authorized maintainer or mentor must apply WOCS labels using `/level 1`, `/level 2`, or `/level 3`.');
    }

    const difficultyLabels = activePrLabels.filter(l => VALID_WOCS_LEVELS.includes(l));
    if (difficultyLabels.length === 0) {
      errors.push('PR is missing a difficulty level label (`level 1`, `level 2`, or `level 3`). An authorized maintainer must review the code and apply the level using `/level 1`, `/level 2`, or `/level 3`.');
    } else if (difficultyLabels.length > 1) {
      errors.push(`PR has multiple conflicting difficulty labels (\`${difficultyLabels.join(', ')}\`). An authorized maintainer must resolve these using \`/level <number>\`.`);
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
    isDraft: false
  };
}

/**
 * Evaluates PR policy using GitHub API client and event payload.
 * Fails closed if fresh PR details cannot be retrieved.
 *
 * @param {object} params
 * @param {object} params.client - GitHub API client
 * @param {object} params.event - Event payload
 * @param {number|string} [params.dispatchPrNumber] - Optional override PR number
 * @returns {Promise<object>} Policy evaluation report
 */
export async function evaluatePullRequestWithApi({ client, event, dispatchPrNumber }) {
  let pr = event?.pull_request;
  const dispatchNum = dispatchPrNumber || event?.inputs?.pr_number;
  if (!pr && dispatchNum) {
    const num = parseInt(dispatchNum, 10);
    if (isNaN(num)) {
      throw new Error(`Invalid dispatch PR number: ${dispatchNum}`);
    }
    pr = await client.getPullRequest(num);
  }

  if (!pr) {
    throw new Error('No pull_request found in event payload or workflow_dispatch inputs');
  }

  const prNumber = pr.number;
  let freshPr;
  try {
    freshPr = await client.getPullRequest(prNumber);
  } catch (err) {
    throw new Error(`Failed to refresh PR #${prNumber} details via GitHub API: ${err.message}. Failing closed for policy integrity.`);
  }

  // Fetch linked issue if referenced
  const linkedNum = extractLinkedIssueNumber(freshPr.body);
  let linkedIssue = null;
  if (linkedNum) {
    try {
      linkedIssue = await client.getIssue(linkedNum);
    } catch {
      linkedIssue = null;
    }
  }

  const prLabels = (freshPr.labels || []).map(l => (typeof l === 'string' ? l : l.name));
  return validatePullRequestPolicy({ pr: freshPr, linkedIssue, prLabels });
}

// CLI runner for GitHub Actions workflow
if (process.env.GITHUB_EVENT_PATH && process.argv[1]?.endsWith('pr-policy.mjs')) {
  import('node:fs').then(async fs => {
    try {
      const { createGitHubClient } = await import('./issue-command.mjs');
      const eventPath = process.env.GITHUB_EVENT_PATH;
      const event = JSON.parse(fs.readFileSync(eventPath, 'utf8'));
      const token = process.env.GITHUB_TOKEN;
      const repo = process.env.GITHUB_REPOSITORY;

      if (!token || !repo) {
        console.error('Missing GITHUB_TOKEN or GITHUB_REPOSITORY');
        process.exit(1);
      }

      const client = createGitHubClient(token, repo);
      const prNumber = event?.pull_request?.number || process.env.DISPATCH_PR_NUMBER || event?.inputs?.pr_number;

      const report = await evaluatePullRequestWithApi({
        client,
        event,
        dispatchPrNumber: process.env.DISPATCH_PR_NUMBER
      });

      console.log(`--- PULL REQUEST POLICY REPORT (PR #${prNumber}) ---`);
      if (report.isDraft) {
        console.log('Status: DRAFT PR (final validation deferred)');
        process.exit(0);
      }

      if (report.warnings.length > 0) {
        console.log('Warnings:');
        report.warnings.forEach(w => console.log(`  ⚠ ${w}`));
      }

      if (!report.valid) {
        console.error('Policy validation FAILED:');
        report.errors.forEach(err => console.error(`  ❌ ${err}`));
        process.exit(1);
      }

      console.log('✅ All pull request policy checks PASSED.');
      process.exit(0);
    } catch (error) {
      console.error('Fatal error during PR policy evaluation:', error.message || error);
      process.exit(1);
    }
  });
}
