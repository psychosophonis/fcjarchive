#!/usr/bin/env python3
# Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
"""Render `site/` from `content/`.

Governed by docs/architecture.md ("Output layout").

This stage reads ONLY `content/` and `assets/`. It never touches the mirror.
That boundary is the separation of form from content: the text people download
from the repository is the exact text the site renders, so the two cannot
disagree, and restyling the journal cannot damage a single word of it.

It is also why design iteration is cheap. `extract.py` takes seconds and runs
once; this runs in about a second over 268 pages, so the loop is edit
`assets/style.css`, re-run, reload.
"""
from __future__ import annotations

import html as htmllib
import os
import re
import shutil
from dataclasses import dataclass, field

import extract
import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content")
ASSETS = os.path.join(ROOT, "assets")
SITE = os.path.join(ROOT, "site")

def _issue_sort(number: str) -> tuple[int, int]:
    """Numeric order, with `mesh` last. Mesh is a standing section, not an
    issue number, so it cannot sort among them."""
    return (1, 0) if not number.isdigit() else (0, int(number))


def issue_order(issues) -> list[str]:
    """The issue order, derived from `content/` alone.

    This used to import `inventory.ISSUE_HOSTS`, which made the render stage
    depend on a tool that exists to read the mirror. Each tool has to stand on
    its own, so the order comes from the files actually present.
    """
    return sorted(issues, key=_issue_sort)

# The host the archive will be served from. It appears in citation metadata and
# in the sitemap, both of which require absolute URLs, so it cannot be inferred
# from the output. Change it here if the archive moves.
CANONICAL_HOST = "fibreculturejournal.org"

# Where the Markdown archive lives, for the link in the footer. While empty the
# footer omits the link rather than publishing a dead one, and the build says so
# on every run. Set once the public repository existed, 2026-11-27.
ARCHIVE_REPO = "https://github.com/psychosophonis/fcjarchive"


@dataclass
class Report:
    pages: int = 0
    media: int = 0
    media_bytes: int = 0
    linked: int = 0
    hardlinked: int = 0
    missing_media: list[str] = field(default_factory=list)
    pruned: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# loading content


@dataclass
class Doc:
    meta: dict
    body: str
    path: str


def load(kind: str) -> dict[str, Doc]:
    out: dict[str, Doc] = {}
    directory = os.path.join(CONTENT, kind)
    if not os.path.isdir(directory):
        return out
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(directory, name)
        with open(path, encoding="utf-8") as fh:
            meta, body = extract.parse_front_matter(fh.read())
        out[name[:-3]] = Doc(meta, body, path)
    return out


# `content/` stores links RELATIVE to the file that uses them, so the Markdown
# works in a GitHub file view, in an editor, and in a bare clone. The website
# needs root-relative URLs with the output's own path shapes, and the renderer
# is the only thing that knows those — so the translation lives here.
REL_MEDIA = re.compile(r"\]\((?:\.\./)+(media/[^)]*)\)")
REL_ISSUE = re.compile(r"\]\((?:\.\./)*issues/([^)/]+?)\.md(#[^)]*)?\)")
# The `papers/` segment is REQUIRED, not optional: without it this also
# matched `19.md` and sent an issue link to `/papers/19/`.
REL_PAPER = re.compile(r"\]\((?:\.\./)*papers/([^)/#]+?)\.md(#[^)]*)?\)")
# Institutional pages publish at the site root, `/about/` not `/pages/about/`,
# so this rule drops the directory rather than keeping it. The `pages/` segment
# is still required on the content side, for the same reason as `papers/`.
REL_PAGE = re.compile(r"\]\((?:\.\./)*pages/([^)/#]+?)\.md(#[^)]*)?\)")
# The same two conventions, but inside RAW HTML. This dialect passes some HTML
# through untouched — tables, and a few early papers' `<img>` tags — so a
# content-relative `src="../media/…"` can reach the renderer in an attribute
# rather than a Markdown link target. Relative to the Markdown file it is
# correct; served from `/papers/<slug>/` it resolves one directory too high.
REL_ATTR = re.compile(r'\b(src|href)="(?:\.\./)+(media/[^"]*)"')


