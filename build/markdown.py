#!/usr/bin/env python3
# Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
"""HTML -> Markdown, and the Markdown dialect -> HTML.

Governed by docs/architecture.md ("Content format", "API Contracts").

Both directions live in one module on purpose. The dialect is CLOSED: the only
Markdown this project renders is the Markdown this project writes. That is what
makes a stdlib-only renderer honest rather than a toy — it does not have to
handle every construct CommonMark allows, only the ones `to_markdown` emits, and
`tests/test_markdown.py` round-trips real papers to prove the two halves agree.
Splitting them into separate modules would let the writer and the reader drift.

THE DIALECT

    ## … ######        section headings; an in-body <h1> demotes to ##
    text {#para76}     a paragraph, with the journal's citation number
    *em*  **strong**   emphasis; `em` carries meaning (work titles), not style
    [text](url)        link
    ![caption](src)    figure; the caption is the alt text (Pandoc's convention)
    > quote            blockquote
    - item             list item
    ---                horizontal rule
    ::: embed          an embedded player the archive cannot host
    url
    :::
    <table>…</table>   raw HTML, passed through: 9 tables in 237 papers, and a
                       pipe-table conversion would lose their colspans

WHY `{#para76}` AND NOT DERIVED NUMBERING

`proofs/markdown-fidelity.py` tried to show the numbers need not be stored, and
failed. They are sequential 1..N, but only 90 of 237 papers number EVERY
paragraph, so the nth paragraph is not paragraph n. These numbers are the
journal's citation unit — "(Rossiter 2003, para. 76)" — so renumbering them
would break citations in other people's published work. They are carried
visibly rather than in a comment or in front matter, because someone reusing
the text needs to SEE which paragraph they are citing. Stripping them is one
regex, provided at the bottom of this module as `strip_paragraph_numbers`.
"""
from __future__ import annotations

import html as htmllib
import re

# The citation apparatus, in both of the journal's markup variants.
LINENO_SPAN = re.compile(r"(?is)<span[^>]*class=['\"]lineno['\"][^>]*>.*?</span>")
PARA_ID = re.compile(r"""(?i)\bid=['"]para(\d+)['"]""")
# `<p>- 76 - As artistic director…` — the number printed in the paragraph's own
# text, with no id anywhere. FCJ-047 does this 39 times.
PARA_INLINE = re.compile(r"^\s*-\s*(\d+)\s*-\s*")
PARA_BLOCK = re.compile(
    r"(?is)<p\b([^>]*)>(.*?)"
    r"(?=</p\s*>|<p\b|<blockquote\b|</blockquote|<h[1-6]\b|<ul\b|<ol\b|<li\b|"
    r"<table\b|<hr\b|</div|\Z)")

# Theme boilerplate that is not part of the article. Every paper ends with the
# permalink notice, and it is the only multi-line <strong> in the corpus, which
# is what made the fidelity probe report emphasis loss.
BOILERPLATE = (
    re.compile(r"(?is)<strong>\s*when commenting on this article.*?</strong>"),
    re.compile(r"(?is)<p[^>]*>\s*when commenting on this article.*?</p>"),
)


# ==========================================================================
# metadata


META = re.compile(
    r"""(?is)<meta[^>]*(?:name|property)=['"]([^'"]+)['"][^>]*content=['"]([^'"]*)['"]""")
META_REV = re.compile(
    r"""(?is)<meta[^>]*content=['"]([^'"]*)['"][^>]*(?:name|property)=['"]([^'"]+)['"]""")


