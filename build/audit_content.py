#!/usr/bin/env python3
# Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
"""Audit `content/` for residue of the platform the archive was lifted off.

Five defects in one session were found by a person reading pages rather than by
the build: `#####` headings, a dead `::` menu, the old theme's PDF icons, a run
of `Issue:ePubIssue:pdf` labels, and an issue recorded under a generic title.
Each was then fixed with a one-off rule.

That approach scales with how many pages somebody reads, and this archive has
275. **The defect CLASS is the thing to detect.** What these all share is that
they are WordPress or theme furniture that survived extraction: text that was
interface on the old site and is meaningless in a Markdown archive.

This tool REPORTS and never rewrites. Several checks need judgement — an
indented code block is legitimate in a paper about software, and `::` is an
authored separator on one page — and a tool that silently rewrote those would
damage the thing it is meant to protect. Fixing belongs in `extract.py`, where
it is tested; this decides what needs fixing.

Run it:

    python3 build/audit_content.py            # report everything
    python3 build/audit_content.py --enforced # only the categories under test

Exit status is 1 if any ENFORCED category has a hit, so it can gate a build.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field

CONTENT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "content")

# Categories whose hits have all been read and confirmed to be furniture. Only
# these fail the build. A category is promoted here once its false-positive
# rate is zero, not before — enforcing a noisy check trains people to ignore
# the whole report, which is worse than not having it.
ENFORCED = {
    "download-label",
    "nav-menu",
    "top-anchor",
    "theme-asset",
    "deep-heading",
    "empty-heading",
    "platform-residue",
    "empty-link",
    "generic-theme",
    "numbered-apparatus",
}

# `deep-heading` is furniture on an issue or institutional page, where the old
# theme used heading level as a font size — that is what made issue 29 render
# `#####`. In a PAPER it is an authored subsection: FCJ-210 nests five levels
# to separate the phases of a robot's fall, and FCJ-217 to number five
# ethnographic vignettes. Enforcing it everywhere would have had me "fix"
# those by flattening an author's structure.
SCOPED = {"deep-heading": ("issues/", "pages/")}


@dataclass
class Hit:
    category: str
    path: str
    line: int
    text: str


@dataclass
class Audit:
    hits: list[Hit] = field(default_factory=list)

    def add(self, category: str, path: str, line: int, text: str) -> None:
        self.hits.append(Hit(category, path, line, text.strip()[:110]))

    def by_category(self) -> dict[str, list[Hit]]:
        out: dict[str, list[Hit]] = {}
        for hit in self.hits:
            out.setdefault(hit.category, []).append(hit)
        return dict(sorted(out.items()))

    def enforced(self) -> list[Hit]:
        return [h for h in self.hits if h.category in ENFORCED]


# --------------------------------------------------------------------------
# the checks
#
# Each is anchored tightly enough that an authored sentence cannot trip it.
# Where a pattern COULD appear in real prose it is left unenforced, and the
# comment says what the ambiguity is.

# `Issue: pdf`, `Editorial:pdf`, and runs of them with no separator. The
# archive renders its own download links from front matter, so these are
# duplicates of what it already knows.
DOWNLOAD_LABEL = re.compile(
    r"(?i)^[ \t]*(?:(?:issue|editorial|article|full\s*issue)\s*:\s*"
    r"(?:pdf|epub)[ \t]*)+$")

# A line-initial `::` menu item. `::` mid-line is an authored separator on the
# About page, and `::: embed` is a fence in this archive's Markdown dialect, so
# both the anchor and the following space are load-bearing.
NAV_MENU = re.compile(r"^[ \t]*::[ \t]+\S")

# `^ top` — a jump-to-top anchor whose target no longer exists.
TOP_ANCHOR = re.compile(r"(?:^|\s)\^\s*top\b", re.I)

# Any surviving reference to a theme directory. The archive publishes in its
# own format; the old theme's CSS and images are not content.
THEME_ASSET = re.compile(r"wp-content/themes")

# This archive's pages use `##` and `###`. Anything deeper is WordPress using
# heading level as a font size, which is what made issue 29 render `#####`.
DEEP_HEADING = re.compile(r"^#{5,6}\s")

EMPTY_HEADING = re.compile(r"^#{1,6}[ \t]*$")

# Platform and widget residue. `-->` is a comment terminator that survived the
# HTML strip; the rest is WordPress and sharing-widget furniture.
PLATFORM_RESIDUE = re.compile(
    r"(?i)(SHARETHIS|addthis|addEntry\(|Continue Reading|Post a comment|"
    r"-->|\[&#8230;\]|wp-admin|sourceURL=|concatemoji)")

# A link with an empty TARGET: `[text]()`. Furniture — the rewriter drops an
# internal href it cannot resolve, which leaves the text and no link.
EMPTY_LINK = re.compile(r"\[[^\]]*\]\(\s*\)")

# An image with no alt text: `![](src)`. NOT furniture — it is a figure whose
# caption was not found, which matters because 69 captions were once lost to
# `alt` attributes. Reported, never enforced: some figures genuinely have no
# caption in the source, and there is nothing to invent one from.
UNCAPTIONED_FIGURE = re.compile(r"^\s*!\[\s*\]\([^)]+\)")

# An image whose source is a host the crawl never fetched. These will not
# resolve from the archive at all — `journal.fibreculture.org` is a different
# domain from `fibreculturejournal.org` and is not in the mirror. Unenforced
# because it cannot be fixed by editing text; the files have to be found.
REMOTE_IMAGE = re.compile(r"!\[[^\]]*\]\(https?://(?!fibreculturejournal\.org)")

# An issue theme that is only the journal's name and a number, which means the
# themed title was not found and a generic page title was used instead.
GENERIC_THEME = re.compile(
    r"^\"?(?:the\s+)?fibreculture\s+journal\s*:?\s*\d+\"?$", re.I)

# --- unenforced, because each can be legitimate ---

# A paragraph that is entirely bold was usually a heading WordPress styled
# rather than marked up. But a pull-quote or an epigraph is legitimately bold,
# so this is reported for reading, not failed on.
BOLD_AS_HEADING = re.compile(r"^\*\*[^*]{2,80}\*\*:?$")

# An indented block is a code block in Markdown. Real ones exist here — papers
# about software quote source — so a hit means "look", not "wrong". Issue 20's
# `Issue:ePubIssue:pdf` was indented four spaces, which is why it rendered in a
# monospace box rather than looking like the stray text it was.
INDENTED = re.compile(r"^(?: {4,}|\t)\S")

LINE_CHECKS = [
    ("download-label", DOWNLOAD_LABEL),
    ("nav-menu", NAV_MENU),
    ("top-anchor", TOP_ANCHOR),
    ("theme-asset", THEME_ASSET),
    ("deep-heading", DEEP_HEADING),
    ("empty-heading", EMPTY_HEADING),
    ("platform-residue", PLATFORM_RESIDUE),
    ("empty-link", EMPTY_LINK),
    ("uncaptioned-figure", UNCAPTIONED_FIGURE),
    ("remote-image", REMOTE_IMAGE),
    ("bold-as-heading", BOLD_AS_HEADING),
    ("code-block", INDENTED),
]


# Paragraph numbers are the journal's citable unit, and they ran on into the
# notes, references and biographies — 5,335 of 17,796 of them. In an offprint
# they are set in the margin, so a reference list arrived with a numbered rail
# beside it, implying a reference can be cited by paragraph.
#
# The check is DOCUMENT-level, not line-level: it needs to know where the
# trailing apparatus run begins. Deliberately a second, independent
# implementation of that idea — if `extract`'s version drifts, this one
# notices, which a shared helper could not.
APPARATUS = re.compile(
    r"(?i)^(notes?|endnotes?|references?|works\s+cited|bibliography|"
    r"acknowledge?ments?|appendi(?:x|ces)\b.*|artworks?|thanks|"
    r"journal\s+notes?|sites?|websites?|"
    r"authors?['\u2019]?s?\s+bio\w*|biographical\s+notes?|"
    r"bio\w*\s+notes?)\s*:?$")
HEADING_LINE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
PARA_NUMBER = re.compile(r"\{#para\d+\}")


def numbered_apparatus(body: list[str], skip: set[int]) -> int | None:
    """The line where a numbered apparatus starts, or None.

    Returns the first line of the trailing apparatus run if any paragraph
    number survives inside it.
    """
    heads = [(i, HEADING_LINE.match(l)) for i, l in enumerate(body)
             if i not in skip and HEADING_LINE.match(l)]
    cut = None
    for i, m in reversed(heads):
        if not APPARATUS.match(m.group(2).strip(" *_#")):
            break
        cut = i
    if cut is None:
        return None
    return cut if any(PARA_NUMBER.search(l) for l in body[cut:]) else None


def split_front_matter(text: str) -> tuple[list[str], list[str]]:
    """Front-matter lines and body lines, kept apart.

    Deliberately re-implemented rather than imported from `extract`: an audit
    that shares a parser with the thing it audits cannot see a defect in that
    parser. It also keeps this tool independently deletable, which the
    architecture requires of every tool here.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return [], lines
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], lines[i + 1:]
    return [], lines


