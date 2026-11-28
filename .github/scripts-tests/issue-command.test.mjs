import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { parseCommand, extractLinkedIssueNumber } from '../scripts/lib/command-parser.mjs';
import { handleIssueComment } from '../scripts/issue-command.mjs';

function createMockClient(initialState = {}) {
  const state = {
    issue: {
      number: 101,
      state: 'open',
      locked: false,
      assignees: [],
      labels: [{ name: 'wocs' }, { name: 'level 2' }],
      ...(initialState.issue || {})
    },
    pr: {
      number: 202,
      body: 'Closes #101\nFixes complexity bug',
      user: { login: 'contributorA' },
      labels: [{ name: 'wocs' }],
      ...(initialState.pr || {})
    },
    collaboratorPermission: initialState.collaboratorPermission || 'write',
    activeWocsIssues: initialState.activeWocsIssues || [],
    comments: [],
    labelsAdded: [],
    labelsRemoved: [],
    addAssigneesError: initialState.addAssigneesError || null,
    assigneesRaceWinner: initialState.assigneesRaceWinner || null
  };

  const client = {
    owner: 'KartikeyG-world',
    repo: 'pycode-intelligence-workbench',
    state,
    async getIssue(issueNumber) {
      if (initialState.issueNotFound) {
        const err = new Error('Not found');
        err.status = 404;
        throw err;
      }
      return { ...state.issue, number: issueNumber };
    },
    async createComment(issueNumber, body) {
      state.comments.push({ issueNumber, body });
      return { id: state.comments.length, body };
    },
    async addAssignees(issueNumber, assignees) {
      if (state.addAssigneesError) {
        throw new Error(state.addAssigneesError);
      }
      if (state.assigneesRaceWinner) {
        // Simulate race condition where someone else got assigned
        state.issue.assignees = [{ login: state.assigneesRaceWinner }];
      } else {
        state.issue.assignees = assignees.map(login => ({ login }));
      }
      return state.issue;
    },
    async removeAssignees(issueNumber, assignees) {
      const loginsToRemove = new Set(assignees);
      state.issue.assignees = state.issue.assignees.filter(a => !loginsToRemove.has(a.login));
      return state.issue;
    },
    async listOpenWocsIssuesForAssignee(username) {
      return state.activeWocsIssues;
    },
    async getCollaboratorPermission(username) {
      return state.collaboratorPermission;
    },
    async getPullRequest(prNumber) {
      return { ...state.pr, number: prNumber };
    },
    async addLabels(issueNumber, labels) {
      state.labelsAdded.push(...labels);
      state.pr.labels.push(...labels.map(l => ({ name: l })));
      return state.pr.labels;
    },
    async removeLabel(issueNumber, labelName) {
      state.labelsRemoved.push(labelName);
      state.pr.labels = state.pr.labels.filter(l => l.name !== labelName);
      return null;
    }
  };

  return client;
}

function makeEvent({ body, author = 'contributorA', action = 'created', isPr = false, isBot = false }) {
  return {
    action,
    issue: {
      number: isPr ? 202 : 101,
      pull_request: isPr ? { url: 'https://api.github.com/repos/test/pulls/202' } : undefined
    },
    comment: {
      id: 555,
      body,
      user: {
        login: author,
        type: isBot ? 'Bot' : 'User'
      }
    }
  };
}

describe('Command Parser Tests', () => {
  test('parses standalone /claim', () => {
    const res = parseCommand('/claim');
    assert.deepEqual(res, { command: 'claim', args: [], rawLine: '/claim' });
  });

  test('parses /assign with leading/trailing whitespace', () => {
    const res = parseCommand('   /assign   ');
    assert.deepEqual(res, { command: 'assign', args: [], rawLine: '/assign' });
  });

  test('parses /level with argument', () => {
    const res = parseCommand('/level 2');
    assert.deepEqual(res, { command: 'level', args: ['2'], rawLine: '/level 2' });
  });

  test('parses command when followed by contributor explanation lines', () => {
    const body = '/claim\nI would like to resolve this with AST visitor.';
    const res = parseCommand(body);
    assert.deepEqual(res, { command: 'claim', args: [], rawLine: '/claim' });
  });

  test('ignores commands embedded inside ordinary discussion text', () => {
    const body = 'I think we should not /claim this yet until reviewed.';
    const res = parseCommand(body);
    assert.equal(res, null);
  });

  test('ignores commands inside blockquotes', () => {
    const body = '> /claim this issue\nI agree with the quote above.';
    const res = parseCommand(body);
    assert.equal(res, null);
  });

  test('ignores commands inside markdown code blocks', () => {
    const body = '```bash\n/claim\n```\nHere is some code.';
    const res = parseCommand(body);
    assert.equal(res, null);
  });

  test('extracts linked issue from PR body', () => {
    assert.equal(extractLinkedIssueNumber('Closes #101'), 101);
    assert.equal(extractLinkedIssueNumber('Fixes: #42'), 42);
    assert.equal(extractLinkedIssueNumber('Resolves #789\nSome notes'), 789);
    assert.equal(extractLinkedIssueNumber('No linked issue here'), null);
  });
});