def metadata(doc: str) -> dict[str, list[str]]:
    """Citation metadata from the page head.

    The mirror carries Google Scholar (`citation_*`), Dublin Core (`dc.*`) and
    EPrints tags on 218 of 237 papers — authors, title, publication date,
    journal, ISSN. This is the journal's own structured record of each article,
    so the archive takes authorship from it rather than guessing at a byline in
    the prose. Attribute order varies between eras of the theme, hence the
    second pattern.
    """
    found: dict[str, list[str]] = {}
    for pattern, flip in ((META, False), (META_REV, True)):
        for m in pattern.finditer(doc):
            key, value = (m.group(2), m.group(1)) if flip else (m.group(1), m.group(2))
            key = key.strip().lower()
            value = re.sub(r"\s+", " ", htmllib.unescape(value)).strip()
            if value and value not in found.setdefault(key, []):
                found[key].append(value)
    return found


def authors(doc: str) -> list[str]:
    meta = metadata(doc)
    for key in ("citation_author", "dc.creator", "eprints.creators_name", "author"):
        if meta.get(key):
            return meta[key]
    return []


DOI = re.compile(r"\b(10\.\d{4,9}/[^\s<>\"')\]]+)")


def doi(doc: str, body: str = "") -> str:
    """The article's DOI.

    Academic citation needs it, and the journal printed it in the body as
    `doi:10.15307/fcj.29.218.2017` rather than putting it in a meta tag on most
    papers — so the body is searched as a fallback. It is lifted into front
    matter because a DOI is metadata about the article, not a sentence in it.
    """
    meta = metadata(doc)
    for key in ("citation_doi", "dc.identifier", "eprints.id_number"):
        for value in meta.get(key, []):
            found = DOI.search(value)
            if found:
                return found.group(1).rstrip(".")
    found = DOI.search(body) if body else None
    return found.group(1).rstrip(".") if found else ""


def published(doc: str) -> str:
    meta = metadata(doc)
    for key in ("citation_publication_date", "eprints.datestamp", "dc.date"):
        if meta.get(key):
            return meta[key][0].replace("/", "-")
    return ""


# ==========================================================================
# HTML -> Markdown


def to_markdown(content: str, rewrite_url=lambda u: u) -> str:
    """Convert an extracted content region to the dialect above.

    `rewrite_url` is applied to every link and image target so the caller can
    map mirror URLs onto archive paths without this module knowing anything
    about the archive's layout.
    """
    s = content
    for pattern in BOILERPLATE:
        s = pattern.sub("", s)
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", s)
    s = re.sub(r"(?is)<!--.*?-->", "", s)

    # Tables are set aside WHOLE, before any other pass, and put back at the
    # very end. They are the one construct passed through as HTML, so every
    # later pass would damage them: the embed rule put a `::: embed` fence
    # inside FCJ-101's table, and collapsing whitespace or rewriting links
    # inside raw HTML produces markup that is neither Markdown nor valid HTML.
    tables: list[str] = []
    s = _park_tables(s, tables, rewrite_url)

    s = _figures(s, rewrite_url)
    s = _paragraph_numbers(s)
    s = _embeds(s, rewrite_url)
    s = _inline(s, rewrite_url)
    s = _blocks(s)
    s = _tidy(s)
    for i, table in enumerate(tables):
        s = s.replace(f"\x01TABLE{i}\x01", table)
    return s


TABLE_OPEN = re.compile(r"(?i)<table\b")
TABLE_TAG = re.compile(r"(?i)<(/?)table\b[^>]*>")


