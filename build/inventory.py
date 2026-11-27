#!/usr/bin/env python3
# Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
"""Inventory the crawled mirror into a Manifest.

Governed by docs/architecture.md ("API Contracts", "Data Models").

The manifest is driven from **each issue root's own links**, not from slug
patterns and not from the FCJ number sequence. Both of those demonstrably miss
content: FCJ-212 is issue 29's editorial rather than a paper, and issue 16's
papers carry no number in their slugs at all (`/games-of-multitude/` is
FCJ-113). The issue root is the journal's own record of what the issue contains,
so it is the authority on membership.

Nothing here writes to the mirror, and nothing is silently discarded: every link
an issue root carries ends up in exactly one of papers, editorials, unclassified
or unresolved, and `check_accounting` asserts that.
"""
from __future__ import annotations

import html
import os
import re
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit, unquote

import resolve

SITE = resolve.SITE

# Issue number -> host prefix. Written out rather than generated from a
# number-word function because the mapping is a fact about the deployed site,
# not a rule: "mesh" is a 31st host with no number, and a generated list would
# quietly invent hosts that never existed.
ISSUE_HOSTS: list[tuple[str, str]] = [
    ("1", "one"), ("2", "two"), ("3", "three"), ("4", "four"), ("5", "five"),
    ("6", "six"), ("7", "seven"), ("8", "eight"), ("9", "nine"), ("10", "ten"),
    ("11", "eleven"), ("12", "twelve"), ("13", "thirteen"), ("14", "fourteen"),
    ("15", "fifteen"), ("16", "sixteen"), ("17", "seventeen"), ("18", "eighteen"),
    ("19", "nineteen"), ("20", "twenty"), ("21", "twentyone"), ("22", "twentytwo"),
    ("23", "twentythree"), ("24", "twentyfour"), ("25", "twentyfive"),
    ("26", "twentysix"), ("27", "twentyseven"), ("28", "twentyeight"),
    ("29", "twentynine"), ("30", "thirty"), ("mesh", "mesh"),
]

# WordPress furniture: generated views of content the archive holds canonically
# elsewhere, so they are skipped rather than reported unresolved.
#
# `wp-content` is NOT furniture as a whole. Across the mirror it holds exactly
# five things: `themes` and `plugins`, which are furniture, and `dynmed`,
# `pdfs` and `ePubs`, which are author-supplied content. Treating the whole
# directory as furniture discarded the 53 files of interactive supplementary
# material behind FCJ-062, which the paper's own text links to and which has no
# other copy.
FURNITURE = re.compile(
    r"^(wp-includes|wp-admin|wp-login|wp-json|xmlrpc|author|tag|"
    r"category|feed|page|comments|wp-content/(themes|plugins))(/|$)", re.I)

# A bare year or year/month path is a WordPress date archive. A dated permalink
# (`/2016/03/21/<slug>/`) is content, so the distinction is the trailing slug,
# not the leading digits.
DATE_ARCHIVE = re.compile(r"^\d{4}(/\d{2}){0,2}/?$")

