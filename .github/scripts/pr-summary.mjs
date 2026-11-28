/**
 * Security-isolated PR summary script.
 * Runs on workflow_run completion, reporting trusted CI job status
 * and updating an existing comment with a stable HTML marker.
 *
 * CRITICAL SECURITY GUARANTEES:
 * - Does not checkout pull request branch code.
 * - Does not execute pull request scripts or download artifacts.
 * - Relies strictly on trusted GitHub API metadata.
 */

import { MARKERS } from './lib/response-templates.mjs';

function formatStatus(conclusion) {
  switch (conclusion) {
    case 'success':
      return '✅ Passed';
    case 'failure':
      return '❌ Failed';
    case 'cancelled':
      return '⚪ Cancelled';
    case 'skipped':
      return '⚪ Skipped';
    default:
      return '⏳ In Progress';
  }
}

/**
 * Generates markdown summary body for CI status report.
 *
 * @param {object} params
 * @param {Array<{ name: string, conclusion: string }>} params.jobs
 * @param {string} params.runUrl
 * @param {string} params.overallConclusion
 * @returns {string} Markdown comment body
 */
export function generateCiSummaryComment({ jobs = [], runUrl, overallConclusion }) {
  const jobRows = jobs.map(j => `| ${j.name} | ${formatStatus(j.conclusion)} |`).join('\n');
  const isSuccess = overallConclusion === 'success';

  return `${MARKERS.PR_CI_SUMMARY}
### 🤖 Pull Request CI Summary

| Verification Job | Status |
|---|---|
${jobRows}

- **Overall Result:** ${isSuccess ? '✅ **All automated CI checks passed!**' : '❌ **One or more checks failed.**'}
- **Workflow Run Details:** [Inspect GitHub Actions Run](${runUrl})

${isSuccess 
  ? '🔍 **Maintainer review is pending.** An authorized maintainer or mentor will review your contribution shortly.' 
  : '⚠️ Please inspect the failed job logs at the workflow run link above and push updates to resolve the issues.'}`;
}

/**
 * Handles workflow_run completion event to publish or update PR summary.
 *
 * @param {object} params
 * @param {object} params.client - GitHub API client
 * @param {object} params.event - Webhook event payload
 * @returns {Promise<{ handled: boolean, action?: string, reason?: string }>}
 */
export async function handleWorkflowRunCompleted({ client, event }) {
  const run = event.workflow_run;
  if (!run) {
    return { handled: false, reason: 'No workflow_run found in event' };
  }

  // 1. Identify related pull request using trusted metadata
  const pullRequests = run.pull_requests;
  if (!pullRequests || pullRequests.length === 0) {
    return { handled: false, reason: 'No associated pull request found in workflow_run metadata' };
  }

  const prNumber = pullRequests[0].number;
  const runId = run.id;
  const runUrl = run.html_url;
  const overallConclusion = run.conclusion;

  // 2. Query trusted GitHub API for jobs list
  const jobsRes = await fetch(`https://api.github.com/repos/${client.owner}/${client.repo}/actions/runs/${runId}/jobs`, {
    headers: {
      'Accept': 'application/vnd.github+json',
      'Authorization': `Bearer ${process.env.GITHUB_TOKEN}`,
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'pycode-maintainer-automation'
    }
  });

  let jobs = [];
  if (jobsRes.ok) {
    const jobsData = await jobsRes.json();
    if (jobsData?.jobs && Array.isArray(jobsData.jobs)) {
      jobs = jobsData.jobs.map(j => ({
        name: j.name,
        conclusion: j.conclusion
      }));
    }
  }

  const commentBody = generateCiSummaryComment({
    jobs,
    runUrl,
    overallConclusion
  });

  // 3. Search for existing bot-managed comment to update idempotently
  const commentsRes = await fetch(`https://api.github.com/repos/${client.owner}/${client.repo}/issues/${prNumber}/comments`, {
    headers: {
      'Accept': 'application/vnd.github+json',
      'Authorization': `Bearer ${process.env.GITHUB_TOKEN}`,
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'pycode-maintainer-automation'
    }
  });

  if (commentsRes.ok) {
    const comments = await commentsRes.json();
    if (Array.isArray(comments)) {
      const existing = comments.find(c => c.body && c.body.includes(MARKERS.PR_CI_SUMMARY));
      if (existing) {
        // Update existing comment
        await fetch(`https://api.github.com/repos/${client.owner}/${client.repo}/issues/comments/${existing.id}`, {
          method: 'PATCH',
          headers: {
            'Accept': 'application/vnd.github+json',
            'Authorization': `Bearer ${process.env.GITHUB_TOKEN}`,
            'Content-Type': 'application/json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'pycode-maintainer-automation'
          },
          body: JSON.stringify({ body: commentBody })
        });
        return { handled: true, action: 'comment_updated', prNumber };
      }
    }
  }

  // Create new comment if none exists
  await client.createComment(prNumber, commentBody);
  return { handled: true, action: 'comment_created', prNumber };
}

// CLI runner
if (process.env.GITHUB_EVENT_PATH && process.argv[1]?.endsWith('pr-summary.mjs')) {
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
      const result = await handleWorkflowRunCompleted({ client, event });
      console.log('Result:', JSON.stringify(result));
    } catch (error) {
      console.error('Fatal error during PR summary generation:', error);
      process.exit(1);
    }
  });
}
