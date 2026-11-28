import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';

const WORKFLOWS_DIR = '.github/workflows';

function validateWorkflows() {
  const files = fs.readdirSync(WORKFLOWS_DIR).filter(f => f.endsWith('.yml') || f.endsWith('.yaml'));
  console.log(`Validating ${files.length} workflow files in ${WORKFLOWS_DIR}...`);

  let hasErrors = false;

  for (const file of files) {
    const filePath = path.join(WORKFLOWS_DIR, file);
    const content = fs.readFileSync(filePath, 'utf8');

    console.log(`\nChecking ${filePath}:`);

    // 1. Check for pull_request_target
    if (file === 'pull-request-policy.yml') {
      if (content.includes('pull_request_target')) {
        // Verify hardening: must checkout trusted base_ref and never PR head sha
        const hasBaseRefCheckout = content.includes('ref: ${{ github.base_ref || github.event.repository.default_branch }}');
        const hasHeadShaCheckout = content.includes('head.sha');
        if (hasBaseRefCheckout && !hasHeadShaCheckout) {
          console.log(`  ✔ Hardened pull_request_target used (executes only trusted base ref, no PR code checkout)`);
        } else {
          console.error(`  ❌ Insecure pull_request_target: must checkout base_ref only, never untrusted head SHA!`);
          hasErrors = true;
        }
      } else {
        console.error(`  ❌ pull-request-policy.yml expected to use hardened pull_request_target!`);
        hasErrors = true;
      }
    } else if (content.includes('pull_request_target')) {
      console.error(`  ❌ Forbidden trigger: pull_request_target detected in ${file}!`);
      hasErrors = true;
    } else {
      console.log(`  ✔ No pull_request_target used`);
    }

    // 1b. Check repository-wide concurrency queue for issue-commands.yml
    if (file === 'issue-commands.yml') {
      const hasRepoConcurrency = content.includes('group: issue-commands-${{ github.repository }}');
      const hasQueueMax = content.includes('queue: max');
      const hasCancelFalse = content.includes('cancel-in-progress: false');
      if (hasRepoConcurrency && hasQueueMax && hasCancelFalse) {
        console.log(`  ✔ Repository-wide concurrency queue (group: issue-commands-\${{ github.repository }}, queue: max, cancel-in-progress: false) verified`);
      } else {
        console.error(`  ❌ issue-commands.yml must specify repository-wide concurrency group (issue-commands-\${{ github.repository }}), queue: max, and cancel-in-progress: false!`);
        hasErrors = true;
      }
    }

    // 1c. Check CI workflow defines Maintainer Automation Tests job
    if (file === 'pull-request-ci.yml') {
      if (content.includes('name: Maintainer Automation Tests')) {
        console.log(`  ✔ Dedicated Maintainer Automation Tests job verified`);
      } else {
        console.error(`  ❌ pull-request-ci.yml must define Maintainer Automation Tests job!`);
        hasErrors = true;
      }
    }

    // 2. Check permissions block
    if (!content.includes('permissions:')) {
      console.error(`  ❌ Missing top-level permissions block!`);
      hasErrors = true;
    } else {
      console.log(`  ✔ Explicit permissions defined`);
    }

    // 3. Check action pinning (must be 40-character commit SHA)
    const usesMatches = content.matchAll(/uses:\s*([^\s#]+)(?:\s*#\s*([^\s\r\n]+))?/g);
    for (const match of usesMatches) {
      const actionRef = match[1];
      const commentTag = match[2];

      const parts = actionRef.split('@');
      if (parts.length === 2) {
        const [actionName, ref] = parts;
        const isSha = /^[0-9a-f]{40}$/i.test(ref);
        if (!isSha) {
          console.error(`  ❌ Unpinned action: ${actionRef}. Must use 40-character full commit SHA.`);
          hasErrors = true;
        } else {
          console.log(`  ✔ Pinned action: ${actionName}@${ref.substring(0, 7)} (${commentTag || 'no tag comment'})`);
        }
      }
    }

    // 4. Check for dangerous shell interpolation
    // Flags things like: run: echo "${{ github.event.comment.body }}"
    const lines = content.split(/\r?\n/);
    let inRun = false;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (/^\s*run:\s*/.test(line)) {
        inRun = true;
      } else if (/^\s*[a-zA-Z0-9_-]+:/.test(line)) {
        inRun = false;
      }

      if (inRun && /\${{\s*github\.event\.(comment|issue|pull_request)\./i.test(line)) {
        console.error(`  ❌ Dangerous inline expression in shell run block at line ${i + 1}: ${line}`);
        hasErrors = true;
      }
    }
    if (!hasErrors) {
      console.log(`  ✔ Safe shell execution (zero untrusted event interpolations)`);
    }
  }

  // 5. Run external workflow syntax linter (actionlint) if available on PATH
  console.log('\nChecking workflow syntax with actionlint (if available)...');
  try {
    execSync('actionlint', { stdio: ['ignore', 'pipe', 'pipe'], encoding: 'utf8' });
    console.log('  ✔ actionlint validation PASSED with 0 syntax or schema errors.');
  } catch (err) {
    const errorText = `${err.stderr || ''} ${err.stdout || ''} ${err.message || ''}`;
    if (err.code === 'ENOENT' || errorText.includes('is not recognized') || errorText.includes('not found')) {
      console.log('  ℹ actionlint is not installed in this environment; structural validation handled via Node.js rules.');
    } else {
      console.error('  ❌ actionlint detected workflow syntax errors:');
      console.error(err.stdout || err.stderr || err.message);
      hasErrors = true;
    }
  }

  if (hasErrors) {
    console.error('\nWorkflow validation FAILED.');
    process.exit(1);
  } else {
    console.log('\nAll workflow files PASSED security and pinning validation.');
  }
}

validateWorkflows();
