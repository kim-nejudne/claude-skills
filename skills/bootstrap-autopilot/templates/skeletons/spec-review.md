# <App> — Spec Review

<Date> · Review of `docs/spec.md` (<date>) through four lenses: product design, architecture, security and privacy, ops and deploy. No spec changes yet; each finding proposes the text the spec should say instead, and a default that applies if Kim doesn't choose.

> **Applied <date>.** <Filled in at the Q&A gate: which findings were applied as defaults, and Kim's answers to the forks.>

Ground rules:

- Items marked **[decided]** in the spec can be challenged. Findings that do so say **Reverses [decided]**.
- Severity: **Must** (blocks an unattended build or ships something broken or unsafe), **Should** (real cost if skipped), **Could** (polish).
- **Clear-cut** findings have one sensible answer and are applied as defaults. **Fork** findings are a genuine product or cost choice and go to Kim, one question at a time.

## Verdict

<3–6 sentences: what is strong, the top three risks, whether the spec can drive an unattended build once the Musts are applied.>

## Locks

These are fixed before the roadmap, because changing them after launch touches every screen and test:

- **Audience and locale:** <who uses it, where, which language(s), US or UK spelling, units, time zones>.
- **Look:** <the mock or design reference that is the target, light/dark, the fonts>.
- **Stack:** <named by the spec, or the default>.
- **Keyed services:** <each, with its fake for build sessions>.
- **Data:** <in memory / SQLite on a volume / other; backups>.

## Findings

### Product designer

#### 1. <Title>

- **Severity:** Must | Should | Could · **Kind:** clear-cut | fork
- **Where:** <spec sections>
- **What goes wrong:** <a concrete scene: who does what, what breaks>
- **Proposed spec text:**
  - <exact wording to add or replace>
- **Default:** <what gets applied if Kim doesn't choose>

### Architect / tech lead

### Security / privacy

### Ops / deploy

## Questions for Kim

<Only the forks, numbered, each with its options and the default.>
