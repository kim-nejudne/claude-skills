#!/usr/bin/env node
// Render the bootstrap-autopilot templates into an app repo.
//
//   node render.mjs <bootstrap.json> <repo-dir> [--force] [--only <out-path>...] [--list]
//
// <bootstrap.json> holds the project facts (see ../reference/bootstrap-json.md). The skill writes
// it to <repo>/.claude/bootstrap.json, which stays local (.claude/ is gitignored).
//
// Template syntax, deliberately small:
//   {{KEY}}                 a value from bootstrap.json or a derived value (see derive()).
//   {{#FLAG}} … {{/FLAG}}   kept only when FLAG is truthy; {{^FLAG}} … {{/FLAG}} only when falsy.
//                           A tag alone on its line removes that whole line.
// GitHub's ${{ expr }} has spaces and lowercase, so it never matches. Any {{UPPER}} left after
// rendering is an error, as is an unknown key.
//
// Existing files are never overwritten unless --force is given; skipped files are listed.
import { readFileSync, writeFileSync, mkdirSync, existsSync, chmodSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));

// Template path (under templates/) -> output path (in the repo), and the flag that gates it.
const MANIFEST = [
  ['gitignore', '.gitignore'],
  ['CLAUDE.md', 'CLAUDE.md'],
  ['autopilot.sh', 'scripts/autopilot.sh', null, 0o755],
  ['claude/settings.json', '.claude/settings.json'],
  ['claude/scripts/roadmap.mjs', '.claude/scripts/roadmap.mjs'],
  ['claude/scripts/spec.mjs', '.claude/scripts/spec.mjs'],
  ['claude/hooks/protect-files.mjs', '.claude/hooks/protect-files.mjs'],
  ['claude/hooks/format-file.mjs', '.claude/hooks/format-file.mjs'],
  ['claude/hooks/stop-typecheck.mjs', '.claude/hooks/stop-typecheck.mjs'],
  ['claude/hooks/session-context.mjs', '.claude/hooks/session-context.mjs'],
  ['claude/agents/spec-checker.md', '.claude/agents/spec-checker.md'],
  ['claude/agents/ui-reviewer.md', '.claude/agents/ui-reviewer.md', 'UI'],
  ['claude/agents/playtester.md', '.claude/agents/playtester.md', 'WEB'],
  ['claude/skills/next-feature/SKILL.md', '.claude/skills/next-feature/SKILL.md'],
  ['claude/skills/verify/SKILL.md', '.claude/skills/verify/SKILL.md'],
  ['claude/skills/review-feature/SKILL.md', '.claude/skills/review-feature/SKILL.md'],
  ['claude/skills/fix-bug/SKILL.md', '.claude/skills/fix-bug/SKILL.md'],
  ['claude/skills/add-feature/SKILL.md', '.claude/skills/add-feature/SKILL.md'],
  ['claude/skills/playtest/SKILL.md', '.claude/skills/playtest/SKILL.md', 'WEB'],
  ['claude/rules/tests.md', '.claude/rules/tests.md'],
  ['docs/PROGRESS.md', 'docs/PROGRESS.md'],
  ['docs/DECISIONS.md', 'docs/DECISIONS.md'],
  ['docs/deploy-kit/README.md', 'docs/deploy-kit/README.md'],
  ['docs/deploy-kit/deploy.yml', 'docs/deploy-kit/deploy.yml'],
  ['docs/deploy-kit/docker-smoke.sh', 'docs/deploy-kit/docker-smoke.sh', null, 0o755],
  ['docs/deploy-kit/Dockerfile.node', 'docs/deploy-kit/Dockerfile.node', 'NODE'],
  ['github/ci.yml', '.github/workflows/ci.yml'],
  ['deploy/compose.deploy.yaml', 'deploy/compose.deploy.yaml'],
  ['deploy/nginx/app.conf', 'deploy/nginx/{{APP}}.conf'],
  ['deploy/nginx/app-bootstrap.conf', 'deploy/nginx/{{APP}}-bootstrap.conf'],
  ['deploy/placeholder/index.html', 'deploy/placeholder/index.html'],
];
// One file per entry in an array: [template, output pattern, array key, item-key prefix].
const PER_ITEM = [
  ['claude/agents/invariant-reviewer.md', '.claude/agents/{{R_NAME}}.md', 'INVARIANT_REVIEWERS', 'R_'],
  ['claude/rules/rule.md', '.claude/rules/{{RULE_FILE}}', 'RULES', 'RULE_'],
];

