#!/usr/bin/env python3
# Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
"""Discover the domains injected into the compromised WordPress site.

Governed by docs/architecture.md (invariant 1).

The site was compromised at some point and had links to junk domains — casinos,
crypto, CBD, sweepstakes — inserted inline into article body text, like
`…platforms like an <a href="instantcasino.com">instant play casino</a> are
designed to…`. 145 HTML files carry them. All 145 are on the apex host; not one
is on any of the 32 issue subdomains.

WHY THIS IS GENERATED AND NOT A LIST SOMEONE TYPED

A hand-written blocklist is a second artefact that has to agree with the mirror,
with nothing enforcing the agreement, and it goes stale the first time anyone
looks at a file it does not cover. `docs/architecture.md` requires this file to
be generated for that reason.

HOW A DOMAIN IS IDENTIFIED, AND HOW STRONG THE EVIDENCE IS

The mirror holds most articles twice: a copy on the apex host and a clean copy
on the issue's own subdomain. So the injection can be found by **diffing an
article against itself**: a domain in the apex body that is absent from the same
article's subdomain twin was put there by someone who was not the author.

Two conditions must BOTH hold before a domain is enforced:

  1. it appears in an apex copy's content and not in that copy's own clean twin;
  2. it appears nowhere in the content of any of the 32 issue subdomains.

(1) is the positive evidence. (2) is the guard against false positives, and it
is the condition that matters, because a false positive makes the archive forbid
a source a paper genuinely cites. Anything meeting only one condition is
REPORTED, never enforced.

This is not a new method. It is how the contamination was found in the first
place; the measured result is in `../fcj-problems.md` P1 and P3.
"""
from __future__ import annotations

import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import inventory
import resolve

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(DATA, "spam-domains.txt")

LINK_HOST = re.compile(r"""(?i)\bhref\s*=\s*["']https?://([^/"'?#]+)""")

# Hosts that are part of the journal or its own furniture, so they can never be
# an injection and are excluded before any comparison.
OWN = re.compile(r"(?i)(^|\.)(fibreculturejournal\.org|fibreculture\.org)$")
# The theme's own credit links, present in 2,253 of the mirror's 2,278 files.
# Not spam, just furniture, and leaving them in would put them in every diff.
FURNITURE_HOSTS = {"wordpress.org", "themasterplan.in", "creativecommons.org",
                   "i.creativecommons.org", "openhumanitiespress.org",
                   "www.openhumanitiespress.org", "gmpg.org", "validator.w3.org"}


@dataclass
class SpamReport:
    enforced: list[str] = field(default_factory=list)
    # domain -> the evidence that put it on the list
    evidence: dict[str, list[str]] = field(default_factory=dict)
    # met the twin-diff test but DOES appear on a subdomain: not enforced
    rejected: dict[str, str] = field(default_factory=dict)
    # on the apex only, with no twin to compare against: reported for review
    unverifiable: dict[str, list[str]] = field(default_factory=dict)
    apex_files_affected: list[str] = field(default_factory=list)
    twins_compared: int = 0


def hosts_in(content: str) -> set[str]:
    """External link hosts in a content region, lower-cased."""
    found: set[str] = set()
    for host in LINK_HOST.findall(content):
        host = host.lower().strip().removeprefix("www.")
        if not host or OWN.search(host) or host in FURNITURE_HOSTS:
            continue
        if f"www.{host}" in FURNITURE_HOSTS:
            continue
        found.add(host)
    return found


# Domain-shaped text anywhere in a content region, linked or not. Used ONLY for
# the guard, never as positive evidence.
#
# This exists because of a measured false positive. `chcf.org` — the California
# Health Care Foundation — was flagged as injected into FCJ-144, a paper about
# GE's "healthymagination". It is a real citation: the author printed the URL
# as PLAIN TEXT in their reference list, and the apex copy has it as a link. A
# guard that only reads `href` attributes sees "present in the apex, absent
# from the twin" and accuses a source the paper actually cites.
DOMAIN_TEXT = re.compile(
    r"(?i)\b([a-z0-9][a-z0-9-]{0,62}(?:\.[a-z0-9-]{2,63})+)\b")


def _content_hosts(path: str) -> set[str]:
    try:
        return hosts_in(inventory.content_of(inventory.read(path)))
    except OSError:
        return set()


def _content_mentions(path: str) -> set[str]:
    """Every domain-shaped string in a page's content, however it is written."""
    try:
        text = inventory.content_of(inventory.read(path))
    except OSError:
        return set()
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    found = set()
    for token in DOMAIN_TEXT.findall(text):
        token = token.lower().removeprefix("www.")
        if not OWN.search(token):
            found.add(token)
    return found


