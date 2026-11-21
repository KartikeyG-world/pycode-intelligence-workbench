## Description

### Linked Issue
Closes #<!-- issue number -->

### Issue Assignment Confirmation
- [ ] I confirm that this issue was formally assigned to me by a Project Admin or Mentor before I started work.

### Problem Addressed
<!-- Brief description of the problem, bug, or feature being solved -->

### Summary of Changes
<!-- Coherent summary of what was added, fixed, or updated -->

### Files / Modules Changed
<!-- List modified files or components -->

### Key Design Decisions
<!-- Explain architectural choices or contract considerations -->

---

## Verification & Testing

### Verification Commands & Environment
<!--
Provide exact commands executed, runtime versions, and environment details.
Example:
  cd backend; uv run pytest tests/test_complexity_analyzer.py -v
  cd frontend; npm run lint; npx tsc --noEmit; npm run build
-->
```powershell

```

### Verification Outcome
- [ ] Backend test(s) executed (record module names and pass counts):
- [ ] Frontend linting (`npm run lint`) passed with 0 errors.
- [ ] Frontend type-check (`npx tsc --noEmit`) passed with 0 errors.
- [ ] Frontend build (`npm run build`) succeeded.

### Known Limitations or Partial Behaviors
<!-- List any partial behavior, unsupported syntax, or environment constraints -->

### UI Changes & Visual Proof
<!-- Required for any visual, layout, or frontend UI modification -->
- [ ] Not applicable (no UI changes).
- [ ] UI changes included below (attach before / after screenshots or recordings):

### Documentation Updates
- [ ] Documentation updated to reflect changes (or not required).

---

## AI Assistance Disclosure

- **Did you use AI tools (e.g., Gemini, ChatGPT, Claude, Copilot) to assist with this pull request?**
  - [ ] No
  - [ ] Yes (please disclose tools used and extent of assistance below):
- [ ] I confirm that I understand, have personally verified, and can explain every line of code and documentation submitted in this pull request.
- [ ] I confirm that this contribution contains no mass-generated, copied, or unverified code.

---

## Maintainer Review & WOCS Scoring Checklist (Maintainer Use Only)

- [ ] **Issue Assignment:** Verified that the contributor was assigned to the linked issue prior to PR submission.
- [ ] **Technical Correctness:** Verifies AST immutability, deterministic complexity modeling, and contract compliance.
- [ ] **Static-Only Security Boundary:** Confirmed no `eval`, `exec`, execution-oriented compilation, or runtime tracing.
- [ ] **Tests & Verification Evidence:** Adequate tests provided and exact execution evidence documented.
- [ ] **UI Screenshots:** Screenshots provided for visual/component modifications (if applicable).
- [ ] **Documentation:** Accurate and updated where public behavior or contracts changed.
- [ ] **WOCS Labels Applied (Mandatory Before Merging):**
  - [ ] `wocs`
  - Exactly one difficulty level determined by maintainer based on verified scope:
    - [ ] `level 1`
    - [ ] `level 2`
    - [ ] `level 3`
