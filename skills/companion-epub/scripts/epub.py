"""Build one EPUB 3 that pairs each reading companion with its chapter text.

Usage:
    uv run --with markdown --with pymupdf python epub.py BOOKDIR

Reads BOOKDIR/chapters/.parts.json (from /split-book), the source PDF it names, and
BOOKDIR/companions/src/NN-*.md (paired with parts by the two-digit prefix). Spine per part:
companion, chapter text, the part's notes (linked both ways when markers and notes agree).
Writes BOOKDIR/<BOOKDIR name>-companion.epub.

BOOKDIR/companions/epub-settings.json describes the layout (keys and defaults in DEFAULTS;
the defaults fit The Selfish Gene, OUP 2016). Notes styles:
    asterisk   "*" in the text, endnotes headed "p. N lemma" in note_head_font (Dawkins)
    numbered   superscript numbers, numbered endnotes in the parts' "notes" page ranges
    footnotes  superscript numbers, numbered notes at the foot of body pages
    none       notes (if any) follow the chapter unlinked
Sizes are [min, max] bands in pt, so OCR'd scans with jittery sizes work too.

BOOKDIR/companions/epub-fixes.json, optional, a list of
    {"file": "02-notes.xhtml", "find": "...", "replace": "..."}  (find must match exactly once)
    {"compound": "cold-blooded"}  (keep this hyphen when a line break falls on it)
    {"sup": "55", "replace": "\u201d"}  (every unlinked <sup>55</sup> in the text: an OCR'd quote mark)
A line-end hyphen is kept only if the compound occurs mid-line somewhere in the book.
"""
import collections
import datetime
import html
import json
import re
import sys
import uuid
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import markdown
import pymupdf

DEFAULTS = {
    "head_y": 42,             # spans starting above this are running heads
    "foot_y": 9999,           # bare page numbers starting below this are folios
    "body_size": [10.0, 10.5],
    "notes_size": [9.1, 9.3],  # endnote or footnote text
    "small_max": 7.0,         # smaller spans: fraction parts, superscripts, note markers
    "display_min": 16,        # larger spans: chapter numbers, titles, drop caps (dropped)
    "opening_skip_y": 0,      # on a part's first page, drop lines starting above this (title block);
                              # or {"default": y, "02": y} to set it per part (two-digit file prefix)
    "dropcap": True,          # a single display letter on the opening page starts the first paragraph
    "notes": "asterisk",      # asterisk | numbered | footnotes | none
    "note_head_font": "Medium",  # asterisk style: font of the "p. N lemma" lines
    "notes_heading": r"chapter\s+(\d+)",  # endnotes: heading line opening each chapter's block; null = whole range
}
NOTE_NO = r"[0-9ilIO]{1,3}"  # OCR reads 1 as i, l or I
NOTE_START = rf"\s*(?:<sup>)?({NOTE_NO})\s*[.,]?(?:</sup>)?\s*[.,]?\s+"  # "12. ", "<sup>5.</sup> ", "i. "
XML_ENTITIES = {"amp", "lt", "gt", "quot", "apos"}
CSS = """\
.eyebrow { font-size: 0.85em; text-transform: uppercase; letter-spacing: 0.05em; }
blockquote { margin: 0.5em 1.5em; }
figure { margin: 1em 0; text-align: center; }
figure img { max-width: 100%; }
a.noteref { text-decoration: none; padding: 0 0.15em; }
.note { margin-bottom: 1em; }
.note-head { font-weight: bold; }
"""