def _park_tables(s: str, tables: list[str], rewrite_url) -> str:
    """Hold each table aside as one line of HTML, with its embeds linkified.

    Tables are matched by BALANCING the tags, not with `<table.*?</table>`.
    FCJ-101 nests a table inside a table — a two-column script-and-commentary
    layout — and the non-greedy regex stopped at the inner `</table>`, parking
    a 21,000-character fragment that was missing its own closing tags. That
    produced a malformed table in `content/` and on the page, and it is the
    same mistake as bounding a content region by counting divs.

    Collapsed to a single line because Markdown blocks are separated by blank
    lines: a table containing one would be split, and the renderer — which
    recognises a raw block by its opening `<table` — escaped the remainder and
    printed `td td width 40 tr tbody table` to the reader as prose.
    """
    out: list[str] = []
    pos = 0
    while True:
        start = TABLE_OPEN.search(s, pos)
        if not start:
            out.append(s[pos:])
            break
        out.append(s[pos:start.start()])
        depth = 0
        end = None
        for tag in TABLE_TAG.finditer(s, start.start()):
            depth += -1 if tag.group(1) else 1
            if depth == 0:
                end = tag.end()
                break
        if end is None:                      # unclosed: take the rest
            end = len(s)
        html = re.sub(r"\s+", " ", s[start.start():end])
        html = re.sub(
            r"""(?is)<iframe[^>]*\bsrc=['"]([^'"]+)['"][^>]*>(?:.*?</iframe>)?""",
            lambda i: f'<a href="{rewrite_url(i.group(1)) or i.group(1)}">'
                      f"{i.group(1)}</a>", html)
        tables.append(html)
        out.append(f"\n\n\x01TABLE{len(tables) - 1}\x01\n\n")
        pos = end
    return "".join(out)


def _figures(s: str, rewrite_url) -> str:
    """WordPress caption blocks become `![caption](src)`.

    Markdown has no figure element, but an image alone in a block with alt text
    is Pandoc's figure convention and renders as a real `<figure>` with a
    `<figcaption>`. 72 papers use `class="wp-caption"` with a
    `<p class="wp-caption-text">` caption, which is where figure numbers and
    image credits live — academic apparatus, not decoration.
    """
    def one(m: re.Match[str]) -> str:
        inner = m.group(0)
        src = re.search(r"""(?i)<img[^>]*\bsrc=['"]([^'"]+)['"]""", inner)
        cap = re.search(
            r"""(?is)class=['"][^'"]*wp-caption-text[^'"]*['"][^>]*>(.*?)</p>""", inner)
        if not src:
            return ""
        target = rewrite_url(src.group(1))
        text = _plain(cap.group(1)) if cap else ""
        # An image the archive does not hold: keep the caption as prose rather
        # than emit `![caption]()`, which renders as a broken image and loses
        # the credit line that the caption usually carries.
        if not target:
            return f"\n\n{text}\n\n" if text else ""
        return f"\n\n![{text}]({target})\n\n"

    return re.sub(
        r"""(?is)<(div|figure)[^>]*class=['"][^'"]*wp-caption[^'"]*['"][^>]*>.*?</\1>""",
        one, s)


def _paragraph_numbers(s: str) -> str:
    """Move each paragraph's citation number to a `{#paraN}` suffix.

    The number is taken from `id="paraN"` where the theme put one, and otherwise
    from a `- N -` prefix inside the paragraph's own text. Both are the same
    apparatus; only the markup differs. The floating `lineno` span that printed
    the number is dropped, because the renderer draws the margin rail itself.
    """
    s = LINENO_SPAN.sub("", s)

    def one(m: re.Match[str]) -> str:
        attrs, body = m.group(1), m.group(2)
        ident = PARA_ID.search(attrs)
        number = ident.group(1) if ident else None
        if number is None:
            inline = PARA_INLINE.match(_plain(body)[:24])
            if inline:
                number = inline.group(1)
                body = re.sub(r"-\s*%s\s*-\s*" % re.escape(number), "", body, count=1)
        suffix = f" {{#para{number}}}" if number else ""
        return f"<p>{body}{suffix}</p>"

    # Terminate on the next block element, not only on `</p>`. The mirror
    # leaves paragraphs unclosed, and a `<p ...>(.*?)</p>` match then runs from
    # one paragraph's opening tag to the NEXT paragraph's closing tag, keeping
    # the first one's attributes and throwing the second one's id away. That
    # silently lost five citation numbers in FCJ-047 alone. Any `</p>` left
    # over becomes a paragraph break in `_blocks`, which is harmless.
    return PARA_BLOCK.sub(one, s)