def site_links(body: str) -> str:
    """Relative file links -> site URLs. The inverse of what extract writes."""
    body = REL_MEDIA.sub(lambda m: f"](/{m.group(1)})", body)
    body = REL_ATTR.sub(lambda m: f'{m.group(1)}="/{m.group(2)}"', body)
    body = REL_ISSUE.sub(lambda m: f"](/issues/{m.group(1)}/{m.group(2) or ''})", body)
    body = REL_PAGE.sub(lambda m: f"](/{m.group(1)}/{m.group(2) or ''})", body)
    return REL_PAPER.sub(lambda m: f"](/papers/{m.group(1)}/{m.group(2) or ''})", body)


def as_list(value) -> list[str]:
    if not value:
        return []
    return value if isinstance(value, list) else [value]


# --------------------------------------------------------------------------
# templates


def issue_label(number: str) -> str:
    return "Mesh" if number == "mesh" else f"Issue {number}"


# `The Fibreculture Journal`, `… : 29`, `… : Mesh` — a root title that names the
# site and nothing else. Mesh is a standing section rather than a themed issue,
# so it genuinely has no theme and showing the site's name back at the reader
# would be worse than showing none.
SITE_NAME = re.compile(
    r"(?i)^\s*(the\s+)?fibreculture\s+journal\s*:?\s*(\d+|mesh)?\s*$")
NUMBER_PREFIX = re.compile(
    r"(?i)^\s*(the\s+)?(fibreculture\s+journal|fcj)?\s*:?\s*"
    r"(issue)?\s*\d{1,2}\s*[-–—:|]*\s*")


def clean_theme(number: str, meta: dict, papers: dict) -> str:
    """The issue's theme, without the number the page template already prints.

    The mirror writes it three ways — `Issue 08 – Gaming Networks`,
    `Issue 21: Exploring affect…`, `FCJ 28: Creative Robotics` — so the number
    is stripped however it is spelled rather than assuming one separator.

    Two issues have no theme in their root `<title>` at all: issue 29's reads
    `The Fibreculture Journal : 29`, and mesh's is the site name. For those the
    theme is in the issue's own intro paper — FCJ-212 is titled `Issue 29 :
    Computing The City` — so that is used instead of printing the site's name
    back at the reader.
    """
    theme = str(meta.get("theme", "")).strip()
    if not theme or SITE_NAME.match(theme):
        for ident in as_list(meta.get("papers")):
            entry = papers.get(ident)
            title = str(entry[1].meta.get("title", "")) if entry else ""
            if re.match(rf"(?i)^\s*(issue)?\s*{re.escape(number)}\b", title):
                theme = title
                break
    cleaned = NUMBER_PREFIX.sub("", theme).strip(" :–—-")
    return cleaned or ""


def issue_nav(current: str | None, issues: dict[str, Doc],
              themes: dict[str, str]) -> str:
    """The issue index, on every page.

    A reader of a journal archive navigates by issue, so the index is
    permanent rather than something you go back to the front page for. `mesh`
    is shown by name because it has no number.
    """
    links = []
    for number in issue_order(issues):
        label = "mesh" if number == "mesh" else number
        current_attr = ' aria-current="page"' if number == current else ""
        theme = themes.get(number, "")
        # The theme travels INSIDE the link as a span, not in a `title`
        # attribute. A title tooltip is slow, unstyleable, and invisible to a
        # keyboard or a touch screen; a span can be shown on hover AND on
        # focus, and read out by a screen reader as part of the link.
        links.append(
            f'<a href="/issues/{number}/"{current_attr}>'
            f'<span class="n">{_text(label)}</span>'
            f'<span class="t">{_text(issue_label(number))}'
            f'{" — " + _text(theme) if theme else ""}</span>'
            f"</a>")
    return ('<nav class="issues" aria-label="Issues">'
            '<span class="label">Issues</span>' + "".join(links) + "</nav>")


def load_journal(content_dir: str) -> dict:
    """Journal-level metadata from `content/journal.md`.

    Read rather than hardcoded, because a journal's ISSN, licence, publisher
    and preservation statement are the things another journal must change to
    adopt this — and several of them were sitting in Python string literals.
    """
    path = os.path.join(content_dir, "journal.md")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        meta, _ = extract.parse_front_matter(fh.read())
    return meta