describe('Issue Command Bot Tests', () => {
  test('/claim on an unassigned eligible issue succeeds', async () => {
    const client = createMockClient();
    const event = makeEvent({ body: '/claim', author: 'newContributor' });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, true);
    assert.equal(result.action, 'claim_approved');
    assert.equal(client.state.comments.length, 1);
    assert.match(client.state.comments[0].body, /claim has been successfully approved/i);
    assert.deepEqual(client.state.issue.assignees, [{ login: 'newContributor' }]);
  });

  test('/assign acts as an exact alias for /claim', async () => {
    const client = createMockClient();
    const event = makeEvent({ body: '/assign', author: 'newContributor' });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, true);
    assert.equal(result.action, 'claim_approved');
    assert.match(client.state.comments[0].body, /claim has been successfully approved/i);
  });

  test('race condition: two contributors requesting same issue (loser rejected)', async () => {
    const client = createMockClient({ assigneesRaceWinner: 'competitorBob' });
    const event = makeEvent({ body: '/claim', author: 'slowAlice' });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, true);
    assert.equal(result.action, 'claim_lost_race');
    assert.match(client.state.comments[0].body, /already been assigned to @competitorBob/i);
  });

  test('already assigned issue rejects new claim', async () => {
    const client = createMockClient({
      issue: { assignees: [{ login: 'existingUser' }] }
    });
    const event = makeEvent({ body: '/claim', author: 'anotherUser' });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, true);
    assert.equal(result.action, 'claim_rejected_already_assigned');
    assert.match(client.state.comments[0].body, /already been assigned to @existingUser/i);
  });

  test('closed issue rejects claim', async () => {
    const client = createMockClient({
      issue: { state: 'closed' }
    });
    const event = makeEvent({ body: '/claim', author: 'someone' });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, true);
    assert.equal(result.action, 'claim_rejected_closed');
    assert.match(client.state.comments[0].body, /issue is closed/i);
  });

  test('locked issue rejects claim', async () => {
    const client = createMockClient({
      issue: { locked: true }
    });
    const event = makeEvent({ body: '/claim', author: 'someone' });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, true);
    assert.equal(result.action, 'claim_rejected_locked');
    assert.match(client.state.comments[0].body, /issue is locked/i);
  });

  test('missing wocs label rejects claim', async () => {
    const client = createMockClient({
      issue: { labels: [{ name: 'enhancement' }, { name: 'level 1' }] }
    });
    const event = makeEvent({ body: '/claim', author: 'someone' });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, true);
    assert.equal(result.action, 'claim_rejected_missing_wocs');
    assert.match(client.state.comments[0].body, /mandatory `wocs` label/i);
  });

  test('missing difficulty label rejects claim', async () => {
    const client = createMockClient({
      issue: { labels: [{ name: 'wocs' }] }
    });
    const event = makeEvent({ body: '/claim', author: 'someone' });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, true);
    assert.equal(result.action, 'claim_rejected_missing_level');
    assert.match(client.state.comments[0].body, /approved difficulty label/i);
  });

  test('multiple difficulty labels reject claim', async () => {
    const client = createMockClient({
      issue: { labels: [{ name: 'wocs' }, { name: 'level 1' }, { name: 'level 2' }] }
    });
    const event = makeEvent({ body: '/claim', author: 'someone' });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, true);
    assert.equal(result.action, 'claim_rejected_conflicting_levels');
    assert.match(client.state.comments[0].body, /multiple conflicting difficulty labels/i);
  });

  test('maximum active issue limit (> 2 active WOCS issues) rejects claim', async () => {
    const client = createMockClient({
      activeWocsIssues: [
        { number: 10, title: 'Issue 10' },
        { number: 11, title: 'Issue 11' }
      ]
    });
    const event = makeEvent({ body: '/claim', author: 'busyContributor' });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, true);
    assert.equal(result.action, 'claim_rejected_max_issues');
    assert.match(client.state.comments[0].body, /at most \*\*two active WOCS issues\*\*/i);
  });

  test('ineligible GitHub user API failure handled gracefully', async () => {
    const client = createMockClient({
      addAssigneesError: 'User is not eligible to be assigned'
    });
    const event = makeEvent({ body: '/claim', author: 'ineligibleUser' });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, true);
    assert.equal(result.action, 'claim_failed_api_error');
    assert.match(client.state.comments[0].body, /assignment could not be completed via GitHub API/i);
  });

  test('successful /unclaim by assigned contributor', async () => {
    const client = createMockClient({
      issue: { assignees: [{ login: 'currentAssignee' }] }
    });
    const event = makeEvent({ body: '/unclaim', author: 'currentAssignee' });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, true);
    assert.equal(result.action, 'unclaim_success');
    assert.equal(client.state.issue.assignees.length, 0);
    assert.match(client.state.comments[0].body, /unassigned from this issue/i);
  });

  test('attempted /unclaim by another user is rejected', async () => {
    const client = createMockClient({
      issue: { assignees: [{ login: 'currentAssignee' }] }
    });
    const event = makeEvent({ body: '/unclaim', author: 'intruder' });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, true);
    assert.equal(result.action, 'unclaim_not_assignee');
    assert.match(client.state.comments[0].body, /cannot unclaim this issue because it is not currently assigned to you/i);
  });

  test('/help returns documentation', async () => {
    const client = createMockClient();
    const event = makeEvent({ body: '/help' });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, true);
    assert.equal(result.action, 'help');
    assert.match(client.state.comments[0].body, /Workbench Maintainer Bot Commands/i);
  });

  test('/status returns correct status report', async () => {
    const client = createMockClient();
    const event = makeEvent({ body: '/status' });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, true);
    assert.equal(result.action, 'status');
    assert.match(client.state.comments[0].body, /Issue Status & WOCS Eligibility/i);
    assert.match(client.state.comments[0].body, /Available for claiming/i);
  });

  test('bot comments are ignored', async () => {
    const client = createMockClient();
    const event = makeEvent({ body: '/claim', isBot: true });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, false);
    assert.match(result.reason, /bot/i);
    assert.equal(client.state.comments.length, 0);
  });

  test('malformed/unknown commands are ignored', async () => {
    const client = createMockClient();
    const event = makeEvent({ body: 'Just a regular comment' });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, false);
    assert.equal(client.state.comments.length, 0);
  });

  test('non-created actions (e.g. edited) are ignored', async () => {
    const client = createMockClient();
    const event = makeEvent({ body: '/claim', action: 'edited' });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, false);
    assert.equal(client.state.comments.length, 0);
  });
});

