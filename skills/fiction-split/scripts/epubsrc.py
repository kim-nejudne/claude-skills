"""Read a source EPUB: metadata, spine, nav, and the slices that make up each unit.

Shared by fiction-split (probe.py, split.py) and fiction-epub (epub.py, check.py).

    uv run --quiet --with lxml python -I epubsrc.py --selftest

Paths are relative to the OPF's folder, as nav hrefs are (e.g. "text/chapter-1.xhtml").
A unit's "src" is a list of {"file", "from", "to"}: "from" and "to" are element ids (null = the
start or end of the file's body). A slice runs from the "from" element up to, not including, the
"to" element, in document order, and keeps the ancestors that hold it (so wrappers stay).
"""
import copy
import posixpath
import re
import sys
import zipfile
from urllib.parse import unquote

from lxml import etree

X = "http://www.w3.org/1999/xhtml"
OPS = "http://www.idpf.org/2007/ops"
OPF = "http://www.idpf.org/2007/opf"
DC = "http://purl.org/dc/elements/1.1/"
NCX = "http://www.daisy.org/z3986/2005/ncx/"
EPUB_TYPE = f"{{{OPS}}}type"
BLOCKS = {f"{{{X}}}{t}" for t in ("p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "dt", "dd", "td", "th",
                                    "div", "blockquote", "pre", "figcaption", "caption", "header", "footer",
                                    "section", "article", "aside", "hgroup", "table", "tr", "ol", "ul", "dl")}
PARSER = etree.XMLParser(recover=True, resolve_entities=False, no_network=True, huge_tree=True)
WORD = re.compile(r"[^\W_]+(?:[’'][^\W_]+)*")


def words(s: str) -> list[str]:
    return WORD.findall(s)


def etypes(el) -> set[str]:
    return set((el.get(EPUB_TYPE) or "").split())


def skipped(el) -> bool:
    """Noterefs and page-break markers: not part of the running text."""
    t = etypes(el)
    return bool(t & {"noteref", "pagebreak"}) or el.get("role") in ("doc-noteref", "doc-pagebreak")


