import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
  generateCiSummaryComment,
  handleWorkflowRunCompleted,
  EXPECTED_JOBS
} from '../scripts/pr-summary.mjs';
import { MARKERS } from '../scripts/lib/response-templates.mjs';

describe('PR CI Summary Tests - Strict Job Validation & Idempotency', () => {
  // Helper for generating all 4 passing expected jobs
  const makeAllFourPassingJobs = () => [
    { name: 'Backend Validation (Python 3.11)', conclusion: 'success' },
    { name: 'Backend Validation (Python 3.13)', conclusion: 'success' },
    { name: 'Frontend Validation (Lint, Typecheck, Build)', conclusion: 'success' },
    { name: 'Maintainer Automation Tests', conclusion: 'success' }
  ];

  // 1. All four expected jobs present and passing
  test('1. generates markdown summary with success badges when all four expected jobs pass', () => {
    const jobs = makeAllFourPassingJobs();
    const comment = generateCiSummaryComment({
      jobs,
      runUrl: 'https://github.com/owner/repo/actions/runs/12345',
      overallConclusion: 'success'
    });

    assert.ok(comment.includes(MARKERS.PR_CI_SUMMARY));
    assert.match(comment, /Backend Validation \(Python 3.11\).*✅ Passed/);
    assert.match(comment, /Backend Validation \(Python 3.13\).*✅ Passed/);
    assert.match(comment, /Frontend Validation \(Lint, Typecheck, Build\).*✅ Passed/);
    assert.match(comment, /Maintainer Automation Tests.*✅ Passed/);
    assert.match(comment, /All automated CI checks passed/);
    assert.match(comment, /Maintainer review is pending/);
  });

  // 2. One expected job missing
  test('2. rejects when one expected job is missing (e.g. Maintainer Automation Tests)', () => {
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

    assert.match(comment, /One or more checks failed or incomplete/);
    assert.ok(!comment.includes('All automated CI checks passed!'));
  });

  // 3. Two expected jobs missing
  test('3. rejects when two expected jobs are missing', () => {
    const jobs = [
      { name: 'Backend Validation (Python 3.11)', conclusion: 'success' },
      { name: 'Frontend Validation (Lint, Typecheck, Build)', conclusion: 'success' }
    ];
    const comment = generateCiSummaryComment({
      jobs,
      runUrl: 'https://github.com/owner/repo/actions/runs/12345',
      overallConclusion: 'success'
    });

    assert.match(comment, /One or more checks failed or incomplete/);
    assert.ok(!comment.includes('All automated CI checks passed!'));
  });

  // 4. Duplicate expected job
  test('4. rejects when duplicate expected jobs are returned', () => {
    const jobs = [
      ...makeAllFourPassingJobs(),
      { name: 'Maintainer Automation Tests', conclusion: 'success' } // duplicate
    ];
    const comment = generateCiSummaryComment({
      jobs,
      runUrl: 'https://github.com/owner/repo/actions/runs/12345',
      overallConclusion: 'success'
    });

    assert.match(comment, /One or more checks failed or incomplete/);
    assert.ok(!comment.includes('All automated CI checks passed!'));
  });

  // 5. One failed job
  test('5. rejects when one expected job has failed', () => {
    const jobs = [
      { name: 'Backend Validation (Python 3.11)', conclusion: 'failure' },
      { name: 'Backend Validation (Python 3.13)', conclusion: 'success' },
      { name: 'Frontend Validation (Lint, Typecheck, Build)', conclusion: 'success' },
      { name: 'Maintainer Automation Tests', conclusion: 'success' }
    ];
    const comment = generateCiSummaryComment({
      jobs,
      runUrl: 'https://github.com/owner/repo/actions/runs/12345',
      overallConclusion: 'failure'
    });

    assert.match(comment, /Backend Validation \(Python 3.11\).*❌ Failed/);
    assert.match(comment, /One or more checks failed or incomplete/);
    assert.ok(!comment.includes('All automated CI checks passed!'));
  });

  // 6. One skipped job
  test('6. rejects when one expected job was skipped', () => {
    const jobs = [
      { name: 'Backend Validation (Python 3.11)', conclusion: 'success' },
      { name: 'Backend Validation (Python 3.13)', conclusion: 'skipped' },
      { name: 'Frontend Validation (Lint, Typecheck, Build)', conclusion: 'success' },
      { name: 'Maintainer Automation Tests', conclusion: 'success' }
    ];
    const comment = generateCiSummaryComment({
      jobs,
      runUrl: 'https://github.com/owner/repo/actions/runs/12345',
      overallConclusion: 'success'
    });

    assert.match(comment, /Backend Validation \(Python 3.13\).*⚪ Skipped/);
    assert.match(comment, /One or more checks failed or incomplete/);
    assert.ok(!comment.includes('All automated CI checks passed!'));
  });

  // 7. One cancelled job
  test('7. rejects when one expected job was cancelled', () => {
    const jobs = [
      { name: 'Backend Validation (Python 3.11)', conclusion: 'success' },
      { name: 'Backend Validation (Python 3.13)', conclusion: 'cancelled' },
      { name: 'Frontend Validation (Lint, Typecheck, Build)', conclusion: 'success' },
      { name: 'Maintainer Automation Tests', conclusion: 'success' }
    ];
    const comment = generateCiSummaryComment({
      jobs,
      runUrl: 'https://github.com/owner/repo/actions/runs/12345',
      overallConclusion: 'cancelled'
    });

    assert.match(comment, /Backend Validation \(Python 3.13\).*⚪ Cancelled/);
    assert.match(comment, /One or more checks failed or incomplete/);
    assert.ok(!comment.includes('All automated CI checks passed!'));
  });

  // 8. Null conclusion
  test('8. rejects when a job conclusion is null (still in progress or unknown)', () => {
    const jobs = [
      { name: 'Backend Validation (Python 3.11)', conclusion: 'success' },
      { name: 'Backend Validation (Python 3.13)', conclusion: null },
      { name: 'Frontend Validation (Lint, Typecheck, Build)', conclusion: 'success' },
      { name: 'Maintainer Automation Tests', conclusion: 'success' }
    ];
    const comment = generateCiSummaryComment({
      jobs,
      runUrl: 'https://github.com/owner/repo/actions/runs/12345',
      overallConclusion: 'in_progress'
    });

    assert.match(comment, /Backend Validation \(Python 3.13\).*⏳ In Progress/);
    assert.match(comment, /One or more checks failed or incomplete/);
    assert.ok(!comment.includes('All automated CI checks passed!'));
  });

  // 9. Unknown job only
  test('9. rejects when only unknown or arbitrary jobs are returned', () => {
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

  // 10. Jobs API failure
  test('10. reports error message when jobs API query failed', () => {
    const comment = generateCiSummaryComment({
      jobs: [],
      runUrl: 'https://github.com/owner/repo/actions/runs/12345',
      overallConclusion: 'failure',
      errorMessage: 'GitHub API error fetching jobs (HTTP 500)'
    });

    assert.match(comment, /Error Retrieving CI Job Details:\*\* GitHub API error fetching jobs \(HTTP 500\)/);
    assert.match(comment, /Check run outcome could not be verified automatically/);
  });

  // 11. Comments API failure
  test('11. throws error and stops when comments listing API fails (does not duplicate comments)', async () => {
    const client = { owner: 'owner', repo: 'repo' };
    const event = {
      workflow_run: {
        id: 123,
        pull_requests: [{ number: 99 }]
      }
    };

    let postAttempted = false;

    const mockFetch = async (url, opts = {}) => {
      if (url.includes('/actions/runs/123/jobs')) {
        return { ok: true, json: async () => ({ jobs: makeAllFourPassingJobs() }) };
      }
      if (url.includes('/issues/99/comments') && !opts.method) {
        return { ok: false, status: 502 }; // Bad Gateway listing comments
      }
      if (opts.method === 'POST') {
        postAttempted = true;
        return { ok: true, json: async () => ({ id: 999 }) };
      }
      return { ok: false };
    };

    await assert.rejects(
      async () => handleWorkflowRunCompleted({ client, event, fetchFn: mockFetch }),
      /Failed to list comments for PR #99 \(HTTP 502\): cannot safely determine existing summary status/
    );
    assert.equal(postAttempted, false, 'Should never attempt creating comment when listing comments fails');
  });

  // 12. Comment update failure
  test('12. throws error when comment update API fails', async () => {
    const client = { owner: 'owner', repo: 'repo' };
    const event = {
      workflow_run: {
        id: 123,
        pull_requests: [{ number: 99 }]
      }
    };

    const mockFetch = async (url, opts = {}) => {
      if (url.includes('/actions/runs/123/jobs')) {
        return { ok: true, json: async () => ({ jobs: makeAllFourPassingJobs() }) };
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

  // 13. Comment creation failure
  test('13. throws error when comment creation API fails', async () => {
    const client = { owner: 'owner', repo: 'repo' };
    const event = {
      workflow_run: {
        id: 123,
        pull_requests: [{ number: 99 }]
      }
    };

    const mockFetch = async (url, opts = {}) => {
      if (url.includes('/actions/runs/123/jobs')) {
        return { ok: true, json: async () => ({ jobs: makeAllFourPassingJobs() }) };
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

  // 14. Existing summary comment beyond the first API page
  test('14. correctly discovers existing summary comment on page 2 via pagination and updates it', async () => {
    const client = { owner: 'owner', repo: 'repo' };
    const event = {
      workflow_run: {
        id: 123,
        html_url: 'https://github.com/owner/repo/actions/runs/123',
        conclusion: 'success',
        pull_requests: [{ number: 99 }]
      }
    };

    const requestedPages = [];
    let updatedCommentId = null;
    let postCalled = false;

    const mockFetch = async (url, opts = {}) => {
      if (url.includes('/actions/runs/123/jobs')) {
        return {
          ok: true,
          json: async () => ({ jobs: makeAllFourPassingJobs() })
        };
      }
      if (url.includes('/issues/99/comments') && !opts.method) {
        const parsedUrl = new URL(url);
        const page = parseInt(parsedUrl.searchParams.get('page'), 10);
        requestedPages.push(page);

        if (page === 1) {
          // Page 1: 100 regular comments without the marker
          const page1Comments = Array.from({ length: 100 }, (_, i) => ({
            id: i + 1,
            body: `Regular comment #${i + 1}`
          }));
          return { ok: true, json: async () => page1Comments };
        } else if (page === 2) {
          // Page 2: Summary comment is present
          return {
            ok: true,
            json: async () => [
              { id: 777, body: `${MARKERS.PR_CI_SUMMARY}\nOld status on page 2` }
            ]
          };
        }
        return { ok: true, json: async () => [] };
      }
      if (url.includes('/issues/comments/777') && opts.method === 'PATCH') {
        updatedCommentId = 777;
        return { ok: true, json: async () => ({ id: 777 }) };
      }
      if (url.includes('/issues/99/comments') && opts.method === 'POST') {
        postCalled = true;
        return { ok: true, json: async () => ({ id: 888 }) };
      }
      return { ok: false, status: 404 };
    };

    const result = await handleWorkflowRunCompleted({ client, event, fetchFn: mockFetch });
    assert.equal(result.handled, true);
    assert.equal(result.action, 'comment_updated');
    assert.deepEqual(requestedPages, [1, 2]);
    assert.equal(updatedCommentId, 777);
    assert.equal(postCalled, false, 'Should not create duplicate comment when comment exists on page 2');
  });

  // 15. Four expected jobs plus additional successful unknown job
  test('15. rejects when four expected jobs are present plus an additional successful unknown job', () => {
    const jobs = [
      ...makeAllFourPassingJobs(),
      { name: 'Unexpected Extra Step', conclusion: 'success' }
    ];
    const comment = generateCiSummaryComment({
      jobs,
      runUrl: 'https://github.com/owner/repo/actions/runs/12345',
      overallConclusion: 'success'
    });

    assert.match(comment, /One or more checks failed or incomplete/);
    assert.ok(!comment.includes('All automated CI checks passed!'));
  });

  // 16. Four expected jobs plus additional failed unknown job
  test('16. rejects when four expected jobs are present plus an additional failed unknown job', () => {
    const jobs = [
      ...makeAllFourPassingJobs(),
      { name: 'Unexpected Extra Step', conclusion: 'failure' }
    ];
    const comment = generateCiSummaryComment({
      jobs,
      runUrl: 'https://github.com/owner/repo/actions/runs/12345',
      overallConclusion: 'failure'
    });

    assert.match(comment, /One or more checks failed or incomplete/);
    assert.ok(!comment.includes('All automated CI checks passed!'));
  });

  // 17. Empty job results
  test('17. rejects when jobs array is empty', () => {
    const comment = generateCiSummaryComment({
      jobs: [],
      runUrl: 'https://github.com/owner/repo/actions/runs/12345',
      overallConclusion: 'success'
    });

    assert.match(comment, /No Job Execution Records Available/);
    assert.match(comment, /Checks unverified/);
    assert.ok(!comment.includes('All automated CI checks passed!'));
  });
});