ASSET_EXT = (".pdf", ".epub", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")

TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
# `issue-08-editorial`, `issue-18-trans`, `issue-21-affect-in-interaction`,
# `issue-1-ubiquity`. Classification only — the issue number comes from the HOST
# the page was found on, never from this slug, because `nineteen.../issue-1-ubiquity`
# is issue 19's editorial under a slug reading as issue 1. Requiring the hyphen
# after "issue" keeps issue 15's retired `issue15_<author>.html` convention out.
EDITORIAL_SLUG = re.compile(r"^issue-\d{1,2}(-|$)", re.I)
# An issue whose editorial page cannot be recognised by its slug.
#
# `mesh` is the only issue that is not numbered, so no `issue-NN` slug exists
# for it and `EDITORIAL_SLUG` can never match. It therefore kept its root as
# its editorial — and the mesh root is a WordPress blog index: nine post
# excerpts, each cut off with a "read more" link that resolves nowhere now,
# three of them repeating the table of contents the generator writes from the
# manifest. The About page holds the real thing, 555 words of it, opening with
# the sentence the front page was truncating.
#
# Declared explicitly rather than by loosening the pattern to `about-*`: that
# would apply to all 31 issue hosts and could promote a genuine About page over
# a real editorial. Same reasoning as the institutional page list, which the
# spec requires to be explicit and never a directory scan.
EDITORIAL_BY_SLUG = {"mesh": "about-mesh"}
# "FCJ-218", "FCJ-002", "FCJMesh-002" — the citation as the theme prints it.
# The separator is a plain hyphen in every observed title, but en-dashes appear
# in slugs, so both are accepted here rather than assumed away.
CITATION = re.compile(r"\bFCJ(MESH)?\s*[-–]\s*(\d{1,3})\b", re.I)
LINKISH = re.compile(r'(?:href|src)\s*=\s*"([^"]*)"', re.I)


@dataclass
class Paper:
    fcj_id: str
    issue: str
    slug: str
    source: str
    title: str
    words: int
    images: list[str] = field(default_factory=list)
    pdf: str | None = None
    epub: str | None = None


@dataclass
class Issue:
    number: str
    theme: str
    editorial_html: str
    # "mirror-standalone" | "mirror-root" | "dump" | "absent"
    editorial_source: str
    editorial_path: str | None = None
    papers: list[str] = field(default_factory=list)
    full_issue_pdf: str | None = None
    full_issue_epub: str | None = None


@dataclass
class Page:
    """A linked page that is neither a paper nor an editorial."""
    issue: str
    url: str
    source: str
    title: str
    words: int


@dataclass
class Unresolved:
    issue: str
    kind: str        # "page" | "asset"
    url: str
    referrer: str


@dataclass
class Manifest:
    papers: dict[str, Paper] = field(default_factory=dict)
    issues: dict[str, Issue] = field(default_factory=dict)
    assets: dict[str, int] = field(default_factory=dict)
    unresolved: list[Unresolved] = field(default_factory=list)
    unclassified: list[Page] = field(default_factory=list)
    # fcj_ids whose only copy was found on the apex host, where all the known
    # spam contamination is. These need the spam audit before they are published.
    apex_sourced: list[str] = field(default_factory=list)
    # issue -> {"links": n, "papers": n, "editorials": n, ...}; see check_accounting
    counts: dict[str, dict[str, int]] = field(default_factory=dict)


# --------------------------------------------------------------------------
# text extraction


def read(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


FOOTER = re.compile(r'<div[^>]*id\s*=\s*"footer"', re.I)

# Where a content region ends, in order of preference. Div balance cannot be
# used (see extract_region), so these are structural landmarks, each measured
# across the whole mirror before being relied on:
#   the theme's own marker        502 of 1,161 article pages
#   the sidebar                 1,161 of 1,161, and all 31 issue roots
#   the footer                  1,189 of 1,189, all roots, all apex editorials
# The sidebar matters as much as the footer: it sits INSIDE `post_content` and
# holds the journal's `/category/…` nav, which is what put 1,702 identical
# "dead links" into the first generated build.
BOUNDARIES = (
    re.compile(r"<!--\s*\.post_text\s*-->", re.I),
    re.compile(r'<div[^>]*id\s*=\s*"side_categories"', re.I),
    re.compile(r'<div[^>]*class\s*=\s*"column span-3', re.I),
    FOOTER,
)

# The article body proper, then the issue root, then the outer wrapper as a
# fallback for the 28 article pages that have no `post_text`.
CONTAINERS = (
    re.compile(r'<div[^>]*class\s*=\s*"post_text"[^>]*>', re.I),
    re.compile(r'<div[^>]*id\s*=\s*"home_content"[^>]*>', re.I),
    re.compile(r'<div[^>]*id\s*=\s*"post_content"[^>]*>', re.I),
)


def balance_divs(fragment: str) -> str:
    """Make a fragment's div tags balance, so it can be embedded in a page.

    Needed because the source fragments genuinely don't balance, and an
    unclosed div in the output would swallow the generated page's own footer.
    Leading unmatched closes are dropped and missing closes are appended, which
    is what a browser effectively does anyway.
    """
    out: list[str] = []
    depth = 0
    pos = 0
    for tag in re.finditer(r"<(/?)div\b[^>]*>", fragment, re.I):
        out.append(fragment[pos:tag.start()])
        pos = tag.end()
        if tag.group(1):
            if depth == 0:
                continue        # stray close; dropping it is the safe repair
            depth -= 1
        else:
            depth += 1
        out.append(tag.group(0))
    out.append(fragment[pos:])
    return "".join(out) + "</div>" * depth


def extract_region(doc: str, container_id: str) -> str:
    """The inner HTML of `<div id="...">`.

    Div balance CANNOT be the boundary here. The mirror's pages don't balance —
    `one/fcj-001.html` has 32 `<div>` against 31 `</div>` — so counting tags
    runs past the real close and swallows the site footer, which is how the
    first generated build picked up 1,948 identical "dead links" to
    `/category/…` and `/feed`. A browser mismatches it the same way, matching
    each close to the nearest open div, so this is broken HTML rather than a
    parsing subtlety.

    So the boundary is a sentinel, in order of preference:

      1. the theme's own `<!-- #post_content -->` comment, where present (502
         of 1,189 article pages);
      2. the opening of `<div id="footer">`, present in 1,189 of 1,189 article
         pages, all 31 issue roots and all three apex editorial pages — the
         only structural landmark that is actually universal;
      3. failing both, the balanced scan, which is still right for well-formed
         fragments and is what the unit tests exercise.

    Returns "" if the container is absent, which is how a page that is not an
    article (an archive listing, a nav stub) announces itself.
    """
    return region(doc, re.compile(
        rf'<div[^>]*id\s*=\s*"{re.escape(container_id)}"[^>]*>', re.I),
        marker=f"<!-- #{container_id} -->")


def region(doc: str, container: re.Pattern[str], marker: str | None = None) -> str:
    """The inner HTML of the first match of `container`. See extract_region."""
    m = container.search(doc)
    if not m:
        return ""
    start = m.end()

    cuts = [doc.find(marker, start)] if marker else []
    cuts += [(b.start() if (b := pat.search(doc, start)) else -1) for pat in BOUNDARIES]
    cuts = [c for c in cuts if c > start]
    if cuts:
        cut = min(cuts)
        close = doc.rfind("</div", start, cut)
        return balance_divs(doc[start:close if close > start else cut])

    depth = 1
    for tag in re.finditer(r"<(/?)div\b[^>]*>", doc[start:], re.I):
        depth += -1 if tag.group(1) else 1
        if depth == 0:
            return doc[start:start + tag.start()]
    return doc[start:]          # unclosed container: take the rest, don't lose it


def content_of(doc: str) -> str:
    """The article or editorial region of a page, theme furniture removed.

    The same WordPress theme runs across every era of the site: an article's
    text is `class="post_text"` (1,161 pages), an issue root's is
    `id="home_content"` (all 31), and `id="post_content"` is the outer wrapper
    that holds the article AND the sidebar — used only as a fallback for the 28
    article pages with no `post_text`, where its sidebar is cut off by the
    boundary sentinels.
    """
    for container in CONTAINERS:
        if (text := region(doc, container,
                           marker="<!-- .post_text -->")) and text.strip():
            return text
    return ""


def words(fragment: str) -> int:
    f = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", fragment)
    f = re.sub(r"(?s)<[^>]+>", " ", f)
    return len(html.unescape(f).split())


def title_of(doc: str) -> str:
    m = TITLE.search(doc)
    if not m:
        return ""
    return re.sub(r"\s+", " ", html.unescape(m.group(1))).strip()


def fcj_id(doc: str) -> str | None:
    """The FCJ citation from the page's <title>, or None.

    Identity comes from the citation and nowhere else. The slug cannot be
    trusted: issue 16 numbers nothing in its URLs, issue 1 writes `fcj002.html`
    while issue 29 writes `fcj-218-<words>`, and
    `nineteen.../issue-1-ubiquity` is issue 19's editorial under a slug that
    reads as issue 1. The `<title>` citation is the one convention the theme
    kept for twenty years.

    Only the <title> is searched, never the body: a paper's body routinely cites
    other papers by number, and a body search would hand a paper its
    bibliography's identity.
    """
    m = CITATION.search(title_of(doc))
    if not m:
        return None
    kind = "FCJMesh" if m.group(1) else "FCJ"
    return f"{kind}-{int(m.group(2)):03d}"


# A title that is only the journal's name and a number — "Fibreculture
# Journal: 20". EVERY issue root carries one of these, because the subdomain's
# front page was never given a themed title. Issues 1–19 get a real theme from
# their standalone editorial page; the four issues whose editorial comes from
# the root have nothing better to fall back on, which is how issue 20 came to
# be recorded as "Fibreculture Journal: 20" instead of "Networked Utopias and
# Speculative Futures".
GENERIC_TITLE = re.compile(
    r"^(?:the\s+)?fibreculture\s+journal\s*:?\s*\d+$", re.I)


def theme_from_apex(number: str, static_root: str) -> str:
    """An issue's themed title, recovered from the apex host's own page.

    The apex republished each issue under a descriptive slug, and its `<title>`
    carries the title the journal actually used. Found by matching `Issue <N>`
    in the title rather than by guessing the slug, because the slugs are
    unpredictable — `issue-20-networked-utopias`, `trans-issue`,
    `unnatural-ecologies-issue`.

    Requires EXACTLY ONE match, and returns nothing otherwise. The apex also
    holds a call for papers and an announcement for the same issues; if a
    future crawl made the match ambiguous, a silently wrong issue title is
    worse than the generic one, which at least looks wrong.
    """
    want = re.compile(rf"\bIssue\s+0?{re.escape(number)}\b", re.I)
    apex = os.path.join(static_root, resolve.host_dir(resolve.SITE))
    if not os.path.isdir(apex):
        return ""
    found = set()
    for name in sorted(os.listdir(apex)):
        path = os.path.join(apex, name, "index.html")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as fh:
            head = fh.read(4000)
        candidate = display_title(head)
        if candidate and want.search(candidate):
            found.add(re.sub(r"\s+", " ", candidate).strip())
    return found.pop() if len(found) == 1 else ""


def display_title(doc: str) -> str:
    """The page's own title, with the site name and citation prefix removed."""
    t = title_of(doc)
    if "|" in t:
        t = t.split("|", 1)[1]
    t = CITATION.sub("", t, count=1)
    return t.strip(" :–-").strip()


# --------------------------------------------------------------------------
# links


def page_links(doc: str, host: str) -> list[str]:
    """Same-host URL paths this page links, in document order, deduplicated.

    Order is kept because an issue root lists its papers in the order the issue
    presents them, and that order is editorial information the archive should
    not lose. A set would throw it away.
    """
    out: list[str] = []
    seen: set[str] = set()
    origin = f"https://{resolve.host_dir(host)}/"
    for raw in LINKISH.findall(doc):
        href = resolve.clean_href(raw)
        if not href or href.startswith(("mailto:", "javascript:", "data:", "tel:")):
            continue
        parts = urlsplit(urljoin(origin, href))
        if parts.netloc and parts.netloc.lstrip("www.") != resolve.host_dir(host):
            continue
        path = parts.path
        if path and path not in seen:
            seen.add(path)
            out.append(path)
    return out


def is_furniture(url_path: str) -> bool:
    rel = unquote(url_path).lstrip("/")
    return (bool(FURNITURE.match(rel)) or bool(DATE_ARCHIVE.match(rel))
            or rel.lower().endswith(".php"))


def is_asset(url_path: str) -> bool:
    return unquote(url_path).lower().rstrip("/").endswith(ASSET_EXT)


def slug_of(url_path: str) -> str:
    """Last meaningful path segment, percent-decoded and NFC-normalised.

    NFC because these become output directory names and a mix of NFC and NFD on
    disk would produce two directories that look identical in a listing.
    """
    rel = unquote(resolve.clean_href(url_path)).strip("/")
    seg = rel.rsplit("/", 1)[-1] if rel else ""
    seg = re.sub(r"\.html?$", "", seg, flags=re.I)
    return unicodedata.normalize("NFC", seg)


# --------------------------------------------------------------------------
# duplicate editorials


def _fingerprint(fragment: str) -> str:
    f = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", fragment)
    f = re.sub(r"(?s)<[^>]+>", " ", f)
    f = html.unescape(f).lower()
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", f)).strip()


def duplicates(a: str, b: str, floor: int = 400) -> bool:
    """True if two content regions are the same editorial text.

    Measured, not guessed: on issues 8, 11, 18 and 19 the standalone editorial
    page repeats the issue root's text, and keeping both would publish the same
    editorial twice under different URLs.

    The test is prefix containment on normalised text, with a length floor. A
    looser test (word-count proximity) would have discarded issue 16's
    `games-of-multitude` — 15,482 words against a 6,469-word root, and actually
    FCJ-113, a paper. The floor exists because short nav stubs normalise to
    near-identical strings and would collapse into each other.
    """
    fa, fb = _fingerprint(a), _fingerprint(b)
    if len(fa) < floor or len(fb) < floor:
        return False
    head = min(len(fa), len(fb), 2000)
    return fa[:head] == fb[:head]


# --------------------------------------------------------------------------
# build


def resolve_with_apex(host: str, url_path: str,
                      static_root: str) -> tuple[str | None, bool]:
    """Resolve on the issue's own host, then fall back to the apex host.

    Returns (path, came_from_apex).

    This exists because of one measured case, not as a general convenience.
    Issue 19's root links `/fcj-129-interaction-designs-for-ubicomp-cultures/`,
    which does not exist on `nineteen.`; the only copy of FCJ-129 in the mirror
    is `fibreculturejournal.org/fcj-129-…-3/` — a WordPress duplicate suffix —
    and `fcj-redirects.conf` has no rule for it. Without this fallback the paper
    is simply absent from the archive, which is the failure this whole exercise
    is meant to prevent.

    The caller MUST treat an apex hit as needing a spam check: all 145
    contaminated files in the mirror are on the apex host and none are on an
    issue subdomain, so apex is exactly the risky source. FCJ-129's apex copy
    was checked by hand and is clean; `audit_spam` will cover the general case.
    """
    local = resolve.local_path(host, url_path, static_root)
    if local is not None:
        return local, False
    if resolve.host_dir(host) == SITE:
        return None, False

    # The apex copy may carry a WordPress collision suffix. When WordPress is
    # asked to publish a post whose slug already exists it appends `-2`, `-3`
    # and so on; FCJ-129 lives at `fcj-129-…-cultures-3` while every link to it
    # says `fcj-129-…-cultures`. The suffixes are tried in order and the first
    # hit wins, so the result is deterministic. The ceiling is 5 because this is
    # a lookup for a known-missing page, not a search: without a bound a
    # malformed link would probe the filesystem indefinitely.
    cleaned = resolve.clean_href(url_path).rstrip("/")
    for n in range(2, 6):
        for h in (host, SITE):
            hit = resolve.local_path(h, f"{cleaned}-{n}", static_root)
            if hit is not None:
                return hit, resolve.host_dir(h) == SITE
    return resolve.local_path(SITE, url_path, static_root), True


def in_code_theme(local: str) -> bool:
    """Is this file part of a WordPress theme's own interface?

    The distinction matters because `wp-content/themes` holds two unlike
    things. Four directories are code themes, whose images are the old site's
    chrome — `PDFicon.gif`, `epub.gif`, `favicon2.ico`. One,
    `themes/fcsharedimg`, is a bare asset bucket holding 183 files of issue
    artwork, **including every issue banner** under `banners<N>/`.

    Excluding the whole of `themes` would therefore delete the banners, which
    is the same mistake `FURNITURE` records for `wp-content/uploads`: a
    directory is not a category.

    The test is structural rather than a list of theme names: **WordPress
    requires a theme to declare itself in `style.css`**, so a theme directory
    that has one is code and a directory that has none is storage. If a crawl
    ever missed a theme's `style.css` this keeps files rather than dropping
    them, which is the safe direction to be wrong in.
    """
    parts = local.replace(os.sep, "/").split("/")
    try:
        at = len(parts) - 1 - parts[::-1].index("themes")
    except ValueError:
        return False
    if at == 0 or parts[at - 1] != "wp-content" or at + 1 >= len(parts):
        return False
    theme_dir = os.sep.join(parts[:at + 2])
    return os.path.isfile(os.path.join(theme_dir, "style.css"))


def _collect_assets(doc: str, host: str, issue: str, referrer: str,
                    man: Manifest, static_root: str) -> tuple[list[str], str | None, str | None]:
    """Assets a page references.

    Images are taken from the CONTENT region only. Scanning the whole document
    pulls in the theme's logos, feed icons and sidebar furniture: 1,311 image
    references across the mirror against 323 that are actually part of a paper.

    PDFs and ePubs are taken from the whole document, because the per-paper
    download links sit in `class="post_meta"`, which is inside `post_content`
    but OUTSIDE `post_text` — so a content-only scan would silently drop the
    109 paper PDFs and 92 ePubs. The looser scan is safe for them: they are
    named per paper, and the theme references none.
    """
    images: list[str] = []
    pdf = epub = None
    content = content_of(doc)
    in_content = set(page_links(content, host))
    for path in page_links(doc, host):
        if not is_asset(path):
            continue
        if path.lower().rstrip("/").endswith(IMAGE_EXT) and path not in in_content:
            continue
        local = resolve.local_path(host, path, static_root)
        if local is None:
            man.unresolved.append(Unresolved(issue, "asset", path, referrer))
            continue
        if in_code_theme(local):
            continue
        low = local.lower()
        if low.endswith(IMAGE_EXT):
            if local not in images:
                images.append(local)
        elif low.endswith(".pdf") and pdf is None:
            pdf = local
        elif low.endswith(".epub") and epub is None:
            epub = local
        man.assets[os.path.relpath(local, static_root)] = os.path.getsize(local)
    return images, pdf, epub


def build(static_root: str = resolve.STATIC_ROOT) -> Manifest:
    """Walk every issue root and classify everything it links. Read-only."""
    man = Manifest()

    for number, host in ISSUE_HOSTS:
        root_file = resolve.local_path(host, "/", static_root)
        if root_file is None:
            man.unresolved.append(Unresolved(number, "page", "/", "(issue root)"))
            continue
        root_doc = read(root_file)
        root_content = content_of(root_doc)

        # Every issue root's own title is generic, so where no standalone
        # editorial page supplies a themed one, recover it from the apex.
        root_theme = display_title(root_doc)
        if GENERIC_TITLE.match(root_theme):
            root_theme = theme_from_apex(number, static_root) or root_theme

        man.issues[number] = Issue(
            number=number,
            theme=root_theme,
            editorial_html=root_content,
            editorial_source="mirror-root",
        )
        counts = {"links": 0, "papers": 0, "editorials": 0,
                  "unclassified": 0, "unresolved": 0, "furniture": 0, "assets": 0}

        _collect_assets(root_doc, host, number, "(issue root)", man, static_root)

        for path in page_links(root_doc, host):
            if is_asset(path):
                counts["assets"] += 1
                continue
            counts["links"] += 1
            if is_furniture(path):
                counts["furniture"] += 1
                continue
            local, via_apex = resolve_with_apex(host, path, static_root)
            if local is None:
                man.unresolved.append(Unresolved(number, "page", path, "(issue root)"))
                counts["unresolved"] += 1
                continue
            if local == root_file:
                counts["editorials"] += 1
                continue

            doc = read(local)
            content = content_of(doc)
            ident = fcj_id(doc)

            # A citation wins over everything else. FCJ-212 is issue 29's intro
            # and FCJ-129 is issue 19's editorial continuation; both are
            # numbered, so both are cited as papers and must stay reachable
            # under their numbers whatever else they also are.
            if ident is None:
                if (EDITORIAL_SLUG.match(slug_of(path))
                        or slug_of(path) == EDITORIAL_BY_SLUG.get(str(number))
                        or duplicates(content, root_content)):
                    # the issue's editorial, published at its own URL. Prefer it
                    # over the root: the root carries the editorial text PLUS a
                    # hand-written list of the issue's papers, and the generator
                    # writes that list itself from the manifest. Taking the
                    # standalone page avoids publishing the list twice and
                    # avoids inheriting its links to the old hosts.
                    iss = man.issues[number]
                    if iss.editorial_source != "mirror-standalone":
                        iss.editorial_html = content
                        iss.editorial_source = "mirror-standalone"
                        iss.editorial_path = local
                        if (theme := display_title(doc)):
                            iss.theme = theme
                    counts["editorials"] += 1
                    continue
                man.unclassified.append(Page(number, path, local,
                                             display_title(doc), words(content)))
                counts["unclassified"] += 1
                continue

            images, pdf, epub = _collect_assets(doc, host, number, path, man, static_root)
            if via_apex:
                man.apex_sourced.append(ident)
            man.papers[ident] = Paper(
                fcj_id=ident,
                issue=number,
                slug=slug_of(path),
                source=local,
                title=display_title(doc),
                words=words(content),
                images=images,
                pdf=pdf,
                epub=epub,
            )
            man.issues[number].papers.append(ident)
            counts["papers"] += 1

        man.counts[number] = counts

    return man


KNOWN_ABSENT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data",
    "known-absent.txt")

# Why a number is missing, where the archive can say. Keyed by FCJ id so the
# reason travels with the evidence rather than living in a commit message.
ABSENT_REASONS = {
    "FCJ-222": ("Absent from the mirror, from the crawl index, and from the "
                "tables of contents of both adjacent issues. It sits exactly on "
                "the issue boundary: issue 29 ends at FCJ-221 and issue 30 "
                "begins at FCJ-223. Wayback holds no capture of it either, and "
                "no capture of FCJ-223 to FCJ-228, which demonstrably exist, so "
                "its coverage of thirty.fibreculturejournal.org is too thin to "
                "prove anything. Withdrawn or skipped; only editorial records "
                "can say which. See ../fcj-problems.md P2."),
}


def absent_numbers(man: Manifest, last: int = 228) -> list[str]:
    """FCJ numbers from 001 to `last` that the manifest does not hold."""
    return [f"FCJ-{n:03d}" for n in range(1, last + 1)
            if f"FCJ-{n:03d}" not in man.papers]


def write_known_absent(man: Manifest, path: str = KNOWN_ABSENT) -> list[str]:
    """Write `data/known-absent.txt`. Generated, never hand-edited.

    Invariant 3 requires every FCJ number from 001 to 228 to be either present
    or listed here WITH A REASON. The reason is the point: a bare list of gaps
    reads as an oversight, and the next person to look would spend a day
    rediscovering that FCJ-222 is not recoverable from anything the archive has.
    """
    missing = absent_numbers(man)
    lines = [
        "# FCJ numbers absent from the archive, with the reason for each.",
        "# GENERATED by build/inventory.py — never hand-edited.",
        "#",
        f"# {len(man.papers)} papers held. "
        f"{228 - len(missing)} of the 228 numbered articles are present.",
        "",
    ]
    for ident in missing:
        reason = ABSENT_REASONS.get(ident, "No reason recorded. INVESTIGATE.")
        lines.append(ident)
        lines.extend("    " + part for part in _wrap(reason, 74))
        lines.append("")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines).rstrip() + "\n")
    return missing


