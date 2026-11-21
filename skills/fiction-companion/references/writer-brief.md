# Subagent brief: writer

**Subagent:** these are your instructions. Every `{…}` takes its value from the values block in
your prompt. `{SKILL}` = `/home/kim/.claude/skills/fiction-companion`.

---

You are writing the reading companion for one unit of {AUTHOR}, *{BOOK}* ({FORM}). Kim reads the
book one unit at a time: the **Before you read** part just before the unit, the **After you read**
part just after it. A companion that reveals anything beyond the unit ruins the book for its
reader. A separate checker will hunt for exactly that.

## Your unit
- **Unit:** {UNIT TITLE} (`{SLUG}`), {WORDS} words.
- **Output file** (the ONLY file you may create or edit): `{BOOKDIR}/companions/src/{SLUG}.md`
- **Meta:** `Title: {UNIT TITLE}` and `Eyebrow: {EYEBROW}`.
- **Parts:** {PARTS: "Before you read + After you read" | "After you read only (first unit)" |
  "After you read only (a story in a collection)"}.
- **Previously** recaps: {PREVIOUS UNIT: its title, or "none"}.

## What you may use: ONLY these files
- **Read in full:** your unit's text, {CHAPTER: BOOKDIR/companions/.text/<slug>.txt}.
- **Read in full:** what happens in each earlier unit, in order: {DIGESTS: the paths
  BOOKDIR/companions/.digest/<slug>.md of units 1..N−1, or "none"}. The last is the source of
  **Previously**.
- **Read in full:** the cast and threads at the end of the previous unit: {CAST: BOOKDIR/companions/.digest/<slug of N−1>.cast.md, or "none"}.
  - Its **Cast so far** is your **Characters so far**, regrouped by household or milieu and
    trimmed to the spec's 12 words.
  - Its **Threads so far** feed **Themes and motifs so far**.
- **Grep only, never Read:** the earlier units' texts, {EARLIER: the .text paths of units 1..N−1,
  or "none"}. Use them to confirm a detail a digest gives, or to get a quote verbatim.

**Do not open, Read or grep any other file:** no later `.text` file, no later digest, no other
companion, not the source EPUB. They hold later chapters.

**You may know this book.** Treat that knowledge as forbidden. Write nothing that you cannot
point to in the files above. Before each sentence about a character, ask: where in these files
does it say so? If nowhere, cut it. This applies with most force to the cast list, character
descriptions, themes and questions, where memory of the whole book leaks most easily.

## Read first
1. `{SKILL}/references/spec.md`: the rules, structure and length. Follow it exactly.
2. `{SKILL}/references/example-chapter.md`: the Markdown conventions (an invented book). Copy the
   markup, not the content.

## Tools: STRICT
Kim is away, and any other command blocks on a permission prompt.
- **Read:** the spec, the example, your unit's text, the digests and the cast file only.
- **Write/Edit:** only your output file.
- **Bash:** one command per call, one call per message, absolute paths. No `cd`, `&&`, `;`,
  pipes, redirection or loops. Only:
  - `python3 -I {SKILL}/scripts/check.py {BOOKDIR}/companions/src/{SLUG}.md {BOOKDIR}`
  - `grep -n -i -e "<phrase>" -e "<phrase>" <your unit's text> <the earlier texts>`: one call for
    all the phrases you need at that point, not one call per phrase.
  - `wc -w <your output file>`

`check.py` reads the whole book to find leaks. That is the only way later chapters may touch
your work: through its report.

## Steps
1. Read the spec and the example.
2. Read the digests in order, the cast file, then your unit's text.
3. Write the .md.
4. Run check.py and fix what it reports. Exit 1 with problems is normal output.
   - **SPOILER QUOTE, LOCATOR, STRUCTURE, LENGTH:** always fix.
   - **MISS:** fix the quote to match the text exactly, using grep on your unit's text and the earlier texts.
   - **CAST:** someone in the cast file is missing from Characters so far. Add them.
   - **LATER WORD:** a proper noun your scope never uses but a later unit does. If it names a
     person or place of the plot, it leaked from memory: delete the claim. If it is a harmless
     coincidence (a name you used for something else), keep it, and list it in your report with
     a one-line reason.
5. Rerun check.py until only LATER WORD lines you have judged harmless remain.

## Report back (concise)
- Word count against target; the Before you read count.
- Remaining check.py lines, and why each is acceptable.
- Every statement you were tempted to make from memory and cut.
- Anything in the text you found unclear, and any rule in the spec that didn't fit this unit.
