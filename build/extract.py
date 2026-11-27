#!/usr/bin/env python3
# Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
"""Write `content/` — the canonical Markdown archive.

Governed by docs/architecture.md ("Content format").

This is the lossy, one-way stage of the build: mirror HTML in, Markdown out.
`generate.py` then renders the site from `content/` and never reads the mirror,
so the text people download from GitHub is exactly the text the website shows.
That is the separation of form and content the archive is for, and it is
enforced by a file boundary rather than by discipline.

Run once, audit the result, and it need not run again. Everything downstream is
cheap to re-run.

FRONT MATTER

A deliberately small YAML subset — scalars and lists of scalars — so that it
parses with the standard library and reads cleanly in a GitHub file view. No
third-party YAML, and nothing nested, because nothing here needs nesting.
"""
from __future__ import annotations

import glob
import os
import re
import shutil
from dataclasses import dataclass
from typing import NamedTuple

import inventory
import markdown
import resolve

SITE = resolve.SITE
CONTENT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "content")

# `abstract\b` and not `abstract`: without the boundary this matched the first
# word of a paper whose opening sentence is about *abstraction*, and silently
# moved that sentence into the front matter.
ABSTRACT = re.compile(r"(?i)^\s*\**\s*abstract\b\s*:?\s*\**\s*:?\s*")
# No trailing \b after `universit`: "University" continues with a word
# character, so `universit\b` never matched and every affiliation was missed.
AFFILIATION_HINT = re.compile(
    r"(?i)\b(universit\w*|college|school of|department|faculty|institute|academy|"
    r"polytechnic|centre for|center for)")


@dataclass
class ExtractReport:
    papers: int = 0
    issues: int = 0
    media: int = 0
    media_bytes: int = 0
    with_authors: int = 0
    without_authors: list[str] = None
    with_abstract: int = 0
    paragraph_numbers: int = 0
    banners: int = 0
    with_editors: int = 0
    full_issue_files: int = 0
    pages: int = 0
    page_assets: int = 0
    recovered_media: int = 0
    dropped_links: int = 0
    journal_kept: bool = False
    pages_missing: list = None
    pruned: list[str] = None

    def __post_init__(self):
        if self.without_authors is None:
            self.without_authors = []
        if self.pruned is None:
            self.pruned = []
        if self.pages_missing is None:
            self.pages_missing = []


# --------------------------------------------------------------------------
# front matter


