---
name: reading-companion
description: Write reading-companion PDFs for a book, one per body unit (primer page, context in depth, argument map, section summaries, close reading, glossary, who's who, quotations, cross-chapter links) plus a 2–3 page book overview, for understanding a book whose context is new to the reader. Splits the book first with /split-book if needed. Parallel subagents write the units, a separate checker subagent fact-checks each one, and the main agent writes the overview, checks consistency and the rendered PDFs. Resumable: units whose source already exists are skipped. Runs without questions.
argument-hint: "<book.pdf>"
disable-model-invocation: true
allowed-tools: Bash(uv run:*), Bash(pdftotext:*), Bash(pdftoppm:*), Bash(pdfinfo:*), Bash(python3 -I:*), Bash(mkdir:*), Bash(cat:*), Bash(grep:*), Bash(wc:*), Read, Write, Edit, Agent
---

# Reading companions for a book

**Argument:** $ARGUMENTS is the book PDF. If it is a folder, use the single PDF inside it.
`BOOKDIR` is the folder holding the PDF.

**Ask Kim nothing, and don't stop for a pilot.** Make the best call at every step and list each
guess in the final report. Kim may be away for hours, so finish the whole run.

**Paths:**
- `SKILL` = `/home/kim/.claude/skills/reading-companion`
- `TEXTDIR` = `BOOKDIR/companions/.text` (kept with the book, so later runs and `check.py` can use it)
- `SCRATCH` = `<scratchpad>`

Use absolute paths everywhere.

**Bash:** run every Bash call on its own, one per message. The auto-mode classifier often gives no
verdict on parallel calls.

**Read first:** `SKILL/references/spec.md`, the format, which is not negotiable.

## 1. Split
If `BOOKDIR/chapters/.parts.json` does not exist, follow `/home/kim/.claude/skills/split-book/SKILL.md`
in full. Then read the manifest.

## 2. Extract text, check the text layer
For each `chapters/*.pdf`, in order:
```
pdftotext -layout BOOKDIR/chapters/<file>.pdf TEXTDIR/<file-stem>.txt
```
Run `mkdir -p TEXTDIR SCRATCH/img` first. Skip files whose `.txt` already exists. Keep the
`-layout` default of a form feed between pages: `check.py` maps quotes to pages with it.

Then compare `wc -c` on the text files with the page counts. If they average under ~200
characters per page, **stop**. Report: "No text layer. Install `ocrmypdf` and `tesseract`
(`sudo pacman -S ocrmypdf tesseract tesseract-data-eng`), run `ocrmypdf in.pdf out.pdf`, then rerun
`/reading-companion` on the output." The split itself is still valid.

## 3. Infer the book-wide settings
Read the front matter: title page, copyright page, preface, the introduction's opening, and the
back-cover blurb from the probe or `pdftotext` on the original PDF.

- **Reader:** a graduate student in the book's field who is new to its specific context. Write one
  paragraph that says:
  - the field and what such a reader already knows;
  - what this book assumes that they lack: the regions, periods, languages, theorists, archives.
- **Accent colour:**
  - Pick a dark colour that suits the book's subject or cover.
  - It must differ from oxblood `#7A2E2E` unless oxblood clearly suits the book better.
  - `accent_soft` is a very pale tint of it, roughly 92–95% white, used as the callout fill.
  - Check the contrast is at least 7:1 against white:
    ```
    python3 -I -c "h='RRGGBB';c=[int(h[i:i+2],16)/255 for i in (0,2,4)];l=[x/12.92 if x<=0.03928 else ((x+0.055)/1.055)**2.4 for x in c];L=0.2126*l[0]+0.7152*l[1]+0.0722*l[2];print(round(1.05/(L+0.05),2))"
    ```
- **Unit labels:**
  - **Citation:** the Chicago chapter citation for each unit (format in spec.md).
  - **Running:** a short footer label.
  - **Eyebrow:** e.g. "Chapter 3 · Reading companion".
  - **Body offset:** for each unit, book page minus chapter-PDF page. That is the body's first
    printed page minus 1.
  - **Source file:** the slug for `companions/src/NN-slug.md`. Use the chapter PDF's `NN-` prefix
    and 1–3 words of the title.

If `BOOKDIR/companions/src/book.json` exists, keep it and skip this step. Otherwise write it:
```json
{"book": "<Title as on the cover, main title only>", "author": "<Author>",
 "accent": "#RRGGBB", "accent_soft": "#RRGGBB", "reader": "<the paragraph>"}
```

## 4. Write the units: parallel subagents
**Resume:** skip every unit whose `companions/src/<NN-slug>.md` already exists, and list the skipped
units in the report. To redo a unit, Kim deletes or moves its .md.

Each subagent's prompt is short. It tells the subagent to read
`SKILL/references/subagent-brief.md` and to follow it as its instructions, and gives a
**values block** that fills every `{…}` in the brief: AUTHOR, BOOK, CITY, PUBLISHER, YEAR, the
unit fields, READER, the paths, and BODY_OFFSET. There is no word target to pass: `check.py`
computes it from the `Pages:` meta.
- **Unit-specific advice:** add advice drawn from a quick skim of each unit's text. Examples: a
  survey chapter with many names, or a short polemical epilogue. Before you name an interlocutor
  in the advice, `grep` the unit's text for them. Names guessed from memory of the book have been
  wrong, e.g. figures who only appear in another chapter.
- **Context for each unit:** name the context that unit's reader needs.
- **Launch:** start all the general-purpose subagents in **one message**, so they run in parallel.
  Don't set a model, so they inherit yours.

**Checkers:** as each writer returns, launch a checker subagent for that unit (general-purpose,
no model set). Its prompt tells it to read `SKILL/references/checker-brief.md` and follow it, with
the same values block. A checker never checks a unit it wrote. Keep each writer's and checker's
report for step 7.

While they run, read the units' texts yourself for the overview: at least each unit's opening and
closing pages, and its subheadings.

## 5. Overview and review (main agent)
**Overview:** write `BOOKDIR/companions/src/book-overview.md`. Skip it if it already exists.
- Pattern: `SKILL/references/example-overview.md`.
- Meta:
  - Title: the book title
  - Subtitle: "Book overview"
  - Eyebrow: "Overview · Reading companion"
  - Running: "Book overview"
  - Pages: the body, notes and bibliography ranges
  - Citation: the whole-book Chicago citation
- Sources: the drafts and the front matter.
- Thesis: a verbatim quote if the book states one.

**Consistency pass** (the checkers have done the per-unit fact-check): across units, the same term
is defined the same way and the same person gets the same description. Fix differences directly
in the .md. Read the checkers' reports, and settle anything a checker could not.

**Check** every .md, the overview included (it gets the quote checks only):
```
python3 -I SKILL/scripts/check.py BOOKDIR/companions/src/<NN-slug>.md BOOKDIR
```
Every STRUCTURE, CHARACTER, WRONG PAGE and LENGTH line must be fixed. Each remaining MISS must be
one of these:
- an OCR artefact;
- a quote broken by a page break or footnote;
- the title of an outside work.

Grep any miss scoring under ~70% and read it in the text before you accept it. UNCHECKED lines
(quotes found only in book-end notes) need their page checked by hand.

## 6. Build and check visually
```
uv run --quiet --with markdown python SKILL/scripts/build.py BOOKDIR/companions/src/*.md
```
The build writes `BOOKDIR/companions/<stem>-companion.pdf`. It needs no `cd`, since paths are
absolute.

**Gates:** fix and rebuild until all pass.
- **Primer fits page 1:** `pdftotext -f 2 -l 2 <pdf> -` begins with "1 Context in depth" for every
  unit. If not, tighten the primer text.
- **Overview length:** ≤ 3 pages (`pdfinfo`). If it is longer, trim redundant blocks:
  - drop meta bullets;
  - merge glossary entries;
  - shorten question lines.

  A spill of 2–3 lines is common.
- **Looks right:** `pdftoppm -r 60 -png` of pages 1–2 and the last page of each PDF, viewed with
  Read. Check for:
  - callouts, footer and accent in place;
  - no orphaned headings;
  - no merged blockquotes (fix with a `<!-- -->` line between them).
- **Length:** `check.py` prints no LENGTH problem.

## 7. Report
Make it concise:
- The PDFs in `BOOKDIR/companions/`, with page counts and word counts.
- The split's report, if `/split-book` ran in this session: uncertain boundaries and judgement
  calls.
- The inferred reader, and the accent colour with a word on why.
- Units skipped because their .md already existed.
- Edits made by the checkers and in the consistency pass.
- Outside-knowledge claims that were kept (from the checkers' reports).
- Errors in the book itself that the companions flag.
- Remaining check.py lines, and why each is acceptable.
- Any permission prompts or Bash calls outside the allowed list, yours or the subagents'.

The sources in `companions/src/` can be edited and rebuilt with the build command above.

## Optional: EPUB for phone reading
Only when Kim asks: `/companion-epub BOOKDIR` builds one EPUB with each companion before its
chapter text.
