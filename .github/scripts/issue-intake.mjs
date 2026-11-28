/**
 * Issue intake automation script.
 * Sends a welcome response with claiming instructions and WOCS policy
 * when an issue is opened, avoiding duplicate comments.
 */

import { MARKERS, welcomeIssue } from './lib/response-templates.mjs';

/**
 * Handles newly opened issue event.
 *
 * @param {object} params
 * @param {object} params.client - GitHub API client
 * @param {object} params.event - Webhook event payload
 * @returns {Promise<{ handled: boolean, action?: string, reason?: string }>}
 */
export async function handleIssueOpened({ client, event }) {
  const { action, issue } = event;

  if (action !== 'opened') {
    return { handled: false, reason: `Ignored action: ${action}` };
  }

  // Do not process pull requests
  if (issue.pull_request) {
    return { handled: false, reason: 'Ignored pull request' };
  }

  const author = issue.user;
  if (!author || author.type === 'Bot' || author.login.endsWith('[bot]')) {
    return { handled: false, reason: 'Ignored bot author' };
  }

  const issueNumber = issue.number;

  // Check for existing comments to prevent duplicates
  const baseUrl = `https://api.github.com/repos/${client.owner}/${client.repo}/issues/${issueNumber}/comments`;
  const commentsRes = await fetch(baseUrl, {
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
      const alreadyWelcomed = comments.some(c => c.body && c.body.includes(MARKERS.ISSUE_INTAKE));
      if (alreadyWelcomed) {
        return { handled: false, reason: 'Welcome message already posted' };
      }
    }
  }

  // Post welcome comment
  const welcomeBody = welcomeIssue(author.login, client.owner, client.repo);
  await client.createComment(issueNumber, welcomeBody);

  return { handled: true, action: 'welcome_posted' };
}

// CLI runner
if (process.env.GITHUB_EVENT_PATH && process.argv[1]?.endsWith('issue-intake.mjs')) {
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
      const result = await handleIssueOpened({ client, event });
      console.log('Result:', JSON.stringify(result));
    } catch (error) {
      console.error('Fatal error during issue intake:', error);
      process.exit(1);
    }
  });
}