def dump_front_matter(fields: dict[str, object]) -> str:
    lines = ["---"]
    for key, value in fields.items():
        if value in (None, "", [], {}):
            continue
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines += [f"  - {_scalar(v)}" for v in value]
        else:
            lines.append(f"{key}: {_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def _scalar(value: object) -> str:
    s = str(value)
    # Quote when the value could otherwise be read as something else. Colons
    # are the common case: FCJ titles are full of them ("Babylonian Dreams:
    # From Info-Cities to Smart Cities").
    if re.search(r'^[\s>|&*!%@`\[{]|[:#]\s|\s$|^$|^-|"', s) or s != s.strip():
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def parse_front_matter(text: str) -> tuple[dict[str, object], str]:
    """Inverse of dump_front_matter. Returns (fields, body)."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 3)
    if end == -1:
        return {}, text
    fields: dict[str, object] = {}
    key = None
    for line in text[4:end + 1].split("\n"):
        if not line.strip():
            continue
        if line.startswith("  - ") and key:
            fields.setdefault(key, [])
            if not isinstance(fields[key], list):
                fields[key] = []
            fields[key].append(_unscalar(line[4:]))
        elif ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            fields[key] = _unscalar(value) if value else []
    return fields, text[end + 5:].lstrip("\n")


def _unscalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


# --------------------------------------------------------------------------
# splitting article front matter out of the prose


def take_abstract(md: str) -> tuple[str, str]:
    """Pull an "Abstract:" paragraph out of the body into front matter.

    An abstract is metadata about the article, not part of its argument, and
    putting it in front matter lets the site present it as an abstract and lets
    anyone reusing the text find it without parsing prose. Only a block that
    actually opens with the word is taken, and only the first one.
    """
    blocks = md.split("\n\n")
    for i, block in enumerate(blocks):
        if ABSTRACT.match(block):
            abstract = ABSTRACT.sub("", block).strip()
            # a bare "Abstract" heading with the text in the next block
            if not abstract and i + 1 < len(blocks):
                abstract = blocks[i + 1].strip()
                del blocks[i + 1]
            del blocks[i]
            return markdown.strip_paragraph_numbers(abstract), "\n\n".join(blocks).strip() + "\n"
    return "", md


DOI_LINE = re.compile(r"(?im)^\s*\**\s*doi\s*:?\s*\**\s*\[?[^\n]*10\.\d{4,9}/[^\n]*$")


# ---- issue-root cleanup
#
# An issue root is a WordPress landing page, so it carries furniture the
# archive generates for itself. Left in, issue 29 opened with an empty `####`
# heading, a PDF icon GIF, and the words "Issue:pdf" — which is what a link
# label looks like once its target has gone.
EMPTY_HEADING = re.compile(r"(?m)^\s*#{1,6}\s*$")

# The apparatus at the end of an article: what follows the argument rather
# than continuing it.
#
# The apostrophe class is load-bearing: the mirror uses a curly `’`, and
# `Authors’ Biographies` failed to match a pattern written for `Author's`.
# Because the cut is the TRAILING RUN, one unmatched heading in the middle of
# the apparatus stops the walk — so that single miss left `Notes` numbered in
# ten papers, which is the defect this function exists to fix.
APPARATUS_HEADING = re.compile(
    r"(?i)^(notes?|endnotes?|references?|works\s+cited|bibliography|"
    # `Appendix I`, `Appendix: Participants' responses to the artist's
    # question` — an appendix is titled, so it cannot be matched as a bare
    # word. `Artworks` is the same kind of end-matter list as `References`.
    r"acknowledge?ments?|appendi(?:x|ces)\b[^\n]*|artworks?|"
    # `Thanks` and `Journal Note` are end-matter under other names.
    r"thanks|journal\s+notes?|sites?|websites?|"
    r"authors?['’’]?s?\s+bio\w*|biographical\s+notes?|"
    r"bio\w*\s+notes?)\s*:?$")
ANY_HEADING = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")


def unnumber_apparatus(md: str) -> str:
    """Stop the paragraph numbers at the end of the main text.

    The numbers are the journal's citable unit, and they ran on into the
    notes, references and biographies — 5,307 of 17,796 of them, in 217 of 237
    papers. In an offprint they are set in the margin, so a reference list
    arrived with a numbered rail beside it, implying a reference can be cited
    by paragraph. That is not what the numbering is for.

    The cut is NOT the first apparatus heading. Eight papers have a `Note`
    heading inside the main text, and cutting there would unnumber the rest of
    the article — destroying the citable unit for most of a paper in order to
    tidy up its reference list.

    Instead: walk back from the end while each heading is apparatus, and cut at
    the start of that unbroken TRAILING run. A `Note` section followed by
    `Discussion` is not in the run, so it keeps its numbers. The rule reads a
    property of the document rather than a list of filenames.
    """
    headings = list(ANY_HEADING.finditer(md))
    if not headings:
        return md
    cut = None
    for match in reversed(headings):
        if not APPARATUS_HEADING.match(match.group(2).strip(" *_#")):
            break
        cut = match.start()
    if cut is None:
        return md
    return md[:cut] + markdown.strip_paragraph_numbers(md[cut:])
# The old theme's own interface images — `PDFicon.gif`, `epub.gif`,
# `favicon2.ico` — which WordPress rendered beside download links. The archive
# prints those links as text, so these are chrome from a design that is gone.
#
# The `(?:\.\./)*` is not decoration. This rule was written against the
# root-relative `/media/…` the rewriter used to emit; when the archive moved to
# relative paths it silently stopped matching, and the icons came back on three
# issue pages. A path-shaped regex has to accept both shapes or it rots the
# next time the convention changes.
THEME_IMAGE = re.compile(
    r"!\[[^\]]*\]\((?:\.\./)*/?media/[^)]*/wp-content/themes/[^)]*\)")
# `Issue: pdf`, and also `Issue:ePubIssue:pdf   Editorial:pdf` — the download
# labels the old theme rendered beside its icons. The archive prints its own
# download links from front matter, so these are duplicates of what it already
# knows.
#
# A RUN of pairs, not one: the source had them in adjacent inline elements, so
# they collapse onto a single line with no separator, and the earlier
# one-pair-per-line rule left them in issue 20's editorial. The leading
# whitespace is load-bearing too — four spaces made the line an indented code
# block, which is why it rendered in a monospace box.
ORPHAN_PDF_LABEL = re.compile(
    r"(?im)^[ \t]*(?:(?:issue|editorial|article|full\s*issue)\s*:\s*"
    r"(?:pdf|epub)[ \t]*)+$")
ISSUE_DOI = re.compile(
    r"(?im)^\s*\**\s*(issue|introduction)\s+doi\s*:?\s*\**\s*:?\s*"
    r"\[?(10\.\d{4,9}/[^\s\]]+)\]?.*$")
# A block that is ONLY a link to a paper: the hand-written table of contents.
# A paper cited inside a sentence is not this, which is the discriminator.
CONTENTS_LINK = re.compile(r"^\s*\[[^\]]+\]\(/papers/[^)]+/\)\s*$")
# The author line that follows such a link in the hand-written list.
NAME_ONLY = re.compile(r"^\s*[A-Z][\w’'.-]+(?:\s+[A-Z][\w’'.-]+){0,3}"
                       r"(?:\s*(?:,|and)\s*[A-Z][\w’'.-]+(?:\s+[A-Z][\w’'.-]+){0,3})*\s*$")
# The heading the hand-written contents sat under. Removing the list without
# it leaves a bare "Articles" at the foot of the page.
CONTENTS_HEADING = re.compile(
    r"(?i)^#{2,6}\s*(articles?|contents|in this issue|table of contents)\s*$")


def take_issue_doi(md: str) -> tuple[str, str]:
    """Lift `issue doi: 10.15307/fcj.29` out of the body into front matter."""
    doi = ""
    for match in ISSUE_DOI.finditer(md):
        if match.group(1).lower() == "issue" or not doi:
            doi = match.group(2).rstrip(".)")
        md = md.replace(match.group(0), "")
    return doi, md


def strip_issue_furniture(md: str) -> str:
    """Remove what the archive renders for itself from an issue's editorial.

    The hand-written contents list is the important one. Four issues take their
    editorial from the issue ROOT, which ends with the issue's own table of
    contents — every paper linked, with its author underneath. The archive
    generates that list from the manifest and puts it above the editorial, so
    leaving the original in prints the whole issue twice.
    """
    md = THEME_IMAGE.sub("", md)
    md = EMPTY_HEADING.sub("", md)
    md = ORPHAN_PDF_LABEL.sub("", md)
    md = CONTINUE_READING.sub("", md)

    blocks = md.split("\n\n")
    kept: list[str] = []
    for i, block in enumerate(blocks):
        if CONTENTS_LINK.match(block):
            continue
        # A bare name directly after a contents link is that entry's author.
        if (NAME_ONLY.match(block) and len(block.split()) <= 6 and i
                and CONTENTS_LINK.match(blocks[i - 1])):
            continue
        kept.append(block)
    # The heading that introduced the list has to go with it. Issues 20, 28
    # and 29 ended on a bare "#### Articles" with nothing beneath it once the
    # hand-written contents was removed.
    while kept and (CONTENTS_HEADING.match(kept[-1].strip())
                    or not kept[-1].strip()):
        kept.pop()

    md = "\n\n".join(kept)
    md = re.sub(r"(?m)^[ \t]+$", "", md)
    return re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"


def take_doi_line(md: str) -> str:
    """Remove the printed `doi:` line once the DOI is in front matter.

    Leaving it would print the DOI twice on the page and leave a bare
    identifier at the top of the text someone downloads as the article.
    """
    return "\n\n".join(b for b in md.split("\n\n") if not DOI_LINE.fullmatch(b.strip())).strip() + "\n"


# ---- issue editors
#
# The journal credited issue editors three different ways, and the WordPress
# theme presented them through metadata inserts that the crawl flattened into
# ordinary prose. They have to be recovered from the text and shown at the top
# of the issue, where a reader looks for them.
#
#   1. `###### Issue Edited by Armin Beverungen, Florian Sprenger, Susan Ballard`
#   2. `Introduction by **Armin Beverungen** of Leuphana University Lüneburg
#       and **Florian Sprenger** of Goethe University Frankfurt.`
#   3. bios near the end: `[Tanya Notley](…) is a Lecturer in Internet Studies…`
#
# (2) is the only one that carries institutions, so it wins where both exist.
EDITED_BY = re.compile(
    r"(?im)^\s*#*\s*(?:issue\s+)?edited\s+by[:\s]+(.{3,160}?)\s*$")
INTRO_BY = re.compile(r"(?im)^\s*Introduction\s+by\s+(.{3,400}?)\s*$")
# `**Name** of Institution`, the pairing used in (2).
# The institution must not cross an asterisk: with `[^,.]` it ran straight
# through "and **Florian Sprenger** of …" and gave the first editor an
# institution containing the second editor's name.
NAMED_OF = re.compile(r"\*\*([^*]{3,60})\*\*\s*(?:of\s+(?:the\s+)?([^,.*]{3,120}))?")
# A bio paragraph: a name, optionally linked, then "is a/is the/is Director…".
BIO = re.compile(
    r"^\s*(?:\[([^\]]{3,60})\]\([^)]*\)|\*\*([^*]{3,60})\*\*|([A-Z][\w’'-]+"
    r"(?:\s+[A-Z][\w’'’-]+){1,3}))\s+(is\s+(?:a|an|the|currently)?\s*[^.]{10,}\.)")
# "Lone Bertelsen, Issue Editor" — the role written into the name.
ROLE_SUFFIX = re.compile(
    r"(?i)\s*[,–—-]?\s*\(?\b(issue\s+)?(guest\s+)?editors?\b\)?\s*$")


def clean_editor_name(name: str) -> str:
    """A person's name, with markup and any role written into it removed.

    Issue 30 prints `**Lone Bertelsen***, Issue Editor*` — the role is inside
    the emphasis, so a reader of the raw text sees "Lone Bertelsen, Issue
    Editor" as though that were the name.
    """
    name = re.sub(r"[*_`\[\]]", "", name).strip()
    name = re.sub(r"\(.*?\)", "", name).strip()
    name = ROLE_SUFFIX.sub("", name).strip(" ,.;:–—-")
    return re.sub(r"\s+", " ", name)


def _split_names(text: str) -> list[str]:
    text = re.sub(r"(?i)\s+and\s+", ", ", re.sub(r"[*_]", "", text))
    return [clean_editor_name(part) for part in text.split(",")
            if clean_editor_name(part)]


def take_editors(md: str, *, heading_only: bool = True) -> tuple[list[str], str]:
    """Pull the issue's editors out of the prose. Returns (editors, body).

    Each entry is `Name` or `Name, Institution`, which is how a byline reads
    and matches the shape of a paper's `authors` plus `affiliation`.
    """
    editors: dict[str, str] = {}
    drop: list[str] = []

    for match in EDITED_BY.finditer(md):
        line = match.group(0)
        # Guard: "edited by" also appears inside prose citing other people's
        # books — "an anthology edited by Ulrik Ekman presents…". Only a line
        # that is ENTIRELY the credit counts, which in practice means it is a
        # heading or a short standalone line.
        if len(line.strip()) > 170:
            continue
        if heading_only and not re.match(r"\s*#", line):
            continue
        # On an issue ROOT the credit is a standalone line rather than a
        # heading, so headings cannot be required there. The guard instead is
        # that a credit names people and stops: a sentence citing someone
        # else's edited book runs on past the names.
        if not heading_only and not re.match(r"\s*#", line):
            names_part = match.group(1).strip()
            if len(names_part) > 120 or re.search(r"[.;:]\s*\S", names_part):
                continue
        for name in _split_names(match.group(1)):
            editors.setdefault(name, "")
        drop.append(line)

    for match in INTRO_BY.finditer(md):
        line = match.group(0)
        if "{#para" in line and len(line) > 400:
            continue
        pairs = NAMED_OF.findall(match.group(1))
        if pairs:
            for raw_name, institution in pairs:
                name = clean_editor_name(raw_name)
                if name:
                    # "Leuphana University Lüneburg and" — the conjunction
                    # joining this editor to the next one is not part of the
                    # institution's name.
                    inst = re.sub(r"(?i)\s+(and|&)\s*$", "",
                                  re.sub(r"\s+", " ", institution).strip(" .,"))
                    editors[name] = inst
            drop.append(line)
        elif len(match.group(1)) < 120:
            for name in _split_names(match.group(1)):
                editors.setdefault(name, "")
            drop.append(line)

    if not editors:
        for block in md.split("\n\n"):
            found = BIO.match(block.strip())
            if found:
                name = clean_editor_name(
                    found.group(1) or found.group(2) or found.group(3) or "")
                if name:
                    editors.setdefault(name, "")

    for line in drop:
        md = md.replace(line, "")
    out = [f"{name}, {inst}" if inst else name for name, inst in editors.items()]
    return out, re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"


def merge_editors(primary: list[str], secondary: list[str]) -> list[str]:
    """Combine two credit lists, keeping the richer entry for each person.

    The issue root usually gives the full list of names; the editorial's
    "Introduction by **Name** of Institution" sentence gives institutions for
    one or two of them. Neither source alone is complete.
    """
    merged: dict[str, str] = {}
    for entry in list(primary) + list(secondary):
        name, _, institution = str(entry).partition(", ")
        name = name.strip()
        if not name:
            continue
        if institution.strip() or name not in merged:
            merged[name] = institution.strip() or merged.get(name, "")
    return [f"{n}, {i}" if i else n for n, i in merged.items()]


def take_byline(md: str, names: list[str]) -> tuple[str, str]:
    """Remove the printed byline and affiliation from the top of the body.

    The site re-renders authorship from front matter, so leaving the byline in
    the prose would print it twice and would also leave the author's name inside
    the text someone downloads as the article. Only leading blocks are
    considered, only ones that match an author name the page's own citation
    metadata already gave, plus an immediately following affiliation line — so
    a paper that happens to name its author in the first sentence of the
    argument is untouched.
    """
    if not names:
        return "", md
    surnames = [n.split()[-1].lower() for n in names if n.split()]
    blocks = md.split("\n\n")
    affiliation = ""
    taken = 0
    for block in blocks[:4]:
        # Collapse whitespace: the byline is often ONE emphasised run with a
        # line break inside it — `**Ned Rossiter\n Communications and Media
        # Studies, … Monash University**` — and a newline left in the middle
        # stops the name ever matching the start of the line.
        plain = re.sub(r"\s+", " ", re.sub(r"[#*_]|\{#para\d+\}", "", block)).strip()
        if not plain:
            taken += 1
            continue
        low = plain.lower()
        # A byline STARTS with the author's name. Merely containing it is not
        # enough: raising a length limit to catch "Ned Rossiter <affiliation>"
        # also caught "As Paula Bialski argues at length in her earlier
        # work…", which would have deleted the opening sentence of a paper.
        # The short-block case stays for bylines written as just a surname.
        starts_with_name = any(plain.lower().startswith(n.lower()) for n in names)
        is_name = starts_with_name or (
            len(plain) < 60 and any(s in low for s in surnames))
        is_affil = len(plain) < 200 and bool(AFFILIATION_HINT.search(plain)) and taken > 0
        if is_name or is_affil:
            # The name and the affiliation are often ONE line: FCJ-001 opens
            # "Ned Rossiter Communications and Media Studies, School of
            # Political and Social Inquiry, Monash University". Taking only
            # blocks that are purely an affiliation found 41 of 237; splitting
            # the byline at the end of the author's name finds the rest.
            if is_name and not affiliation:
                # Split after the AUTHOR'S NAME, not at the affiliation hint.
                # Splitting at the hint put the break inside the affiliation:
                # "Ned Rossiter Communications and Media Studies, | School of
                # Political and Social Inquiry, Monash University".
                for full_name in names:
                    if plain.lower().startswith(full_name.lower()):
                        rest = plain[len(full_name):].strip(" ,.–—-")
                        if rest and AFFILIATION_HINT.search(rest):
                            affiliation = rest
                        break
            if is_affil and not affiliation:
                affiliation = plain
            taken += 1
            continue
        break
    if not taken:
        return "", md
    rest = "\n\n".join(blocks[taken:]).lstrip("-\n ").strip()
    return affiliation, rest + "\n"


# --------------------------------------------------------------------------
# url rewriting into archive paths


def make_rewriter(man: inventory.Manifest, host: str, static_root: str,
                  *, from_dir: str = "papers",
                  used_recovered: set[str] | None = None):
    """Rewrite a mirror URL to a path inside `content/`, or leave it external.

    Paths are RELATIVE to the file being written, not root-relative. A
    root-relative `/media/…` resolves on the website and nowhere else: in a
    GitHub file view it points at the repository root rather than the file, and
    in a local editor, or in a single `.md` someone downloaded, it is broken.
    The archive promises text that can be reused without the website, so the
    links have to work without it.

    `from_dir` is the directory the file being written lives in, so the depth
    is computed rather than written as a literal `../`.
    """
    up = "../" * len(from_dir.strip("/").split("/"))
    from urllib.parse import urljoin, urlsplit

    paper_by_source = {p.source: p for p in man.papers.values()}
    issue_by_source: dict[str, str] = {}
    for number, iss in man.issues.items():
        if iss.editorial_path:
            issue_by_source[iss.editorial_path] = number
        root = resolve.local_path(dict(inventory.ISSUE_HOSTS)[number], "/", static_root)
        if root:
            issue_by_source.setdefault(root, number)

    def rewrite(raw: str) -> str:
        href = resolve.clean_href(raw)
        if not href or href.startswith(("mailto:", "javascript:", "data:", "tel:", "#")):
            return raw
        parts = urlsplit(urljoin(f"https://{resolve.host_dir(host)}/", href))
        netloc = parts.netloc.lower().removeprefix("www.")
        if netloc and not netloc.endswith(SITE):
            # Off-domain, but the archive may hold a recovered copy. 85 files
            # are referenced on `journal.fibreculture.org`, the journal's
            # pre-2008 domain, which the crawl never entered; the live host
            # now returns 503, so leaving the absolute URL publishes a figure
            # that cannot load. Point at the recovered copy instead.
            found = resolve.recovered_path(netloc, parts.path)
            if found is not None:
                if used_recovered is not None:
                    used_recovered.add(found)
                return up + recovered_rel(found)
            return parts.geturl()
        target = netloc or resolve.host_dir(host)
        local, _ = inventory.resolve_with_apex(target, parts.path, static_root)
        frag = f"#{parts.fragment}" if parts.fragment else ""
        if local is not None:
            # Always with the directory segment, even for a sibling. Writing a
            # sibling as a bare filename made `issues/19.md` link another issue
            # as `19.md`, which is indistinguishable from a paper filename —
            # the renderer turned it into `/papers/19/`, a 404.
            if local in paper_by_source:
                return f"{up}papers/{paper_dir(paper_by_source[local])}.md{frag}"
            if local in issue_by_source:
                return f"{up}issues/{issue_by_source[local]}.md{frag}"
            if os.path.relpath(local, static_root) in man.assets:
                return up + media_rel(local, static_root)
        # Inside the journal's own domains, but not something the archive
        # publishes: a category listing, a date archive, or a URL that never
        # worked (one paper cites `.../N.d.` as a link). Returning the old
        # absolute URL would put links into the archive that are dead by
        # construction, since those hosts are going away. Returning "" keeps
        # the author's link TEXT and drops the anchor, so the sentence still
        # reads and nothing pretends to be clickable.
        return ""

    return rewrite


def paper_dir(paper: inventory.Paper) -> str:
    """`fcj-218-train-ticket-sharing…` — the id first, then the slug.

    The id leads because it is the only identity stable across the mirror's five
    slug conventions, and because a reader holding a citation ("FCJ-218") can
    find the paper by typing the start of the path.

    Where the historical slug is only the number in another spelling — issue 1
    writes `fcj002` — the slug adds nothing and is dropped, so FCJ-002 lives at
    `/papers/fcj-002/` rather than the tautological `/papers/fcj-002-fcj002/`.
    """
    ident = paper.fcj_id.lower()
    slug = paper.slug.lower()
    if not slug:
        return ident
    if slug.startswith(ident):
        return slug
    squash = lambda s: re.sub(r"[^a-z0-9]", "", s)       # noqa: E731
    if squash(slug) == squash(ident):
        return ident
    return f"{ident}-{slug}"


def media_rel(source: str, static_root: str) -> str:
    return "media/" + os.path.relpath(source, static_root)


# An absolute URL to a media file on a host the crawl could not reach, found
# anywhere in the body text. `make_rewriter` only sees Markdown link targets,
# so it misses two shapes that are common in the early issues: a raw
# `<img src="https://journal.fibreculture.org/images/melinda1.jpg">` inside
# HTML this dialect passes through untouched, and a bare URL in running text.
# 13 recovered files were referenced only that way.
#
# Restricted to MEDIA extensions on purpose. A bare URL in a reference list is
# a citation, and rewriting a citation's target to a local path would corrupt
# what an author wrote; a figure or a supplementary PDF is not a citation.
OFF_DOMAIN_MEDIA = re.compile(
    r"(?i)\bhttps?://([a-z0-9.-]+\.[a-z]{2,})(/[^\s\"'<>)\]]*"
    r"\.(?:jpe?g|png|gif|pdf|mov|mp4|mp3))")


def point_at_recovered(md: str, up: str,
                       used_recovered: set[str] | None = None) -> str:
    """Repoint off-domain media URLs at the archive's recovered copies."""
    def swap(match: re.Match[str]) -> str:
        host, path = match.group(1).lower(), match.group(2)
        found = resolve.recovered_path(host, path)
        if found is None:
            return match.group(0)
        if used_recovered is not None:
            used_recovered.add(found)
        return up + recovered_rel(found)
    return OFF_DOMAIN_MEDIA.sub(swap, md)


def recovered_rel(source: str) -> str:
    """A recovered file's path inside `content/`.

    Deliberately the same `media/<host>/<path>` shape as a mirror asset, so a
    reader does not have to care which input a figure came from — while
    `recovered/MANIFEST.tsv` still records, for anyone who does care, exactly
    which snapshot each one was taken from.
    """
    return "media/" + os.path.relpath(source, resolve.RECOVERED_ROOT)


# ---- institutional pages
#
# A journal's standing rests on being able to show who edits it, how it
# reviews, and who preserves it. An archive of the articles alone silently
# demotes a peer-reviewed journal to a pile of PDFs.
#
# The list is EXPLICIT, never a directory scan: the same directory on the apex
# host holds `write-for-us-sponsored-posts`, which is an artefact of the
# compromise, and several hundred category and date-archive pages.
#
# `title` here overrides the page's own, which is a WordPress slug in two
# cases: `policy-and-style` is a poor public name for the page that holds the
# editorial board, the review policy and the submission guidelines.
class Page(NamedTuple):
    """One institutional page, and where in the mirror to find it."""

    source: str         # slug on the apex host
    slug: str           # slug this archive publishes it at — a permanent URL
    title: str          # overrides the page's own WordPress title
    order: int          # position in the header nav


INSTITUTIONAL_PAGES = [
    Page("about", "about", "About the Journal", 1),
    Page("policy-and-style", "editorial-and-guidelines",
         "Editorial Board, Policy and Guidelines", 2),
]


# The archive's ONE departure from the pages as crawled.
#
# Everything else here is faithful: the extractor reproduces what the mirror
# said, errors included, because an archive that quietly improves its source
# cannot be cited. A correction therefore needs three things — a scope narrow
# enough that it cannot hit anything else, a stated reason, and a record. The
# record is `content/corrections.md`, generated from this list, so there is no
# second copy to keep in step.
#
# Scoped to a SECTION of a page, not the whole page, because "Andrew Murphie"
# is also one of the five Journal Editors on this same page and must not be
# touched there.
CORRECTIONS = [
    {
        "slug": "editorial-and-guidelines",
        "section": "Journal Manager",
        "old": "Andrew Murphie",
        "new": "Mat Wall-Smith",
        "reason": ("The apex page names Andrew Murphie as journal manager; he "
                   "never held that role. Mat Wall-Smith was journal manager, "
                   "from Issue 15 (Remix, 2010) — corroborated by the Issue 18 "
                   "editorial, which thanks “the Fibreculture Journal’s "
                   "manager, Mat Wall-Smith”, and by the apex Trans issue "
                   "page, which calls him “our journal editor”. "
                   "Corrected on the request of the journal's editors."),
    },
    {
        "slug": "editorial-and-guidelines",
        "section": "Journal Editors",
        "old": "Mat Wall-Smith (Independent scholar, Wollongong)",
        "new": "Mat Wall-Smith (University of Wollongong)",
        "reason": ("Affiliation out of date on the crawled page. Corrected on "
                   "the request of the journal's editors."),
    },
]


SECTION = re.compile(r"(?m)^##+ ")


def apply_corrections(slug: str, md: str) -> str:
    """Apply any correction declared for this page, within its section only."""
    for fix in CORRECTIONS:
        if fix["slug"] != slug:
            continue
        start = None
        for match in SECTION.finditer(md):
            line_end = md.find("\n", match.end())
            heading = md[match.end():line_end if line_end > 0 else len(md)]
            if heading.strip() == fix["section"]:
                start = line_end
            elif start is not None:
                md = (md[:start] + md[start:match.start()]
                      .replace(fix["old"], fix["new"]) + md[match.start():])
                start = None
                break
        if start is not None:                       # last section on the page
            md = md[:start] + md[start:].replace(fix["old"], fix["new"])
    return md


# A paragraph that is entirely bold and ends in a colon was a heading in the
# original page — "**Journal Editors:**", "**Editorial Policy:**". WordPress
# styled them rather than marking them up, which leaves a 1,730-word page of
# board members and submission guidelines with no structure at all.
PSEUDO_HEADING = re.compile(r"^\*\*([^*]{2,70}?):?\*\*:?$")
# A list item that begins with its own dash: `- – informational logics`. The
# mirror's `<li>` carried a literal en-dash as text, because the old theme's
# list styling showed no marker, so the dash WAS the bullet. Rendered here it
# doubles up — a bullet and then a dash.
#
# Applied in `structure_page`, which only institutional pages go through, and
# deliberately not in `markdown.py`: FCJ-134 and FCJ-119 open list items with
# the same dash to introduce propositions quoted from a cited framework. That
# is the authors' prose under CC BY-NC-ND, and a rule in the shared converter
# would silently edit it. Scoping by call site rather than by a cleverer
# pattern means papers cannot be touched even if this rule is later widened.
#
# The trailing `\s` matters: it distinguishes a bullet-substitute from a dash
# that opens a compound, which has no space after it.
LIST_DASH = re.compile(r"(?m)^(\s*[-*+]\s+)[–—-]\s+")
# "Page Navigation: :: editorial policy :: style …" — in-page anchors that no
# longer exist, listing sections that are now headings in their own right.
PAGE_NAV = re.compile(r"(?s)^\s*\*\*Page Navigation:?\*\*.*?(?=\n\n)")
# The menu ITSELF, which is a separate <p> from its "Page Navigation:" label —
# so removing the label left the links behind:
#
#     :: editorial board and management
#     :: editorial policy
#     :: guidelines for submission
#
# They were `<a href="#managed">` in-page anchors. The archive emits no
# `<a name>` targets, and every section they point at is now a real heading, so
# they are dead links to content that is still there.
#
# Anchored to LINE-INITIAL `::` in a LEADING block, because `::` is also an
# authored separator in the About page's list of topics — mid-line, never at
# the start — and `::: embed` is a fence in the Markdown dialect.
NAV_ITEMS = re.compile(r"(?m)^\s*::\s+\S")
# `^ top` — a jump-to-top anchor. Its target was an `<a name>` the archive does
# not emit, so it is a dead control, and it appears six times on one page.
# Matched wherever it falls, including welded to the end of a link's text, which
# is how `[email editors](mailto:…)^ top` reaches the Markdown.
TOP_ANCHOR = re.compile(r"(?m)[ \t]*\^[ \t]*top[ \t]*$")
# WordPress's excerpt link, pointing at the page it is already on.
CONTINUE_READING = re.compile(
    r"(?im)^\s*\[continue reading[^\]]*\]\([^)]*\)\s*(\{#para\d+\})?\s*$")


# `#### **editor**` — the mirror puts the heading text in bold INSIDE the
# heading. Harmless in HTML, but it leaves literal asterisks in the Markdown
# and in any renderer's table of contents.
BOLD_HEADING = re.compile(r"^(#{1,6})\s*\*\*(.+?)\*\*\s*$", re.M)
HEADING = re.compile(r"^(#{1,6})\s+(.*)$", re.M)


def structure_page(md: str) -> str:
    """Give an institutional page the headings its styling implied."""
    md = LIST_DASH.sub(r"\1", md)
    md = PAGE_NAV.sub("", md, count=1)
    md = TOP_ANCHOR.sub("", md)
    # Leading nav blocks only: walk from the top and stop at the first block
    # that is not a menu, so an authored `::` further down is never touched.
    blocks = md.split("\n\n")
    while blocks:
        first = blocks[0].strip()
        if not first:
            blocks.pop(0)
            continue
        lines = [ln for ln in first.splitlines() if ln.strip()]
        if lines and all(NAV_ITEMS.match(ln) for ln in lines):
            blocks.pop(0)
            continue
        break
    md = "\n\n".join(blocks)
    out = []
    for block in md.split("\n\n"):
        match = PSEUDO_HEADING.match(block.strip())
        out.append(f"## {match.group(1).strip()}" if match else block)
    md = "\n\n".join(out)
    md = BOLD_HEADING.sub(lambda m: f"{m.group(1)} {m.group(2).strip()}", md)
    # A heading glued to the paragraph under it renders correctly but reads
    # badly in the file, and the file is the published artifact.
    md = re.sub(r"^(#{1,6} .*)\n(?=[^\n#])", r"\1\n\n", md, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"


def write_status(out_dir: str, man: inventory.Manifest,
                 report: "ExtractReport",
                 written_pages: set[str] | None = None) -> None:
    """`content/pages/publication-status.md` — the journal has closed.

    Replaces the mirror's "Where to Next?" page, which was written while the
    journal was still running and now reads as a plan rather than a record.

    The year comes from `journal.md`, not from a literal here, so it is changed
    in one place. The last issue is named from the manifest so the claim is
    checkable against the archive's own contents rather than asserted.
    """
    meta = read_journal(out_dir)
    year = str(meta.get("ceased") or "").strip()
    if not year:
        report.pages_missing.append("publication-status (no `ceased` in journal.md)")
        return
    title = str(meta.get("title") or "The journal")
    numbers = [n for n in man.issues if n.isdigit()]
    last = max(numbers, key=int) if numbers else ""
    lines = [f"*{title}* ceased publishing in {year}."]
    front = {
        "title": f"Ceased Publication {year}",
        "nav_order": 3,
        "journal": title,
    }
    target = os.path.join(out_dir, "pages", "publication-status.md")
    _write(target, dump_front_matter(front) + "\n".join(lines).strip() + "\n")
    if written_pages is not None:
        written_pages.add(target)
    report.pages += 1


def page_assets(doc: str, host: str, static_root: str,
                man: inventory.Manifest) -> list[str]:
    """Files an institutional page offers for download, added to the manifest.

    The manifest is built by walking issue roots and papers, so it never saw
    these — and `make_rewriter` drops any internal link whose target is not in
    it. The journal's four procedural forms (the referee's report, the issue
    editor agreement, the author forms, and the full FCJ Guidelines 2014) were
    therefore published as plain text with no link at all: the only copies of
    the documents the journal's own peer review ran on.

    Registering them in the manifest is what makes the rewriter resolve them;
    the caller copies them. Returns the local paths it added.
    """
    added = []
    for path in inventory.page_links(inventory.content_of(doc), host):
        if not inventory.is_asset(path):
            continue
        local, _ = inventory.resolve_with_apex(host, path, static_root)
        if local is None or inventory.in_code_theme(local):
            continue
        rel = os.path.relpath(local, static_root)
        if rel not in man.assets:
            man.assets[rel] = os.path.getsize(local)
        added.append(local)
    return added


def write_pages(man: inventory.Manifest, out_dir: str, static_root: str,
                report: "ExtractReport",
                written_pages: set[str] | None = None,
                written_media: set[str] | None = None,
                used_recovered: set[str] | None = None) -> None:
    """Extract the journal's institutional pages into `content/pages/`."""
    written_pages = written_pages if written_pages is not None else set()
    for page in INSTITUTIONAL_PAGES:
        host = resolve.SITE
        local, _ = inventory.resolve_with_apex(
            host, "/" + page.source, static_root)
        if local is None:
            report.pages_missing.append(page.source)
            continue
        doc = inventory.read(local)
        for source in page_assets(doc, host, static_root, man):
            rel = media_rel(source, static_root)
            _copy(source, os.path.join(out_dir, rel))
            if written_media is not None:
                written_media.add(os.path.join(out_dir, rel))
            report.page_assets += 1
        rewrite = make_rewriter(man, host, static_root, from_dir="pages",
                                used_recovered=used_recovered)
        body = markdown.to_markdown(inventory.content_of(doc), rewrite)
        body = strip_issue_furniture(body)
        body = structure_page(body)
        body = apply_corrections(page.slug, body)
        if inventory.words(body) < 50:
            report.pages_missing.append(f"{page.source} (too thin)")
            continue
        front = {
            "title": page.title,
            "nav_order": page.order,
            "journal": "The Fibreculture Journal",
            "source_url": f"https://{host}/{page.source}/",
            "source_file": os.path.relpath(local, static_root),
        }
        target = os.path.join(out_dir, "pages", page.slug + ".md")
        _write(target, dump_front_matter(front) + body)
        written_pages.add(target)
        report.pages += 1


def read_journal(out_dir: str) -> dict:
    """`journal.md`'s front matter, or {} before it has been seeded."""
    path = os.path.join(out_dir, "journal.md")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        meta, _body = parse_front_matter(fh.read())
    return meta


# `content/journal.md` — journal-level metadata, read by the renderer instead
# of FCJ's details sitting in Python string literals. SEEDED ONCE and then
# hand-maintained: it is the only file in `content/` that is not regenerated,
# because it is the file another journal edits to adopt this archive.
JOURNAL_SEED = {
    "title": "The Fibreculture Journal",
    "issn": "1449-1443",
    "publisher": "Open Humanities Press",
    "publisher_url": "https://openhumanitiespress.org/",
    "licence": "CC BY-NC-ND",
    "licence_url": "https://creativecommons.org/licenses/by-nc-nd/4.0/",
    "founded": "2003",
    "ceased": "2019",
    # Verbatim. A LOCKSS crawler looks for this exact sentence, so it is
    # functional text, not a caption — in the mirror it survived only as the
    # `title` attribute of a GIF, where it does nothing.
    "lockss_statement": ("LOCKSS system has permission to collect, preserve, "
                         "and serve this open access Archival Unit."),
    "contact": "fcjeditor@gmail.com",
}


def write_journal(out_dir: str, report: "ExtractReport") -> None:
    path = os.path.join(out_dir, "journal.md")
    if os.path.isfile(path):
        report.journal_kept = True
        return
    _write(path, dump_front_matter(JOURNAL_SEED) + (
        "Journal-level metadata. **This file is seeded once and then yours** — "
        "`extract.py` will not overwrite it.\n\nThe renderer reads the footer "
        "indicators, the licence and the ISSN from here, so another journal "
        "adopting this archive edits this file rather than the code.\n"))


# ---- whole-issue compilations
#
# `wp-content/pdfs/FC29_FullIssue.pdf` and `wp-content/ePubs/FC29_FullIssue.epub`.
# Nothing links them, so the link-driven inventory never sees them and they are
# not in `Manifest.assets` — which is how they silently stopped shipping when
# the render stage moved to reading `content/` alone. They are found the only
# way they can be: by their filename.
FULL_ISSUE = re.compile(r"FC(\d{1,2})_FullIssue\.(pdf|epub)$", re.I)


def full_issue_files(static_root: str) -> dict[str, dict[str, str]]:
    """issue number -> {"pdf": path, "epub": path} in the mirror."""
    found: dict[str, dict[str, str]] = {}
    for dirpath, _dirs, files in os.walk(static_root):
        for name in files:
            match = FULL_ISSUE.match(name)
            if match:
                found.setdefault(str(int(match.group(1))), {})[
                    match.group(2).lower()] = os.path.join(dirpath, name)
    return found


# ---- issue banners
#
# The old WordPress themes carried a header strip per issue. 13 of the 31 have
# their own artwork and it is specific to the issue — the Konami code for the
# games issue, phones with hearts for Apps and Affect, an aerial photograph for
# Computing The City. The other 18 shared one generic strip, which is not an
# identity and is not extracted.
#
# This lives in `extract`, not in `generate`, because it reads the MIRROR, and
# the render stage must never do that. `generate` decides whether to show the
# banner; it does not go looking for one.
BANNER_NAMES = ("home_banner.jpg", "home_banner.png",
                "archive_banner.jpg", "archive_banner.png")


def banner_source(number: str, static_root: str) -> str | None:
    """The issue's OWN header image, or None. Never the shared generic one."""
    host = dict(inventory.ISSUE_HOSTS).get(number)
    if not host:
        return None
    themes = os.path.join(static_root, resolve.host_dir(host), "wp-content",
                          "themes", "fcsharedimg")
    if not os.path.isdir(themes):
        return None
    for directory in sorted(os.listdir(themes)):
        # `banners29`, not `banners`: the numbered directory is the issue's own.
        if not re.fullmatch(r"banners\d+", directory):
            continue
        for name in BANNER_NAMES:
            candidate = os.path.join(themes, directory, name)
            if os.path.isfile(candidate):
                return candidate
    return None


def image_size(path: str) -> tuple[int, int] | None:
    """(width, height) from a PNG or JPEG header, without a library."""
    import struct
    try:
        with open(path, "rb") as fh:
            data = fh.read(65536)
    except OSError:
        return None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            if data[i + 1] in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA):
                height, width = struct.unpack(">HH", data[i + 5:i + 9])
                return width, height
            if i + 4 > len(data):
                break
            i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return None


# The banners were drawn to different proportions: most are a thin band of
# 9.6:1 or 13.7:1, but issue 22's artwork sits in the middle of a 960x560
# canvas at 1.7:1, mostly empty. Recording a floored ratio lets the renderer
# crop that one to its band instead of opening the page with whitespace.
MIN_BANNER_RATIO = 8.0


# --------------------------------------------------------------------------
# write


def write_content(man: inventory.Manifest, out_dir: str = CONTENT,
                  static_root: str = resolve.STATIC_ROOT) -> ExtractReport:
    report = ExtractReport()
    os.makedirs(out_dir, exist_ok=True)
    written: set[str] = set()
    written_media: set[str] = set()
    written_pages: set[str] = set()
    used_recovered: set[str] = set()

    for ident, paper in man.papers.items():
        host = os.path.relpath(paper.source, static_root).split(os.sep)[0]
        doc = inventory.read(paper.source)
        rewrite = make_rewriter(man, host, static_root,
                                used_recovered=used_recovered)
        body = markdown.to_markdown(inventory.content_of(doc), rewrite)

        names = markdown.authors(doc)
        identifier = markdown.doi(doc, body[:4000])
        affiliation, body = take_byline(body, names)
        abstract, body = take_abstract(body)
        # A heading with no text is a styling hook the old theme left behind,
        # and it is the one piece of issue furniture that also reaches papers.
        # The rest of `strip_issue_furniture` must NOT run here: it removes
        # hand-written contents lists, which a paper does not have.
        body = EMPTY_HEADING.sub("", body)
        body = point_at_recovered(body, "../", used_recovered)
        body = unnumber_apparatus(body)
        body = take_doi_line(body)

        report.paragraph_numbers += len(re.findall(r"\{#para\d+\}", body))
        if names:
            report.with_authors += 1
        else:
            report.without_authors.append(ident)
        if abstract:
            report.with_abstract += 1

        front = {
            "fcj_id": paper.fcj_id,
            "title": paper.title,
            "authors": names,
            "affiliation": affiliation,
            "issue": paper.issue,
            "published": markdown.published(doc),
            "doi": identifier,
            "journal": "The Fibreculture Journal",
            "issn": "1449-1443",
            "licence": "CC BY-NC-ND",
            "abstract": abstract,
            "pdf": media_rel(paper.pdf, static_root) if paper.pdf else "",
            "epub": media_rel(paper.epub, static_root) if paper.epub else "",
            "source_url": _original_url(doc, host, paper),
            "source_file": os.path.relpath(paper.source, static_root),
        }
        target = os.path.join(out_dir, "papers", paper_dir(paper) + ".md")
        _write(target, dump_front_matter(front) + body)
        written.add(target)
        report.papers += 1

    compilations = full_issue_files(static_root)
    for number, iss in man.issues.items():
        host = dict(inventory.ISSUE_HOSTS)[number]
        rewrite = make_rewriter(man, host, static_root, from_dir="issues",
                                used_recovered=used_recovered)
        body = markdown.to_markdown(iss.editorial_html, rewrite)
        _, body = take_abstract(body)
        issue_doi, body = take_issue_doi(body)
        editors, body = take_editors(body)

        # The credit usually lives on the issue ROOT, not in the editorial.
        # 27 of 31 editorials come from a standalone page, and reading only
        # that found 14 issues with editors; the roots carry them for 30.
        # Same mistake as fcj-problems.md P5 — looking on the wrong page.
        root_path = resolve.local_path(host, "/", static_root)
        if root_path and root_path != iss.editorial_path:
            root_md = markdown.to_markdown(
                inventory.content_of(inventory.read(root_path)), rewrite)
            root_editors, _ = take_editors(root_md, heading_only=False)
            editors = merge_editors(root_editors, editors)
        else:
            root_editors, _ = take_editors(body, heading_only=False)
            editors = merge_editors(editors, root_editors)
        body = strip_issue_furniture(body)
        body = point_at_recovered(body, "../", used_recovered)
        body = unnumber_apparatus(body)
        if editors:
            report.with_editors += 1
        full = {}
        for kind, source_path in compilations.get(number, {}).items():
            rel = media_rel(source_path, static_root)
            _copy(source_path, os.path.join(out_dir, rel))
            written_media.add(os.path.join(out_dir, rel))
            full[kind] = rel
            report.full_issue_files += 1

        banner = banner_rel = ""
        banner_ratio = ""
        source_banner = banner_source(number, static_root)
        if source_banner:
            banner_rel = f"media/banners/{number}{os.path.splitext(source_banner)[1].lower()}"
            _copy(source_banner, os.path.join(out_dir, banner_rel))
            written_media.add(os.path.join(out_dir, banner_rel))
            size = image_size(source_banner)
            if size and size[1]:
                banner_ratio = f"{max(size[0] / size[1], MIN_BANNER_RATIO):.2f}"
            banner = banner_rel
            report.banners += 1

        front = {
            "issue": number,
            "theme": iss.theme,
            "editorial_source": iss.editorial_source,
            "editors": editors,
            "full_issue_pdf": full.get("pdf", ""),
            "full_issue_epub": full.get("epub", ""),
            "doi": issue_doi,
            "banner": banner,
            "banner_ratio": banner_ratio,
            "papers": iss.papers,
            "journal": "The Fibreculture Journal",
            "issn": "1449-1443",
            "source_file": (os.path.relpath(iss.editorial_path, static_root)
                            if iss.editorial_path else ""),
        }
        target = os.path.join(out_dir, "issues", f"{number}.md")
        _write(target, dump_front_matter(front) + body)
        written.add(target)
        report.issues += 1

    for rel in man.assets:
        src = os.path.join(static_root, rel)
        dst = os.path.join(out_dir, media_rel(src, static_root))
        _copy(src, dst)
        written_media.add(dst)
        report.media += 1
        report.media_bytes += os.path.getsize(src)

    write_pages(man, out_dir, static_root, report, written_pages,
                written_media, used_recovered)
    write_status(out_dir, man, report, written_pages)

    # Files the crawl could not reach, recovered from the Wayback Machine and
    # referenced by the Markdown. Copied after the mirror's own assets so a
    # mirror file always wins a path collision: the crawl is the primary
    # source and recovery only fills what it could not reach.
    for source in sorted(used_recovered):
        dst = os.path.join(out_dir, recovered_rel(source))
        _copy(source, dst)
        written_media.add(dst)
        report.recovered_media += 1

    write_journal(out_dir, report)
    _write(os.path.join(out_dir, "README.md"), _readme(man, report))
    report.pruned = _prune(out_dir, written, written_media, written_pages)
    return report


MEDIA_FLOOR = 400


def _prune(out_dir: str, written: set[str],
           written_media: set[str] | None = None,
           written_pages: set[str] | None = None) -> list[str]:
    """Delete generated files this build did not write.

    `content/` is generated, so a file in it that the build no longer produces
    is stale — and stale is worse than missing, because it still renders and
    still serves. This bit when `paper_dir` changed and FCJ-002 moved from
    `fcj-002-fcj002.md` to `fcj-002.md`: the old file stayed, the archive
    reported 238 papers, and the site published the same article twice.

    Markdown: only `.md` files directly inside `papers/` and `issues/`, which
    are the only files written there.

    Media: every file under `media/` that this build did not copy. Added when
    excluding the old theme's icons left 52 orphans on disk — the same defect
    the Markdown pruning exists to prevent, in the directory that holds 270 MB
    and is about to be committed to a repository.

    **`MEDIA_FLOOR` is a refusal, not a tuning knob.** This function deletes
    from a tree that holds every image, PDF and ePub in the archive, driven by
    a set assembled by its caller. If that set comes back short — an exception
    swallowed upstream, a manifest that failed to build, a caller that forgot
    to pass it — the honest outcome is to delete nothing and say so, because
    the mirror is read-only and a wrong deletion here is only recoverable by a
    full re-extract. A floor well under the real count (585) catches the
    catastrophic case without pretending to catch a subtle one.
    """
    removed: list[str] = []
    for sub in ("papers", "issues"):
        directory = os.path.join(out_dir, sub)
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            path = os.path.join(directory, name)
            if name.endswith(".md") and os.path.isfile(path) and path not in written:
                os.remove(path)
                removed.append(os.path.relpath(path, out_dir))

    if written_pages:
        pages_dir = os.path.join(out_dir, "pages")
        for name in sorted(os.listdir(pages_dir)) if os.path.isdir(pages_dir) else []:
            path = os.path.join(pages_dir, name)
            if name.endswith(".md") and os.path.isfile(path) and path not in written_pages:
                os.remove(path)
                removed.append(os.path.relpath(path, out_dir))

    media = os.path.join(out_dir, "media")
    if written_media and len(written_media) >= MEDIA_FLOOR and os.path.isdir(media):
        for root, _dirs, files in os.walk(media, topdown=False):
            for name in sorted(files):
                path = os.path.join(root, name)
                if path not in written_media:
                    os.remove(path)
                    removed.append(os.path.relpath(path, out_dir))
            if not os.listdir(root) and root != media:
                os.rmdir(root)
    return removed


def _original_url(doc: str, host: str, paper: inventory.Paper) -> str:
    meta = markdown.metadata(doc)
    for key in ("citation_fulltext_html_url", "citation_abstract_html_url", "og:url"):
        if meta.get(key):
            return meta[key][0]
    return f"https://{host}/{paper.slug}/"


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _copy(src: str, dst: str) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src):
        return
    shutil.copy2(src, dst)