def _embeds(s: str, rewrite_url) -> str:
    """An embedded player becomes an explicit fenced block.

    19 iframes across 237 papers. A static archive cannot host an iframe at
    all, so rather than drop it and leave a reader wondering what is missing,
    the archive records that something was embedded and where it pointed.
    """
    def embed(m: re.Match[str]) -> str:
        src = re.search(r"""(?i)\bsrc=['"]([^'"]+)['"]""", m.group(0))
        target = (rewrite_url(src.group(1)) or src.group(1)) if src else "unknown"
        return f"\n\n::: embed\n{target}\n:::\n\n"

    s = re.sub(r"(?is)<iframe[^>]*>.*?</iframe>", embed, s)
    s = re.sub(r"(?is)<iframe[^>]*/?>", embed, s)
    return s


def _inline(s: str, rewrite_url) -> str:
    # Whitespace INSIDE the tag has to move OUTSIDE the markers. The mirror
    # writes `<em>Uzume </em>(2002)`, and squeezing the inner text without
    # putting that space back produces `*Uzume*(2002)` — which renders as
    # "Uzume(2002)" and runs words together across 1,153 places in the corpus.
    def emphasis(m: re.Match[str], marker: str) -> str:
        inner = m.group(2)
        text = _squeeze(inner)
        if not text:
            return " " if inner else ""
        lead = " " if inner[:1].isspace() else ""
        trail = " " if inner[-1:].isspace() else ""
        return f"{lead}{marker}{text}{marker}{trail}"

    s = re.sub(r"(?is)<(em|i|cite)\b[^>]*>(.*?)</\1>", lambda m: emphasis(m, "*"), s)
    s = re.sub(r"(?is)<(strong|b)\b[^>]*>(.*?)</\1>", lambda m: emphasis(m, "**"), s)
    s = re.sub(r"(?is)</?(sup|sub)\b[^>]*>", "", s)

    def image(m: re.Match[str]) -> str:
        tag = m.group(0)
        src = re.search(r"""(?i)\bsrc=['"]([^'"]+)['"]""", tag)
        alt = re.search(r"""(?i)\balt=['"]([^'"]*)['"]""", tag)
        if not src:
            return ""
        target = rewrite_url(src.group(1))
        if not target:
            return ""        # not held by the archive; see _figures
        return f"![{_plain(alt.group(1)) if alt else ''}]({target})"

    s = re.sub(r"(?is)<img\b[^>]*/?>", image, s)

    def link(m: re.Match[str]) -> str:
        raw, text = m.group(1).strip(), _squeeze(m.group(2))
        if not text:
            return ""
        # A link to a fragment on the same page is the mirror's footnote
        # machinery: `<a href="#1">[1]</a>` pointing at an `<a name="1">`
        # target. Both ends are dropped and `render` rebuilds the linking from
        # the Notes section's structure, which survives editing of the Markdown
        # and does not leave `[[1]](#1)` in text people are meant to reuse.
        if raw.startswith("#"):
            return text
        href = rewrite_url(raw)
        return f"[{text}]({href})" if href else text

    s = re.sub(r"""(?is)<a\b[^>]*\bhref=['"]([^'"]*)['"][^>]*>(.*?)</a>""", link, s)
    # `<a name="7">` footnote targets: the text survives, the anchor does not.
    # render() rebuilds the linking from the Notes section's own structure.
    s = re.sub(r"(?is)<a\b[^>]*>(.*?)</a>", lambda m: m.group(1), s)
    return s