def xhtml(title: str, body: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="en" lang="en">
<head><meta charset="utf-8"/><title>{html.escape(title)}</title><link rel="stylesheet" href="style.css"/></head>
<body>
{body}
</body>
</html>
"""


def xml_safe(s: str) -> str:
    """Named HTML entities are not XML: turn them into characters."""
    return re.sub(r"&([a-zA-Z][a-zA-Z0-9]*);",
                  lambda m: m.group(0) if m.group(1) in XML_ENTITIES else html.unescape(m.group(0)), s)


def warn(msg: str):
    print(f"  ! {msg}", file=sys.stderr)


def in_band(size: float, band) -> bool:
    return band[0] <= size <= band[1]


# ---------- companion ----------

def companion(md_path: Path) -> tuple[str, str, list[tuple[str, str]]]:
    """Return (title, body xhtml, [(h2 id, h2 label)])."""
    md = markdown.Markdown(extensions=["meta", "extra", "sane_lists"], output_format="xhtml")
    text = re.sub(r"\b(pp?\.|nn?\.) (?=\d)", "\\1\u00a0", md_path.read_text())  # as reading-companion's build.py
    body = xml_safe(md.convert(text))
    meta = {k: " ".join(v) for k, v in md.Meta.items()}
    if "title" not in meta:
        sys.exit(f"{md_path.name}: missing meta 'title'")

    def inline(s: str) -> str:
        return xml_safe(markdown.markdown(s, output_format="xhtml").removeprefix("<p>").removesuffix("</p>"))

    sections = []

    def add_id(m: re.Match) -> str:
        sid = f"s{len(sections) + 1}"
        label = re.sub(r'<span class="num">.*?</span>|<[^>]+>', "", m.group(1)).strip()
        sections.append((sid, html.unescape(label)))
        return f'<h2 id="{sid}">{m.group(1)}</h2>'

    body = re.sub(r"<h2>(.*?)</h2>", add_id, body)
    head = (f'<p class="eyebrow">{html.escape(meta.get("eyebrow", "Reading companion"))}</p>\n'
            f'<h1>{inline(meta["title"])}</h1>\n')
    return meta["title"], head + body, sections


# ---------- PDF text ----------

class Line:
    def __init__(self, top, bottom, x0, size, html_, plain, head):
        self.top, self.bottom, self.x0, self.size = top, bottom, x0, size
        self.html, self.plain, self.head = html_, plain, head


class PageItems(list):
    """One page's items, top to bottom: ("line", top, Line) and ("fig", top, name, png, alt)."""
    band: list


def italic(font: str) -> bool:
    return "Italic" in font or "Ital" in font or font.endswith("It")


def span_html(s: dict) -> str:
    t = html.escape(s["text"], quote=False)
    return f"<i>{t}</i>" if italic(s["font"]) and s["text"].strip() else t


def figure_regions(page, spans, band, small_max):
    """Big vector drawings, grown to take in nearby labels and captions (text outside the main band)."""
    rects = [d["rect"] for d in page.get_drawings() if d["rect"].width > 40 and d["rect"].height > 30]
    regions = []
    for r in sorted(rects, key=lambda r: r.y0):
        if regions and r.y0 < regions[-1].y1 + 30:
            regions[-1] |= r
        else:
            regions.append(pymupdf.Rect(r))
    others = [s for s in spans if s["size"] >= small_max and not in_band(s["size"], band)]
    for k in range(len(regions)):
        grown = True
        while grown:
            grown = False
            for s in others:
                reg, b = regions[k], pymupdf.Rect(s["bbox"])
                if reg.y0 - 35 < b.y1 and b.y0 < reg.y1 + 35 and (reg | b) != reg:
                    regions[k] = pymupdf.Rect(reg) | b
                    grown = True
    merged = []  # grown regions can overlap: merge them so nothing is drawn twice
    for r in regions:
        if merged and r.y0 < merged[-1].y1:
            merged[-1] = merged[-1] | r
        else:
            merged.append(r)
    return merged


def page_items(page, cfg, band, fig_name, opening, heads):
    """Lines and figures of one page, top to bottom. fig_name(i) -> image file name."""
    small_max = cfg["small_max"]
    spans = [s for b in page.get_text("dict")["blocks"] if b["type"] == 0
             for l in b["lines"] for s in l["spans"]
             if s["bbox"][1] >= cfg["head_y"] and s["size"] < cfg["display_min"]
             and not (opening is not None and s["bbox"][1] < opening)]
    for s in spans:  # InDesign "indent to here" (\x07) and other controls are not XML
        s["text"] = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s["text"])
    inline_imgs = [b["bbox"] for b in page.get_text("dict")["blocks"]
                   if b["type"] == 1 and b["bbox"][3] - b["bbox"][1] < 15]
    items = PageItems()
    items.band = band
    for i, reg in enumerate(figure_regions(page, spans, band, small_max)):
        reg = pymupdf.Rect(reg.x0 - 4, reg.y0 - 4, reg.x1 + 4, reg.y1 + 4)
        inside = sorted((s for s in spans if pymupdf.Rect(s["bbox"]).intersects(reg)),
                        key=lambda s: (round(s["bbox"][1]), s["bbox"][0]))
        alt = " ".join(s["text"].strip() for s in inside if s["text"].strip())
        spans = [s for s in spans if s not in inside]
        items.append(("fig", reg.y0, fig_name(i), page.get_pixmap(clip=reg, dpi=220).tobytes("png"), alt))

    # stacked fractions: small span over small span with the same centre; other small spans are superscripts
    small = [s for s in spans if s["size"] < small_max and s["text"].strip()]
    normal = [s for s in spans if s["size"] >= small_max and s["text"].strip()]
    # whitespace-only spans can sit off the baseline: they join a row, never start one
    tokens = [(s["bbox"], s["text"], s["text"]) for s in spans if s["size"] >= small_max and not s["text"].strip()]
    used = set()
    for a in small:
        if id(a) in used:
            continue
        ca = (a["bbox"][0] + a["bbox"][2]) / 2
        den = next((b for b in small if id(b) not in used and b is not a
                    and abs((b["bbox"][0] + b["bbox"][2]) / 2 - ca) < 4
                    and 4 < b["bbox"][1] - a["bbox"][1] < 10), None)
        if den:
            used |= {id(a), id(den)}
            frac = a["text"].strip() + "/" + den["text"].strip()
            tokens.append((a["bbox"], frac, frac))
        else:
            used.add(id(a))
            t = html.escape(a["text"].strip())
            tokens.append((a["bbox"], f"<sup>{'<i>' + t + '</i>' if italic(a['font']) else t}</sup>", a["text"].strip()))

    # group normal spans into lines by baseline
    rows: list[list[dict]] = []
    for s in sorted(normal, key=lambda s: (s["origin"][1], s["origin"][0])):
        if rows and abs(rows[-1][0]["origin"][1] - s["origin"][1]) < 2:
            rows[-1].append(s)
        else:
            rows.append([s])
    boxes = [(min(s["bbox"][1] for s in row), max(s["bbox"][3] for s in row)) for row in rows]
    extra = [[] for _ in rows]
    for bbox, th, tp in tokens:  # each token joins the row whose middle is nearest
        cy = (bbox[1] + bbox[3]) / 2
        if rows:
            k = min(range(len(rows)), key=lambda k: abs((boxes[k][0] + boxes[k][1]) / 2 - cy))
            extra[k].append((bbox[0], th, tp))
    for row, (top, bottom), toks in zip(rows, boxes, extra):
        parts = [(s["bbox"][0], span_html(s), s["text"]) for s in row] + toks
        for bbox in inline_imgs:
            if top - 2 <= (bbox[1] + bbox[3]) / 2 <= bottom + 2:
                warn(f"inline image skipped, PDF page {page.number + 1}: add a fix")
        parts.sort(key=lambda p: p[0])
        for k in range(1, len(parts)):  # mixed number: "6" + "1/4" -> "6 1/4"
            if re.fullmatch(r"\d+/\d+", parts[k][2]) and parts[k - 1][2][-1:].isdigit():
                parts[k] = (parts[k][0], " " + parts[k][1], " " + parts[k][2])
        sizes = collections.Counter()
        for s in row:
            sizes[round(s["size"], 1)] += len(s["text"].strip())
        plain = "".join(p[2] for p in parts)
        if top > cfg["foot_y"] and re.fullmatch(r"\s*[0-9ivxlc]{1,4}\s*", plain, re.I):
            continue  # folio
        head = heads and any(cfg["note_head_font"] in s["font"] for s in row)
        items.append(("line", top, Line(top, bottom, min(p[0] for p in parts if p[2].strip()),
                                         sizes.most_common(1)[0][0], "".join(p[1] for p in parts), plain, head)))
    items.sort(key=lambda it: it[1])
    return items