def _readme(man: inventory.Manifest, report: ExtractReport) -> str:
    return f"""# The Fibreculture Journal — text archive

{report.papers} articles and {report.issues} issue editorials from
*The Fibreculture Journal* (ISSN 1449-1443), a peer-reviewed open-access journal
of digital media, networks and culture published since 2003.

Every article is one Markdown file with YAML front matter. Figures, PDFs and
ePubs are under `media/`. There is no build step and no database: the text is
flat files, and the website in this repository is generated from exactly these
files, so what you read here is what the site shows.

## Layout

```
papers/<fcj-id>-<slug>.md     one article
issues/<n>.md                 one issue editorial, listing its articles
media/…                       figures, article PDFs and ePubs, full-issue PDFs
```

## Front matter

```yaml
fcj_id: FCJ-218
title: "Train Ticket Sharing: Alternative Forms of Computing in the City"
authors:
  - Paula Bialski
issue: 29
published: 2017-06-29
abstract: "…"
source_url: https://twentynine.fibreculturejournal.org/fcj-218-…/
```

`source_url` is the article's original address, so a citation to the published
version can still be checked against it.

## Paragraph numbers

The journal numbers paragraphs, and those numbers are citable — "(Rossiter
2003, para. 76)". They are preserved as a `{{#para76}}` suffix on each
paragraph, {report.paragraph_numbers:,} of them across the archive. They cannot
be derived from position: the numbering skips captions and some blocks, so only
90 of {report.papers} articles number every paragraph.

To read the text without them:

```bash
sed -E 's/ *\\{{#para[0-9]+\\}}//g' papers/fcj-218-*.md
```

## Licence

Articles remain the copyright of their authors, published under Creative
Commons BY-NC-ND. This archive adds no new claim over them.
"""


