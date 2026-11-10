// PreToolUse (Edit|Write): block edits to owner-controlled, secret and generated files.
// Written by the bootstrap-autopilot skill for {{APP_TITLE}}.
import { readFileSync, existsSync } from 'node:fs';
import { isAbsolute, relative, resolve } from 'node:path';

const LOCKFILE = '{{LOCKFILE}}';

function normalise(filePath, root) {
  let p = String(filePath).replace(/\\/g, '/');
  if (isAbsolute(p) || /^[A-Za-z]:\//.test(p)) {
    p = relative(root, resolve(p)).replace(/\\/g, '/');
  }
  return p.replace(/^\.\//, '');
}

function block(reason) {
  process.stderr.write(reason + '\n');
  process.exit(2);
}

let input;
try {
  input = JSON.parse(readFileSync(0, 'utf8') || '{}');
} catch {
  process.exit(0);
}

try {
  const root = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const filePath = input?.tool_input?.file_path ?? input?.tool_input?.notebook_path;
  if (!filePath) process.exit(0);

  const rel = normalise(filePath, root);
  const segments = rel.split('/');
  const base = segments[segments.length - 1];

  if (rel.toLowerCase() === 'docs/spec.md' && !existsSync(resolve(root, '.claude/spec-unlocked'))) {
    block(
      'docs/spec.md is owner-controlled. Record the gap in docs/DECISIONS.md (and a // SPEC-QUESTION: comment at the code site). Only Kim may unlock it by creating .claude/spec-unlocked; never create that file yourself.',
    );
  }
  if (rel === '.claude/spec-unlocked') {
    block('.claude/spec-unlocked is Kim\'s switch. Never create it.');
  }
  if (rel === 'scripts/autopilot.sh') {
    block(
      'scripts/autopilot.sh is the unattended runner and may be running right now. Only Kim changes it; note what you need in docs/DECISIONS.md.',
    );
  }
  if (base === '.env' || base.startsWith('.env.')) {
    if (base !== '.env.example') block(`${rel}: .env files hold secrets and are off-limits. Code reads env vars; tests use fakes.`);
  }
{{#ANDROID}}
  if (/\.(jks|keystore|p12)$/i.test(base)) {
    block(`${rel}: signing keys never live in the repo. The release keystore exists only in GitHub secrets and Kim's backup.`);
  }
{{/ANDROID}}
  if (LOCKFILE && base === LOCKFILE) {
    block(`${rel}: the lockfile changes only through the package manager.`);
  }
  if (segments.includes('.git')) {
    block(`${rel}: files inside .git/ are never edited directly. Use git commands.`);
  }
} catch {
  // Never crash the tool call on a hook bug.
}
process.exit(0);
