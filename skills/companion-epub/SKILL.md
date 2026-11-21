---
name: companion-epub
description: Build one EPUB of a book for phone reading (KOReader, Moon+). For each body unit it holds the reading companion, then the chapter text reflowed from the PDF, then that chapter's notes, linked both ways. Needs /split-book's chapters/.parts.json and /reading-companion's companions/src/*.md. Probes the layout, writes per-book settings and fixes, then checks the result (word diff, epubcheck, screenshots). Runs without questions.
argument-hint: "<book.pdf or book folder>"
disable-model-invocation: true
allowed-tools: Bash(uv run:*), Bash(pdftotext:*), Bash(pdftoppm:*), Bash(pdfinfo:*), Bash(python3 -I:*), Bash(mkdir:*), Bash(cat:*), Bash(grep:*), Bash(wc:*), Read, Write, Edit
---

# Companion EPUB for a book

**Argument:** $ARGUMENTS is the book PDF or its folder. `BOOKDIR` is that folder.

**Ask Kim nothing.** Make the best call at every step and list each guess in the final report.

**Paths:**
- `SKILL` = `/home/kim/.claude/skills/companion-epub`
- `SCRATCH` = `<scratchpad>/epub`

Use absolute paths everywhere.

**Bash:** run every Bash call on its own, one per message. The auto-mode classifier often gives no
verdict on parallel calls. Quote paths: book folders and PDFs often hold spaces and `’`.

**Never edit the scripts in `SKILL/scripts/`.** Everything book-specific goes in two files in
`BOOKDIR/companions/`:
- `epub-settings.json` describes the layout.
- `epub-fixes.json` holds local patches.

If a layout is beyond what the settings can express, build the best EPUB you can and say what's
wrong in the report.

## What the EPUB holds (fixed; don't change)
For each part in `chapters/.parts.json`, in order:
1. the whole companion (`companions/src/NN-*.md`, header = eyebrow + title);
2. the chapter text, reflowed;
3. the chapter's notes, linked both ways where markers and notes agree.

There is no overview, front matter, bibliography or cover. The styling is plain. The TOC is
nested: chapter → Companion (its sections), Chapter text, Notes. The output is
`BOOKDIR/<folder name>-companion.epub`.

## 1. Preconditions
- `BOOKDIR/chapters/.parts.json` exists.
- Every part has exactly one `companions/src/NN-*.md`, where NN is the part file's two-digit
  prefix.
- If either is missing, stop and report which.
- `companions/.text/<part stem>.txt` exists for each part. If not, make each one with
  `pdftotext -layout BOOKDIR/chapters/<file>.pdf BOOKDIR/companions/.text/<stem>.txt`.

## 2. Probe
```
uv run --with pymupdf python SKILL/scripts/probe.py BOOKDIR
```
Read all of it. Then render and Read three pages (`pdftoppm -r 60 -png -f N -l N`): the first
part's opening page, a body page with notes or quotes, and a notes page if the book has one.

The probe tells you:
- whether the book is a scan with an OCR text layer (sizes jitter, expect OCR typos);
- the font-size mix;
- the running heads (top lines) and folios;
- the small spans (note markers, superscripts, fraction parts);
- the display type and title block on opening pages;
- vector figures;
- the notes layout.