def read_known_absent(path: str = KNOWN_ABSENT) -> dict[str, str]:
    """ident -> reason, for the invariant test."""
    out: dict[str, str] = {}
    if not os.path.isfile(path):
        return out
    current = None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            if not line.startswith(" "):
                current = line.strip()
                out[current] = ""
            elif current:
                out[current] = (out[current] + " " + line.strip()).strip()
    return out


def _wrap(text: str, width: int) -> list[str]:
    words_, line, out = text.split(), "", []
    for word in words_:
        if line and len(line) + 1 + len(word) > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out


def check_accounting(man: Manifest) -> list[str]:
    """Every linked page is in exactly one bucket. Returns a list of failures.

    This is the module's own falsification check, kept in the code rather than
    only in the tests because it is cheap and because both earlier throwaway
    versions of this inventory produced totals that looked complete and were
    not. A report that cannot account for its own inputs is not evidence.
    """
    bad: list[str] = []
    for issue, c in man.counts.items():
        placed = (c["papers"] + c["editorials"] + c["unclassified"]
                  + c["unresolved"] + c["furniture"])
        if placed != c["links"]:
            bad.append(f"issue {issue}: {c['links']} links but {placed} accounted for")
    return bad


def _main() -> None:
    man = build()
    print(f"{'issue':<7}{'theme':<44}{'papers':>7}{'uncls':>7}{'unres':>7}{'ed words':>10}")
    for number, _ in ISSUE_HOSTS:
        if number not in man.issues:
            print(f"{number:<7}(no root)")
            continue
        iss = man.issues[number]
        c = man.counts[number]
        print(f"{number:<7}{iss.theme[:43]:<44}{c['papers']:>7}"
              f"{c['unclassified']:>7}{c['unresolved']:>7}{words(iss.editorial_html):>10}")
    total_bytes = sum(man.assets.values())
    print(f"\npapers:        {len(man.papers)}")
    print(f"unclassified:  {len(man.unclassified)}")
    print(f"unresolved:    {len(man.unresolved)}")
    print(f"assets:        {len(man.assets)} ({total_bytes / 1024 / 1024:.0f} MB)")
    print(f"apex-sourced:  {len(man.apex_sourced)} {' '.join(man.apex_sourced)}")
    ed = {}
    for iss in man.issues.values():
        ed[iss.editorial_source] = ed.get(iss.editorial_source, 0) + 1
    print(f"editorials:    {ed}")
    missing = write_known_absent(man)
    print(f"FCJ numbers not present as papers ({len(missing)}): {' '.join(missing)}")
    print(f"  reasons written to {KNOWN_ABSENT}")
    for fail in check_accounting(man):
        print(f"ACCOUNTING: {fail}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    _main()
