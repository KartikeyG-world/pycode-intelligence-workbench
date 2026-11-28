/**
 * Security-isolated PR summary script.
 * Runs on workflow_run completion, reporting trusted CI job status
 * and updating an existing comment with a stable HTML marker.
 *
 * CRITICAL SECURITY GUARANTEES:
 * - Does not checkout pull request branch code.
 * - Does not execute pull request scripts or download artifacts.
 * - Relies strictly on trusted GitHub API metadata.
 * - Never publishes "All passed" unless every expected job succeeded.
 */

import { MARKERS } from './lib/response-templates.mjs';

export const EXPECTED_JOBS = [
  'Backend Validation (Python 3.11)',
  'Backend Validation (Python 3.13)',
  'Frontend Validation (Lint, Typecheck, Build)',
  'Maintainer Automation Tests'
];

export function formatStatus(conclusion) {
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
      return '⏳ In Progress / Unknown';
  }
}

/**
 * Generates markdown summary body for CI status report.
 * Strictly verifies that all expected jobs are present, unique, and succeeded.
 *
 * @param {object} params
 * @param {Array<{ name: string, conclusion: string, status?: string }>} [params.jobs]
 * @param {string} params.runUrl
 * @param {string} params.overallConclusion
 * @param {string} [params.errorMessage]
 * @returns {string} Markdown comment body
 */
export function generateCiSummaryComment({ jobs = [], runUrl, overallConclusion, errorMessage }) {
  if (errorMessage) {
    return `${MARKERS.PR_CI_SUMMARY}
### 🤖 Pull Request CI Summary

⚠️ **Error Retrieving CI Job Details:** ${errorMessage}

- **Workflow Run Details:** [Inspect GitHub Actions Run](${runUrl || '#'})
- **Status:** Check run outcome could not be verified automatically. Please inspect the workflow run link directly.`;
  }

  if (!Array.isArray(jobs) || jobs.length === 0) {
    return `${MARKERS.PR_CI_SUMMARY}
### 🤖 Pull Request CI Summary

⚠️ **No Job Execution Records Available:** Workflow run has not reported any completed jobs.

- **Workflow Run Details:** [Inspect GitHub Actions Run](${runUrl || '#'})
- **Overall Result:** ❌ **Checks unverified**`;
  }

  const jobRows = jobs.map(j => `| ${j.name || 'Unknown Job'} | ${formatStatus(j.conclusion)} |`).join('\n');

  // Strict exact set matching:
  // 1. Overall workflow conclusion must be 'success'
  // 2. All expected jobs must exist and no unexpected/extra jobs are allowed (exact length match)
  // 3. Every job's name must be in EXPECTED_JOBS
  // 4. Every expected job must appear exactly once (no duplicates, no omissions)
  // 5. Every job must have conclusion === 'success' (no null, skipped, cancelled, failed)
  const jobCounts = new Map();
  for (const job of jobs) {
    const name = job?.name;
    if (name) {
      jobCounts.set(name, (jobCounts.get(name) || 0) + 1);
    }
  }

  const exactJobCount = jobs.length === EXPECTED_JOBS.length;
  const noUnexpectedJobs = jobs.every(j => EXPECTED_JOBS.includes(j?.name));
  const everyExpectedPresentOnce = EXPECTED_JOBS.every(name => jobCounts.get(name) === 1);
  const allJobsValidSuccess = jobs.every(j => j?.conclusion === 'success');
  const allExpectedSucceeded = EXPECTED_JOBS.every(name => {
    const matchingJobs = jobs.filter(j => j.name === name);
    return matchingJobs.length === 1 && matchingJobs[0].conclusion === 'success';
  });

  const isStrictSuccess = overallConclusion === 'success' &&
                          exactJobCount &&
                          noUnexpectedJobs &&
                          everyExpectedPresentOnce &&
                          allExpectedSucceeded &&
                          allJobsValidSuccess;

  return `${MARKERS.PR_CI_SUMMARY}
### 🤖 Pull Request CI Summary

| Verification Job | Status |
|---|---|
${jobRows}

- **Overall Result:** ${isStrictSuccess ? '✅ **All automated CI checks passed!**' : '❌ **One or more checks failed or incomplete.**'}
- **Workflow Run Details:** [Inspect GitHub Actions Run](${runUrl || '#'})

${isStrictSuccess 
  ? '🔍 **Maintainer review is pending.** An authorized maintainer or mentor will review your contribution shortly.' 
  : '⚠️ Please inspect the failed job logs at the workflow run link above and push updates to resolve the issues.'}`;
}

/**
 * Handles workflow_run completion event to publish or update PR summary.
 *
 * @param {object} params
 * @param {object} params.client - GitHub API client
 * @param {object} params.event - Webhook event payload
 * @param {typeof fetch} [params.fetchFn] - Optional fetch function for testing
 * @returns {Promise<{ handled: boolean, action?: string, reason?: string, error?: string }>}
 */
