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

// Template path (under templates/) -> output path (in the app dir), and the flag that gates it
// ("!FLAG": only when FLAG is falsy).
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
  ['docs/deploy-kit/deploy.yml', 'docs/deploy-kit/deploy.yml', 'DOCKER'],
  ['docs/deploy-kit/deploy.vercel.yml', 'docs/deploy-kit/deploy.yml', 'VERCEL'],
  ['docs/deploy-kit/docker-smoke.sh', 'docs/deploy-kit/docker-smoke.sh', 'DOCKER', 0o755],
  ['docs/deploy-kit/Dockerfile.node', 'docs/deploy-kit/Dockerfile.node', 'DOCKER_NODE'],
  ['docs/deploy-kit/apk-release.sh', 'docs/deploy-kit/apk-release.sh', 'ANDROID', 0o755],
  // A monorepo has one CI workflow at its root: F01 adds this app's jobs to it from the snippet.
  ['docs/deploy-kit/ci-jobs.yml', 'docs/deploy-kit/ci-jobs.yml', 'MONOREPO'],
  ['dockerignore', '.dockerignore', 'MONOREPO'],
  ['github/ci.yml', '.github/workflows/ci.yml', '!MONOREPO'],
  // The droplet's own files; a Vercel app has none (reference/vercel.md).
  ['deploy/compose.deploy.yaml', 'deploy/compose.deploy.yaml', 'DOCKER'],
  ['deploy/nginx/app.conf', 'deploy/nginx/{{APP}}.conf', 'DOCKER'],
  ['deploy/nginx/app-bootstrap.conf', 'deploy/nginx/{{APP}}-bootstrap.conf', 'DOCKER'],
  ['deploy/placeholder/index.html', 'deploy/placeholder/index.html', 'DOCKER'],
];
// One file per entry in an array: [template, output pattern, array key, item-key prefix].
const PER_ITEM = [
  ['claude/agents/invariant-reviewer.md', '.claude/agents/{{R_NAME}}.md', 'INVARIANT_REVIEWERS', 'R_'],
  ['claude/rules/rule.md', '.claude/rules/{{RULE_FILE}}', 'RULES', 'RULE_'],
];

const REQUIRED = [
  'APP', 'APP_TITLE', 'APP_PITCH', 'OWNER', 'DOMAIN',
  'GH_REPO', 'REPO_URL', 'STACK', 'INSTALL_CMD', 'LOCKFILE', 'CHECKS', 'FORMAT_CMD', 'FORMATTER',
  'TYPECHECK', 'TEST_ONE_CMD', 'DEV_CMD', 'DEV_PORTS', 'HEALTH_PATH', 'UI', 'WEB', 'DB', 'DRAIN',
  'NEVER_BREAK', 'INVARIANT_REVIEWERS', 'RULES', 'DEPLOY_FEATURE', 'NODE_VERSION',
];
// Per DEPLOY_TARGET: the droplet (default) or Vercel (reference/vercel.md).
const REQUIRED_BY_TARGET = {
  droplet: ['PORT', 'CONTAINER_PORT', 'DROPLET', 'DOCKER_FEATURE', 'MEM_LIMIT'],
  vercel: ['VERCEL_SCOPE', 'VERCEL_PROJECT'],
};

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
  Object.assign(d, hookLists(v));
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
  Object.assign(d, monorepo(v));
  Object.assign(d, android(v, d));
  Object.assign(d, target(v, d));
  return d;
}

// FORMATTER and TYPECHECK: one object (or null), or an array of them. Entry 0 renders the usual
// hook file; each later entry (it needs a `name`) renders the same template again as
// format-file-<name>.mjs or stop-typecheck-<name>.mjs, and settings.json runs it beside the first.
function hookLists(v) {
  const split = (key, file, extraHook) => {
    const list = Array.isArray(v[key]) ? v[key] : [v[key]];
    for (const e of list.slice(1))
      if (!e || typeof e.name !== 'string' || !/^[a-z0-9-]+$/.test(e.name))
        fail(`${key}: every entry after the first needs a "name" (a-z, 0-9, -)`);
    const extras = list.slice(1).map((e) => ({ out: `.claude/hooks/${file}-${e.name}.mjs`, json: JSON.stringify(e) }));
    return [JSON.stringify(list[0] ?? null), extras, extras.map((x) => extraHook(x.out)).join('')];
  };
  const hook = (out, timeout) =>
    `, { "type": "command", "command": "node \\"$CLAUDE_PROJECT_DIR/${out}\\""${timeout ? `, "timeout": ${timeout}` : ''} }`;
  const [FORMATTER_JSON, FORMATTER_EXTRAS, FORMAT_HOOKS_EXTRA] = split('FORMATTER', 'format-file', (o) => hook(o));
  const [TYPECHECK_JSON, TYPECHECK_EXTRAS, STOP_HOOKS_EXTRA] = split('TYPECHECK', 'stop-typecheck', (o) => hook(o, 120));
  return { FORMATTER_JSON, FORMATTER_EXTRAS, FORMAT_HOOKS_EXTRA, TYPECHECK_JSON, TYPECHECK_EXTRAS, STOP_HOOKS_EXTRA };
}

// A native Android client in android/ beside the Node app (reference/stack-android.md). Standalone
// and monorepo alike; a monorepo's apps share one set of repo secrets, so the keystore's carry the
// app's name there.
function android(v, d) {
  const on = Boolean(v.ANDROID);
  if (on && !/^F\d+[a-z]?$/.test(v.APK_FEATURE ?? '')) fail('ANDROID needs APK_FEATURE, the release APK feature\'s roadmap ID (e.g. "F22")');
  return {
    ANDROID: on,
    APK_FEATURE: on ? v.APK_FEATURE : '',
    ANDROID_SECRET_PREFIX: on && d.MONOREPO ? `${d.APP_ID.toUpperCase()}_` : '',
    CHECKS_TIMEOUT: on ? 30 : 15,
  };
}