def _blocks(s: str) -> str:
    for level in range(6, 0, -1):
        s = re.sub(rf"(?is)<h{level}\b[^>]*>(.*?)</h{level}>",
                   lambda m, lv=level: f"\n\n{'#' * min(lv + 1, 6)} {_squeeze(m.group(1))}\n\n",
                   s)
    s = re.sub(r"(?is)<blockquote\b[^>]*>(.*?)</blockquote>",
               lambda m: "\n\n" + _quote(m.group(1)) + "\n\n", s)
    s = re.sub(r"(?is)<li\b[^>]*>(.*?)</li>", lambda m: f"\n- {_squeeze(m.group(1))}", s)
    s = re.sub(r"(?is)</?(ul|ol|dl)\b[^>]*>", "\n\n", s)
    s = re.sub(r"(?is)<hr\b[^>]*/?>", "\n\n---\n\n", s)
    s = re.sub(r"(?is)<br\s*/?>", "\n", s)
    s = re.sub(r"(?is)</p\s*>", "\n\n", s)
    s = re.sub(r"(?is)<p\b[^>]*>", "\n\n", s)
    return s


def _quote(fragment: str) -> str:
    """Prefix a quotation's lines with `> `, keeping its paragraph breaks.

    The breaks matter: a blockquote in this journal often holds several
    numbered paragraphs, and collapsing them into one run would put each
    paragraph's `{#paraN}` marker in the middle of the text instead of at the
    end of its own paragraph, where the renderer looks for it.
    """
    text = re.sub(r"(?s)<[^>]+>", "", _blocks(fragment))
    paragraphs = [re.sub(r"\s+", " ", p).strip()
                  for p in re.split(r"\n\s*\n", htmllib.unescape(text))]
    return "\n>\n".join(f"> {p}" for p in paragraphs if p).strip()


# Markup the AUTHOR quoted, surfacing only after unescaping. Every real tag has
# been stripped by this point and tables are parked, so anything tag-shaped
# left in the text was written as text — `&lt;annotation&gt;` in FCJ-127's
# discussion of XML, `&lt;think&rsquo;…&gt;` in FCJ-135. It becomes a code
# span, which is what it always was, and which stops another Markdown tool
# reading it as HTML.
LEFTOVER_TAG = re.compile(r"<(/?[A-Za-z][^<>]{0,80}?)>")


