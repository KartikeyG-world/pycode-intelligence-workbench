import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { validatePullRequestPolicy } from '../scripts/pr-policy.mjs';

function makeValidPrBody({
  linkedIssue = '101',
  assignmentConfirmed = true,
  aiChoice = 'No',
  understandConfirmed = true,
  noCopiedConfirmed = true,
  problem = 'Linear recurrence solver returns O(1) for recursive factorial step.',
  summary = 'Updated recurrence tree visitor to correctly recognize linear step functions.',
  verification = 'uv run pytest tests/test_recurrence_regression.py -v'
} = {}) {
  const aiSection = aiChoice === 'No'
    ? '- [x] No\n- [ ] Yes (please disclose tools used and extent of assistance below):'
    : (aiChoice === 'Yes'
      ? '- [ ] No\n- [x] Yes (Assisted with test docstrings):\nUsed Claude for test docstrings'
      : (aiChoice === 'Both'
        ? '- [x] No\n- [x] Yes'
        : '- [ ] No\n- [ ] Yes'));

  return `## Description

### Linked Issue
${linkedIssue ? `Closes #${linkedIssue}` : 'No issue linked'}

### Issue Assignment Confirmation
- [${assignmentConfirmed ? 'x' : ' '}] I confirm that this issue was formally assigned to me by a Project Admin or Mentor before I started work.

### Problem Addressed
${problem}

### Summary of Changes
${summary}

### Files / Modules Changed
backend/app/analyzers/recurrence_solver.py

### Key Design Decisions
Preserved AST immutability and zero-execution boundary.

---

## Verification & Testing

### Verification Commands & Environment
\`\`\`powershell
${verification}
\`\`\`

### Verification Outcome
- [x] Backend test(s) executed

---

## AI Assistance Disclosure

- **Did you use AI tools (e.g., Gemini, ChatGPT, Claude, Copilot) to assist with this pull request?**
  ${aiSection}
- [${understandConfirmed ? 'x' : ' '}] I confirm that I understand, have personally verified, and can explain every line of code and documentation submitted in this pull request.
- [${noCopiedConfirmed ? 'x' : ' '}] I confirm that this contribution contains no mass-generated, copied, or unverified code.
`;
}

function makePr(overrides = {}) {
  return {
    base: { ref: 'main' },
    draft: false,
    author_association: 'CONTRIBUTOR',
    user: { login: 'contributorA' },
    body: makeValidPrBody(),
    ...overrides
  };
}

function makeIssue(overrides = {}) {
  return {
    number: 101,
    state: 'open',
    pull_request: null,
    assignees: [{ login: 'contributorA' }],
    labels: [{ name: 'wocs' }, { name: 'level 2' }],
    ...overrides
  };
}