def fenced(body: list[str]) -> set[int]:
    """Indices inside a ``` fence or a `::: embed` block.

    Both legitimately contain anything at all — this archive's dialect parks
    raw HTML tables inside backticks — so the checks must skip them or every
    table in the archive becomes a hit.
    """
    inside: set[int] = set()
    fence = None
    for i, line in enumerate(body):
        stripped = line.strip()
        if fence is None:
            if stripped.startswith("```"):
                fence, _ = "```", inside.add(i)
            elif stripped.startswith("::: "):
                fence, _ = ":::", inside.add(i)
            continue
        inside.add(i)
        if (fence == "```" and stripped.startswith("```")) or \
           (fence == ":::" and stripped == ":::"):
            fence = None
    return inside


def audit(content_dir: str = CONTENT) -> Audit:
    report = Audit()
    for sub in ("papers", "issues", "pages"):
        directory = os.path.join(content_dir, sub)
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".md"):
                continue
            path = f"{sub}/{name}"
            with open(os.path.join(directory, name), encoding="utf-8") as fh:
                text = fh.read()
            front, body = split_front_matter(text)
            offset = len(text.splitlines()) - len(body)

            for line in front:
                if line.startswith("theme:") and GENERIC_THEME.match(
                        line.split(":", 1)[1].strip()):
                    report.add("generic-theme", path, 1, line)

            skip = fenced(body)
            at = numbered_apparatus(body, skip)
            if at is not None:
                report.add("numbered-apparatus", path, offset + at + 1,
                           body[at])
            for i, line in enumerate(body):
                if i in skip:
                    continue
                for category, pattern in LINE_CHECKS:
                    if category in SCOPED and not path.startswith(SCOPED[category]):
                        continue
                    if pattern.search(line):
                        report.add(category, path, offset + i + 1, line)
    return report


def _main() -> int:
    only_enforced = "--enforced" in sys.argv
    report = audit()
    groups = report.by_category()
    if not groups:
        print("content/: clean")
        return 0
    failed = 0
    for category, hits in groups.items():
        is_enforced = category in ENFORCED
        if only_enforced and not is_enforced:
            continue
        mark = "FAIL" if is_enforced else "note"
        print(f"\n{mark}  {category}: {len(hits)}")
        for hit in hits[:12]:
            print(f"    {hit.path}:{hit.line}  {hit.text}")
        if len(hits) > 12:
            print(f"    … and {len(hits) - 12} more")
        if is_enforced:
            failed += len(hits)
    print(f"\n{len(report.hits)} hit(s); {failed} in enforced categories")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
