// SessionStart: print a short project briefing that becomes Claude's context.
import { readFileSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';

const LINE = /^\s*- \[( |~|x|!)\] ([FB]\d+[a-z]?)\s+(.*)$/;

function git(args, cwd) {
  try {
    return execFileSync('git', args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], timeout: 3000 }).trim();
  } catch {
    return null;
  }
}

try {
  try {
    readFileSync(0, 'utf8');
  } catch {
    // no stdin
  }
  const root = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const out = [];

  const roadmapPath = join(root, 'docs', 'ROADMAP.md');
  if (existsSync(roadmapPath)) {
    const lines = readFileSync(roadmapPath, 'utf8').split(/\r?\n/);
    const items = [];
    lines.forEach((line, index) => {
      const m = LINE.exec(line);
      if (m) items.push({ mark: m[1], id: m[2], title: m[3].trim(), start: index });
    });
    for (const [k, item] of items.entries()) {
      const end = k + 1 < items.length ? items[k + 1].start : lines.length;
      item.gated = lines.slice(item.start + 1, end).some((l) => /^\s*- Gate:/.test(l));
    }
    const features = items.filter((i) => i.id.startsWith('F'));
    const done = features.filter((i) => i.mark === 'x').length;
    out.push(`Roadmap: ${done}/${features.length} features done`);
    for (const i of items.filter((i) => i.mark === '~')) out.push(`In progress: ${i.id} ${i.title}`);
    for (const i of items.filter((i) => i.mark === '!')) out.push(`BLOCKED: ${i.id} ${i.title} (see note in ROADMAP.md)`);
    for (const i of features.filter((i) => i.gated && i.mark !== 'x')) out.push(`Gated (Kim approves): ${i.id} ${i.title}`);
    const openBugs = items.filter((i) => i.id.startsWith('B') && i.mark === ' ');
    if (openBugs.length) out.push(`Open bugs: ${openBugs.map((i) => i.id).join(', ')}`);
    const next = features.find((i) => i.mark === ' ' && !i.gated);
    out.push(next ? `Next todo: ${next.id} ${next.title}` : 'Next todo: none');
  } else {
    out.push('Roadmap: docs/ROADMAP.md not found');
  }

  const progressPath = join(root, 'docs', 'PROGRESS.md');
  if (existsSync(progressPath)) {
    const text = readFileSync(progressPath, 'utf8');
    const marker = text.indexOf('<!-- entries below, newest first -->');
    const body = marker >= 0 ? text.slice(marker).split(/\r?\n/).slice(1) : [];
    const start = body.findIndex((l) => l.startsWith('## '));
    if (start >= 0) {
      const entry = [];
      for (let k = start; k < body.length; k++) {
        if (k > start && body[k].startsWith('## ')) break;
        entry.push(body[k]);
      }
      while (entry.length && entry[entry.length - 1].trim() === '') entry.pop();
      out.push('Latest progress entry:');
      out.push(...entry.slice(0, 15));
    } else {
      out.push('Latest progress entry: none yet');
    }
  }

  // symbolic-ref also works before the first commit, when rev-parse HEAD fails.
  const branch = git(['symbolic-ref', '--short', 'HEAD'], root) ?? git(['rev-parse', '--abbrev-ref', 'HEAD'], root);
  if (branch === null) {
    out.push('Git: not a repository');
  } else {
    const status = git(['status', '--porcelain', '--untracked-files=all'{{#MONOREPO}}, '--', '.'{{/MONOREPO}}], root) ?? '';
    const changed = status ? status.split(/\r?\n/).filter(Boolean).length : 0;
    const last = git(['log', '-1', '--format=%h %s'{{#MONOREPO}}, '--', '.'{{/MONOREPO}}], root) || 'no commits yet';
    out.push(`Git: branch ${branch}, ${changed} uncommitted file(s), last commit: ${last}`);
  }

  out.push('Workflow: {{WORKFLOW_LINE}}');
  process.stdout.write(out.slice(0, 30).join('\n') + '\n');
} catch {
  // Never block a session on a briefing failure.
}
process.exit(0);
