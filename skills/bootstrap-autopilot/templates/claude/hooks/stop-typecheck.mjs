// Stop: refuse to finish while changed source fails to typecheck.
import { readFileSync, existsSync } from 'node:fs';
import { execFileSync, spawnSync } from 'node:child_process';
import { join } from 'node:path';

// { cmd: [...argv], exts: [...], needs: path that must exist first } or null to disable.
const TYPECHECK = {{TYPECHECK_JSON}};

try {
  const input = JSON.parse(readFileSync(0, 'utf8') || '{}');
  if (input.stop_hook_active === true || !TYPECHECK) process.exit(0);

  const root = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  // Before the scaffold and the first install there is nothing to check.
  if (TYPECHECK.needs && !existsSync(join(root, TYPECHECK.needs))) process.exit(0);

  let status = '';
  try {
    status = execFileSync('git', ['status', '--porcelain', '--untracked-files=all'{{#MONOREPO}}, '--', '.'{{/MONOREPO}}], {
      cwd: root,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
      timeout: 5000,
    });
  } catch {
    process.exit(0);
  }
  const changed = status
    .split(/\r?\n/)
    .filter(Boolean)
    .some((line) => TYPECHECK.exts.some((ext) => line.trim().replace(/"$/, '').endsWith(ext)));
  if (!changed) process.exit(0);

  const [cmd, ...args] = TYPECHECK.cmd;
  const result = spawnSync(cmd, args, { cwd: root, encoding: 'utf8', timeout: 110000 });
  if (result.status === 0 || result.error) process.exit(0);

  const output = `${result.stdout ?? ''}${result.stderr ?? ''}`.split(/\r?\n/);
  process.stderr.write(output.slice(-40).join('\n') + '\nFix these type errors before finishing.\n');
  process.exit(2);
} catch {
  process.exit(0);
}
