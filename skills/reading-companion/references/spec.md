# Reading-companion format (approved by Kim, 2026-11-16)

Companions are for Kim's own study: to understand a book. Recall, exam prep and reflection
(discussion questions, the companion's own critique) belong to a separate skill, not here.

`example-companion.md` is Asad, *Genealogies of Religion*, Chapter 1, which Kim approved. Match its
structure, tone, depth and Markdown exactly.

## Reader and use
- **Reader:** a graduate student in the book's field who knows its classic debates but is **new to
  the book's specific context** (its region, period, sources or sub-field). Explain context, not
  the field's basics. Example: for a theology grad, explain Korean shamanism, not Chalcedon.
- **Use:**
  - **Before reading:** the one-page primer, then section 1, Context in depth.
  - **After reading:** sections 2–8, to consolidate.

## Voice
- Neutral expository third person ("Asad argues…", never "we" or "you will").
- British spelling: labour, centred, organisation, -ise.
- Plain, exact sentences. No hype and no filler.

## Length (`wc -w` on the .md, including markup)
Length follows the unit's body pages (the first range in `Pages:`). `check.py` prints the target.
- **15+ body pages:** 2,000 + 50 × pages, clamped to 2,800–4,500, within ±15%. A 28-page chapter
  gets ~3,400; a 43-page one ~4,150.
- **Under 15 body pages** (prologue, epilogue, short introduction or conclusion): 1,600–2,000 words.
  Keep all 8 sections but scale them down: ~300 words of context in depth, 4–5 argument steps,
  1 close-reading passage, 3 quotations, and a shorter glossary and who's who.

## One PDF per unit; structure in this order
**Meta header** (python-markdown `meta`):
- Title
- Subtitle (omit the line if there is none)
- Eyebrow: "Chapter N · Reading companion", or "Introduction · Reading companion"
- Running: a short footer label, e.g. "Ch. 3 · Korean Women"
- Pages: e.g. "Chapter pp. 83–113 · Notes pp. 219–24". Drop the Notes part when notes are footnotes.
- Citation: Chicago notes-bibliography, for the chapter:

  `Surname, First. “Chapter Title.” In *Book Title*, first–last. Series. City: Publisher, Year.`

  Omit Series if there is none. For a single-author book, the chapter-in-book form is still right.

**Page 1: "Before you read" primer.** Use `<section class="primer" markdown="1">`, which must fit
page 1 under the masthead. It has four parts:
1. **Thesis:** 2–3 sentences in `<p class="thesis">`.
2. **Context you need:** the history, places, people, traditions and debates this reader lacks.
3. **Watch for:** 3–5 things to notice while reading.
4. **Key terms preview:** a one-line list in `<p class="terms-preview">`.

Then 8 sections headed `## <span class="num">N</span> Title`. Section 1 is still read before the
chapter; 2–8 after it.
1. **Context in depth** (before reading): 400–700 words of prose under short `###` sub-heads. The
   history, places, people, traditions and debates the unit assumes and this reader lacks. Expand
   the primer's "Context you need" bullets; don't repeat them. General knowledge is allowed here,
   at textbook level only (dates, events, what a tradition holds), stated plainly: no outside
   citations, page numbers or quotations. Page refs to the book are welcome where the author
   touches the same ground.
2. **Argument map:** numbered steps of how the argument builds, in `<div class="argument" markdown="1">`.
3. **Section by section:** one paragraph per author subheading, headed
   `### Heading <span class="pp">pp. X–Y</span>`. Add what the argument map leaves out (evidence,
   examples, interlocutors); don't restate the map's steps.
4. **Close reading:** the 1–2 hardest or most load-bearing passages, 400–600 words in all. Each is a
   `### Short label <span class="pp">p. N</span>` heading, a verbatim blockquote ending
   `> <span class="src">Speaker · p. N</span>`, then prose that unpacks it phrase by phrase: what
   each term means here, what the sentence does in the argument, and what it presupposes. Pick
   passages not used in Key quotations.
5. **Key terms:** concepts and non-English terms, defined as this chapter uses them, as a
   definition list in `<div class="glossary" markdown="1">`.
6. **Who's who:** thinkers and figures cited, and the position each holds *in this chapter*, in
   `<div class="people" markdown="1">`. One line each; group minor figures.
7. **Key quotations:** 4–6 verbatim blockquotes, each ending `> <span class="src">Speaker · p. N</span>`.
   Separate consecutive blockquotes with a `<!-- -->` line with blank lines around it, or they
   merge into one box. The same applies in Close reading.
8. **Cross-chapter connections:** links to other units, with page references.

## Book overview (`book-overview.md`, 2–3 pages, written last)
The pattern is `example-overview.md`. It contains:
- **At a glance:** the `primer glance` section, with thesis, author and suggested reading order.
- **The argument in one page.**
- **Chapter map table:** unit, pages, setting/topic, main voices, central claim or image.
- **Threads across chapters,** with page references.
- **Core vocabulary,** pointing to the chapter companions.
- **Questions for the whole book,** labelled as the companion's own, as a plain bulleted list
  after the `<p class="note">`.

## Accuracy rules (non-negotiable)
- **Quotations:** every quotation, whether a blockquote or an inline “…” of 4+ words, is verbatim
  from the book text, with obvious OCR errors fixed. Never put paraphrase in quotation marks.
- **Page references:** use the printed book page, not the PDF page. Each must fall inside the
  unit's range or its notes range. Cross-chapter references are checked against that chapter's
  text.
- **Outside sources:** never invent specific outside citations, page numbers or quotations. A
  well-known debate may be named ("the Hampson–Coakley debate over kenosis") without fake detail.
- **Outside knowledge** (mostly in Context in depth and the primer): textbook-level only. Every
  such claim is fact-checked by the checker and listed in the run's report. If in doubt, leave it out.
- **Attribution:** if the author reports someone else's view, say whose it is. Do not overstate
  the author's claims.

## Characters
- Write Arabic ʿayn as ‘ (U+2018) and hamza as ’ (U+2019), not the modifier letters U+02BF and
  U+02BE. Crimson Pro lacks those, and the fallback glyph leaves a wide gap.
- Keep the book's own transliteration: its macrons and dots, and its spellings of names. Note
  misspellings rather than silently correcting them.

## Look
"Modern study guide":
- **Fonts:** Crimson Pro body, IBM Plex Sans headings.
- **Callouts:** shaded boxes for the primer and the quotes.
- **Page:** US Letter, with a running footer and page numbers.
- **Accent:** one colour per book. It is set in `book.json` as `accent` (dark, contrast ≥ 7:1 on
  white, legible in greyscale) and `accent_soft` (a very pale tint of it, for the callout fill).
  The first book used oxblood `#7A2E2E` / `#F5ECEA`.