const REQUIRED = [
  'APP', 'APP_TITLE', 'APP_PITCH', 'OWNER', 'DOMAIN', 'PORT', 'CONTAINER_PORT', 'DROPLET',
  'GH_REPO', 'REPO_URL', 'STACK', 'INSTALL_CMD', 'LOCKFILE', 'CHECKS', 'FORMAT_CMD', 'FORMATTER',
  'TYPECHECK', 'TEST_ONE_CMD', 'DEV_CMD', 'DEV_PORTS', 'HEALTH_PATH', 'UI', 'WEB', 'DB', 'DRAIN',
  'NEVER_BREAK', 'INVARIANT_REVIEWERS', 'RULES', 'DOCKER_FEATURE', 'DEPLOY_FEATURE', 'MEM_LIMIT',
  'NODE_VERSION',
];

function fail(message) {
  process.stderr.write(`render: ${message}\n`);
  process.exit(1);
}

const mdList = (items) => items.map((s) => `- ${s}`).join('\n');
const shq = (s) => `'${String(s).replace(/'/g, `'\\''`)}'`;

// Values the templates need in more than one shape, computed once from the facts.
function derive(v) {
  const d = {};
  const checks = v.CHECKS;
  if (!Array.isArray(checks) || !checks.length) fail('CHECKS must be a non-empty array');
  for (const c of checks) if (!c.name || !c.cmd) fail('every CHECKS entry needs name and cmd');
  d.CHECKS_BASH = checks.map((c) => `  ${shq(`${c.name}|${c.cmd}`)}`).join('\n');
  d.CHECKS_NAMES = checks.map((c) => c.name).join(', ');
  d.CHECKS_STEPS_MD = checks.map((c, i) => `${i + 1}. \`${c.cmd}\``).join('\n');
  d.CHECKS_TABLE_MD = ['| Stage | Result |', '| --- | --- |', ...checks.map((c) => `| ${c.name} | pass / fail |`)].join('\n');
  // Workflow steps; `ci: false` keeps a check out of CI (a build already done in the image).
  d.CHECKS_YAML = checks
    .filter((c) => c.ci !== false)
    .map((c) => `      - name: ${c.ciName ?? c.name}\n        run: ${c.cmd}`)
    .join('\n');
  // The step names the autopilot treats as "the code's fault" when the deploy run fails there.
  d.CI_STEPS_RE = checks
    .filter((c) => c.ci !== false)
    .map((c) => (c.ciName ?? c.name).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .join('|');
  // Headless sessions treat an `ask` rule as a refusal, so everything a feature session needs
  // (checks, formatter, installs) must be allowed outright (see reference/lessons.md).
  d.ALLOW_CMDS_ITEMS = [
    ...new Set([...checks.map((c) => c.cmd), v.FORMAT_CMD, v.INSTALL_CMD, v.TEST_ONE_CMD, ...(v.EXTRA_ALLOW ?? [])]),
  ]
    .filter(Boolean)
    .map((c) => c.replace(/\s*<[^>]*>.*$/, '').trim())
    .flatMap((c) => [`Bash(${c})`, `Bash(${c} *)`])
    .map((s) => JSON.stringify(s))
    .join(', ');
  const cmds = [
    ...checks.map((c) => [c.cmd, c.name]),
    [v.FORMAT_CMD, 'fix formatting'],
    [v.DEV_CMD, `dev server (${v.DEV_URL})`],
  ];
  const width = Math.max(...cmds.map(([c]) => c.length));
  d.COMMANDS_BLOCK = [
    ...cmds.map(([c, note]) => `${c.padEnd(width)}   # ${note}`),
    ...(v.EXTRA_COMMANDS_MD ? [v.EXTRA_COMMANDS_MD] : []),
  ].join('\n');
  d.BOOTSTRAP_DATE = v.BOOTSTRAP_DATE ?? new Date().toISOString().slice(0, 10);
  d.SMOKE_CMD = v.SMOKE_CMD ?? 'npm run smoke --';
  d.APP_ID = v.APP.replace(/-/g, '_');
  d.MAX_BODY = v.MAX_BODY ?? '1m';
  d.REPO_VISIBILITY = v.REPO_VISIBILITY ?? 'public';
  if (!['public', 'private'].includes(d.REPO_VISIBILITY))
    fail(`REPO_VISIBILITY must be "public" or "private", not ${JSON.stringify(d.REPO_VISIBILITY)}`);
  d.PLAYTEST_CMD = v.PLAYTEST_CMD ?? 'npm run playtest --';
  d.TEST_GLOBS = JSON.stringify(v.TEST_GLOBS ?? ['**/*.test.*', '**/*.spec.*', 'tests/**']);
  d.FORMATTER_JSON = JSON.stringify(v.FORMATTER);
  d.TYPECHECK_JSON = JSON.stringify(v.TYPECHECK);
  d.DEV_PORTS_SS = v.DEV_PORTS.map((p) => `sport = :${p}`).join(' or ');
  d.DEV_PORTS_LIST = v.DEV_PORTS.join(', ');
  d.REVIEWER_NAMES = v.INVARIANT_REVIEWERS.map((r) => r.NAME).join(', ');
  const fanout = v.INVARIANT_REVIEWERS.map((r) => `the \`${r.NAME}\` agent when ${r.WHEN}`);
  if (v.UI) fanout.push(`the \`ui-reviewer\` agent when ${v.UI_WHEN ?? 'UI code changed'}`);
  d.HAS_REVIEWERS = fanout.length > 0;
  d.REVIEWER_FANOUT = fanout.join(', ');
  d.NEVER_BREAK_MD = Array.isArray(v.NEVER_BREAK) ? mdList(v.NEVER_BREAK) : v.NEVER_BREAK;
  const skills = ['/next-feature builds the next feature. Also: /fix-bug, /add-feature, /verify'];
  if (v.WEB) skills.push('/playtest');
  d.WORKFLOW_LINE = skills.join(', ') + '.';
  d.NODE = v.STACK === 'node';
  d.LIVE_URL = `https://${v.DOMAIN}`;
  d.WORKFLOW_FILE = `deploy-${v.APP}.yml`;
  d.PUSH_URL_HINT = v.REPO_URL;
  d.STACK_SUMMARY = v.STACK_SUMMARY ?? v.STACK;
  d.HEAP_MB = v.HEAP_MB ?? 128;
  d.DATA_DIR = v.DB ? `/opt/${v.APP}/data` : '';
  return d;
}