describe('Maintainer PR /level Command Tests', () => {
  test('/level 2 by maintainer applies label and removes conflicting levels', async () => {
    const client = createMockClient({
      collaboratorPermission: 'maintain',
      issue: {
        number: 101,
        assignees: [{ login: 'prAuthor' }],
        labels: [{ name: 'wocs' }]
      },
      pr: {
        number: 202,
        body: 'Closes #101\nSome description',
        user: { login: 'prAuthor' },
        labels: [{ name: 'level 1' }]
      }
    });

    const event = makeEvent({ body: '/level 2', author: 'maintainerAlice', isPr: true });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, true);
    assert.equal(result.action, 'level_2_applied');
    assert.ok(client.state.labelsRemoved.includes('level 1'));
    assert.ok(client.state.labelsAdded.includes('level 2'));
    assert.match(client.state.comments[0].body, /level successfully set to \*\*level 2\*\*/i);
  });

  test('/level rejected when executed by non-maintainer', async () => {
    const client = createMockClient({
      collaboratorPermission: 'read'
    });

    const event = makeEvent({ body: '/level 2', author: 'regularUser', isPr: true });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, true);
    assert.equal(result.action, 'level_unauthorized');
    assert.match(client.state.comments[0].body, /do not have permission/i);
  });

  test('/level rejected when executed on issue instead of PR', async () => {
    const client = createMockClient({ collaboratorPermission: 'admin' });
    const event = makeEvent({ body: '/level 2', author: 'maintainerAlice', isPr: false });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, true);
    assert.equal(result.action, 'level_on_issue_rejected');
    assert.match(client.state.comments[0].body, /can only be used on pull request/i);
  });

  test('/level rejected when linked issue is missing', async () => {
    const client = createMockClient({
      collaboratorPermission: 'write',
      pr: { body: 'No link here' }
    });

    const event = makeEvent({ body: '/level 2', author: 'maintainerAlice', isPr: true });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, true);
    assert.equal(result.action, 'level_missing_linked_issue');
    assert.match(client.state.comments[0].body, /No linked issue/i);
  });

  test('/level rejected when PR author is not assigned to linked issue', async () => {
    const client = createMockClient({
      collaboratorPermission: 'write',
      issue: {
        number: 101,
        assignees: [{ login: 'differentPerson' }],
        labels: [{ name: 'wocs' }]
      },
      pr: {
        number: 202,
        body: 'Closes #101',
        user: { login: 'prAuthor' }
      }
    });

    const event = makeEvent({ body: '/level 2', author: 'maintainerAlice', isPr: true });
    const result = await handleIssueComment({ client, event });

    assert.equal(result.handled, true);
    assert.equal(result.action, 'level_author_not_assigned');
    assert.match(client.state.comments[0].body, /not an assigned contributor/i);
  });
});
