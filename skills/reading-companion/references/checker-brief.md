# Subagent brief template: checker

**Subagent:** these are your instructions. Every `{…}` takes its value from the values block in
your prompt. `{SKILL}` = `/home/kim/.claude/skills/reading-companion`.

---

You are fact-checking one reading-companion that another agent wrote, for a unit of {AUTHOR},
*{BOOK}*. You did not write it. Assume it has errors and find them against the book's text.

## Files
- **Draft** (the ONLY file you may edit): `{BOOKDIR}/companions/src/{NN-slug}.md`
- **Unit text:** `{BOOKDIR}/companions/.text/{chapter}.txt` (book pages {BOOK PAGES}; chapter-PDF
  page = book page − {BODY_OFFSET} for the body; notes follow the body).
- **Other units' texts:** `{BOOKDIR}/companions/.text/`.
- **Rules:** `{SKILL}/references/spec.md`. Read its accuracy rules first.

## What to verify
Read the draft, then read the whole unit text. Check, with `grep -n -i` and Read:
1. **Every** name, date, number and statistic.
2. **Every** page reference: does the cited page say that? Check the section headings' `pp.`
   spans against where each author subheading starts and ends.
3. The thesis wording and the argument map: is each step the author's claim, or someone the
   author reports? Is anything overstated?
4. Every cross-chapter claim, against that unit's text.
5. Every outside-knowledge claim (mostly in the primer and Context in depth). Keep it only if it
   is textbook-level and you are confident it is right. Delete anything doubtful, vague or
   specific beyond general knowledge (precise figures, attributed quotations, named works with
   dates you can't confirm).
6. The Close reading: is each passage verbatim, and does the unpacking match how the author
   actually uses the terms?
7. The spec's rules: section structure, voice, British spelling, no paraphrase in quotation marks.

**Fix errors directly in the .md.** Keep fixes minimal: correct the fact, don't rewrite the prose.
If a fix changes the length noticeably, keep the length within the check.py target.

## Tools: STRICT
Kim is away, and any other command blocks on a permission prompt.
- **Read:** freely. **Write/Edit:** ONLY the draft.
- **Bash:** one command per call, one call per message, absolute paths, no `cd`, `&&`, `;`,
  pipes, redirection or loops. Only:
  - `python3 -I {SKILL}/scripts/check.py {BOOKDIR}/companions/src/{NN-slug}.md {BOOKDIR}`
  - `uv run --quiet --with markdown python {SKILL}/scripts/build.py {BOOKDIR}/companions/src/{NN-slug}.md`
  - `grep -n -i "<phrase>" {BOOKDIR}/companions/.text/<file>.txt`
  - `pdftotext …`, `pdftoppm …`, `pdfinfo …`, `wc -w <file>`

## Finish
Run check.py and fix what it reports (MISS lines that are pure OCR-letter differences may stay).
Build, then confirm `pdftotext -f 2 -l 2 {BOOKDIR}/companions/{NN-slug}-companion.pdf -` begins
with "1 Context in depth".

## Report back (concise)
- Each change you made: the old claim, the new one, and the page that settled it.
- Outside-knowledge claims you kept, one line each.
- Outside-knowledge claims you deleted.
- Errors in the book itself (wrong names, dates, arithmetic) that the draft flags or should flag.
- Remaining check.py lines and why each is acceptable.
- Anything you could not settle.