function renderText(text, vars, where) {
  // Conditionals first, so a gated block's keys need not exist.
  const block = /^[ \t]*\{\{([#^])([A-Z][A-Z0-9_]*)\}\}[ \t]*\n([\s\S]*?)^[ \t]*\{\{\/\2\}\}[ \t]*\n|\{\{([#^])([A-Z][A-Z0-9_]*)\}\}([\s\S]*?)\{\{\/\5\}\}/m;
  let guard = 0;
  for (let m = block.exec(text); m; m = block.exec(text)) {
    if (++guard > 1000) fail(`${where}: runaway conditionals`);
    const [whole, lineSign, lineKey, lineBody, inSign, inKey, inBody] = m;
    const sign = lineSign ?? inSign;
    const key = lineKey ?? inKey;
    const body = lineBody ?? inBody;
    if (!(key in vars)) fail(`${where}: unknown flag ${key}`);
    const keep = sign === '#' ? Boolean(vars[key]) : !vars[key];
    text = text.slice(0, m.index) + (keep ? body : '') + text.slice(m.index + whole.length);
  }
  text = text.replace(/\{\{([A-Z][A-Z0-9_]*)\}\}/g, (_, key) => {
    if (!(key in vars)) fail(`${where}: unknown key ${key}`);
    const value = vars[key];
    if (value !== null && typeof value === 'object') fail(`${where}: ${key} is not a scalar`);
    return String(value);
  });
  const left = /\{\{[#^/]?[A-Z][A-Z0-9_]*\}\}/.exec(text);
  if (left) fail(`${where}: unrendered ${left[0]}`);
  return text;
}

function main() {
  const args = process.argv.slice(2);
  const force = args.includes('--force');
  const list = args.includes('--list');
  const onlyAt = args.indexOf('--only');
  const only = onlyAt >= 0 ? args.slice(onlyAt + 1) : null;
  const [jsonPath, repoDir] = args.filter((a, i) => !a.startsWith('--') && (onlyAt < 0 || i < onlyAt));
  if (!jsonPath || !repoDir) fail('usage: render.mjs <bootstrap.json> <repo-dir> [--force] [--list] [--only <out-path>...]');

  let facts;
  try {
    facts = JSON.parse(readFileSync(jsonPath, 'utf8'));
  } catch (e) {
    fail(`cannot read ${jsonPath}: ${e.message}`);
  }
  const missing = REQUIRED.filter((k) => !(k in facts));
  if (missing.length) fail(`bootstrap.json is missing: ${missing.join(', ')}`);
  if (!/^[a-z][a-z0-9-]{1,30}$/.test(facts.APP)) fail('APP must be a lowercase slug (a-z, 0-9, -)');
  const vars = { ...facts, ...derive(facts) };

  const jobs = [];
  for (const [tpl, outPattern, flag, mode] of MANIFEST) {
    if (flag && !vars[flag]) continue;
    jobs.push({ tpl, out: renderText(outPattern, vars, outPattern), vars, mode });
  }
  for (const [tpl, outPattern, key, prefix] of PER_ITEM) {
    for (const item of vars[key] ?? []) {
      const itemVars = { ...vars };
      // Arrays become a Markdown list, except PATHS (YAML frontmatter takes a JSON array).
      for (const [k, val] of Object.entries(item))
        itemVars[prefix + k] = Array.isArray(val) ? (k === 'PATHS' ? JSON.stringify(val) : mdList(val)) : val;
      jobs.push({ tpl, out: renderText(outPattern, itemVars, outPattern), vars: itemVars });
    }
  }

  const repo = resolve(repoDir);
  const written = [];
  const skipped = [];
  for (const job of jobs) {
    if (only && !only.includes(job.out)) continue;
    if (list) {
      process.stdout.write(`${job.out}\n`);
      continue;
    }
    const target = join(repo, job.out);
    if (existsSync(target) && !force) {
      skipped.push(job.out);
      continue;
    }
    const text = renderText(readFileSync(join(HERE, job.tpl), 'utf8'), job.vars, job.tpl);
    mkdirSync(dirname(target), { recursive: true });
    writeFileSync(target, text);
    if (job.mode) chmodSync(target, job.mode);
    written.push(job.out);
  }
  if (list) return;
  process.stdout.write(`wrote ${written.length} file(s)\n${written.map((f) => `  ${f}`).join('\n')}\n`);
  if (skipped.length) process.stdout.write(`skipped ${skipped.length} existing file(s) (use --force):\n${skipped.map((f) => `  ${f}`).join('\n')}\n`);
}

main();
