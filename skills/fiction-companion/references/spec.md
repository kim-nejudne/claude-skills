# Fiction-companion format

Companions are for Kim's own reading of a novel or a story collection, one unit at a time. Each
chapter's companion has two parts: **Before you read** comes before the chapter text and orients
the reader; **After you read** comes after it and consolidates. `example-chapter.md` shows the
Markdown conventions for an invented book; match its markup, not its content.

## The three rules that override everything
1. **Spoilers: strict.** The companion for unit N uses only units 1..N (a collection story: only
   that story). See "Spoilers" below.
2. **Text only.** Nothing from outside the book. See "Text only" below.
3. **Locators are quotes.** No page, paragraph, location or chapter numbers beyond N, and no links.
   To point at a moment, quote a few of its words.

## Voice
- Neutral expository third person. Never "we", "you will" or "the reader will".
- British spelling: colour, realise, centre, neighbour.
- Plot is told in the present tense ("Elizabeth overhears…").
- Plain, exact sentences. No hype ("masterful", "iconic") and no filler.
- Name characters as the text has named them by that point. If a figure is "the stranger" until
  a later chapter names him, he is "the stranger".

## Spoilers
- **Allowed:** what units 1..N say, and fair inferences from them that a careful first-time
  reader could make.
- **Banned:**
  - any event, name, place, relationship, secret or outcome that first appears after N;
  - foreshadowing: "this matters later", "for now", "at least for the moment", "the first of
    many", "will prove", "eventually", "as events show", "ironically, given what follows";
  - judgements that need the ending: "the hero", "the villain", "her future husband", "Darcy's
    pride, which he will overcome";
  - selecting a passage or theme *because* it pays off later. Choose by what matters in 1..N;
  - the book's reputation: famous lines, its reception, its "twist".
- **Digests:** agents know the earlier units through `companions/.digest/` (`<slug>.md`, what
  happens; `<slug>.cast.md`, the cumulative cast and threads), written from each unit alone plus
  the cast file before it. A digest is allowed text for every later
  unit; nothing in it may go beyond its own unit.
- **Memory:** the model may know this book well. That knowledge is forbidden. A statement is
  allowed only if a sentence in units 1..N supports it. When unsure, cut it.
- **Questions** ask about what has been read. They may invite prediction only openly ("What does
  Elizabeth expect of Mr Darcy now?"), never in a way that hints at the answer.
- **Collections:** a story's companion uses that story only: no other stories, no links between
  stories, no "as in the previous story".

## Text only
- **Banned:**
  - author biography;
  - history, customs, money, law, class, religion or geography from outside the book;
  - word glosses and period vocabulary notes;
  - critics, interpretations, literary movements, influence, adaptations, reception.
- **Allusions are named, never explained:** "Mary quotes a moral maxim", "Mr Collins reads from
  Fordyce's Sermons" (the text names it). If the text alludes to a recognisable work without naming
  it, the companion may name the work in a few words, with no explanation of it.
- What the book itself says about its world (an income, an entail, a custom) may be reported as
  the book says it, attributed: "the narrator says…", "Mrs Bennet explains…".

## Quotations
- Every blockquote and every inline “…” quote of 3+ words is verbatim from the scope's text.
  Use double curly quotes for words from the book. Ellipses `…` mark cuts, `[brackets]`
  insertions. Never put paraphrase in quotation marks.
- `Mr.`, `Mrs.` and other spellings stay as the text has them inside quotes. Outside quotes,
  write British `Mr Bennet`.
- Separate consecutive blockquotes with a `<!-- -->` line with blank lines around it, or they
  merge.

## Length
`check.py` prints the targets (words of prose, markup and the cast list excluded).
- **Whole unit:** `clamp(300 + chapter words / 4, 400, 1500)`, ±20%. A 900-word chapter gets ~525;
  a 4,000-word chapter ~1,300.
- **Before you read:** at most 275 words, cast list excluded. The cast list is exempt from both
  limits, but stays terse.
- **Intro:** 400–700 words. **End essay:** 1,500–2,500.

## Unit file: `companions/src/<slug>.md`
**Meta header** (python-markdown `meta`, then a blank line):
- `Title:` the unit's title from the manifest ("Chapter 3", "Chapter 3: The Ball", or the story's title)
- `Eyebrow:` "Chapter 3 · Reading companion", "Prologue · Reading companion" or "Story 4 · Reading companion"

**`# Before you read`**: novels only, and not for the first unit (the intro comes before it).
1. `## Previously`: a recap of unit N−1 only, in 60–150 words. Plot only, no interpretation.
2. `## Characters so far`: everyone met or named in units 1..N−1, *as known at the end of N−1*.
   Wrap the list in `<div class="cast" markdown="1">`.
   - Group by household or milieu, groups in order of first appearance, each group a bold line.
   - One line per principal: `- **Name**: what the text has shown, in 12 words or fewer.`
   - Minor and offstage figures go on one names-only line per group: `**Also:** Mrs Long, Mr Morris.`
   - It equals the previous chapter's list plus that chapter's newcomers, with descriptions
     updated only by what N−1 showed.

**`# After you read`**:
1. `## What happened`: the unit's events in order, 15–25% of the total.
2. `## Characters in this chapter` (`story` in a collection): everyone who appears or is
   discussed at length, one line each on what they do here. First appearances get
   `<span class="new">new</span>` after the name: `- **Mr Collins** <span class="new">new</span>: …`
   "First appearance" means the first time the text names or shows the character: someone named
   in an earlier unit who now appears in person is not new, as they are already in the cast list.
3. `## Craft`: narration, point of view and style, with short quotes as evidence: who tells, whose
   mind the narration enters, irony, dialogue, free indirect speech, pace, letters, set pieces.
   These terms are craft vocabulary, not outside knowledge.
4. `## Themes and motifs so far` (`## Themes and motifs` for a story): what units 1..N develop, and
   what this unit adds. No themes that only later chapters make visible.
5. `## Close reading`: one passage for a unit under 1,500 words, two up to 4,000, three above that.
   Each is a `### Short label` heading, a verbatim blockquote ending
   `> <span class="src">Speaker</span>` (or `Narrator`), then prose unpacking it phrase by phrase:
   what each phrase does, whose voice it is, and what it shows. Pick passages not quoted at
   length elsewhere in the file.
6. `## Questions`: 3–5 open discussion questions, numbered.

A story's file has only `# After you read`, with its own cast list in section 2.

## Intro: `companions/src/intro.md`
- **Meta:** `Title: Introduction`, `Eyebrow: Before you begin · Reading companion`.
- **Sources:** the first unit's text and the manifest's unit list (the number of units, the part
  titles). Nothing beyond the opening: no chapter titles after the first unit, no events after it.
- **Sections:**
  - `## The premise`: the situation the opening sets up.
  - `## Narrator and setup`: who tells it, and where and when as the text gives it.
  - `## How the book is organised`: counts, parts and volumes; for a collection, the stories' titles.
  - `## What to watch for`: 3–5 bullets about how to read, drawn from the opening's own manner,
    not from where the plot goes.

## End essay: `companions/src/end.md`
- **Meta:** `Title: After the end`, `Eyebrow: Whole book · Full spoilers`.
- **Opening banner:** the first line after the meta is
  `<p class="spoiler">Full spoilers: read this only after finishing the book.</p>`
- **Sections:**
  - `## The ending`
  - `## Structure`
  - `## How the themes develop`
  - `## Arcs`: the principal characters, from first to last appearance.
- **Rules:** text only, quotes verbatim from anywhere in the book, chapters named as "Chapter 34".
