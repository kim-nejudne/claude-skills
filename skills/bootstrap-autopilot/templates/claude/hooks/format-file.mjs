// PostToolUse (Edit|Write): format the one file just written. Best effort: the verify skill's
// format check is the gate.
import { readFileSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { isAbsolute, join, relative, resolve } from 'node:path';

// { bin: path relative to the repo (or a command on PATH), args: [...], exts: [...] } or null.
const FORMATTER = {{FORMATTER_JSON}};

try {
  const input = JSON.parse(readFileSync(0, 'utf8') || '{}');
  if (!FORMATTER) process.exit(0);
  const root = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const filePath = input?.tool_input?.file_path;
  if (!filePath) process.exit(0);

  let rel = String(filePath).replace(/\\/g, '/');
  if (isAbsolute(rel) || /^[A-Za-z]:\//.test(rel)) rel = relative(root, resolve(rel)).replace(/\\/g, '/');
  if (rel.startsWith('../') || !FORMATTER.exts.some((ext) => rel.endsWith(ext))) process.exit(0);

  const local = join(root, FORMATTER.bin);
  // Before the first install there is nothing to run; that is not an error.
  const bin = FORMATTER.bin.includes('/') ? local : FORMATTER.bin;
  if (FORMATTER.bin.includes('/') && !existsSync(local)) process.exit(0);

  execFileSync(bin, [...FORMATTER.args, rel], { cwd: root, stdio: 'ignore', timeout: 10000 });
} catch {
  // Formatting is best-effort.
}
process.exit(0);