describe('Pull Request Policy Tests', () => {
  test('valid PR linked to WOCS issue with level 2 passes all checks', () => {
    const pr = makePr();
    const issue = makeIssue();
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: issue,
      prLabels: ['wocs', 'level 2']
    });

    assert.equal(result.valid, true);
    assert.deepEqual(result.errors, []);
  });

  test('valid PR with Level 1 passes', () => {
    const pr = makePr();
    const issue = makeIssue({ labels: [{ name: 'wocs' }, { name: 'level 1' }] });
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: issue,
      prLabels: ['wocs', 'level 1']
    });

    assert.equal(result.valid, true);
  });

  test('valid PR with Level 3 passes', () => {
    const pr = makePr();
    const issue = makeIssue({ labels: [{ name: 'wocs' }, { name: 'level 3' }] });
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: issue,
      prLabels: ['wocs', 'level 3']
    });

    assert.equal(result.valid, true);
  });

  test('PR targeting non-main branch fails', () => {
    const pr = makePr({ base: { ref: 'feature-dev' } });
    const issue = makeIssue();
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: issue,
      prLabels: ['wocs', 'level 2']
    });

    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /targets `feature-dev` branch instead of `main`/i);
  });

  test('draft PR defers full policy enforcement', () => {
    const pr = makePr({ draft: true });
    const issue = makeIssue();
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: issue,
      prLabels: []
    });

    assert.equal(result.isDraft, true);
    assert.equal(result.valid, true);
    assert.match(result.warnings[0], /draft/i);
  });

  test('missing linked issue reference fails for ordinary contributor', () => {
    const pr = makePr({ body: makeValidPrBody({ linkedIssue: null }) });
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: null,
      prLabels: ['wocs', 'level 2']
    });

    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /No linked issue reference found/i);
  });

  test('unassigned contributor on linked issue fails', () => {
    const pr = makePr();
    const issue = makeIssue({ assignees: [] });
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: issue,
      prLabels: ['wocs', 'level 2']
    });

    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /is unassigned/i);
  });

  test('wrong assigned contributor fails', () => {
    const pr = makePr();
    const issue = makeIssue({ assignees: [{ login: 'differentUser' }] });
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: issue,
      prLabels: ['wocs', 'level 2']
    });

    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /assigned to @differentUser, not PR author @contributorA/i);
  });

  test('missing assignment confirmation checkbox fails', () => {
    const pr = makePr({ body: makeValidPrBody({ assignmentConfirmed: false }) });
    const issue = makeIssue();
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: issue,
      prLabels: ['wocs', 'level 2']
    });

    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /Issue Assignment Confirmation checkbox is not checked/i);
  });

  test('missing AI disclosure choice fails', () => {
    const pr = makePr({ body: makeValidPrBody({ aiChoice: 'None' }) });
    const issue = makeIssue();
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: issue,
      prLabels: ['wocs', 'level 2']
    });

    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /neither `No` nor `Yes` is checked/i);
  });

  test('ambiguous AI disclosure (both Yes and No checked) fails', () => {
    const pr = makePr({ body: makeValidPrBody({ aiChoice: 'Both' }) });
    const issue = makeIssue();
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: issue,
      prLabels: ['wocs', 'level 2']
    });

    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /both `No` and `Yes` are checked/i);
  });

  test('missing AI ownership sub-confirmations fails', () => {
    const pr = makePr({ body: makeValidPrBody({ understandConfirmed: false }) });
    const issue = makeIssue();
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: issue,
      prLabels: ['wocs', 'level 2']
    });

    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /AI Disclosure confirmation missing/i);
  });

  test('missing wocs label on PR linked to WOCS issue generates actionable failure', () => {
    const pr = makePr();
    const issue = makeIssue(); // issue has wocs
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: issue,
      prLabels: ['level 2'] // missing wocs
    });

    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /missing the mandatory `wocs` label.*maintainer.*\/level/i);
  });

  test('missing difficulty label on PR linked to WOCS issue generates actionable failure', () => {
    const pr = makePr();
    const issue = makeIssue();
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: issue,
      prLabels: ['wocs'] // missing level label
    });

    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /missing a difficulty level label/i);
    assert.match(result.errors.join(' '), /\/level 1/i);
  });

  test('multiple difficulty labels on PR fails', () => {
    const pr = makePr();
    const issue = makeIssue();
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: issue,
      prLabels: ['wocs', 'level 1', 'level 2']
    });

    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /multiple conflicting difficulty labels/i);
  });

  test('empty Problem Addressed description fails', () => {
    const pr = makePr({ body: makeValidPrBody({ problem: '<!-- brief description -->' }) });
    const issue = makeIssue();
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: issue,
      prLabels: ['wocs', 'level 2']
    });

    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /Problem Addressed section is empty/i);
  });

  test('empty Verification Commands section fails', () => {
    const pr = makePr({ body: makeValidPrBody({ verification: '   ' }) });
    const issue = makeIssue();
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: issue,
      prLabels: ['wocs', 'level 2']
    });

    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /Verification Commands & Environment section is empty/i);
  });
});