## 3. Settings
Write `BOOKDIR/companions/epub-settings.json`. If it exists from an earlier run, keep it and
adjust it. Keys (defaults in `epub.py`'s `DEFAULTS`, fitted to *The Selfish Gene*):

| key | set it from |
| --- | --- |
| `head_y` | Spans starting above this y are dropped: just below the running heads' y0, above the first body line. |
| `foot_y` | Bare page numbers starting below this y are dropped (bottom folios). |
| `body_size` | `[min, max]` around the main text size. For scans, wide enough for the jitter (e.g. `[9.6, 11.8]`). |
| `notes_size` | Band of the endnote text (endnote styles) or the footnote text (footnotes). Leave out caption and quote sizes. |
| `small_max` | Spans below this are superscripts, note markers or fraction parts. Set it above the markers and below the smallest real text. |
| `display_min` | Spans at or above this are dropped: chapter numbers, display titles, drop caps. |
| `opening_skip_y` | On each part's first page, drop lines above this y (the title block). Use `{"default": y, "02": y}` when one part differs, e.g. an epigraph high on the page. |
| `dropcap` | `true` only if a single display letter starts the first word. |
| `notes` | `asterisk`: `*` markers, endnotes headed "p. N lemma". `numbered`: superscript numbers, numbered notes in the parts' `notes` ranges. `footnotes`: numbered notes at the foot of body pages. `none`: notes (if any) follow unlinked. |
| `note_head_font` | asterisk style: a substring of the font name of the "p. N" head lines. |
| `notes_heading` | Endnote styles: a regex for the heading that opens each chapter's block on shared notes pages, with the chapter number as group 1. Use `null` when each part's notes range is its own. |

## 4. Build and check
```
uv run --with markdown --with pymupdf python SKILL/scripts/epub.py BOOKDIR
uv run --with pymupdf python SKILL/scripts/check.py BOOKDIR SCRATCH/check
```
Two separate Bash calls. `epub.py` stops on malformed XHTML, an unpaired part, or a fix that
doesn't match exactly once. Its `!` lines are warnings:
- **asterisk pages disagree, or notes found no marker:** links are missing; work out why.
- **inline image skipped:** a word set as an image (e.g. Hebrew). Type it in with a fix.
- **note text before the first numbered note:** footnote detection caught a non-note.

`check.py` prints five sections; Read every screenshot it lists.
1. **Word diff against pdftotext.** Only-in-PDF words should be running heads, titles and
   folios. Anything else was lost. Only-in-EPUB fragments ("bril liant") are words split at
   a paragraph break.
2. **Line-break joins never seen unbroken.** Most are fine. Real compounds need a fix.
3. **Unlinked superscripts and plain asterisks.**
4. **epubcheck.**
5. **Screenshots** at phone width.

## 5. Fix, rebuild, recheck
Fix systematic problems in the settings and local ones in `epub-fixes.json`, a JSON list of:
- `{"file": "06-text.xhtml", "find": "...", "replace": "..."}`: exact text of the generated
  file (copy it from `SCRATCH/check/epub/OEBPS/`). It must match exactly once.
- `{"compound": "cold-blooded"}`: keep the hyphen when a line break falls on this compound.
- `{"sup": "55", "replace": "”"}`: every unlinked `<sup>55</sup>` in the text files. Use it
  for OCR'd quote marks and stray accents.

Typical fixes:
- A garbled glyph, or a decimal point dropped by the layout.
- A print typo. Say so in the report.
- A word set as an image, typed in.
- A note whose marker the OCR misread. Links are made before fixes run, so linking it by hand
  takes two fixes: the noteref anchor in the text file and the back link in the notes file,
  each copied from a linked note's markup with the right numbers. Otherwise leave it unlinked
  and report it.

For scans, fix the OCR errors the checks surface (word diff, superscripts, screenshots). Don't
proofread the whole book.

Repeat step 4 until all of these hold:
- epubcheck reports 0 errors;
- the word diff shows no lost text;
- every remaining warning has a reason you can state;
- the screenshots look right: headings, paragraphs, quotes, figures, note links.

Stop after five rounds whatever is left, and report it.

## 6. Report
Keep it concise:
- The EPUB path and size, and its parts.
- The settings you chose, and why the non-obvious ones.
- The fixes: how many of each kind, and each print typo corrected.
- Notes linked per part (e.g. `03: 24/24`), and why any are unlinked.
- What remains imperfect (OCR quirks, compounds left joined), and the last epubcheck line.
- Any permission prompts, or Bash calls outside the allowed list.
