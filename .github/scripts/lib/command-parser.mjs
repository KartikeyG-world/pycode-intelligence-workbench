/**
 * Strict command parser for issue and pull-request comments.
 * Adheres to repository security guidelines: prevents execution of commands
 * embedded in ordinary text, blockquotes, or markdown code blocks.
 */

const KNOWN_COMMANDS = ['claim', 'assign', 'unclaim', 'help', 'status', 'level'];

/**
 * Parses a comment body and extracts any valid, standalone command directive.
 *
 * @param {string} body - Raw comment markdown text
 * @returns {{ command: string, args: string[], rawLine: string } | null}
 */
export function parseCommand(body) {
  if (!body || typeof body !== 'string') {
    return null;
  }

  const lines = body.split(/\r?\n/);
  let inCodeBlock = false;

  for (const rawLine of lines) {
    const trimmed = rawLine.trim();

    // Toggle multi-line code block state
    if (trimmed.startsWith('```')) {
      inCodeBlock = !inCodeBlock;
      continue;
    }

    // Skip if inside a code block or blockquote or empty line
    if (inCodeBlock || trimmed.startsWith('>') || trimmed.length === 0) {
      continue;
    }

    // Skip inline code formatting that wraps the command e.g. `/claim`
    if (trimmed.startsWith('`') && trimmed.endsWith('`') && trimmed.length > 2) {
      continue;
    }

    // Command must start with '/' as the first non-whitespace character
    if (trimmed.startsWith('/')) {
      const match = trimmed.match(/^\/([a-zA-Z0-9_-]+)(?:\s+(.*))?$/);
      if (!match) {
        continue;
      }

      const cmdName = match[1].toLowerCase();
      const rawArgs = match[2] ? match[2].trim() : '';
      const args = rawArgs.length > 0 ? rawArgs.split(/\s+/) : [];

      if (KNOWN_COMMANDS.includes(cmdName)) {
        return {
          command: cmdName,
          args,
          rawLine: trimmed
        };
      }
    }
  }

  return null;
}

/**
 * Extracts linked issue number from pull request body.
 * Matches standard GitHub keywords: Closes #123, Fixes #123, Resolves #123, etc.
 *
 * @param {string} body - Pull request markdown body
 * @returns {number | null} Issue number if found, or null
 */
export function extractLinkedIssueNumber(body) {
  if (!body || typeof body !== 'string') {
    return null;
  }

  // Support Closes #123, Fixes #123, Resolves #123 (case-insensitive)
  // Also supports Closes: #123 or Fix: #123
  const pattern = /(?:close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)[:\s]+#(\d+)\b/i;
  const match = body.match(pattern);
  if (match) {
    const num = parseInt(match[1], 10);
    return isNaN(num) ? null : num;
  }

  return null;
}
