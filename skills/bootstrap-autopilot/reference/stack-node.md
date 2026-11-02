# Default stack: F01 scaffold

Used when the spec names no stack: Node 24, TypeScript, Vite + React, vitest, eslint + prettier, npm, one Node process (Express) serving the API and the built client. This is the shape Sketchy and Buzzr shipped. Adapt, don't copy blindly: an app with no server drops `server/`, one with no UI drops `client/`.

## Layout

```
client/            index.html, src/main.tsx, src/… (Vite root)
server/            http.ts (createApp(): routes, /healthz, static dist/client in production), index.ts (listen)
shared/            types, zod schemas, constants used by both sides
scripts/           autopilot.sh (bootstrap), playtest/ (web apps), smoke.ts (F<n-1>)
docs/              spec, review, roadmap, progress, decisions, design/, deploy-kit/
deploy/            compose.deploy.yaml, nginx/, placeholder/ (bootstrap)
```

## package.json

- `"type": "module"`, `"engines": {"node": ">=24"}`, npm.
- Scripts:
  - `dev`: `concurrently` running `tsx watch server/index.ts` and `vite` (Vite on `0.0.0.0:5173`, proxying `/api` and `/healthz` to `:3000`; add `/socket.io` with `ws: true` if the spec uses WebSockets)
  - `build`: `vite build && tsc -p tsconfig.build.json`
  - `start`: `NODE_ENV=production node dist/server/index.js`
  - `test`: `vitest run` · `typecheck`: `tsc -p tsconfig.json --noEmit && tsc -p tsconfig.node.json --noEmit`
  - `lint`: `eslint .` · `format`: `prettier --write .` · `format:check`: `prettier --check .`
  - `playtest`: `tsx scripts/playtest/run.ts` (web apps)
- Install only what F01 uses: `express`, `react`, `react-dom`; dev: `vite`, `@vitejs/plugin-react`, `typescript`, `tsx`, `concurrently`, `vitest`, `eslint`, `@eslint/js`, `typescript-eslint`, `eslint-plugin-react-hooks`, `globals`, `eslint-config-prettier`, `prettier`, `@types/node`, `@types/express`, `@types/react`, `@types/react-dom`, `playwright` (web apps). Later features add `zod`, a CSS framework and the rest, each with a one-line reason. Use current stable majors.

## Config

- `tsconfig.json` (client + shared): `target ES2023`, `module ESNext`, `moduleResolution bundler`, `jsx react-jsx`, `strict`, `noUncheckedIndexedAccess`, `noFallthroughCasesInSwitch`, `isolatedModules`, `verbatimModuleSyntax`, `skipLibCheck`, `noEmit`, `types: ["vite/client"]`.
- `tsconfig.node.json` (server, shared, scripts, configs): the same strictness, `module NodeNext`, `types: ["node"]`. `tsconfig.build.json` emits `server` and `shared` to `dist/`.
- `eslint.config.js`: flat config; `js.configs.recommended`, `tseslint.configs.recommended`, node globals for `server/ shared/ scripts/ *.config.* .claude/**/*.mjs`, browser globals plus `react-hooks` for `client/`, `eslint-config-prettier` last; ignore `dist/ coverage/ .playtest/ test-results/ playwright-report/`.
- `.prettierrc.json`: `{"singleQuote": true, "printWidth": 100}`. `.prettierignore`: `docs/`, `.claude/`, `dist/`, `coverage/`, `.playtest/`, `package-lock.json`, `deploy/`.
- `vite.config.ts`: root `client`, build to `dist/client`, server host `0.0.0.0` port 5173 with the proxies; vitest `include: ['{client,server,shared,scripts}/**/*.test.{ts,tsx}']`, node environment (jsdom per file where needed).
- `.env.example`: every env var the app reads, with fake or empty values and a comment each. Never a real value.

## Runtime stubs

- `server/http.ts`: `createApp()` with `GET /healthz` → `{ok: true}`; in production serves `dist/client` with an `index.html` fallback for client routes, never for `/api/` (an API 404 must stay a 404). `server/index.ts` listens on `PORT` (default 3000) and shuts down on SIGTERM.
- `server/http.test.ts`: the F01 test (`/healthz` answers `{ok: true}`; an unknown `/api/` path is 404).
- `client/index.html` with the viewport meta and `client/src/main.tsx`: a placeholder page using DESIGN.md's tokens and fonts.

## Playtest harness (web apps)

`scripts/playtest/harness.ts`: plain `playwright` (not `@playwright/test`). `launch()`, `openRole(role, device, path)` (one isolated browser context per role or user; devices from DESIGN.md's target viewports, Pixel 7 and iPhone 13 emulation for phones), console-error capture per role, `screenshot(step)` into `.playtest/<id>/`, `closeAll()`. Fall back to `/usr/bin/chromium` when Playwright's browser isn't downloaded (`npx playwright install chromium` in prep if Kim allows). `scripts/playtest/run.ts` runs a scenario file's default export `(h: Harness) => Promise<void>` and exits non-zero on failure, screenshotting every role. `scripts/playtest/smoke.ts` opens the app and asserts it loaded with no console errors.

## bootstrap.json values for this stack

```json
"STACK": "node",
"STACK_SUMMARY": "Node 24 + TypeScript, Express API, Vite + React client, vitest",
"NODE_VERSION": "24",
"INSTALL_CMD": "npm ci",
"LOCKFILE": "package-lock.json",
"SCAFFOLD_FILE": "package.json",
"CHECKS": [
  { "name": "format:check", "cmd": "npm run format:check", "ciName": "format check" },
  { "name": "lint", "cmd": "npm run lint" },
  { "name": "typecheck", "cmd": "npm run typecheck" },
  { "name": "test", "cmd": "npm test", "ciName": "tests" },
  { "name": "build", "cmd": "npm run build", "ci": false }
],
"FORMAT_CMD": "npm run format",
"FORMATTER": { "bin": "node_modules/.bin/prettier", "args": ["--write", "--log-level", "warn"], "exts": [".ts", ".tsx", ".js", ".mjs", ".json", ".css", ".md"] },
"TYPECHECK": { "cmd": ["npm", "run", "typecheck"], "exts": [".ts", ".tsx"], "needs": "node_modules/.bin/tsc" },
"TEST_ONE_CMD": "npx vitest run <file>",
"DEV_CMD": "npm run dev",
"DEV_URL": "http://localhost:5173",
"DEV_PORTS": [3000, 5173],
"CONTAINER_PORT": 3000,
"HEALTH_PATH": "/healthz",
"SMOKE_CMD": "npm run smoke --",
"PLAYTEST_CMD": "npm run playtest --",
"TEST_GLOBS": ["**/*.test.ts", "**/*.test.tsx"],
"EXTRA_ALLOW": ["npm install", "npm uninstall", "npx tsx", "npx tsc", "npx eslint", "npx prettier", "npx playwright install"]
```

`build` stays out of CI (`"ci": false`): the image build runs it on the deploy runner. It still runs in the verify skill and the autopilot's gate.
