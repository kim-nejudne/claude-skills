# Subagent brief: chapter digest

**Subagent:** these are your instructions. Every `{…}` takes its value from the values block in
your prompt. `{SKILL}` = `/home/kim/.claude/skills/fiction-companion`.

---

You are writing the digest of one chapter of {AUTHOR}, *{BOOK}*. A digest is a short, plain record
of what the book has told a first-time reader by the end of this chapter. The companion writers
and checkers for this chapter and every later one rely on it instead of rereading the whole book,
so it must be accurate, complete for names, and contain nothing the book hasn't said yet.

## Your chapter
- **Unit:** {UNIT TITLE} (`{SLUG}`), {WORDS} words.
- **Output files** (the ONLY files you may create or edit):
  - `{BOOKDIR}/companions/.digest/{SLUG}.md`: what happens in this chapter;
  - `{BOOKDIR}/companions/.digest/{SLUG}.cast.md`: the cast and threads so far, cumulative.

## What you may read: ONLY these files
- **Read in full:** the chapter, `{BOOKDIR}/companions/.text/{SLUG}.txt`.
- **Read in full:** the previous unit's cast file, {PREVIOUS CAST: its `.cast.md` path, or "none:
  this is the first unit"}. Its cast and threads are the starting point for yours.

Do not open any other `.text` file, any other digest, or any companion. **You may know this book.**
That knowledge is forbidden: write only what the chapter and the previous cast file support.

## Format
`{SLUG}.md`:
```
# {UNIT TITLE}

## What happens

<150–300 words: the chapter's events in order, plainly. Names as the text gives them by now. No
interpretation, no foreshadowing ("will", "later", "for now").>
```

`{SLUG}.cast.md`:
```
# {UNIT TITLE}: cast and threads

## Cast so far

- **Name**: who they are and what the text has shown, as of the end of this chapter, in 20 words or fewer. (from {chapter where first named})
Also: minor or offstage figures, comma-separated.

## Threads so far

- <up to 8 bullets: open situations, repeated images or motifs, questions the text has raised,
  as of the end of this chapter. Nothing about where they lead.>
```
- **Cast so far** is cumulative: the previous cast file's list, with descriptions updated only by
  what this chapter shows, plus everyone first named here, marked `(from {this chapter})`. Never
  drop a name. A character the text calls by a new name keeps one line: `**Elizabeth (Lizzy)**`.
- No group headings in the cast: a plain list, then the `Also:` line.
- A short quote is welcome where wording matters, verbatim, in “…”.

## Tools: STRICT
Kim is away, and any other command blocks on a permission prompt.
- **Read:** the two files above only. **Write/Edit:** only your two output files.
- **Bash:** one command per call, absolute paths, no `cd`, `&&`, `;`, pipes, redirection or loops.
  Only `python3 -I {SKILL}/scripts/check.py {BOOKDIR}/companions/.digest/<{SLUG}.md or {SLUG}.cast.md> {BOOKDIR}`.

## Steps
1. Read the previous cast file, then the chapter.
2. Write both files.
3. Run check.py on each and fix every line it reports. A LATER WORD is a name the book hasn't used yet:
   it came from memory, so delete it.

## Report back (two lines)
Names first named in this chapter, and the remaining check.py lines.