def page_nav(pages: dict[str, Doc], current: str | None) -> str:
    """Links to the journal's institutional pages.

    A journal's standing rests on being able to show who edits it, how it
    reviews, and who preserves it, so these sit in the masthead rather than
    being buried in the footer.
    """
    if not pages:
        return ""
    ordered = sorted(pages.items(),
                     key=lambda kv: (int(kv[1].meta.get("nav_order") or 99), kv[0]))
    links = []
    for slug, doc in ordered:
        current_attr = ' aria-current="page"' if slug == current else ""
        links.append(f'<a href="/{slug}/"{current_attr}>'
                     f'{_text(str(doc.meta.get("title", slug)))}</a>')
    return f'<nav class="pages" aria-label="About the journal">{"".join(links)}</nav>'


def indicators(journal: dict) -> str:
    """Preservation and publisher indicators.

    The LOCKSS sentence is reproduced VERBATIM and as text. A LOCKSS crawler
    looks for that exact wording; in the mirror it survived only as the
    `title` attribute of a GIF, where it does nothing at all.
    """
    bits = []
    lockss = str(journal.get("lockss_statement", "")).strip()
    if lockss:
        bits.append(f'<p class="lockss">{_text(lockss)}</p>')
    publisher = str(journal.get("publisher", "")).strip()
    if publisher:
        url = str(journal.get("publisher_url", "")).strip()
        name = (f'<a href="{_attr(url)}">{_text(publisher)}</a>' if url
                else _text(publisher))
        bits.append(f'<p class="publisher">Published by {name}.</p>')
    issn = str(journal.get("issn", "")).strip()
    licence = str(journal.get("licence", "")).strip()
    licence_url = str(journal.get("licence_url", "")).strip()
    tail = []
    if issn:
        tail.append(f"ISSN {_text(issn)}")
    if licence:
        tail.append(f'<a href="{_attr(licence_url)}">{_text(licence)}</a>'
                    if licence_url else _text(licence))
    if tail:
        bits.append(f'<p class="imprint">{" · ".join(tail)}</p>')
    return "".join(bits)


def shell(title: str, body: str, *, current_issue: str | None, issues: dict[str, Doc],
          main_class: str = "", description: str = "", skip: tuple[str, str] | None = None,
          head: str = "", canonical: str = "",
          themes: dict[str, str] | None = None,
          pages: dict[str, Doc] | None = None,
          journal: dict | None = None,
          current_page: str | None = None) -> str:
    skip_link = (f'<a class="skip" href="#{skip[0]}">{_text(skip[1])}</a>'
                 if skip else '<a class="skip" href="#main">Skip to content</a>')
    desc = (f'<meta name="description" content="{_attr(description[:300])}">'
            if description else "")
    if canonical:
        desc += f'\n<link rel="canonical" href="https://{CANONICAL_HOST}{canonical}">'
    if head:
        desc += "\n" + head
    repo_link = (f' <a href="{_attr(ARCHIVE_REPO)}">Get it from GitHub</a>.'
                 if ARCHIVE_REPO else "")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_text(title)} — The Fibreculture Journal</title>
{desc}
<link rel="stylesheet" href="/assets/style.css">
<link rel="preload" href="/assets/fonts/ibm-plex-sans-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
</head>
<body>
{skip_link}
<header class="site">
  <div class="masthead">
    <a class="wordmark" href="/">The Fibreculture Journal</a>
    <span class="issn">ISSN 1449-1443</span>
  </div>
  {issue_nav(current_issue, issues, themes or {})}
  {page_nav(pages or {}, current_page)}
</header>
<main id="main" class="{main_class}">
{body}
</main>
<footer class="site">
  <div class="inner">
  {indicators(journal or {})}
  <p>A static archive of the original WordPress powered <em>The Fibreculture
  Journal</em>, a peer-reviewed open-access journal of digital media, networks
  and culture published since 2003. Articles remain the copyright of their
  authors under Creative Commons BY-NC-ND. That site ran well for over a decade
  but exposed issues of archiving, resilience and sustainability. This system
  was designed to answer that and to provide a secure archive. It is
  increasingly being developed as a more resilient journal system.</p>
  <p>The text of this archive is also published as plain Markdown, one file per
  article, so it can be downloaded, quoted and reused without this
  website.{repo_link}</p>
  </div>