// DEPLOY_TARGET: "droplet" (Docker over SSH, the default) or "vercel" (the Vercel CLI from the
// GitHub workflow). DEPLOY_JOB and BUILD_STEP are the deploy workflow's names the autopilot matches.
function target(v, d) {
  const vercel = (v.DEPLOY_TARGET ?? 'droplet') === 'vercel';
  if (vercel && (d.MONOREPO || d.ANDROID)) fail('DEPLOY_TARGET "vercel" is standalone only, without ANDROID');
  return {
    VERCEL: vercel,
    DOCKER: !vercel,
    DOCKER_NODE: !vercel && d.NODE,
    DEPLOY_JOB: vercel ? 'vercel' : 'droplet',
    BUILD_STEP: vercel ? 'vercel build' : 'build and smoke-test the image',
    VERCEL_SCOPE: v.VERCEL_SCOPE ?? '',
    VERCEL_PROJECT: v.VERCEL_PROJECT ?? '',
  };
}

const reEscape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// Monorepo mode: the app is APP_DIR inside a bigger repo, and GH_REPO is that repo. The autopilot
// works in a git worktree on its own branch and may push only the app and a few root files
// (PUSH_ALLOWED). See reference/bootstrap-json.md. Standalone apps get empty values.
function monorepo(v) {
  if (!v.MONOREPO) {
    return {
      MONOREPO: false, APP_DIR: '', ROOT_REL: '', BRANCH: '', PUSH_ALLOWED: '', HUB: false, HUB_DIR: '',
      DEPLOY_SECRETS: '', DEPLOY_ENVIRONMENT: '',
    };
  }
  const dir = v.APP_DIR;
  if (typeof dir !== 'string' || !/^[A-Za-z0-9._-]+(\/[A-Za-z0-9._-]+)*$/.test(dir) || dir.split('/').some((p) => p === '..' || p === '.'))
    fail('MONOREPO needs APP_DIR, the app\'s path from the repo root (e.g. "pinpoint")');
  const hub = v.HUB ? (typeof v.HUB === 'object' ? v.HUB.dir : v.HUB) : '';
  if (hub && (typeof hub !== 'string' || !/^[A-Za-z0-9._-]+$/.test(hub))) fail('HUB.dir must be a top-level directory name');
  const workflows = ['ci', `deploy-${v.APP}`, ...(hub ? ['deploy-hub'] : [])].map(reEscape).join('|');
  const allowed =
    v.PUSH_ALLOWED ??
    `^(${reEscape(dir)}/|\\.github/workflows/(${workflows})\\.yml$|README\\.md$${hub ? `|${reEscape(hub)}/` : ''})`;
  try {
    new RegExp(allowed);
  } catch (e) {
    fail(`PUSH_ALLOWED is not a valid regex: ${e.message}`);
  }
  if (allowed.includes("'")) fail('PUSH_ALLOWED must not contain a single quote');
  const secrets = v.DEPLOY_SECRETS ?? ['SSH_HOST', 'SSH_USER', 'SSH_KEY', 'SSH_KNOWN_HOSTS'];
  if (!Array.isArray(secrets) || !secrets.every((s) => /^[A-Z][A-Z0-9_]*$/.test(s)))
    fail('DEPLOY_SECRETS must be an array of secret names');
  return {
    MONOREPO: true,
    APP_DIR: dir,
    ROOT_REL: '../'.repeat(dir.split('/').length),
    BRANCH: v.BRANCH ?? `autopilot/${v.APP}`,
    PUSH_ALLOWED: allowed,
    HUB: Boolean(hub),
    HUB_DIR: hub,
    DEPLOY_SECRETS: secrets.join(' '),
    DEPLOY_ENVIRONMENT: v.DEPLOY_ENVIRONMENT ?? 'production',
  };
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
  const deployTarget = facts.DEPLOY_TARGET ?? 'droplet';
  if (!(deployTarget in REQUIRED_BY_TARGET)) fail(`DEPLOY_TARGET must be "droplet" or "vercel", not ${JSON.stringify(deployTarget)}`);
  const missing = [...REQUIRED, ...REQUIRED_BY_TARGET[deployTarget]].filter((k) => !(k in facts));
  if (missing.length) fail(`bootstrap.json is missing: ${missing.join(', ')}`);
  if (!/^[a-z][a-z0-9-]{1,30}$/.test(facts.APP)) fail('APP must be a lowercase slug (a-z, 0-9, -)');
  const vars = { ...facts, ...derive(facts) };

  const jobs = [];
  for (const [tpl, outPattern, flag, mode] of MANIFEST) {
    if (flag && (flag.startsWith('!') ? vars[flag.slice(1)] : !vars[flag])) continue;
    jobs.push({ tpl, out: renderText(outPattern, vars, outPattern), vars, mode });
  }
  for (const { out, json } of vars.FORMATTER_EXTRAS)
    jobs.push({ tpl: 'claude/hooks/format-file.mjs', out, vars: { ...vars, FORMATTER_JSON: json } });
  for (const { out, json } of vars.TYPECHECK_EXTRAS)
    jobs.push({ tpl: 'claude/hooks/stop-typecheck.mjs', out, vars: { ...vars, TYPECHECK_JSON: json } });
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
