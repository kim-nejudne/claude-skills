---
name: split-book
description: Split a book PDF into one PDF per body unit (introduction/prologue, chapters, conclusion/epilogue), with each chapter's book-end notes appended. Writes chapters/ next to the PDF plus a hidden manifest (chapters/.parts.json) that /reading-companion reuses. Runs without questions; uncertain boundaries are reported at the end.
argument-hint: "<book.pdf>"
disable-model-invocation: true
allowed-tools: Bash(uv run:*), Bash(pdftotext:*), Bash(pdftoppm:*), Bash(pdfinfo:*), Bash(mkdir:*), Bash(grep:*), Bash(wc:*), Read, Write, Edit
---

# Split a book into chapter PDFs

Argument: $ARGUMENTS, the book PDF. If it is a folder, use the single PDF inside it.

**Ask Kim nothing.** Make the best call at every step and list each guess in the final report.

Scripts are in this skill's `scripts/` folder (`~/.claude/skills/split-book/scripts/`). Run every
Bash call on its own, one per message: the auto-mode classifier often gives no verdict when calls
run in parallel. Quote the PDF path, since book filenames often hold spaces, quotes and `’`. A
`./*.pdf` glob from the book's folder is the safest way to name it.

## 1. Probe

```
uv run --quiet --with pikepdf python ~/.claude/skills/split-book/scripts/probe.py "<book.pdf>" > <scratchpad>/probe.txt
```

Then Read `probe.txt`. It prints:
- the page count;
- the outline (bookmarks) with 1-based PDF pages;
- whether page labels exist;
- one row per page: characters of text and its first lines (running heads, printed page numbers).

## 2. Find the units

Take these sources in order, and confirm each start against the running heads:

1. **Outline.** Bookmark pages are usually exact. Check that the start page's first lines show the
   chapter opening, not a blank page or a part-title page.
2. **Printed TOC plus offset.** Read the contents page from the per-page rows, or from the text with
   `pdftotext -f N -l N -layout`. The offset is PDF page minus printed page; take it from a page
   whose running head shows a number.
   - **The offset can change mid-book**: dropped blank pages, plates, or part-title pages. Check it
     at each unit's start.
   - Running-head digits are often OCR-mangled (`io` = 10, `i8` = 18, `2O` = 20, `n` = 11).
3. **Page images.** If there is no text layer (most rows under ~200 characters), render the
   contents and the candidate pages with `pdftoppm -r 60 -f N -l N -png` into the scratchpad, and
   Read them.

**Keep body units only:**
- introduction/prologue
- the chapters, including chapters grouped inside parts (the part-title page goes with the first
  chapter after it)
- conclusion/epilogue/afterword

**Skip:** cover, front matter, preface, foreword, acknowledgements, appendices, notes section,
bibliography/references, glossary, index.

A unit ends on the page before the next unit starts, or before back matter starts. Drop trailing
blank pages ("This page intentionally left blank", 0–40 characters).

## 3. Find each unit's notes

- **Footnotes, or notes at chapter end:** already inside the unit's range. Set `notes` to null.
- **A book-end Notes section:** find each chapter's sub-heading inside it ("Chapter 3", "3.
  Title", or the chapter title), using `pdftotext -layout` and grep. That unit's notes run from
  the page holding its heading to the page holding the next heading. **Boundary pages are
  included whole**, so a shared page goes in both units.
- **Introduction/prologue notes** sit before Chapter 1's notes, often under the intro's title.

## 4. Book metadata

Take these from the title page and copyright page (the text, or the PDF docinfo as a fallback):
- the title (main title only, plus the subtitle if short)
- the author
- the publisher, its city and the year
- the series

## 5. Write the manifest

Write `chapters/.parts.json`. The `chapters/` folder sits next to the book PDF. The manifest is a
hidden file, so the folder still shows only PDFs.

```json
{"title": "Genealogies of Religion",
 "subtitle": "Discipline and Reasons of Power in Christianity and Islam",
 "author": "Talal Asad",
 "publisher": "Johns Hopkins University Press", "city": "Baltimore", "year": 1993, "series": null,
 "source_pdf": "<file name of the book PDF>",
 "parts": [
  {"file": "00-introduction.pdf", "kind": "introduction", "title": "Introduction",
   "body": [10, 33], "notes": null, "book_pages": "1–24", "page_offset": 9,
   "found_by": "outline", "uncertain": null},
  {"file": "01-construction-of-religion.pdf", "kind": "chapter", "number": 1,
   "title": "The Construction of Religion as an Anthropological Category",
   "body": [34, 61], "notes": null, "book_pages": "27–54", "page_offset": 7,
   "found_by": "outline", "uncertain": null}
 ]}
```

**Fields:**
- `body` and `notes` are 1-based, inclusive PDF pages.
- `page_offset` is PDF page minus printed book page, for that unit's body.
- `book_pages` uses an en dash.
- `kind` is one of `prologue`, `introduction`, `chapter`, `conclusion` or `epilogue`.
- `found_by` is one of `outline`, `toc+offset` or `image`.
- `uncertain` holds a short reason, or null.

**File names:**
- `NN-slug.pdf`: two-digit order starting at `00`, so an intro or prologue is `00` and chapter
  *n* is `0n`.
- The slug is 2–6 lowercase words from the title, without stop-words at the ends.

## 6. Split

From the book's folder:
```
uv run --quiet --with pikepdf python ~/.claude/skills/split-book/scripts/split.py ./<book>.pdf chapters/.parts.json
```
It sets Title (`<book title> — <unit title>`) and Author in both docinfo and XMP. It asserts page
counts.

Spot-check the result: `pdftotext -f 1 -l 1` of each output PDF must show that unit's opening.
For units with notes, check the last page too.

## 7. Report

Give one table with these columns:
- file
- PDF pages (body + notes)
- book pages
- page count
- `found_by`

Below it, list every `uncertain` entry and every judgement call: skipped units, offset changes,
shared notes pages.
