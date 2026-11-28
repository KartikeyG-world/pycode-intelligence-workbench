import fs from 'node:fs';
import path from 'node:path';

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
    if (content.includes('pull_request_target')) {
      console.error(`  ❌ Forbidden trigger: pull_request_target detected!`);
      hasErrors = true;
    } else {
      console.log(`  ✔ No pull_request_target used`);
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

  if (hasErrors) {
    console.error('\nWorkflow validation FAILED.');
    process.exit(1);
  } else {
    console.log('\nAll workflow files PASSED security and pinning validation.');
  }
}

validateWorkflows();
