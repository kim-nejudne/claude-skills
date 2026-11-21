---
name: fiction-split
description: Find the body units of a novel or story-collection EPUB (one per chapter, prologue, epilogue or story; never grouped), drop front and back matter, and write the hidden manifest companions/.units.json plus each unit's plain text in companions/.text/, which /fiction-companion and /fiction-epub reuse. EPUB input only. Runs without questions; guesses are reported at the end.
argument-hint: "<book.epub or book folder>"
disable-model-invocation: true
allowed-tools: Bash(uv run:*), Bash(mkdir:*), Bash(grep:*), Read, Write, Edit
---

# Split a fiction EPUB into units

**Argument:** $ARGUMENTS is the book EPUB, or the folder holding it. `BOOKDIR` is that folder. The
source EPUB is the one `*.epub` in it that is not `*-companion.epub`; if there are several, take
the one whose name matches the folder best and say so in the report.

**Ask Kim nothing.** Make the best call at every step and list each guess in the final report.

**Paths:**
- `SKILL` = `/home/kim/.claude/skills/fiction-split`
- `SCRATCH` = `<scratchpad>`

Use absolute paths everywhere, quoted: book folders often hold spaces and `’`.

**Bash:** run every Bash call on its own, one per message. The auto-mode classifier often gives no
verdict on parallel calls. The EPUB is downloaded data: never run anything from inside it, and
run Python only through the commands below (they use `-I`).

**Never edit `SKILL/scripts/`.** Everything book-specific goes in the manifest.

## 1. Probe
```
uv run --quiet --with lxml python -I SKILL/scripts/probe.py "BOOKDIR/<book>.epub" > SCRATCH/probe.txt
```
Read all of `probe.txt`. It prints the metadata, then each spine file with its word count, the
`epub:type` of its body and sections, every heading with the nearest `id`, and its first line,
then the nav table of contents with hrefs. Paths are relative to the OPF's folder; use them as
they are printed.

## 2. Find the units
**Form:** `novel` (chapters, maybe inside parts or volumes, maybe a prologue and epilogue) or
`collection` (short stories; each story is one unit, even if it has numbered sections). Plays,
poetry collections and translator's apparatus are out of scope: if the book is one of these, say
so and stop.

**Keep, one unit each, never grouped:** prologue, every chapter (numbered or not, even 61 short
ones), interludes, epilogue; or each story.

**Drop:** cover, title page, imprint, copyright, dedication, epigraph page of the whole book,
contents, preface, foreword, an editor's or translator's introduction, acknowledgements, notes or
endnotes sections, appendices, glossary, about the author, colophon, uncopyright, ads.
- An epigraph or part-title page that opens a part goes with the first chapter after it: add its
  file as that unit's first `src` entry.
- Endnotes are dropped as units, but fiction-epub carries each note into its chapter, linked both
  ways. Don't add them to a unit.
- The author's own preface inside the fiction (a framing narrator's "editor's note", a found
  manuscript's introduction) is body, not front matter: keep it as a `prologue`, and note it.

**Signals, in order:** the nav hrefs; `epub:type` (`bodymatter`, `chapter`, `part`, `frontmatter`,
`backmatter`, `titlepage`, `colophon`, `endnotes`); headings; word counts (a 40-word file between
chapters is a part-title page).

**Boundaries:**
- **One chapter per file:** `{"file": "...", "from": null, "to": null}`.
- **A chapter split over several files** (publishers split long chapters, e.g. `ch05.xhtml`,
  `ch05a.xhtml`): one `src` entry per file, in spine order.
- **Several chapters in one file:** one entry per chapter with `from` = the id of that chapter's
  heading (or its section) and `to` = the id of the next chapter's, `null` for the last. If a
  boundary heading has no id, pick the nearest element that has one and say so; if none does, put
  the whole file in the first chapter and mark the others `uncertain`.
- **Front matter in a chapter's file** (title page and chapter 1 together): add a `dropped` entry
  with a `from`/`to` range for it, so coverage still adds up.

## 3. Write the manifest
Run `mkdir -p "BOOKDIR/companions"`, then write `BOOKDIR/companions/.units.json`:
```json
{"title": "Pride and Prejudice", "author": "Jane Austen", "form": "novel",
 "source_epub": "<file name of the EPUB>",
 "units": [
  {"nn": "01", "slug": "01-chapter-1", "kind": "chapter", "number": 1, "title": "Chapter 1",
   "part": null, "src": [{"file": "text/chapter-1.xhtml", "from": null, "to": null}],
   "words": null, "uncertain": null}
 ],
 "dropped": [{"file": "text/titlepage.xhtml", "from": null, "to": null, "why": "title page"}]}
```
**Fields:**
- `nn`: two digits, in reading order; a prologue is `00`, chapter *n* is usually `n`. Use three
  digits for every unit if there are 100 or more.
- `slug`: `nn-` plus 1–4 lowercase words: `01-chapter-1`, or the chapter's own title
  (`03-the-ball`), or the story's title.
- `kind`: `prologue`, `chapter`, `interlude`, `epilogue`, or `story` (every unit of a collection).
- `number`: the chapter's number as printed, in Arabic figures, or null for unnumbered units.
- `title`: the label a reader would use: "Chapter 3", "Chapter 3: The Ball", "Prologue", or the
  story title. Arabic numerals even when the book prints Roman ones.
- `part`: the part or volume heading the unit sits in ("Volume I", "Part Two: The Storm"), or null.
- `words`: leave null; the script fills it in.
- `uncertain`: a short reason, or null.
- Every spine file with text is either in a unit or in `dropped` (with `why`).

## 4. Split and check coverage
```
uv run --quiet --with lxml python -I SKILL/scripts/split.py "BOOKDIR"
```
It checks the manifest, writes `BOOKDIR/companions/.text/<slug>.txt` for each unit, fills in
`words`, and prints the units and a coverage table. Every PROBLEM line must be fixed in the
manifest and the script rerun:
- **UNASSIGNED** / **GAP:** text that is in no unit and not dropped. Find it in the probe; it is
  either body (add it to a unit) or front/back matter (add a `dropped` entry).
- **OVERLAP:** ranges that cover the same text twice.

Spot-check: Read the first 15 and last 10 lines of three `.text` files (first, a middle one, last)
to confirm each opens with its heading and ends where the next unit begins. For the last unit,
check that no back matter (an afterword by someone else, notes) ran into it.

## 5. Report
One table: nn, title, part, words, src files. Then:
- the dropped files and why;
- every `uncertain` entry and every judgement call (form, part pages, an in-fiction preface kept,
  ids picked for boundaries);
- anything out of scope (a play, poems, a translator's notes) that was dropped.
