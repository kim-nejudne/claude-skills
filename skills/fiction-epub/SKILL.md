---
name: fiction-epub
description: Build one EPUB 3 of a novel or story collection for phone reading. It holds the spoiler-free intro; then, for each chapter, Before you read, the chapter text reused from the source EPUB's own XHTML (italics, letters, verse and the source's notes kept, notes linked both ways, publisher CSS dropped) and After you read; then the full-spoiler end essay. Needs /fiction-split's manifest and /fiction-companion's companions/src/*.md. Checks the result (word diff against the source, links, epubcheck, screenshots) and fixes it in up to 5 rounds. Runs without questions.
argument-hint: "<book.epub or book folder>"
disable-model-invocation: true
allowed-tools: Bash(uv run:*), Bash(mkdir:*), Bash(grep:*), Read, Write, Edit
---

# Fiction companion EPUB

**Argument:** $ARGUMENTS is the book EPUB or its folder. `BOOKDIR` is that folder.

**Ask Kim nothing.** Make the best call at every step and list each guess in the final report.

**Paths:**
- `SKILL` = `/home/kim/.claude/skills/fiction-epub`
- `SCRATCH` = `<scratchpad>/epub`

Use absolute paths everywhere, quoted.

**Bash:** run every Bash call on its own, one per message. The auto-mode classifier often gives no
verdict on parallel calls.

**Never edit the scripts in `SKILL/scripts/`** or in fiction-split's. Everything book-specific
goes in two files in `BOOKDIR/companions/`:
- `epub-settings.json`: `{"drop_xpath": [...], "css": "..."}`.
- `epub-fixes.json`: local patches.

## What the EPUB holds (fixed; don't change)
1. `intro.md`, the spoiler-free introduction.
2. For each unit in `companions/.units.json`, in order:
   - Before you read (from the unit's .md; none for the first unit or a story);
   - the unit's text, from the source EPUB's XHTML;
   - After you read.
3. `end.md`, the after-the-end essay, marked as spoilers.

**Style:** plain, the same as the nonfiction companion EPUB. The source's CSS, fonts and inline
styles are dropped.

**TOC:** nested. Part → unit → Before you read, the text, After you read.

**Output:** `BOOKDIR/<folder name>-companion.epub`.

## 1. Preconditions
- `BOOKDIR/companions/.units.json` exists.
- `companions/src/` holds `intro.md`, `end.md` and one `<slug>.md` per unit.

If any is missing, stop and report which. (`epub.py` itself builds without them, with a `!`
warning, so a partial EPUB can be made on request.)

## 2. Build and check
```
uv run --quiet --with lxml --with markdown python -I SKILL/scripts/epub.py "BOOKDIR"
uv run --quiet --with lxml python -I SKILL/scripts/check.py "BOOKDIR" SCRATCH/check
```
Run them as two separate Bash calls. `epub.py` stops on malformed XHTML or on a fix that doesn't
match exactly once. Its `!` lines are warnings:
- **link … leads outside the book's units:** a link into dropped front or back matter that isn't
  a note. It is unlinked; say so in the report. If it *is* a note the script didn't recognise
  (no `noteref` or `endnote` type), see step 3.
- **no companion / no intro.md / no end.md:** see step 1.

`check.py` prints four sections; Read every screenshot it lists.
1. **Words against the source EPUB.** Each unit should be `identical`. Any LOST word is text the
   EPUB dropped: find why and fix it. `added` words come from your fixes. Each carried note is
   compared with the source note too. The dropped front/back-matter list is for the report.
2. **Links.** Hrefs to missing files or ids, and noterefs with no link back.
3. **epubcheck.**
4. **Screenshots** at phone width, 412 px: the intro, a Before you read, chapter text, a letter or
   quotation, a page with notes, an After you read, the end essay, the contents.

## 3. Fix, rebuild, recheck
**Systematic problems go in `epub-settings.json`:**
- `drop_xpath`: XPath 1.0 with prefixes `x` (XHTML) and `epub` (OPS). Use it for publisher
  ornaments, "Chapter" header images or running heads that sit inside the chapter files,
  e.g. `//x:img[contains(@class,'ornament')]`. A dropped element must not hold book text, or the
  word diff will show it LOST.
- `css`: extra rules for this book's markup, e.g. verse lines that need `display: block`, or
  letters with signature blocks.

**Local ones go in `epub-fixes.json`,** a JSON list of
`{"file": "05-text.xhtml", "find": "...", "replace": "..."}`. The `find` is exact text of the
generated file (copy it from `SCRATCH/check/epub/OEBPS/`) and must match exactly once.

Typical fixes:
- a note the script didn't recognise: link it by hand with two fixes, the `href` on the marker and
  an `<aside>` copied from a linked note;
- a broken character entity;
- a print typo in the source. Say so in the report.

**Repeat step 2** until all of these hold:
- every unit is `identical` (or its only changes are fixes you can name);
- links report 0 problems;
- epubcheck reports 0 errors;
- the screenshots look right: headings, paragraphs, italics, letters, verse, notes, the cast list,
  the "new" tags, the spoiler banner.

Stop after five rounds whatever is left, and report it.

## 4. Report
Keep it concise:
- The EPUB path and size, and the units with and without companions.
- Settings and fixes: how many of each kind, and why.
- Notes carried and linked per unit (e.g. `12: 3/3`), and any left unlinked.
- The word-diff result, and the dropped front and back matter.
- The last epubcheck line, and what the screenshots showed.
- What remains imperfect.
- Any permission prompts, or Bash calls outside the allowed list.