describe('Owner-Authored Maintenance Exemption Tests (Section 5)', () => {
  // 1. OWNER-authored maintenance PR without linked issue
  test('1. OWNER-authored maintenance PR without linked issue passes with warnings', () => {
    const pr = makePr({
      author_association: 'OWNER',
      user: { login: 'repoOwner' },
      body: makeValidPrBody({ linkedIssue: null, assignmentConfirmed: false })
    });
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: null,
      prLabels: []
    });

    assert.equal(result.valid, true);
    assert.deepEqual(result.errors, []);
    assert.ok(result.warnings.some(w => w.includes('linked issue reference is exempt')));
    assert.ok(result.warnings.some(w => w.includes('assignment confirmation checkbox is exempt')));
  });

  // 2. OWNER-authored PR with a linked non-WOCS issue
  test('2. OWNER-authored PR with a linked non-WOCS issue passes without requiring WOCS assignment', () => {
    const pr = makePr({
      author_association: 'OWNER',
      user: { login: 'repoOwner' },
      body: makeValidPrBody({ linkedIssue: '50', assignmentConfirmed: false })
    });
    const nonWocsIssue = {
      number: 50,
      state: 'open',
      pull_request: null,
      assignees: [], // unassigned
      labels: [{ name: 'internal' }]
    };
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: nonWocsIssue,
      prLabels: []
    });

    assert.equal(result.valid, true);
    assert.deepEqual(result.errors, []);
    assert.ok(result.warnings.some(w => w.includes('issue assignment requirement on #50 is exempt')));
  });

  // 3. OWNER-authored WOCS PR strictly enforces all WOCS requirements
  test('3. OWNER-authored WOCS PR strictly enforces linked issue assignment and WOCS labels', () => {
    const pr = makePr({
      author_association: 'OWNER',
      user: { login: 'repoOwner' },
      body: makeValidPrBody({ linkedIssue: '101', assignmentConfirmed: false })
    });
    const wocsIssue = makeIssue({ assignees: [{ login: 'anotherPerson' }] }); // assigned to someone else
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: wocsIssue,
      prLabels: ['wocs'] // missing level label
    });

    assert.equal(result.valid, false);
    assert.ok(result.errors.some(e => e.includes('assigned to @anotherPerson, not PR author @repoOwner')));
    assert.ok(result.errors.some(e => e.includes('Issue Assignment Confirmation checkbox is not checked')));
    assert.ok(result.errors.some(e => e.includes('missing a difficulty level label')));
  });

  // 4. Ordinary contributor without linked issue is strictly rejected
  test('4. Ordinary contributor without linked issue is strictly rejected', () => {
    const pr = makePr({
      author_association: 'CONTRIBUTOR',
      user: { login: 'randomContributor' },
      body: makeValidPrBody({ linkedIssue: null })
    });
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: null,
      prLabels: []
    });

    assert.equal(result.valid, false);
    assert.ok(result.errors.some(e => e.includes('No linked issue reference found in PR description')));
  });

  // 5. Ordinary contributor without assignment confirmation is strictly rejected
  test('5. Ordinary contributor without assignment confirmation is strictly rejected', () => {
    const pr = makePr({
      author_association: 'CONTRIBUTOR',
      user: { login: 'contributorA' },
      body: makeValidPrBody({ linkedIssue: '101', assignmentConfirmed: false })
    });
    const issue = makeIssue();
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: issue,
      prLabels: ['wocs', 'level 2']
    });

    assert.equal(result.valid, false);
    assert.ok(result.errors.some(e => e.includes('Issue Assignment Confirmation checkbox is not checked')));
  });

  // 6. Collaborator attempting to use the owner exemption is rejected
  test('6. Collaborator attempting to use the owner exemption is rejected', () => {
    const pr = makePr({
      author_association: 'COLLABORATOR',
      user: { login: 'trustedCollaborator' },
      body: makeValidPrBody({ linkedIssue: null, assignmentConfirmed: false })
    });
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: null,
      prLabels: []
    });

    assert.equal(result.valid, false);
    assert.ok(result.errors.some(e => e.includes('No linked issue reference found in PR description')));
    assert.ok(result.errors.some(e => e.includes('Issue Assignment Confirmation checkbox is not checked')));
  });

  // 7. Correctly assigned external WOCS contribution passes all checks
  test('7. Correctly assigned external WOCS contribution passes all checks cleanly', () => {
    const pr = makePr({
      author_association: 'FIRST_TIME_CONTRIBUTOR',
      user: { login: 'studentContributor' },
      body: makeValidPrBody({ linkedIssue: '101', assignmentConfirmed: true })
    });
    const issue = makeIssue({ assignees: [{ login: 'studentContributor' }] });
    const result = validatePullRequestPolicy({
      pr,
      linkedIssue: issue,
      prLabels: ['wocs', 'level 2']
    });

    assert.equal(result.valid, true);
    assert.deepEqual(result.errors, []);
  });
});