def build(static_root: str = resolve.STATIC_ROOT,
          man: inventory.Manifest | None = None) -> SpamReport:
    report = SpamReport()
    man = man or inventory.build(static_root)
    apex_dir = os.path.join(static_root, resolve.SITE)

    # ---- condition 2 first: everything the clean subdomains legitimately cite.
    # Built before any accusation, so a domain can never be enforced on a
    # technicality when a real article elsewhere links it.
    subdomain_hosts: set[str] = set()
    for _number, prefix in inventory.ISSUE_HOSTS:
        host_dir = os.path.join(static_root, resolve.host_dir(prefix))
        if not os.path.isdir(host_dir):
            continue
        for dirpath, _dirs, files in os.walk(host_dir):
            if os.sep + "wp-content" + os.sep in dirpath + os.sep:
                continue
            for name in files:
                if name.lower().endswith((".html", ".htm")) and "?" not in name:
                    path = os.path.join(dirpath, name)
                    # Mentions, not just links: a reference list that prints a
                    # URL as plain text still proves the paper cites it.
                    subdomain_hosts |= _content_mentions(path)

    # ---- condition 1: diff each published paper against its apex copy
    candidates: dict[str, list[str]] = defaultdict(list)
    for ident, paper in man.papers.items():
        rel = os.path.relpath(paper.source, static_root)
        if rel.split(os.sep)[0] == resolve.SITE:
            continue                      # already the apex copy; no twin
        apex, _ = inventory.resolve_with_apex(
            resolve.SITE, "/" + paper.slug, static_root)
        if apex is None or not os.path.isfile(apex):
            continue
        report.twins_compared += 1
        clean = _content_hosts(paper.source)
        dirty = _content_hosts(apex)
        extra = dirty - clean
        if extra:
            report.apex_files_affected.append(os.path.relpath(apex, static_root))
        for host in extra:
            candidates[host].append(
                f"{ident}: in {os.path.relpath(apex, static_root)}, "
                f"not in {rel}")

    for host, why in sorted(candidates.items()):
        if host in subdomain_hosts:
            report.rejected[host] = (
                "appears on an issue subdomain, so it is cited by a real "
                "article somewhere; not enforced")
        else:
            report.enforced.append(host)
            report.evidence[host] = why

    # ---- apex-only pages have no twin, so their domains cannot be tested this
    # way. Reported so the gap is visible rather than assumed empty.
    if os.path.isdir(apex_dir):
        published_apex = {p.source for p in man.papers.values()}
        for dirpath, _dirs, files in os.walk(apex_dir):
            if os.sep + "wp-content" + os.sep in dirpath + os.sep:
                continue
            for name in files:
                if not name.lower().endswith((".html", ".htm")) or "?" in name:
                    continue
                path = os.path.join(dirpath, name)
                if path in published_apex:
                    continue
                for host in _content_hosts(path) - subdomain_hosts:
                    if host in report.enforced:
                        continue
                    report.unverifiable.setdefault(host, []).append(
                        os.path.relpath(path, static_root))

    report.enforced = sorted(set(report.enforced))
    return report


def write(report: SpamReport, path: str = OUT) -> None:
    """Sorted, deduplicated, one domain per line, with its evidence beside it.

    Stable output: the file must be byte-identical between runs or it churns in
    git and stops being reviewable.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [
        "# Domains injected into the compromised WordPress site.",
        "# GENERATED by build/audit_spam.py — never hand-edited.",
        "#",
        "# A domain is listed only when it appears in an apex copy of an",
        "# article and NOT in that article's clean issue-subdomain twin, AND",
        "# appears nowhere on any of the 32 issue subdomains. See the module",
        "# docstring and ../fcj-problems.md P1 and P3.",
        "#",
        f"# {len(report.enforced)} domains, from {report.twins_compared} "
        f"article pairs compared.",
        "",
    ]
    for host in report.enforced:
        lines.append(host)
    lines.append("")
    lines.append("# Evidence, one line per domain:")
    for host in report.enforced:
        lines.append(f"#   {host}: {report.evidence[host][0]}")
    if report.rejected:
        lines.append("")
        lines.append("# Considered and NOT enforced:")
        for host, why in sorted(report.rejected.items()):
            lines.append(f"#   {host}: {why}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def load(path: str = OUT) -> list[str]:
    """The enforced domains, for the invariant test and the generator."""
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [ln.strip() for ln in fh
                if ln.strip() and not ln.lstrip().startswith("#")]


def _main() -> None:
    report = build()
    write(report)
    print(f"article pairs compared : {report.twins_compared}")
    print(f"apex files with extras : {len(set(report.apex_files_affected))}")
    print(f"domains ENFORCED       : {len(report.enforced)}")
    for host in report.enforced[:20]:
        print(f"    {host:<38} {report.evidence[host][0][:70]}")
    print(f"domains rejected       : {len(report.rejected)}")
    for host, why in list(report.rejected.items())[:6]:
        print(f"    {host:<38} {why[:62]}")
    print(f"apex-only, untestable  : {len(report.unverifiable)} domains on "
          f"{len(set(f for v in report.unverifiable.values() for f in v))} files")
    print(f"written to {OUT}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    _main()
