# Subagent brief: spoiler and text-only checker

**Subagent:** these are your instructions. Every `{…}` takes its value from the values block in
your prompt. `{SKILL}` = `/home/kim/.claude/skills/fiction-companion`.

---

You are checking a reading companion that another agent wrote for one unit of {AUTHOR}, *{BOOK}*.
You did not write it. Assume it leaks: the writer may know this book and may have let what
happens later slip into a description, a theme, a question or a choice of passage. Find every
leak, and every claim that comes from outside the book.

## Files
- **Draft** (the ONLY file you may edit): `{BOOKDIR}/companions/src/{SLUG}.md`
- **Rules:** `{SKILL}/references/spec.md`. Read "Spoilers", "Text only" and "Quotations" first.
- **What the companion may use: ONLY these files.**
  - **Read in full:** {READ: the unit's text, or for the end essay the last unit's text}.
  - **Read in full:** what happens in each earlier unit, in order: {DIGESTS: paths, or "none"}.
  - **Read in full:** the cast and threads at the end of the previous unit: {CAST: path, or "none"}.
  - **Grep only, never Read:** the earlier units' texts: {EARLIER: paths, or "none"}.

**Do not open, Read or grep any other file:** no later `.text` file, no later digest, no other
companion, not the source EPUB. You must judge with what the reader has had. Your memory of the
book is a tool for *suspecting* leaks, never for supporting a claim: a claim stays only if the
files above support it.

## What to verify
Read the spec sections, the draft, the digests, the cast file, then the unit's text. Read each
file once.
1. **Every sentence** of the draft. Claims about this unit must be in its text. Claims about
   earlier units must be in a digest or the cast file, or found by grep in the earlier texts. Pay most attention to:
   - character descriptions in both cast lists (relationships, motives, secrets, "future" roles);
   - themes and motifs (named because the later book develops them?);
   - Craft remarks that assume the whole book's design;
   - the questions (does one hint at an answer the reader can't yet have?);
   - the choice of close-reading passages (picked for a later payoff?);
   - words: "first", "yet", "for now", "will", "later", "eventually", "begins to".
2. **check.py:** `python3 -I {SKILL}/scripts/check.py {BOOKDIR}/companions/src/{SLUG}.md {BOOKDIR}`.
   - Judge each **LATER WORD**: a leaked name or place, or a harmless coincidence.
   - Fix every **SPOILER QUOTE**, **MISS**, **LOCATOR**, **STRUCTURE**, **LENGTH** and **CAST** line.
3. **Outside knowledge:** author biography, history, customs, money, law, glosses, critics,
   reception, adaptations, explained allusions. Delete it, or reduce an allusion to its name.
4. **Quotes:** verbatim, and attributed to the right speaker.
5. **Cast lists:** "Characters so far" matches the cast file. "Characters in this chapter" marks
   first appearances with `<span class="new">new</span>`: someone is new if the cast file doesn't
   hold them.

**Fix directly in the .md.** Keep fixes minimal: cut or correct the claim, don't rewrite the
prose. Keep the length within check.py's target.

## Tools: STRICT
Kim is away, and any other command blocks on a permission prompt.
- **Read:** the spec, the draft, the unit's text, the digests and the cast file only. **Write/Edit:** only the draft.
- **Bash:** one command per call, one call per message, absolute paths. No `cd`, `&&`, `;`,
  pipes, redirection or loops. Only:
  - the check.py command above: run it **twice in all**, once before your edits and once after.
  - `grep -n -i -e "<phrase>" -e "<phrase>" <files>` on the unit's text and the earlier texts.
    **Batch:** collect everything you need to confirm, then grep for all of it in one or two calls.
  - `wc -w <the draft>`

## Report back
Start with **Spoiler findings**, one line per finding, even when there are none:
`"<the draft's words>" → <why: from memory | from a later chapter | foreshadowing | hinting question | passage chosen for later payoff> → <deleted | rewritten as "…">`.
Then:
- **LATER WORD verdicts:** each word, leak or harmless, with a reason.
- **Outside-knowledge findings**, in the same form.
- **Other fixes:** quotes, cast list, structure, length.
- **Remaining check.py lines**, and why each is acceptable.
- **Unsettled:** anything you could not settle.
