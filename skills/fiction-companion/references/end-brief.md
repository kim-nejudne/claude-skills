# Subagent brief: end essay

**Subagent:** these are your instructions. Every `{…}` takes its value from the values block in
your prompt. `{SKILL}` = `/home/kim/.claude/skills/fiction-companion`.

---

You are writing the after-the-end essay for {AUTHOR}, *{BOOK}* ({FORM}). Kim reads it only after
finishing the book, so the whole book is in scope: full spoilers, clearly marked. It is still
text only: nothing from outside the book.

## Output
The ONLY file you may create or edit: `{BOOKDIR}/companions/src/end.md`.

## What you may use
- **Read in full:** what happens in every unit, in order: {DIGESTS: the `.digest/<slug>.md` paths}.
- **Read in full:** the cast and threads at the end of the book: {CAST: the last unit's `.cast.md`}.
- **Read in full:** the last units' texts: {LAST: the .text paths of the final 1–2 units}. The
  ending deserves a close look.
- **Grep only, never Read:** every other unit's text in `{BOOKDIR}/companions/.text/`, to confirm
  details and to get quotes verbatim.
- For a collection there are no digests: read the manifest's story list, and grep the stories.

**You may know this book**, and its reputation. That is outside knowledge: write only what these
files support. No author biography, history, critics, interpretations or adaptations.

## Read first
`{SKILL}/references/spec.md`, above all "End essay", "Text only", "Quotations" and "Voice".

## Tools: STRICT
Kim is away, and any other command blocks on a permission prompt.
- **Read:** the spec, the digests, the cast file and the last units' texts only. **Write/Edit:** only `end.md`.
- **Bash:** one command per call, one call per message, absolute paths. No `cd`, `&&`, `;`,
  pipes, redirection or loops. Only:
  - `python3 -I {SKILL}/scripts/check.py {BOOKDIR}/companions/src/end.md {BOOKDIR}`
  - `grep -n -i -e "<phrase>" -e "<phrase>" <.text files>`: batch every phrase you need into one call.
  - `wc -w {BOOKDIR}/companions/src/end.md`

## Steps
1. Read the spec, the digests in order, the cast file, then the last units' texts.
2. Write `end.md`. Get every quote by grep, so it is verbatim.
3. Run check.py and fix every MISS, LOCATOR, STRUCTURE and LENGTH line.

## Report back (concise)
Word count; remaining check.py lines; any claim you were unsure the text supports.