export async function handleWorkflowRunCompleted({ client, event, fetchFn = globalThis.fetch }) {
  const run = event?.workflow_run;
  if (!run) {
    return { handled: false, reason: 'No workflow_run found in event' };
  }

  // 1. Identify related pull request using trusted metadata
  const pullRequests = run.pull_requests;
  if (!pullRequests || !Array.isArray(pullRequests) || pullRequests.length === 0) {
    return { handled: false, reason: 'No associated pull request found in workflow_run metadata' };
  }

  const prNumber = pullRequests[0].number;
  const runId = run.id;
  const runUrl = run.html_url || '';
  const overallConclusion = run.conclusion || 'unknown';

  let jobs = [];
  let errorMessage = null;

  // 2. Query trusted GitHub API for jobs list
  try {
    const jobsRes = await fetchFn(`https://api.github.com/repos/${client.owner}/${client.repo}/actions/runs/${runId}/jobs`, {
      headers: {
        'Accept': 'application/vnd.github+json',
        'Authorization': `Bearer ${process.env.GITHUB_TOKEN}`,
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'pycode-maintainer-automation'
      }
    });

    if (!jobsRes.ok) {
      errorMessage = `GitHub API error fetching jobs (HTTP ${jobsRes.status})`;
    } else {
      const jobsData = await jobsRes.json();
      if (jobsData?.jobs && Array.isArray(jobsData.jobs)) {
        jobs = jobsData.jobs.map(j => ({
          name: j.name,
          conclusion: j.conclusion,
          status: j.status
        }));
      } else {
        errorMessage = 'Malformed jobs payload received from GitHub API';
      }
    }
  } catch (err) {
    errorMessage = `Network or parse error fetching jobs: ${err.message}`;
  }

  const commentBody = generateCiSummaryComment({
    jobs,
    runUrl,
    overallConclusion,
    errorMessage
  });

  // 3. Search for existing bot-managed comment across all pages with reliable pagination
  let existingCommentId = null;
  let page = 1;
  const perPage = 100;

  while (true) {
    let commentsRes;
    try {
      commentsRes = await fetchFn(
        `https://api.github.com/repos/${client.owner}/${client.repo}/issues/${prNumber}/comments?per_page=${perPage}&page=${page}`,
        {
          headers: {
            'Accept': 'application/vnd.github+json',
            'Authorization': `Bearer ${process.env.GITHUB_TOKEN}`,
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'pycode-maintainer-automation'
          }
        }
      );
    } catch (err) {
      throw new Error(`Failed to query issue comments for PR #${prNumber} on page ${page}: ${err.message}`);
    }

    if (!commentsRes || !commentsRes.ok) {
      const status = commentsRes?.status || 'unknown';
      throw new Error(`Failed to list comments for PR #${prNumber} (HTTP ${status}): cannot safely determine existing summary status`);
    }

    let comments;
    try {
      comments = await commentsRes.json();
    } catch (err) {
      throw new Error(`Failed to parse comments JSON for PR #${prNumber} on page ${page}: ${err.message}`);
    }

    if (!Array.isArray(comments)) {
      throw new Error(`Malformed comments payload for PR #${prNumber} on page ${page}`);
    }

    const existing = comments.find(c => c.body && c.body.includes(MARKERS.PR_CI_SUMMARY));
    if (existing) {
      existingCommentId = existing.id;
      break;
    }

    if (comments.length < perPage) {
      break;
    }
    page++;
  }

  if (existingCommentId) {
    // Update existing comment
    let updateRes;
    try {
      updateRes = await fetchFn(`https://api.github.com/repos/${client.owner}/${client.repo}/issues/comments/${existingCommentId}`, {
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
    } catch (err) {
      throw new Error(`Failed to update PR summary comment #${existingCommentId}: ${err.message}`);
    }

    if (!updateRes || !updateRes.ok) {
      const status = updateRes?.status || 'unknown';
      throw new Error(`Failed to update PR summary comment #${existingCommentId}: HTTP ${status}`);
    }
    return { handled: true, action: 'comment_updated', prNumber, commentId: existingCommentId };
  } else {
    // Create new comment if none exists
    let createRes;
    try {
      createRes = await fetchFn(`https://api.github.com/repos/${client.owner}/${client.repo}/issues/${prNumber}/comments`, {
        method: 'POST',
        headers: {
          'Accept': 'application/vnd.github+json',
          'Authorization': `Bearer ${process.env.GITHUB_TOKEN}`,
          'Content-Type': 'application/json',
          'X-GitHub-Api-Version': '2022-11-28',
          'User-Agent': 'pycode-maintainer-automation'
        },
        body: JSON.stringify({ body: commentBody })
      });
    } catch (err) {
      throw new Error(`Failed to create PR summary comment on #${prNumber}: ${err.message}`);
    }

    if (!createRes || !createRes.ok) {
      const status = createRes?.status || 'unknown';
      throw new Error(`Failed to create PR summary comment on #${prNumber}: HTTP ${status}`);
    }
    const createdData = await createRes.json().catch(() => ({}));
    return { handled: true, action: 'comment_created', prNumber, commentId: createdData?.id };
  }
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