def _tidy(s: str) -> str:
    s = re.sub(r"(?s)<[^>]+>", "", s)
    s = htmllib.unescape(s)
    s = LEFTOVER_TAG.sub(lambda m: f"`<{m.group(1)}>`", s)
    s = re.sub(r"[ \t]+", " ", s)
    # Every image becomes its own block, so the renderer can make it a <figure>
    # with a real <figcaption>. An image left inside a paragraph can only carry
    # its caption as alt text, which no reader sees: 69 of the archive's 390
    # figures lost their caption — and the credit line in it — that way.
    # Promotion is right for this corpus because its images are all figures;
    # there are no inline icons in the prose.
    s = re.sub(r"(!\[[^\]]*\]\([^)\s]*\))", r"\n\n\1\n\n", s)
    s = re.sub(r" *\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip() + "\n"


def _plain(fragment: str) -> str:
    return _squeeze(re.sub(r"(?s)<[^>]+>", "", fragment))


def _squeeze(text: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(text)).strip()


# ==========================================================================
# Markdown -> HTML


H = re.compile(r"^(#{2,6})\s+(.*)$")
PARA_SUFFIX = re.compile(r"\s*\{#para(\d+)\}\s*$")
FIG = re.compile(r"^!\[(.*)\]\((.*)\)$")
NOTE_START = re.compile(r"^\[(\d+)\]\s*")
IMG_INLINE = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")
LINK_INLINE = re.compile(r"\[([^\]]+)\]\(([^)]*)\)")
STRONG = re.compile(r"\*\*(.+?)\*\*", re.S)
EM = re.compile(r"(?<!\*)\*(?!\*)([^*]+?)\*(?!\*)", re.S)
NOTE_REF = re.compile(r"(?<![\w\]])\[(\d{1,3})\](?!\()")
TABLE_BLOCK = re.compile(r"(?i)^\s*<table\b")

NOTES_HEADING = re.compile(r"(?i)^(notes?|endnotes?|footnotes?)\b")
REFS_HEADING = re.compile(r"(?i)^(references?|bibliography|works cited|"
                          r"select bibliography|reference list)\b")


def render(md: str, *, figure_prefix: str = "Figure") -> str:
    """Render the dialect to academically presentable HTML.

    Three things this does that a generic Markdown renderer would not, and that
    the brief asks for:

      - the paragraph number becomes a clickable margin rail and the
        paragraph's own id, restoring citation-by-paragraph;
      - an image alone in a block becomes `<figure>` with a `<figcaption>`,
        numbered where the caption does not already carry its own label;
      - a bare `[7]` in the prose is linked to the matching entry under Notes,
        and the note gets a back-link. The mirror did this with `<a name="7">`
        anchors; the archive rebuilds it from structure instead, which is why
        dropping 1,905 named anchors costs nothing.
    """
    out: list[str] = []
    figure_n = 0
    section = ""
    has_notes = bool(re.search(r"(?mi)^#{2,6}\s+(notes?|endnotes?|footnotes?)\b", md))

    for block in _split_blocks(md):
        if TABLE_BLOCK.match(block):
            out.append(block)
            continue
        if block.startswith("::: embed"):
            lines = block.split("\n")
            url = lines[1].strip() if len(lines) > 1 else ""
            out.append('<aside class="embed"><p>Embedded media, not hosted by this '
                       f'archive: <a href="{_attr(url)}">{_text(url)}</a></p></aside>')
            continue
        if block == "---":
            out.append("<hr>")
            continue

        heading = H.match(block)
        if heading:
            level, text = len(heading.group(1)), heading.group(2)
            section = ("notes" if NOTES_HEADING.match(text) else
                       "references" if REFS_HEADING.match(text) else "")
            slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "section"
            out.append(f'<h{level} id="{_attr(slug)}">'
                       f"{_inline_html(text, has_notes)}</h{level}>")
            continue

        if any(ln.strip().startswith("- ") for ln in block.split("\n")):
            # A block can MIX list items and plain lines, because the mirror
            # puts a <ul> straight after a paragraph with no blank line
            # between. Keeping only the `- ` lines silently dropped the rest —
            # 141 words of reference list in FCJ-160, and the same in eight
            # other papers. So the block is walked line by line and each run is
            # emitted in order.
            cls = ' class="reflist"' if section == "references" else ""
            items: list[str] = []
            for line in block.split("\n"):
                stripped = line.strip()
                if stripped.startswith("- "):
                    items.append(stripped[2:].strip())
                elif stripped:
                    if items:
                        out.append(f"<ul{cls}>" + "".join(
                            f"<li>{_inline_html(i, has_notes)}</li>"
                            for i in items) + "</ul>")
                        items = []
                    attrs = ' class="refpara"' if section == "references" else ""
                    out.append(f"<p{attrs}>{_inline_html(stripped, has_notes)}</p>")
            if items:
                out.append(f"<ul{cls}>" + "".join(
                    f"<li>{_inline_html(i, has_notes)}</li>" for i in items) + "</ul>")
            continue

        if block.startswith(">"):
            inner = "\n".join(ln.lstrip(">").strip() for ln in block.split("\n"))
            paras = [p for p in re.split(r"\n\s*\n", inner) if p.strip()]
            # Quoted paragraphs carry citation numbers too — a block quotation
            # is a numbered paragraph in this journal, and 1,514 of them are
            # inside quotes. Handling them only in the plain-paragraph branch
            # printed the raw `{#para15}` marker to the reader.
            rendered = []
            for para in paras:
                suffix = PARA_SUFFIX.search(para)
                attrs = rail = ""
                if suffix:
                    n = suffix.group(1)
                    para = para[:suffix.start()]
                    attrs = f' id="para{_attr(n)}"'
                    rail = (f'<a class="rail" href="#para{_attr(n)}" '
                            f'aria-label="paragraph {_text(n)}">{_text(n)}</a>')
                rendered.append(f"<p{attrs}>{rail}{_inline_html(para, has_notes)}</p>")
            out.append("<blockquote>" + "".join(rendered) + "</blockquote>")
            continue

        fig = FIG.match(block)
        if fig:
            caption, src = fig.group(1).strip(), fig.group(2).strip()
            figure_n += 1
            label = ""
            if caption and not re.match(
                    r"(?i)^\s*(figure|fig\.?|table|image|img\.?|plate)\s*\d", caption):
                label = f"{figure_prefix} {figure_n}. "
            cap = (f"<figcaption>{label}{_inline_html(caption, has_notes)}</figcaption>"
                   if caption else "")
            out.append(f'<figure><img src="{_attr(src)}" alt="{_attr(caption)}" '
                       f'loading="lazy">{cap}</figure>')
            continue

        number = None
        suffix = PARA_SUFFIX.search(block)
        if suffix:
            number = suffix.group(1)
            block = block[:suffix.start()]
        note = NOTE_START.match(block) if section == "notes" else None
        attrs = rail = ""
        if note:
            n = note.group(1)
            attrs = f' id="note-{_attr(n)}" class="note"'
            block = block[note.end():]
            rail = f'<a class="notenum" href="#noteref-{_attr(n)}">{_text(n)}</a>'
        elif number:
            attrs = f' id="para{_attr(number)}"'
            rail = (f'<a class="rail" href="#para{_attr(number)}" '
                    f'aria-label="paragraph {_text(number)}">{_text(number)}</a>')
        elif section == "references":
            attrs = ' class="refpara"'
        out.append(f"<p{attrs}>{rail}{_inline_html(block, has_notes)}</p>")

    return "\n".join(out)


def _split_blocks(md: str) -> list[str]:
    blocks: list[str] = []
    for raw in re.split(r"\n\s*\n", md):
        block = raw.strip("\n").rstrip()
        if block:
            blocks.append(block)
    return blocks


CODE_SPAN = re.compile(r"`([^`\n]+)`")


def _inline_html(text: str, has_notes: bool) -> str:
    # Code spans are pulled out first and put back last, so that markup an
    # author quoted inside one is never re-read as emphasis or as a link.
    spans: list[str] = []

    def park(m: re.Match[str]) -> str:
        spans.append(m.group(1))
        return f"\x00{len(spans) - 1}\x00"

    text = CODE_SPAN.sub(park, text)
    s = _text(text)
    s = IMG_INLINE.sub(
        lambda m: f'<img src="{_attr(m.group(2))}" alt="{_attr(m.group(1))}" '
                  f'loading="lazy">', s)
    s = LINK_INLINE.sub(lambda m: f'<a href="{_attr(m.group(2))}">{m.group(1)}</a>', s)
    s = STRONG.sub(lambda m: f"<strong>{m.group(1)}</strong>", s)
    s = EM.sub(lambda m: f"<em>{m.group(1)}</em>", s)
    if has_notes:
        s = NOTE_REF.sub(
            lambda m: f'<sup class="noteref" id="noteref-{m.group(1)}">'
                      f'<a href="#note-{m.group(1)}">{m.group(1)}</a></sup>', s)
    s = re.sub(r"\x00(\d+)\x00",
               lambda m: f"<code>{_text(spans[int(m.group(1))])}</code>", s)
    return s.replace("\n", " ")


def _text(s: str) -> str:
    return htmllib.escape(s, quote=False)


def _attr(s: str) -> str:
    return htmllib.escape(s, quote=True)


def strip_paragraph_numbers(md: str) -> str:
    """The one regex a reuser needs, provided so nobody has to guess it."""
    return re.sub(r"\s*\{#para\d+\}", "", md)
