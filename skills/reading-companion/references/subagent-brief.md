# Subagent brief template: writer

**Subagent:** these are your instructions. Every `{…}` takes its value from the values block in
your prompt. `{SKILL}` = `/home/kim/.claude/skills/reading-companion`.

---

You are writing one reading-companion for a unit of {AUTHOR}, *{BOOK}* ({CITY}: {PUBLISHER},
{YEAR}). Your file must match the spec and the approved example in structure, tone, depth and
formatting.

## Your unit
- **Unit:** **{UNIT LABEL}: {UNIT TITLE}**
- **Book pages:** {BOOK PAGES}. Its notes: {NOTES: "book pp. X–Y" | "footnotes on the page" | "at chapter end, pp. X–Y"}
- **Output source file** (the ONLY file you may create or edit): `{BOOKDIR}/companions/src/{NN-slug}.md`
- **Meta header values:**
  - Title: {TITLE}
  - Subtitle: {SUBTITLE, or "(none: omit the line)"}
  - Eyebrow: {EYEBROW}
  - Running: {RUNNING}
  - Pages: {PAGES}
  - Citation: {CHICAGO CITATION}
- **Target length:** `check.py` prints it from the `Pages:` meta (rule in spec.md). {Unit-specific
  advice, e.g. "survey chapter: who's who will be large, group minor figures".}

## Reader
{READER: one or two sentences. Who they are, what they already know, and what this book's context
they lack. Name the context to explain in THIS unit, e.g. "caste, Dalit, Hindu goddess
traditions".}

## Source text
- **Your unit's text:** `{BOOKDIR}/companions/.text/{chapter}.txt`, extracted from
  `{BOOKDIR}/chapters/{chapter}.pdf`.
  - It includes the unit's notes.
  - Book-end notes pages may also hold the tail of the previous unit's notes or the start of the
    next unit's. Ignore those.
  - Read the whole unit before writing, in parts if it is long.
- **Page numbers:** printed book page numbers appear as running heads or folios in the text. Use
  them for every page reference. Chapter-PDF page = book page − {BODY_OFFSET} for the body; notes
  follow the body.
- **Other units' texts:** in `{BOOKDIR}/companions/.text/`. Use them to check cross-chapter
  connections.
- **Unclear words:** if a word is unclear (OCR damage, non-Latin terms, diacritics), render the
  page and look at it. Run
  `pdftoppm -r 110 -png -f N -l N {BOOKDIR}/chapters/{chapter}.pdf {SCRATCH}/img/{NN}-pN`, then
  Read the PNG.

## Read first
1. `{SKILL}/references/spec.md`: the format, voice, length and accuracy rules. Follow it exactly.
   It lists the 8 sections; where the example differs from the spec, the spec wins.
2. `{SKILL}/references/example-companion.md`: the approved example, from another book. Copy its
   Markdown conventions: meta lines, primer section, class names, `### … <span class="pp">`
   headings, and the `<!-- -->` separators between blockquotes. Do not copy its content.

## Tools: STRICT
Kim is away, and any other command blocks on a permission prompt.
- **Read:** use it freely.
- **Write/Edit:** ONLY your own .md file.
- **Bash:** ONLY these command forms.
  - **How to call:**
    - Absolute paths.
    - One command per Bash call, and one Bash call per message. Never send parallel Bash calls.
    - No `cd`, `&&`, `;`, pipes, redirection or loops.
  - **Allowed commands:**
    - `uv run --quiet --with markdown python {SKILL}/scripts/build.py {BOOKDIR}/companions/src/{NN-slug}.md`
    - `python3 -I {SKILL}/scripts/check.py {BOOKDIR}/companions/src/{NN-slug}.md {BOOKDIR}`
      - It checks quotes against every unit's text and the page each quote is on, page refs
        against the `Pages:` ranges (section 8 and refs after "Ch. N" are exempt), the section
        structure and the length.
      - Exit 1 with problems is normal output. Fix every STRUCTURE, CHARACTER, WRONG PAGE and
        LENGTH line. For each MISS, fix real misquotes and leave pure OCR-letter differences.
        PAGE RANGE lines are real unless the ref points to another unit.
    - `grep -n -i "<phrase>" {BOOKDIR}/companions/.text/<file>.txt`
    - `pdftotext …`, `pdftoppm …`, `pdfinfo …`, `wc -w <file>`
- **Do not modify** `book.json`, the skill's files, or other units' files. If the template or CSS
  needs a change, say so in your report.

## Steps
1. Read the spec and the example. Render pages 1–2 of `{SKILL}/references/example-companion.pdf`
   (`pdftoppm -r 60 -png -f 1 -l 2 … {SCRATCH}/img/example`, then Read) to see the look.
2. Read your full unit text.
3. Write the .md.
4. Run check.py and fix what it reports.
5. Build. Check the output:
   - The primer fits page 1: `pdftotext -f 2 -l 2 {BOOKDIR}/companions/{NN-slug}-companion.pdf -`
     must begin with "1 Context in depth". If it doesn't, tighten the primer text. Do not touch
     the CSS.
   - Render pages 1–2 and the last page at `-r 70` and look at them.
6. Rerun check.py until only accepted MISS lines remain.

## Report back (concise)
- Word count against target, PDF page count, and whether the primer fits page 1 (yes/no).
- Remaining check.py lines, and why each one is acceptable.
- Every cross-chapter claim you made, with the page you verified it on.
- Every claim that rests on outside knowledge rather than the book, Context in depth included.
- Errors in the book itself you noticed: wrong names, dates or arithmetic.
- Any claim you are unsure about, and any template or CSS problem.