class Source:
    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        cont = etree.fromstring(self.z.read("META-INF/container.xml"), PARSER)
        self.opf_path = cont.find(".//{*}rootfile").get("full-path")
        self.base = posixpath.dirname(self.opf_path)
        opf = etree.fromstring(self.z.read(self.opf_path), PARSER)
        self.items = {}  # id -> (href, media type, properties)
        for it in opf.iterfind(f".//{{{OPF}}}manifest/{{{OPF}}}item"):
            self.items[it.get("id")] = (unquote(it.get("href")), it.get("media-type"), it.get("properties") or "")
        self.spine = [self.items[r.get("idref")][0] for r in opf.iterfind(f".//{{{OPF}}}spine/{{{OPF}}}itemref")
                      if r.get("idref") in self.items]
        md = opf.find(f".//{{{OPF}}}metadata")
        self.title = (md.findtext(f"{{{DC}}}title") or "").strip()
        self.author = (md.findtext(f"{{{DC}}}creator") or "").strip()
        self.lang = (md.findtext(f"{{{DC}}}language") or "en").strip()
        self.nav_href = next((h for h, _, p in self.items.values() if "nav" in p.split()), None)
        self.ncx_href = next((h for h, m, _ in self.items.values() if m == "application/x-dtbncx+xml"), None)
        self._docs = {}

    def read(self, href: str) -> bytes:
        return self.z.read(posixpath.normpath(posixpath.join(self.base, href)))

    def exists(self, href: str) -> bool:
        try:
            self.z.getinfo(posixpath.normpath(posixpath.join(self.base, href)))
            return True
        except KeyError:
            return False

    def doc(self, href: str):
        if href not in self._docs:
            self._docs[href] = etree.fromstring(self.read(href), PARSER)
        return self._docs[href]

    def body(self, href: str):
        return self.doc(href).find(f"{{{X}}}body")

    def resolve(self, from_href: str, link: str) -> tuple[str, str | None]:
        """A link inside from_href -> (file href relative to the OPF folder, fragment or None)."""
        path, _, frag = unquote(link).partition("#")
        target = posixpath.normpath(posixpath.join(posixpath.dirname(from_href), path)) if path else from_href
        return target, frag or None

    def by_id(self, href: str, ident: str):
        found = self.doc(href).xpath("//*[@id=$i]", i=ident)
        return found[0] if found else None

    def nav(self) -> list[tuple[int, str, str]]:
        """(depth, label, href[#frag]) of the table of contents, hrefs relative to the OPF folder."""
        out = []
        if self.nav_href:
            root = self.doc(self.nav_href)
            navs = [n for n in root.iter(f"{{{X}}}nav") if "toc" in etypes(n)] or list(root.iter(f"{{{X}}}nav"))
            if navs:
                def walk(ol, depth):
                    for li in ol.iterchildren(f"{{{X}}}li"):
                        a = li.find(f"{{{X}}}a")
                        a = a if a is not None else li.find(f"{{{X}}}span")  # lxml elements without children are falsy
                        label = " ".join("".join(a.itertext()).split()) if a is not None else ""
                        href = a.get("href") if a is not None else None
                        if href:
                            f, frag = self.resolve(self.nav_href, href)
                            href = f + (f"#{frag}" if frag else "")
                        out.append((depth, label, href or ""))
                        sub = li.find(f"{{{X}}}ol")
                        if sub is not None:
                            walk(sub, depth + 1)
                ol = navs[0].find(f".//{{{X}}}ol")
                if ol is not None:
                    walk(ol, 0)
                return out
        if self.ncx_href:
            root = self.doc(self.ncx_href)

            def walk_ncx(parent, depth):
                for np in parent.iterchildren(f"{{{NCX}}}navPoint"):
                    label = " ".join("".join(np.find(f"{{{NCX}}}navLabel").itertext()).split())
                    f, frag = self.resolve(self.ncx_href, np.find(f"{{{NCX}}}content").get("src"))
                    out.append((depth, label, f + (f"#{frag}" if frag else "")))
                    walk_ncx(np, depth + 1)
            walk_ncx(root.find(f"{{{NCX}}}navMap"), 0)
        return out

    def slice(self, src: dict):
        """A pruned copy of the file's <body> holding only the from..to range. -> body element copy."""
        body = self.body(src["file"])
        if body is None:
            raise ValueError(f"{src['file']}: no <body>")
        order = {el: i for i, el in enumerate(body.iter())}
        n = len(order)

        def pos(ident, default):
            if not ident:
                return default
            el = self.by_id(src["file"], ident)
            if el is None or el not in order:
                raise ValueError(f"{src['file']}: no element with id {ident!r}")
            return order[el]
        start, end = pos(src.get("from"), 0), pos(src.get("to"), n)
        if start >= end:
            raise ValueError(f"{src['file']}: 'from' {src.get('from')!r} is not before 'to' {src.get('to')!r}")
        if start == 0 and end == n:
            return copy.deepcopy(body)
        last = {}  # element -> order index of its last descendant
        for el in reversed(list(body.iter())):
            kids = [c for c in el if c in order]
            last[el] = last[kids[-1]] if kids else order[el]
        cut = copy.deepcopy(body)
        twin = dict(zip(body.iter(), cut.iter()))
        for el in list(body.iter()):
            if el is body:
                continue
            a, b = order[el], last[el]
            c = twin[el]
            if c.getparent() is None:
                continue  # already removed with an ancestor
            if b < start or a >= end:
                c.tail = None  # text after a removed block is outside the range too
                c.getparent().remove(c)
            elif a < start:  # an ancestor of the start: drop its text before the start
                c.text = None
            if a < end <= b:  # an ancestor of the end: its tail falls after the range
                c.tail = None
        return cut

    def unit_bodies(self, unit: dict) -> list:
        return [self.slice(s) for s in unit["src"]]