def join_lines(lines: list[Line], vocab: set[str]) -> str:
    """Join lines into one HTML string, mending line-end hyphens (soft or plain)."""
    out = ""
    for i, l in enumerate(lines):
        h = l.html.rstrip()
        if i == len(lines) - 1:
            out += h
            break
        nxt = lines[i + 1].plain.lstrip()
        end = l.plain.rstrip()
        a = re.findall(r"[A-Za-z]+$", end[:-1])
        b = re.findall(r"^[A-Za-z]+", nxt)
        compound = bool(a and b) and f"{a[0]}-{b[0]}".lower() in vocab
        if end.endswith("\u00ad"):  # discretionary break; a few real compounds are typeset this way too
            out += re.sub(r"\u00ad((?:</i>)?)$", r"-\1" if compound else r"\1", h)
        elif end.endswith("-"):
            keep = compound or not nxt[:1].islower()
            out += h if keep else re.sub(r"-((?:</i>)?)$", r"\1", h)
        elif end.endswith(("—", "–", "/")):
            out += h
        else:
            out += h + " "
    out = out.replace("\u00ad", "")
    out = re.sub(r"(\d/\d+) ([,.;:)])", r"\1\2", out)  # gap spans set beside stacked fractions
    out = re.sub(r"\( (\d+/\d)", r"(\1", out)
    return re.sub(r"</i>(\s*)<i>", r"\1", out)


