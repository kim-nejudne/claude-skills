---
name: fiction-companion
description: Write spoiler-safe, text-only reading companions for a novel or story collection (EPUB). Each chapter gets a Before you read (recap of the previous chapter, cumulative cast) and an After you read (what happened, cast, craft, themes so far, close reading, questions); the book gets a spoiler-free intro and a full-spoiler end essay. Splits with /fiction-split if needed. A sequential pass writes a short digest per chapter; then parallel writers each read their chapter plus the earlier digests (never later text), a separate Sonnet checker per unit hunts leaks, a subagent writes the end essay, and the main agent writes the intro and checks consistency. Resumable. Runs without questions.
argument-hint: "<book.epub or book folder>"
disable-model-invocation: true
allowed-tools: Bash(uv run:*), Bash(python3 -I:*), Bash(mkdir:*), Bash(grep:*), Bash(wc:*), Read, Write, Edit, Agent
---

# Fiction reading companions

**Argument:** $ARGUMENTS is the book EPUB or its folder. `BOOKDIR` is that folder.

**Ask Kim nothing, and don't stop for a pilot.** Make the best call at every step and list each
guess in the final report. Kim may be away for hours, so finish the whole run.

**Paths:**
- `SKILL` = `/home/kim/.claude/skills/fiction-companion`
- `TEXTDIR` = `BOOKDIR/companions/.text`
- `DIGESTDIR` = `BOOKDIR/companions/.digest`
- `SRC` = `BOOKDIR/companions/src`
- `SCRATCH` = `<scratchpad>`

Use absolute paths everywhere.

**Bash:** run every Bash call on its own, one per message. The auto-mode classifier often gives no
verdict on parallel calls.

**Never edit `SKILL/` files.** Read `SKILL/references/spec.md` first: the format and the
spoiler and text-only rules, which are not negotiable.

**Keep your own context small.** It is re-sent with every step, for the whole run. Read the first
unit's text (for the intro) and nothing else of the book: no other `.text` file, no digests, no
whole companions. Work from the subagents' reports and `check.py` output.

## 1. Split
If `BOOKDIR/companions/.units.json` does not exist, follow
`/home/kim/.claude/skills/fiction-split/SKILL.md` in full. Then read the manifest: `form`, and
each unit's `slug`, `title`, `kind`, `number`, `part` and `words`.

## 2. Book settings
Run `mkdir -p SRC DIGESTDIR`. If `SRC/book.json` does not exist, write
`{"book": "<title>", "author": "<author>", "form": "<novel | collection>"}`.

## 3. Digests (novels only; a collection skips this step)
A digest records what the book has told the reader by the end of one unit, in two files:
`DIGESTDIR/<slug>.md` (what happens) and `DIGESTDIR/<slug>.cast.md` (the cumulative cast and
threads). Writers and checkers read the earlier "what happens" files and the previous cast file
instead of the whole book so far, which keeps each agent's context to about one chapter.

One subagent per unit, **in order, one at a time**: each starts after the previous returns,
because it builds on the previous cast file. Skip units whose two files both exist.
Each prompt tells the subagent to read `SKILL/references/digest-brief.md` and follow it, with a
values block: AUTHOR, BOOK, BOOKDIR, the unit's title, slug and words, and PREVIOUS CAST (the
previous unit's `.cast.md` path, or "none"). General-purpose, no model set.

Check that each report shows no remaining check.py lines before launching the next.

## 4. Write the units: parallel writers, Sonnet checkers
**Resume:** skip every unit whose `SRC/<slug>.md` already exists, and list the skipped units in the
report. To redo a unit, Kim deletes its .md.

Each writer's prompt is short. It tells the subagent to read `SKILL/references/writer-brief.md`
and follow it, and gives a **values block** that fills every `{…}` in the brief:
- AUTHOR, BOOK, FORM, BOOKDIR;
- the unit's title, slug and words;
- EYEBROW;
- PARTS, PREVIOUS UNIT;
- **CHAPTER:** `TEXTDIR/<slug>.txt` of this unit;
- **DIGESTS:** `DIGESTDIR/<slug>.md` of units 1..N−1, in order ("none" for the first unit and for
  every story in a collection);
- **CAST:** `DIGESTDIR/<slug>.cast.md` of unit N−1 ("none" likewise);
- **EARLIER:** `TEXTDIR/<slug>.txt` of units 1..N−1 ("none" likewise).

**Unit advice:** add a line of advice only from what the unit's own text shows (e.g. "mostly
dialogue", "a letter fills the second half"), found by grepping that one file. Never from your
memory of the book: advice naming a later event is itself a leak.

**Launch:** start up to 8 general-purpose writers in one message, so they run in parallel; launch
the next as one returns. Don't set a model, so they inherit yours.

**Checkers:** as each writer returns, launch a checker for that unit: general-purpose, with
`model: "sonnet"`. Its prompt tells it to read `SKILL/references/checker-brief.md` and follow it,
with READ = the unit's text, the same DIGESTS, CAST and EARLIER, and the rest of the values block. A
checker never checks a unit it wrote. Keep every writer's and checker's report for step 7.

## 5. Intro (main agent)
Write `SRC/intro.md` unless it exists.
- Sources: the first unit's text and the manifest's unit list, nothing else.
- Format: the spec's "Intro" section.
- Then launch a checker on it (Sonnet, the checker brief): SLUG `intro`, READ = the first unit's
  text, DIGESTS, CAST and EARLIER "none". Tell it the intro has its own structure (spec, "Intro").

## 6. End essay (subagent)
Once every unit is written, and unless `SRC/end.md` exists: launch one general-purpose subagent
(no model set) to read `SKILL/references/end-brief.md` and follow it. Values: AUTHOR, BOOK, FORM,
BOOKDIR, DIGESTS (every `<slug>.md`, in order), CAST (the last unit's `.cast.md`), LAST (the final
one or two units' text paths).

Then launch a checker on it (Sonnet): SLUG `end`, READ = the last units' texts, DIGESTS = all,
CAST = the last unit's, EARLIER = every other unit's text. Tell it that for end.md there are no spoiler limits: its job is
the text-only rules, quotes and accuracy.

## 7. Consistency and checks (main agent)
**Check** every .md, intro and end included:
```
python3 -I SKILL/scripts/check.py SRC/<slug>.md BOOKDIR
```
- Every SPOILER QUOTE, MISS, LOCATOR, STRUCTURE, LENGTH and CAST line must be fixed.
  CAST means a unit's Characters so far lacks someone in the previous unit's `.cast.md`.
- Each remaining LATER WORD must have a checker's or your verdict of "harmless".

**Consistency:**
- Compare the checkers' reports for clashes: the same character described differently, a
  "new" tag on someone an earlier cast file already holds.
- Fix those directly in the .md, with Grep on SRC rather than reading whole files. Import nothing
  from a later unit into an earlier one.
- Settle anything a checker could not.

## 8. Report
Make it concise:
- The units written and skipped, with word counts against target.
- **Spoiler findings, unit by unit, verbatim from the checkers:** what leaked, from where (memory,
  a later chapter, foreshadowing), and what was done. Say "none" for clean units.
- LATER WORD verdicts kept as harmless.
- Outside-knowledge items removed.
- Consistency fixes.
- Remaining check.py lines, and why each is acceptable.
- Guesses: unit advice, borderline allusions, anything the spec didn't settle.
- Any permission prompts or Bash calls outside the allowed list, yours or the subagents'.

The EPUB is built separately with `/fiction-epub BOOKDIR`.