def text(body) -> str:
    """Plain text of a body copy: one paragraph per innermost block, blank-line separated."""
    paras = []

    def inline(el) -> str:
        parts = [el.text or ""] if not skipped(el) else []
        for c in el:
            if not skipped(c):
                parts.append(inline(c))
            parts.append(c.tail or "")
        return "".join(parts)

    def walk(el):
        if not isinstance(el.tag, str):
            return
        has_block = any(c.tag in BLOCKS for c in el if isinstance(c.tag, str))
        if el.tag in BLOCKS and not has_block:
            t = " ".join(inline(el).split())
            if t:
                paras.append(t)
            return
        loose = " ".join((el.text or "").split())  # text sitting directly in a block wrapper
        if loose and not skipped(el):
            paras.append(loose)
        for c in el:
            if skipped(c):
                continue
            if c.tag in BLOCKS:
                walk(c)
            elif isinstance(c.tag, str):
                t = " ".join(inline(c).split())
                if t:
                    paras.append(t)
            t = " ".join((c.tail or "").split())
            if t:
                paras.append(t)
    walk(body)
    return "\n\n".join(paras)


def make_epub(path, files: dict[str, str], assets: dict[str, bytes] | None = None):
    """A minimal source EPUB for tests: files are spine XHTML bodies, assets other files (OPS/...)."""
    opf = ['<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
           '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>T</dc:title>'
           '<dc:creator>A</dc:creator></metadata><manifest>']
    opf += [f'<item id="i{k}" href="{n}" media-type="application/xhtml+xml"/>' for k, n in enumerate(files)]
    opf += ["</manifest><spine>"] + [f'<itemref idref="i{k}"/>' for k in range(len(files))] + ["</spine></package>"]
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("META-INF/container.xml", '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                   '<rootfiles><rootfile full-path="OPS/c.opf"/></rootfiles></container>')
        z.writestr("OPS/c.opf", "".join(opf))
        for n, body in files.items():
            z.writestr(f"OPS/{n}", f'<html xmlns="http://www.w3.org/1999/xhtml" '
                       f'xmlns:epub="http://www.idpf.org/2007/ops"><body>{body}</body></html>')
        for n, data in (assets or {}).items():
            z.writestr(f"OPS/{n}", data)


def selftest():
    import tempfile
    from pathlib import Path
    make = make_epub

    with tempfile.TemporaryDirectory() as d:
        # three chapters in one file, flat and inside a wrapper section, with a noteref and a pagebreak
        p = Path(d) / "multi.epub"
        make(p, {"t/all.xhtml": '<section><h2 id="c1">One</h2><p>alpha beta<a epub:type="noteref" href="n.xhtml#n1">1</a></p>'
                 '<h2 id="c2">Two</h2><p>gamma <span epub:type="pagebreak" id="pg5" title="5"/>delta</p>'
                 '<h2 id="c3">Three</h2><p>epsilon</p></section>',
                 "t/n.xhtml": '<ol><li id="n1"><p>note text</p></li></ol>'})
        s = Source(p)
        assert s.spine == ["t/all.xhtml", "t/n.xhtml"], s.spine
        one = text(s.slice({"file": "t/all.xhtml", "from": None, "to": "c2"}))
        two = text(s.slice({"file": "t/all.xhtml", "from": "c2", "to": "c3"}))
        three = text(s.slice({"file": "t/all.xhtml", "from": "c3", "to": None}))
        assert one == "One\n\nalpha beta", one
        assert two == "Two\n\ngamma delta", two
        assert three == "Three\n\nepsilon", three
        whole = words(text(s.slice({"file": "t/all.xhtml", "from": None, "to": None})))
        assert whole == words(one) + words(two) + words(three)
        assert s.slice({"file": "t/all.xhtml", "from": "c2", "to": "c3"}).find(f".//{{{X}}}section") is not None
        assert s.resolve("t/all.xhtml", "n.xhtml#n1") == ("t/n.xhtml", "n1")
        # one chapter split over two files
        p2 = Path(d) / "split.epub"
        make(p2, {"a.xhtml": "<h1>Chapter</h1><p>first half</p>", "b.xhtml": "<p>second half</p>"})
        s2 = Source(p2)
        unit = {"src": [{"file": "a.xhtml", "from": None, "to": None}, {"file": "b.xhtml", "from": None, "to": None}]}
        assert "\n\n".join(text(b) for b in s2.unit_bodies(unit)) == "Chapter\n\nfirst half\n\nsecond half"
        try:
            s.slice({"file": "t/all.xhtml", "from": "c3", "to": "c2"})
            raise AssertionError("reversed range accepted")
        except ValueError:
            pass
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        selftest()
    else:
        sys.exit(__doc__)
