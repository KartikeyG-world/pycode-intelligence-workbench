import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
  generateCiSummaryComment,
  handleWorkflowRunCompleted,
  EXPECTED_JOBS
} from '../scripts/pr-summary.mjs';
import { MARKERS } from '../scripts/lib/response-templates.mjs';

describe('PR CI Summary Tests - Hardened Error & Outcome Handling', () => {
  test('generates markdown summary with success badges when all expected jobs pass', () => {
    const jobs = [
      { name: 'Backend Validation (Python 3.11)', conclusion: 'success' },
      { name: 'Backend Validation (Python 3.13)', conclusion: 'success' },
      { name: 'Frontend Validation (Lint, Typecheck, Build)', conclusion: 'success' }
    ];
    const comment = generateCiSummaryComment({
      jobs,
      runUrl: 'https://github.com/owner/repo/actions/runs/12345',
      overallConclusion: 'success'
    });

    assert.ok(comment.includes(MARKERS.PR_CI_SUMMARY));
    assert.match(comment, /Backend Validation \(Python 3.11\).*✅ Passed/);
    assert.match(comment, /Frontend Validation \(Lint, Typecheck, Build\).*✅ Passed/);
    assert.match(comment, /All automated CI checks passed/);
    assert.match(comment, /Maintainer review is pending/);
  });

  test('never claims all checks passed when any expected job failed', () => {
    const jobs = [
      { name: 'Backend Validation (Python 3.11)', conclusion: 'failure' },
      { name: 'Backend Validation (Python 3.13)', conclusion: 'success' },
      { name: 'Frontend Validation (Lint, Typecheck, Build)', conclusion: 'success' }
    ];
    const comment = generateCiSummaryComment({
      jobs,
      runUrl: 'https://github.com/owner/repo/actions/runs/12345',
      overallConclusion: 'failure'
    });

    assert.ok(comment.includes(MARKERS.PR_CI_SUMMARY));
    assert.match(comment, /Backend Validation \(Python 3.11\).*❌ Failed/);
    assert.match(comment, /One or more checks failed/);
    assert.ok(!comment.includes('All automated CI checks passed!'));
  });

  test('never claims all checks passed when overall conclusion is missing or incomplete', () => {
    const jobs = [
      { name: 'Backend Validation (Python 3.11)', conclusion: 'success' },
      { name: 'Backend Validation (Python 3.13)', conclusion: 'success' },
      { name: 'Frontend Validation (Lint, Typecheck, Build)', conclusion: 'success' }
    ];
    const comment = generateCiSummaryComment({
      jobs,
      runUrl: 'https://github.com/owner/repo/actions/runs/12345',
      overallConclusion: null // missing conclusion
    });

    assert.match(comment, /One or more checks failed or incomplete/);
    assert.ok(!comment.includes('All automated CI checks passed!'));
  });

  test('never claims all checks passed when a job is still in progress (null conclusion)', () => {
    const jobs = [
      { name: 'Backend Validation (Python 3.11)', conclusion: 'success' },
      { name: 'Backend Validation (Python 3.13)', conclusion: null },
      { name: 'Frontend Validation (Lint, Typecheck, Build)', conclusion: 'success' }
    ];
    const comment = generateCiSummaryComment({
      jobs,
      runUrl: 'https://github.com/owner/repo/actions/runs/12345',
      overallConclusion: 'in_progress'
    });

    assert.match(comment, /Backend Validation \(Python 3.13\).*⏳ In Progress/);
    assert.match(comment, /One or more checks failed or incomplete/);
  });

  test('reports error when jobs array is empty', () => {
    const comment = generateCiSummaryComment({
      jobs: [],
      runUrl: 'https://github.com/owner/repo/actions/runs/12345',
      overallConclusion: 'success'
    });

    assert.match(comment, /No Job Execution Records Available/);
    assert.match(comment, /Checks unverified/);
    assert.ok(!comment.includes('All automated CI checks passed!'));
  });

  test('reports error when jobs API call failed', () => {
    const comment = generateCiSummaryComment({
      jobs: [],
      runUrl: 'https://github.com/owner/repo/actions/runs/12345',
      overallConclusion: 'failure',
      errorMessage: 'GitHub API error fetching jobs (HTTP 500)'
    });

    assert.match(comment, /Error Retrieving CI Job Details:\*\* GitHub API error fetching jobs \(HTTP 500\)/);
    assert.match(comment, /Check run outcome could not be verified automatically/);
  });

  test('does not claim success when unexpected or unknown jobs are returned without expected jobs', () => {
    const jobs = [
      { name: 'Arbitrary Helper Job', conclusion: 'success' }
    ];
    const comment = generateCiSummaryComment({
      jobs,
      runUrl: 'https://github.com/owner/repo/actions/runs/12345',
      overallConclusion: 'success'
    });

    assert.match(comment, /One or more checks failed or incomplete/);
    assert.ok(!comment.includes('All automated CI checks passed!'));
  });

  test('skips execution when workflow_run has no pull requests attached', async () => {
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

  test('updates existing summary comment when HTML marker is found', async () => {
    const client = { owner: 'owner', repo: 'repo' };
    const event = {
      workflow_run: {
        id: 123,
        html_url: 'https://github.com/owner/repo/actions/runs/123',
        conclusion: 'success',
        pull_requests: [{ number: 99 }]
      }
    };

    let patchCalled = false;
    let postCalled = false;

    const mockFetch = async (url, opts = {}) => {
      if (url.includes('/actions/runs/123/jobs')) {
        return {
          ok: true,
          json: async () => ({
            jobs: [
              { name: 'Backend Validation (Python 3.11)', conclusion: 'success' },
              { name: 'Backend Validation (Python 3.13)', conclusion: 'success' },
              { name: 'Frontend Validation (Lint, Typecheck, Build)', conclusion: 'success' }
            ]
          })
        };
      }
      if (url.includes('/issues/99/comments') && !opts.method) {
        return {
          ok: true,
          json: async () => [
            { id: 456, body: `${MARKERS.PR_CI_SUMMARY}\nOld status` }
          ]
        };
      }
      if (url.includes('/issues/comments/456') && opts.method === 'PATCH') {
        patchCalled = true;
        return { ok: true, json: async () => ({ id: 456 }) };
      }
      if (url.includes('/issues/99/comments') && opts.method === 'POST') {
        postCalled = true;
        return { ok: true, json: async () => ({ id: 789 }) };
      }
      return { ok: false, status: 404 };
    };

    const result = await handleWorkflowRunCompleted({ client, event, fetchFn: mockFetch });
    assert.equal(result.handled, true);
    assert.equal(result.action, 'comment_updated');
    assert.equal(patchCalled, true);
    assert.equal(postCalled, false);
  });

  test('creates new summary comment when no existing comment has marker', async () => {
    const client = { owner: 'owner', repo: 'repo' };
    const event = {
      workflow_run: {
        id: 123,
        html_url: 'https://github.com/owner/repo/actions/runs/123',
        conclusion: 'success',
        pull_requests: [{ number: 99 }]
      }
    };

    let postCalled = false;

    const mockFetch = async (url, opts = {}) => {
      if (url.includes('/actions/runs/123/jobs')) {
        return {
          ok: true,
          json: async () => ({
            jobs: [
              { name: 'Backend Validation (Python 3.11)', conclusion: 'success' },
              { name: 'Backend Validation (Python 3.13)', conclusion: 'success' },
              { name: 'Frontend Validation (Lint, Typecheck, Build)', conclusion: 'success' }
            ]
          })
        };
      }
      if (url.includes('/issues/99/comments') && !opts.method) {
        return {
          ok: true,
          json: async () => [
            { id: 111, body: `Just an ordinary comment without marker` }
          ]
        };
      }
      if (url.includes('/issues/99/comments') && opts.method === 'POST') {
        postCalled = true;
        return { ok: true, json: async () => ({ id: 789 }) };
      }
      return { ok: false, status: 404 };
    };

    const result = await handleWorkflowRunCompleted({ client, event, fetchFn: mockFetch });
    assert.equal(result.handled, true);
    assert.equal(result.action, 'comment_created');
    assert.equal(postCalled, true);
  });

  test('throws error when comment update API fails', async () => {
    const client = { owner: 'owner', repo: 'repo' };
    const event = {
      workflow_run: {
        id: 123,
        pull_requests: [{ number: 99 }]
      }
    };

    const mockFetch = async (url, opts = {}) => {
      if (url.includes('/actions/runs/123/jobs')) {
        return { ok: true, json: async () => ({ jobs: [] }) };
      }
      if (url.includes('/issues/99/comments') && !opts.method) {
        return {
          ok: true,
          json: async () => [{ id: 456, body: MARKERS.PR_CI_SUMMARY }]
        };
      }
      if (opts.method === 'PATCH') {
        return { ok: false, status: 500 };
      }
      return { ok: false };
    };

    await assert.rejects(
      async () => handleWorkflowRunCompleted({ client, event, fetchFn: mockFetch }),
      /Failed to update PR summary comment #456: HTTP 500/
    );
  });

  test('throws error when comment creation API fails', async () => {
    const client = { owner: 'owner', repo: 'repo' };
    const event = {
      workflow_run: {
        id: 123,
        pull_requests: [{ number: 99 }]
      }
    };

    const mockFetch = async (url, opts = {}) => {
      if (url.includes('/actions/runs/123/jobs')) {
        return { ok: true, json: async () => ({ jobs: [] }) };
      }
      if (url.includes('/issues/99/comments') && !opts.method) {
        return { ok: true, json: async () => [] };
      }
      if (opts.method === 'POST') {
        return { ok: false, status: 403 };
      }
      return { ok: false };
    };

    await assert.rejects(
      async () => handleWorkflowRunCompleted({ client, event, fetchFn: mockFetch }),
      /Failed to create PR summary comment on #99: HTTP 403/
    );
  });
});
