import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { generateCiSummaryComment, handleWorkflowRunCompleted } from '../scripts/pr-summary.mjs';
import { MARKERS } from '../scripts/lib/response-templates.mjs';

describe('PR CI Summary Tests', () => {
  test('generates markdown summary with success badges and maintainer review notice', () => {
    const jobs = [
      { name: 'Backend Validation (Python 3.11)', conclusion: 'success' },
      { name: 'Backend Validation (Python 3.13)', conclusion: 'success' },
      { name: 'Frontend Validation', conclusion: 'success' }
    ];
    const comment = generateCiSummaryComment({
      jobs,
      runUrl: 'https://github.com/owner/repo/actions/runs/12345',
      overallConclusion: 'success'
    });

    assert.ok(comment.includes(MARKERS.PR_CI_SUMMARY));
    assert.match(comment, /Backend Validation \(Python 3.11\).*✅ Passed/);
    assert.match(comment, /Frontend Validation.*✅ Passed/);
    assert.match(comment, /Maintainer review is pending/);
  });

  test('generates failure summary when any check fails', () => {
    const jobs = [
      { name: 'Backend Validation (Python 3.11)', conclusion: 'failure' },
      { name: 'Frontend Validation', conclusion: 'success' }
    ];
    const comment = generateCiSummaryComment({
      jobs,
      runUrl: 'https://github.com/owner/repo/actions/runs/12345',
      overallConclusion: 'failure'
    });

    assert.ok(comment.includes(MARKERS.PR_CI_SUMMARY));
    assert.match(comment, /Backend Validation \(Python 3.11\).*❌ Failed/);
    assert.match(comment, /inspect the failed job logs/);
  });

  test('skips summary when workflow_run has no pull requests attached', async () => {
    const client = { owner: 'owner', repo: 'repo' };
    const event = {
      workflow_run: {
        id: 123,
        conclusion: 'success',
        pull_requests: []
      }
    };

    const result = await handleWorkflowRunCompleted({ client, event });
    assert.equal(result.handled, false);
    assert.match(result.reason, /No associated pull request/i);
  });
});