</footer>
</body>
</html>
"""


def citation_meta(meta: dict, *, url_path: str) -> str:
    """Google Scholar and Dublin Core metadata for an article page.

    The mirror emitted these tags on 218 of 237 papers and the first version of
    this generator dropped them, which would have made the archive LESS
    indexable than the site it replaces — quietly removing the journal from
    Google Scholar, and from anything harvesting through CORE or BASE.

    Scholar's inclusion rules accept HTML as full text provided the citation
    tags are present and the article text is on the page, so this matters more
    for discoverability than whether a PDF exists. `citation_pdf_url` is
    emitted only where a PDF actually exists; pointing it at a missing file is
    worse than omitting it.
    """
    tags: list[str] = []

    def add(name: str, value: object) -> None:
        if value not in (None, "", []):
            tags.append(f'<meta name="{_attr(name)}" content="{_attr(value)}">')

    add("citation_title", meta.get("title"))
    for author in as_list(meta.get("authors")):
        add("citation_author", author)
        if meta.get("affiliation"):
            add("citation_author_institution", meta["affiliation"])
    add("citation_journal_title", meta.get("journal", "The Fibreculture Journal"))
    add("citation_issn", meta.get("issn", "1449-1443"))
    issue = str(meta.get("issue", ""))
    if issue and issue != "mesh":
        add("citation_issue", issue)
    published = str(meta.get("published", ""))
    if published:
        add("citation_publication_date", published.replace("-", "/"))
        add("citation_date", published)
    add("citation_doi", meta.get("doi"))
    add("citation_abstract_html_url", f"https://{CANONICAL_HOST}{url_path}")
    add("citation_fulltext_html_url", f"https://{CANONICAL_HOST}{url_path}")
    if meta.get("pdf"):
        add("citation_pdf_url", f"https://{CANONICAL_HOST}/{meta['pdf']}")
    add("citation_language", "en")

    add("DC.title", meta.get("title"))
    for author in as_list(meta.get("authors")):
        add("DC.creator", author)
    add("DC.publisher", "The Fibreculture Journal")
    add("DC.date", published)
    add("DC.type", "Text.Serial.Journal")
    add("DC.identifier", f"https://{CANONICAL_HOST}{url_path}")
    add("DC.rights", meta.get("licence", "CC BY-NC-ND"))
    if meta.get("abstract"):
        add("DC.description", str(meta["abstract"])[:900])
    return "\n".join(tags)


def byline(meta: dict) -> str:
    names = as_list(meta.get("authors"))
    if not names:
        return ""
    if len(names) == 1:
        who = f'<span class="author">{_text(names[0])}</span>'
    else:
        spans = [f'<span class="author">{_text(n)}</span>' for n in names]
        who = ", ".join(spans[:-1]) + " and " + spans[-1]
    affiliation = meta.get("affiliation", "")
    tail = f"<br>{_text(affiliation)}" if affiliation else ""
    return f'<p class="byline">{who}{tail}</p>'


def editor_byline(meta: dict) -> str:
    """"Edited by …" at the top of an issue, where a reader looks for it.

    The journal credited its editors through WordPress metadata inserts, which
    the crawl flattened into prose at odd places in the page — a `######`
    heading in one issue, a sentence before the editorial in another, a bio
    paragraph near the bottom in a third. `extract.py` recovers them; this puts
    them where they belong.

    Each entry is `Name` or `Name, Institution`, so the institution sets in the
    muted colour and the name does not.
    """
    editors = as_list(meta.get("editors"))
    if not editors:
        return ""
    parts = []
    for entry in editors:
        name, _, institution = str(entry).partition(", ")
        parts.append(f'<span class="who">{_text(name)}</span>'
                     + (f' <span class="where">{_text(institution)}</span>'
                        if institution else ""))
    joined = ", ".join(parts[:-1]) + (" and " if len(parts) > 1 else "") + parts[-1]
    return f'<p class="editors"><span class="lbl">Edited by</span> {joined}</p>'


def article_meta(meta: dict) -> str:
    """The citation line: id, issue, date, DOI. Mono, because it is apparatus."""
    bits = []
    if meta.get("fcj_id"):
        bits.append(f'<span>{_text(meta["fcj_id"])}</span>')
    if meta.get("issue"):
        bits.append(f'<span><a href="/issues/{_attr(str(meta["issue"]))}/">'
                    f'{_text(issue_label(str(meta["issue"])))}</a></span>')
    if meta.get("published"):
        bits.append(f'<span>{_text(str(meta["published"]))}</span>')
    if meta.get("doi"):
        doi = str(meta["doi"])
        bits.append(f'<span><a href="https://doi.org/{_attr(doi)}">doi:{_text(doi)}</a></span>')
    return f'<p class="artmeta">{"".join(bits)}</p>' if bits else ""


def downloads(meta: dict, *, issue: bool = False) -> str:
    """Download links as plain text.

    No icons and no buttons. The mirror used a GIF of a PDF icon followed by
    the words "Issue:pdf", which is what a link label looks like after its
    target has gone — and the first version of this put the links in bordered
    boxes, which read as interface rather than as part of the page.
    """
    links = []
    if issue:
        for key, label in (("full_issue_pdf", "Whole issue (PDF)"),
                           ("full_issue_epub", "Whole issue (ePub)")):
            if meta.get(key):
                links.append(f'<a href="/{_attr(str(meta[key]))}">{label}</a>')
    else:
        for key, label in (("pdf", "PDF"), ("epub", "ePub"),
                           ("pdf_generated", "PDF (archival offprint)")):
            if meta.get(key):
                links.append(f'<a href="/{_attr(str(meta[key]))}">{label}</a>')
    if not links:
        return ""
    return ('<p class="downloads"><span class="lbl">Download</span> '
            + " · ".join(links) + "</p>")


# ---- issue banners, display OFF by default
#
# This flag controls PRESENTATION only. The banner itself, and its aspect
# ratio, are extracted into `content/` by `extract.py`, which is the only stage
# allowed to read the mirror. An earlier version of this function went looking
# in `fcj-static` from here, which broke the boundary the whole design rests on
# — see "The repository is the integration point" in docs/architecture.md.
#
# 13 of the 31 issues have their own artwork; the other 18 shared a generic
# strip, which is not extracted, so they show nothing.
BANNERS = os.environ.get("FCJ_BANNERS", "1").lower() in ("1", "true", "yes")


def banner_html(meta: dict) -> str:
    if not BANNERS or not meta.get("banner"):
        return ""
    ratio = str(meta.get("banner_ratio") or "9.6")
    return (f'<img class="banner" src="/{_attr(str(meta["banner"]))}" alt="" '
            f'aria-hidden="true" loading="lazy" style="aspect-ratio: {_attr(ratio)}">\n')


# --------------------------------------------------------------------------
# write


def write_site(out_dir: str = SITE, content_dir: str = CONTENT) -> Report:
    report = Report()
    papers = load("papers")
    issues = load("issues")

    by_id = {d.meta.get("fcj_id"): (slug, d) for slug, d in papers.items()}
    themes = {n: clean_theme(n, d.meta, by_id) for n, d in issues.items()}
    pages = load("pages")
    journal = load_journal(content_dir)
    common = {"issues": issues, "themes": themes, "pages": pages, "journal": journal}

    def put(rel: str, text: str) -> None:
        path = os.path.join(out_dir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        report.pages += 1

    os.makedirs(out_dir, exist_ok=True)
    _copy_tree(os.path.join(ASSETS), os.path.join(out_dir, "assets"), report)

    # ---- papers
    for slug, doc in papers.items():
        meta = doc.meta
        # Offprints are discovered BY PATH, not by importing `pdfs.py` or by
        # having it write into another tool's files. `content/offprints/<slug>.pdf`
        # is the contract between the two, so either can be run, re-run or
        # deleted without the other knowing.
        if os.path.isfile(os.path.join(content_dir, "offprints", slug + ".pdf")):
            meta = dict(meta, pdf_generated=f"offprints/{slug}.pdf")
        issue = str(meta.get("issue", ""))
        abstract = meta.get("abstract", "")
        abstract_html = ""
        if abstract:
            abstract_html = ('<div class="abstract"><span class="lbl">Abstract</span>'
                             f'<p>{markdown._inline_html(str(abstract), False)}</p></div>')
        body = markdown.render(site_links(doc.body))
        article = (
            f'<article>\n<h1>{_text(str(meta.get("title", slug)))}</h1>\n'
            f"{byline(meta)}\n{article_meta(meta)}\n{abstract_html}\n"
            f"{downloads(meta)}\n"
            f'<div class="body">\n{body}\n</div>\n</article>')
        url_path = f"/papers/{slug}/"
        put(f"papers/{slug}/index.html",
            shell(str(meta.get("title", slug)), article,
                  current_issue=issue, main_class="article", **common,
                  description=str(abstract or ""),
                  head=citation_meta(meta, url_path=url_path),
                  canonical=url_path))

    # ---- issues
    for number, doc in issues.items():
        meta = doc.meta
        theme = themes.get(number, "")
        items = []
        for ident in as_list(meta.get("papers")):
            entry = by_id.get(ident)
            if entry is None:
                continue
            pslug, pdoc = entry
            names = as_list(pdoc.meta.get("authors"))
            who = (f'<span class="authors">{_text(", ".join(names))}</span>'
                   if names else "")
            items.append(
                f'<li><span class="id">{_text(ident)}</span>'
                f'<a href="/papers/{_attr(pslug)}/">'
                f'{_text(str(pdoc.meta.get("title", pslug)))}</a>{who}</li>')
        # Contents BEFORE the editorial. The issue page is still the editorial
        # — that is the design rule this archive makes uniform — but a reader
        # arriving at an issue is almost always looking for an article, and
        # making them scroll several thousand words of editorial to find the
        # list was the wrong way round.
        contents = ""
        if items:
            contents = ('<h2 class="sectionhead" id="contents">'
                        f"{len(items)} articles</h2>\n"
                        '<ol class="contents">\n' + "\n".join(items) + "\n</ol>")
        editorial = (
            '<h2 class="sectionhead" id="editorial">Editorial</h2>\n'
            f'<div class="body editorial">\n{markdown.render(site_links(doc.body))}\n</div>')
        body = (f"{banner_html(meta)}"
                f"<h1>{_text(issue_label(number))}</h1>\n"
                # Several issues have no theme at all in their root title.
                # Printing the issue number twice, or the site's own name, is
                # worse than printing nothing.
                + (f'<p class="lede">{_text(theme)}</p>\n' if theme else "")
                + editor_byline(meta)
                + (f'<p class="artmeta"><span>doi:{_text(str(meta["doi"]))}</span></p>\n'
                   if meta.get("doi") else "")
                + f"{downloads(meta, issue=True)}\n"
                f"{contents}\n{editorial}")
        put(f"issues/{number}/index.html",
            shell(f"{issue_label(number)}" + (f" — {theme}" if theme else ""), body,
                  current_issue=number, main_class="wide", **common,
                  description=theme,
                  skip=("editorial", "Skip to editorial") if items else None))

    # ---- front page
    rows = []
    for number in issue_order(issues):
        meta = issues[number].meta
        count = len(as_list(meta.get("papers")))
        rows.append(
            f'<li><a href="/issues/{number}/">'
            f'<span class="n">{_text(issue_label(number))}</span>'
            f'<span class="theme">{_text(themes.get(number, ""))}</span>'
            f'<span class="count">{count} articles</span></a></li>')
    front = (
        "<h1>The Fibreculture Journal</h1>\n"
        '<p class="lede">A peer-reviewed open-access journal of digital media, '
        "networks and culture, published since 2003. This is the complete "
        f"archive: <strong>{len(papers)} articles</strong> across "
        f"<strong>{len(issues)} issues</strong>, with the full text also "
        "available as plain Markdown.</p>\n"
        '<ul class="issuelist">\n' + "\n".join(rows) + "\n</ul>")
    put("index.html", shell("Archive", front, current_issue=None, main_class="wide", **common,
                            description="Complete archive of The Fibreculture Journal, "
                                        "a peer-reviewed journal of digital media, "
                                        "networks and culture."))

    # ---- institutional pages
    #
    # The About page carries a contact for whoever maintains the archive —
    # Invariant 8(b), the only text of the archive's own allowed on a journal
    # page besides an offprint's colophon. A reader who finds a broken link or
    # a mis-scanned figure needs somewhere to report it, and the journal ceased
    # publishing in 2019, so `contact` can no longer answer for the files.
    #
    # Read from `journal.md`, which is hand-maintained, rather than written
    # into `content/pages/about.md`, which `extract.py` regenerates. The
    # invariant holds this to a contact line: it must not grow into an
    # explanation of what the archive is.
    archive_contact = str(journal.get("archive_contact", "")).strip()
    for slug, doc in pages.items():
        meta = doc.meta
        contact = ""
        if slug == "about" and archive_contact:
            contact = (f'\n<p class="archive-contact">This archive is '
                       f'maintained by <a href="mailto:{_attr(archive_contact)}">'
                       f"{_text(archive_contact)}</a>.</p>")
        body = (f'<article>\n<h1>{_text(str(meta.get("title", slug)))}</h1>\n'
                f'<div class="body">\n{markdown.render(site_links(doc.body))}\n'
                f"{contact}\n</div>\n</article>")
        put(f"{slug}/index.html",
            shell(str(meta.get("title", slug)), body, current_issue=None,
                  main_class="", current_page=slug, canonical=f"/{slug}/",
                  **common))

    # ---- sitemap, for harvesters that do not read OAI-PMH
    # A static archive cannot serve OAI-PMH, which takes query parameters, so a
    # sitemap is the one machine-readable index of the whole corpus it can
    # offer. Cheap, and it is what Scholar and CORE follow.
    urls = ["/"] + [f"/{slug}/" for slug in pages] + \
           [f"/issues/{n}/" for n in issue_order(issues)] + \
           [f"/papers/{slug}/" for slug in papers]
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in urls:
        sitemap.append(f"<url><loc>https://{CANONICAL_HOST}{url}</loc></url>")
    sitemap.append("</urlset>")
    put("sitemap.xml", "\n".join(sitemap) + "\n")
    put("robots.txt", f"User-agent: *\nAllow: /\n"
                      f"Sitemap: https://{CANONICAL_HOST}/sitemap.xml\n")

    # The redirect map ships WITH the site, because whatever serves the site is
    # what has to answer the old URLs. It is built at extract time (it depends
    # on the mirror and the crawl index), so this stage only carries it across.
    for name in ("redirects.json", "redirects.map"):
        source = os.path.join(content_dir, name)
        if os.path.isfile(source):
            shutil.copy2(source, os.path.join(out_dir, name))
            report.pages += 0

    # Stale output is worse than missing output: it still serves. When
    # `paper_dir` changed and FCJ-002 moved from `fcj-002-fcj002/` to
    # `fcj-002/`, the old directory stayed behind and the site published the
    # same article at two URLs — which is the duplication this whole archive
    # exists to clean up. Scoped to `papers/` and `issues/`, whose entire
    # contents this function writes.
    for sub, keep in (("papers", set(papers)), ("issues", set(issues))):
        directory = os.path.join(out_dir, sub)
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if name not in keep and os.path.isdir(os.path.join(directory, name)):
                shutil.rmtree(os.path.join(directory, name))
                report.pruned.append(f"{sub}/{name}")

    # Institutional pages publish at the SITE ROOT, so a page withdrawn from
    # `content/pages/` leaves a live directory at a top-level URL that nothing
    # links any more — still indexed, still citable, no longer the archive's.
    #
    # Pruning the root needs an explicit keep list rather than a pattern,
    # because the root also holds `papers/`, `issues/`, `media/`, `offprints/`
    # and `assets/`, and deleting any of those would destroy the site. A
    # directory is removed only if it holds exactly one file, `index.html`:
    # that is the shape this function creates for a page and nothing else.
    protected = {"papers", "issues", "media", "offprints", "assets"}
    for name in sorted(os.listdir(out_dir)):
        directory = os.path.join(out_dir, name)
        if (not os.path.isdir(directory) or name in protected
                or name in pages or name.startswith(".")):
            continue
        if os.listdir(directory) == ["index.html"]:
            shutil.rmtree(directory)
            report.pruned.append(f"{name}/")

    _link_media(content_dir, out_dir, report)
    return report


def _copy_tree(src: str, dst: str, report: Report) -> None:
    for dirpath, _dirs, files in os.walk(src):
        for name in files:
            s = os.path.join(dirpath, name)
            d = os.path.join(dst, os.path.relpath(s, src))
            os.makedirs(os.path.dirname(d), exist_ok=True)
            if not os.path.exists(d) or os.path.getmtime(s) > os.path.getmtime(d):
                shutil.copy2(s, d)


def _link_media(content_dir: str, out_dir: str, report: Report) -> None:
    """Hardlink `content/media` into `site/media` rather than copying it.

    The media is 270 MB. Copying it would mean 540 MB on disk for one archive,
    and every rebuild would rewrite it. A hardlink costs nothing, still reads
    as an ordinary file to a web server or an upload, and keeps the two trees
    byte-identical by construction. Falls back to copying where hardlinks are
    unavailable (a different filesystem, or Windows without privileges).
    """
    for sub in ("media", "offprints"):
        _link_tree(os.path.join(content_dir, sub), os.path.join(out_dir, sub), report)


def _link_tree(src_root: str, dst_root: str, report: Report) -> None:
    expected: set[str] = set()
    for dirpath, _dirs, files in os.walk(src_root):
        for name in files:
            s = os.path.join(dirpath, name)
            d = os.path.join(dst_root, os.path.relpath(s, src_root))
            expected.add(d)
            report.media += 1
            report.media_bytes += os.path.getsize(s)
            if os.path.exists(d):
                if os.path.samefile(s, d) or os.path.getsize(s) == os.path.getsize(d):
                    continue
                os.remove(d)
            os.makedirs(os.path.dirname(d), exist_ok=True)
            try:
                os.link(s, d)
                report.hardlinked += 1
            except OSError:
                shutil.copy2(s, d)
    _prune_tree(dst_root, expected, report)


def _prune_tree(dst_root: str, expected: set[str], report: Report) -> None:
    """Remove files in the output tree that `content/` no longer has.

    This function used to only ever ADD. A file dropped from `content/media`
    therefore stayed in `site/media` for good — which is how 52 of the old
    theme's icons survived being excluded from the archive and stayed in the
    tree that actually gets deployed.

    Two refusals, because this deletes from a 270 MB tree:

    - an EMPTY expected set means the source tree is missing or failed to
      build, so there is nothing to compare against and nothing is removed;
    - a deletion of more than half the output means the source is truncated
      rather than the output stale, and the sane reading is that the input is
      wrong. Say so and delete nothing.

    Both prefer leaving a stale file to destroying a good one, because
    `content/` can be rebuilt from the mirror and a half-deleted `site/` under
    a live server cannot be reasoned about.
    """
    if not expected or not os.path.isdir(dst_root):
        return
    stale = []
    for dirpath, _dirs, files in os.walk(dst_root):
        for name in files:
            path = os.path.join(dirpath, name)
            if path not in expected:
                stale.append(path)
    if not stale:
        return
    if len(stale) > len(expected):
        report.notes.append(
            f"{os.path.basename(dst_root)}/: refusing to prune "
            f"{len(stale)} files against only {len(expected)} in content/ — "
            f"the input looks truncated, not the output stale")
        return
    for path in stale:
        os.remove(path)
        report.pruned.append(os.path.relpath(path, os.path.dirname(dst_root)))
    for dirpath, _dirs, _files in os.walk(dst_root, topdown=False):
        if dirpath != dst_root and not os.listdir(dirpath):
            os.rmdir(dirpath)


def _text(s: str) -> str:
    return htmllib.escape(str(s), quote=False)


def _attr(s: str) -> str:
    return htmllib.escape(str(s), quote=True)


def _main() -> None:
    if not os.path.isdir(CONTENT):
        raise SystemExit("content/ does not exist — run build/extract.py first")
    rep = write_site()
    print(f"site/: {rep.pages} pages, {rep.media} media files "
          f"({rep.media_bytes / 1024 / 1024:.0f} MB, {rep.hardlinked} hardlinked)")
    if rep.pruned:
        shown = ", ".join(rep.pruned[:4])
        more = f" and {len(rep.pruned) - 4} more" if len(rep.pruned) > 4 else ""
        print(f"  pruned {len(rep.pruned)} stale file(s): {shown}{more}")
    for note in rep.notes:
        print(f"  NOTE: {note}")
    if not ARCHIVE_REPO:
        print("  NOTE: ARCHIVE_REPO is unset in build/generate.py, so the "
              "footer omits the link to the Markdown archive.")
    print(f"rendered from {CONTENT}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    _main()