def _main() -> None:
    man = inventory.build()
    rep = write_content(man)
    print(f"content/: {rep.papers} papers, {rep.issues} issues, "
          f"{rep.media} media files ({rep.media_bytes / 1024 / 1024:.0f} MB)")
    print(f"  authors from citation metadata: {rep.with_authors}/{rep.papers}")
    print(f"  abstracts lifted to front matter: {rep.with_abstract}")
    print(f"  paragraph numbers preserved: {rep.paragraph_numbers:,}")
    print(f"  issue banners extracted: {rep.banners} of 31")
    print(f"  issues with named editors: {rep.with_editors} of 31")
    print(f"  whole-issue PDFs/ePubs: {rep.full_issue_files}")
    print(f"  institutional pages: {rep.pages}"
          + (f"  MISSING: {rep.pages_missing}" if rep.pages_missing else ""))
    print(f"  journal.md: {'kept (hand-maintained)' if rep.journal_kept else 'seeded'}")
    if rep.pruned:
        # Media pruning can remove dozens at once; a wall of paths buries the
        # rest of the report, which is what anyone reads this output for.
        shown = ", ".join(rep.pruned[:4])
        more = f" and {len(rep.pruned) - 4} more" if len(rep.pruned) > 4 else ""
        print(f"  pruned {len(rep.pruned)} stale file(s): {shown}{more}")
    if rep.without_authors:
        print(f"  NO AUTHORS ({len(rep.without_authors)}): "
              f"{' '.join(rep.without_authors[:14])}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    _main()