def blocks(pages, dropcap=None):
    """Group page items into blocks: ('p'|'quote'|'head', [Line]) and ('fig', item)."""
    out = []
    margins = {pno: min((it[2].x0 for it in its if it[0] == "line" and in_band(it[2].size, its.band)), default=0)
               for pno, its in pages}
    # body-size block quotes: two or more consecutive indented lines at normal line spacing (a lone
    # indented line is a paragraph's first line; a wider gap ends a quote)
    quoted = set()
    for pno, its in pages:
        main = [it[2] for it in its if it[0] == "line" and in_band(it[2].size, its.band) and not it[2].head
                and not (dropcap and pno == dropcap[0] and it[2].top < dropcap[1])]
        ind = [l.x0 > margins[pno] + 5 for l in main]
        gaps = sorted(b.top - a.top for a, b in zip(main, main[1:]))
        step = gaps[len(gaps) // 2] if gaps else 0
        for k in range(len(main) - 1):
            if ind[k] and ind[k + 1] and main[k + 1].top - main[k].top < 1.3 * step:
                quoted |= {id(main[k]), id(main[k + 1])}
    held = []  # figures met inside a paragraph go after it, as a reflowed book would place them
    for pno, its in pages:
        m = margins[pno]
        for it in its:
            if it[0] == "fig":
                held.append(("fig", it))
                continue
            l = it[2]
            kind = "head" if l.head else ("p" if in_band(l.size, its.band) and id(l) not in quoted else "quote")
            prev = out[-1] if out else None
            new = (prev is None or prev[0] != kind
                   or (kind == "p" and l.x0 > m + 5 and not (dropcap and pno == dropcap[0] and l.top < dropcap[1])))
            if new:
                out += held
                held = []
                out.append((kind, [l]))
            else:
                prev[1].append(l)
    return out + held


def read_pages(doc, cfg, rng, band, fig_prefix, images, opening=None, heads=False):
    """opening: on the range's first page, drop lines starting above this y."""
    pages = []
    for pno in range(rng[0], rng[1] + 1):
        def fig_name(i, pno=pno):
            return f"images/{fig_prefix}-p{pno}-{i + 1}.png"
        its = page_items(doc[pno - 1], cfg, band, fig_name, opening if pno == rng[0] else None, heads)
        for it in its:
            if it[0] == "fig":
                images[it[2]] = it[3]
        pages.append((pno, its))
    return pages


def fig_html(it) -> str:
    _, _, name, _, alt = it
    return f'<figure><img src="{name}" alt="{html.escape(alt)}"/></figure>'


def render(bl, vocab) -> list[str]:
    out = []
    for kind, ls in bl:
        if kind == "fig":
            out.append(fig_html(ls))
        else:
            h = join_lines(ls, vocab)
            out.append(f"<blockquote><p>{h}</p></blockquote>" if kind == "quote" else f"<p>{h}</p>")
    return out


def take_footnotes(pages, cfg):
    """Remove the foot-of-page note lines from body pages -> [(pno, Line)] in reading order."""
    feet = []
    for pno, its in pages:
        lines = [it for it in its if it[0] == "line"]
        last_body = max((k for k, it in enumerate(lines) if in_band(it[2].size, its.band)), default=-1)
        foot = [it for it in lines[last_body + 1:] if in_band(it[2].size, cfg["notes_size"])]
        its[:] = [it for it in its if it not in foot]
        feet += [(pno, it[2]) for it in foot]
    return feet


def numbered_entries(source, vocab):
    """Group note blocks into entries that open with a note number.
    source: ('p'|'quote'|'fig', lines-or-item[, pno]) blocks.
    -> [[number text or None, [html paragraphs], pno or None]]; a leading entry None holds text
    found before the first number."""
    entries = []
    for kind, ls, *pno in source:
        pno = pno[0] if pno else None
        if kind == "fig":
            if entries:
                entries[-1][1].append(fig_html(ls))
            continue
        m = re.match(NOTE_START, ls[0].html)
        if m and (kind == "p" or not entries):
            ls[0].html = ls[0].html[m.end():]
            entries.append([m.group(1), [], pno])
        elif not entries:
            entries.append([None, [], pno])
        h = join_lines(ls, vocab)
        entries[-1][1].append(f"<blockquote><p>{h}</p></blockquote>" if kind == "quote" else f"<p>{h}</p>")
    return entries


def note_number(t: str) -> int | None:
    t = t.translate(str.maketrans("ilIO", "1110"))
    return int(t) if t.isdigit() else None


def footnote_blocks(feet):
    """Foot-of-page lines -> ('p', [Line], pno) blocks, a new block at each line opening with a note number."""
    out = []
    for pno, l in feet:
        m = re.match(NOTE_START, l.html)
        if (m and re.search(r"[.,]", m.group(0))) or not out:  # needs the stop: "1987 study" is no note start
            out.append(("p", [l], pno))
        else:
            out[-1][1].append(l)
    return out


def endnote_pages(doc, cfg, part, images, prefix):
    """The part's slice of the notes pages (pages may hold several chapters' notes)."""
    heads = cfg["notes"] == "asterisk"
    pages = read_pages(doc, cfg, part["notes"], cfg["notes_size"], prefix + "-notes", images, heads=heads)
    if not cfg["notes_heading"]:
        return pages
    want, on, kept = str(part.get("number")), False, []
    for pno, its in pages:
        keep = PageItems()
        keep.band = its.band
        for it in its:
            if it[0] == "line":
                m = re.fullmatch(rf"\s*{cfg['notes_heading']}\s*", it[2].plain, re.I)
                if m:
                    on = m.group(1) == want
                    continue
                if it[2].size >= cfg["body_size"][0] and not it[2].head:  # chapter title under the heading
                    continue
            if on:
                keep.append(it)
        kept.append((pno, keep))
    return kept


def asterisk_notes(pages, vocab, label):
    """Asterisk-style endnotes -> [(book page, head html, body html)]."""
    notes = []
    for kind, ls in blocks(pages):
        if kind == "head":
            plain = re.sub(r"\s+", " ", " ".join(l.plain.strip() for l in ls).replace("\u00ad", ""))
            m = re.match(r"p\.\s*(\d+)\s*(.*)", plain)
            if not m:
                sys.exit(f"{label}: note head without page: {plain!r}")
            notes.append([int(m.group(1)), html.escape(m.group(2)), []])
        elif not notes:
            sys.exit(f"{label}: note text before the first note head")
        else:
            notes[-1][2] += render([(kind, ls)], vocab)
    return [(p, head, "\n".join(b)) for p, head, b in notes]


def chapter(doc, cfg, part, vocab, images, nn, label):
    """-> (text xhtml body, notes xhtml body or None)."""
    first = part["body"][0]
    cap = None
    if cfg["dropcap"]:
        big = [s for b in doc[first - 1].get_text("dict")["blocks"] if b["type"] == 0
               for l in b["lines"] for s in l["spans"] if s["size"] >= cfg["display_min"]]
        cap = next((s for s in big if len(s["text"].strip()) == 1 and s["text"].strip().isalpha()), None)
    skip = cfg["opening_skip_y"]
    skip = skip.get(nn, skip.get("default", 0)) if isinstance(skip, dict) else skip
    pages = read_pages(doc, cfg, part["body"], cfg["body_size"], nn, images, opening=skip)
    style = cfg["notes"]
    feet = take_footnotes(pages, cfg) if style == "footnotes" else []
    bl = blocks(pages, (first, cap["bbox"][3]) if cap else None)
    if cap:
        for kind, ls in bl:
            if kind == "p":
                ls[0].html = cap["text"].strip() + ls[0].html.lstrip()
                ls[0].plain = cap["text"].strip() + ls[0].plain.lstrip()
                break

    # notes -> [(label, head html, body html, linked)]; a linked note k's marker becomes \x00k\x00
    notes, lead = [], ""
    if style == "asterisk":
        star_pages = [pno - part["page_offset"] for pno, its in pages for it in its
                      if it[0] == "line" for _ in range(it[2].html.count("*"))]
        text = "\n".join(render(bl, vocab))
        ok = False
        if part.get("notes"):
            found = asterisk_notes(endnote_pages(doc, cfg, part, images, nn), vocab, label)
            ok = star_pages == [p for p, _, _ in found]
            if not ok:
                warn(f"{label}: {len(star_pages)} asterisks on pp. {star_pages}, {len(found)} notes on pp. "
                     f"{[p for p, _, _ in found]}: notes left unlinked")
            notes = [(f"p. {p}", head, body, ok) for p, head, body in found]
        elif star_pages:
            warn(f"{label}: {len(star_pages)} asterisks but no notes")
        if ok:
            count = iter(range(1, len(star_pages) + 1))
            text = re.sub(r"\*", lambda _m: f"\x00{next(count)}\x00", text)
    elif style in ("numbered", "footnotes"):
        if style == "footnotes":
            source = footnote_blocks(feet)
        else:
            source = blocks(endnote_pages(doc, cfg, part, images, nn)) if part.get("notes") else []
        entries = numbered_entries(source, vocab)
        if entries and entries[0][0] is None:
            warn(f"{label}: note text before the first numbered note added after the chapter text")
            lead = "\n" + "\n".join(entries.pop(0)[1])
        # a note N links to the first unused <sup>N</sup>: on its own page (or the one before) for
        # footnotes, after the previous match for endnotes. OCR'd quote marks that look like
        # superscript numbers then stay plain text instead of shifting every link.
        marks = [(pno, it[2], m.start(), m.end(), note_number(m.group(1)))
                 for pno, its in pages for it in its if it[0] == "line"
                 for m in re.finditer(rf"<sup>({NOTE_NO})</sup>", it[2].html)]
        used, last = {}, -1
        for k, (no, _, epno) in enumerate(entries, 1):
            num = note_number(no)
            free = [i for i, mk in enumerate(marks) if i not in used and mk[4] == num and num is not None]
            if style == "footnotes":
                cand = next((i for i in free if marks[i][0] == epno), None)
                cand = cand if cand is not None else next((i for i in free if marks[i][0] == epno - 1), None)
            else:
                cand = next((i for i in free if i > last), None)
                last = cand if cand is not None else last
            if cand is not None:
                used[cand] = k
        for i in sorted(used, key=lambda i: -marks[i][2]):  # right to left keeps offsets valid
            _, l, a, b, _ = marks[i]
            l.html = l.html[:a] + f"\x00{used[i]}\x00" + l.html[b:]
        text = "\n".join(render(bl, vocab))
        linked_ks = set(used.values())
        notes = [(f"{note_number(no) or no}.", "", "\n".join(paras), k in linked_ks)
                 for k, (no, paras, _) in enumerate(entries, 1)]
        if entries and len(linked_ks) < len(entries):
            warn(f"{label}: {len(entries) - len(linked_ks)} of {len(entries)} notes found no marker; "
                 f"{len(marks) - len(used)} superscripts left as text")
    else:  # none
        text = "\n".join(render(bl, vocab))
        if part.get("notes"):
            notes = [("", "", "\n".join(render(blocks(endnote_pages(doc, cfg, part, images, nn)), vocab)), False)]
    text += lead

    def noteref(m):
        k = int(m.group(1))
        lab = notes[k - 1][0]
        mark = "*" if style == "asterisk" else f"<sup>{lab.rstrip('.')}</sup>"
        return f'<a class="noteref" epub:type="noteref" id="r{k}" href="{nn}-notes.xhtml#n{k}">{mark}</a>'
    text = re.sub(r"\x00(\d+)\x00", noteref, text)
    if not notes:
        return text, None
    asides = []
    for k, (lab, head, body, linked) in enumerate(notes, 1):
        pref = f'<a href="{nn}-text.xhtml#r{k}">{lab}</a>' if linked else lab
        if style == "asterisk":
            asides.append(f'<aside class="note" epub:type="endnote" id="n{k}">'
                          f'<p class="note-head">{pref} {head}</p>\n{body}</aside>')
        else:  # the number goes in front of the first paragraph
            body = re.sub(r"^<p>", f"<p>{pref} " if pref else "<p>", body, count=1)
            asides.append(f'<aside class="note" epub:type="endnote" id="n{k}">{body}</aside>')
    return text, '<section epub:type="endnotes">\n' + "\n".join(asides) + "\n</section>"


def build_vocab(doc, parts) -> set[str]:
    """Hyphenated compounds written mid-line anywhere in the book (a line-end hyphen may be a break)."""
    words = set()
    for p in parts:
        for rng in (p["body"], p.get("notes")):
            for pno in range(rng[0], rng[1] + 1) if rng else ():
                for b in doc[pno - 1].get_text("dict")["blocks"]:
                    for l in b.get("lines", []):
                        t = "".join(s["text"] for s in l["spans"]).rstrip().rstrip("-\u00ad")
                        words |= {w.lower() for w in re.findall(r"[A-Za-z]+-[A-Za-z]+", t)}  # line-end breaks stripped
    return words


# ---------- assemble ----------

def main(bookdir: Path):
    manifest = json.loads((bookdir / "chapters/.parts.json").read_text())
    doc = pymupdf.open(bookdir / manifest["source_pdf"])
    src = bookdir / "companions/src"
    settings = bookdir / "companions/epub-settings.json"
    cfg = DEFAULTS | (json.loads(settings.read_text()) if settings.exists() else {})
    unknown = set(cfg) - set(DEFAULTS)
    assert not unknown, f"unknown settings: {unknown}"
    assert cfg["notes"] in ("asterisk", "numbered", "footnotes", "none"), cfg["notes"]
    fixes_path = bookdir / "companions/epub-fixes.json"
    fixes = json.loads(fixes_path.read_text()) if fixes_path.exists() else []
    parts = manifest["parts"]
    vocab = build_vocab(doc, parts) | {fx["compound"].lower() for fx in fixes if "compound" in fx}
    sups = [fx for fx in fixes if "sup" in fx]
    fixes = [fx for fx in fixes if "compound" not in fx and "sup" not in fx]
    files: dict[str, str] = {}
    images: dict[str, bytes] = {}
    spine, nav = [], []

    for part in parts:
        nn = part["file"][:2]
        mds = sorted(src.glob(f"{nn}-*.md"))
        assert len(mds) == 1, f"part {part['file']}: expected one companion {nn}-*.md, found {mds}"
        label = f"{part['number']} · {part['title']}" if part.get("number") else part["title"]
        print(f"{nn} {label}", file=sys.stderr)

        title, body, sections = companion(mds[0])
        files[f"{nn}-companion.xhtml"] = xhtml(f"Companion: {title}", body)
        text, notes = chapter(doc, cfg, part, vocab, images, nn, label)
        files[f"{nn}-text.xhtml"] = xhtml(part["title"], f"<h1>{html.escape(label)}</h1>\n{text}")
        items = [("Companion", f"{nn}-companion.xhtml", sections), ("Chapter text", f"{nn}-text.xhtml", [])]
        spine += [f"{nn}-companion.xhtml", f"{nn}-text.xhtml"]
        if notes:
            heading = "Endnotes" if cfg["notes"] == "asterisk" else "Notes"
            files[f"{nn}-notes.xhtml"] = xhtml(f"{heading}: {part['title']}",
                                              f"<h1>{heading} to {html.escape(label)}</h1>\n{notes}")
            items.append((heading, f"{nn}-notes.xhtml", []))
            spine.append(f"{nn}-notes.xhtml")
        nav.append((label, items))

    for fx in sups:  # a linked marker sits right after the anchor's '">'
        for name in [n for n in files if n.endswith("-text.xhtml")]:
            files[name] = re.sub(rf'(?<!">)<sup>{re.escape(fx["sup"])}</sup>', fx["replace"], files[name])
    for fx in fixes:
        name = fx["file"]
        assert name in files, f"fix names unknown file {name}"
        count = files[name].count(fx["find"])
        assert count == 1, f"fix for {name} matches {count} times: {fx['find'][:60]!r}"
        files[name] = files[name].replace(fx["find"], fx["replace"])

    for name, content in files.items():
        try:
            ET.fromstring(content.encode())
        except ET.ParseError as e:
            sys.exit(f"{name}: not well-formed XML: {e}\n{content.splitlines()[e.position[0] - 1][:300]}")

    def li(label, href, kids):
        inner = "".join(li(*k) for k in kids)
        return (f'<li><a href="{href}">{html.escape(label)}</a>'
                + (f"<ol>{inner}</ol>" if inner else "") + "</li>")
    toc = "".join(
        li(label, items[0][1], [(t, h, [(sl, f"{h}#{sid}", []) for sid, sl in secs]) for t, h, secs in items])
        for label, items in nav)
    files["nav.xhtml"] = xhtml("Contents", f'<nav epub:type="toc" id="toc"><h1>Contents</h1><ol>{toc}</ol></nav>')

    book_title = f"{manifest['title']} — with reading companions"
    uid = uuid.uuid5(uuid.NAMESPACE_URL, f"reading-companion:{manifest['title']}:{manifest['author']}")
    modified = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    man = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
           '<item id="css" href="style.css" media-type="text/css"/>']
    man += [f'<item id="x{n[:-6]}" href="{n}" media-type="application/xhtml+xml"/>' for n in spine]
    man += [f'<item id="img{i}" href="{n}" media-type="image/png"/>' for i, n in enumerate(images)]
    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid" xml:lang="en">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="uid">urn:uuid:{uid}</dc:identifier>
<dc:title>{html.escape(book_title)}</dc:title>
<dc:creator>{html.escape(manifest['author'])}</dc:creator>
<dc:language>en</dc:language>
<meta property="dcterms:modified">{modified}</meta>
</metadata>
<manifest>
{chr(10).join(man)}
</manifest>
<spine>
{chr(10).join(f'<itemref idref="x{n[:-6]}"/>' for n in spine)}
</spine>
</package>
"""
    container = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>
"""
    out = bookdir / f"{bookdir.name}-companion.epub"
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/style.css", CSS, compress_type=zipfile.ZIP_DEFLATED)
        for name, content in files.items():
            z.writestr(f"OEBPS/{name}", content, compress_type=zipfile.ZIP_DEFLATED)
        for name, data in images.items():
            z.writestr(f"OEBPS/{name}", data, compress_type=zipfile.ZIP_STORED)
    print(out)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]).resolve())
