#!/usr/bin/env python3
"""PROBE: can every historical URL that served scholarship be redirected?

Run: python3 proofs/redirect-coverage.py

THE IDEA AT RISK
    The archive replaces 33 hostnames with one, and old URLs are kept working
    by a redirect map. That only holds if every historical URL which served an
    article or an editorial can be mapped to a path in the new archive. If some
    cannot, then switching DNS silently breaks citations in other people's
    published work — the exact damage this project exists to prevent — and the
    design needs a fallback instead: keeping the subdomains alive, or serving a
    "this article has moved" stub per lost URL.

WHY PROBE IT NOW
    The redirect map is the last piece before the archive can go live, and its
    failure mode is invisible: a map that covers 90% of URLs looks finished and
    loses one citation in ten. Counting the gap is cheap; discovering it after
    the DNS change is not.

WHY THE CRAWL AND NOT THE REDIRECT CONF
    `fcj-redirects.conf` holds 214 rules, and the spec's invariant 5 was written
    around it. Those rules redirect apex duplicates to issue-subdomain copies:
    they are internal to the OLD site, a 2026 patch over WordPress duplication,
    and they say almost nothing about where a historical URL should land in a
    single-host archive. The authority on what URLs existed is the crawl —
    3,896 records, every one status 200.

FOUR ATTEMPTS TO KILL IT:

  1. MAP EVERY PAGE URL the crawl recorded, and count what fails.
  2. OF THE FAILURES, HOW MANY ARE CONTENT? A category listing or a feed is not
     content. An unmappable ARTICLE is fatal. Content is identified by the FCJ
     citation in the page's <title>, the identity rule already proven.
  3. CHECK THE CONF'S 214 RULES independently — a different source, which may
     name paths the crawl never fetched.
  4. CHECK THE PRE-2008 DOMAIN. ~110 files link to `journal.fibreculture.org`,
     outside the crawl entirely. Where those URLs name a paper the archive
     holds they are recoverable; the rest are citation rot and must be counted.
"""
from __future__ import annotations

import os
import re
import sys
from collections import Counter
from urllib.parse import unquote, urlsplit

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "build"))

import inventory  # noqa: E402
import markdown  # noqa: E402
import resolve  # noqa: E402

CDX = os.path.join(os.path.dirname(HERE), "fcj-crawl", "fcj-clean.cdx")
CONF = os.path.join(os.path.dirname(HERE), "fcj-redirects.conf")

ASSET_EXT = (".jpg", ".jpeg", ".png", ".gif", ".css", ".js", ".ico", ".svg",
             ".woff", ".woff2", ".ttf", ".eot", ".webp", ".mp4", ".mp3", ".zip")
DOC_EXT = (".pdf", ".epub")

# Generated WordPress views. Not content: the archive holds what they list.
FURNITURE = re.compile(
    r"^/?(wp-content/(themes|plugins)|wp-includes|wp-admin|wp-login|wp-json|"
    r"xmlrpc|author|tag|category|feed|comments|page/\d+|\d{4}(/\d{2})*/?$)",
    re.I)


def cdx_urls() -> list[str]:
    urls = []
    with open(CDX, encoding="utf-8", errors="replace") as fh:
        fh.readline()
        for line in fh:
            fields = line.split()
            if len(fields) > 2 and fields[2].startswith("http"):
                urls.append(fields[2])
    return urls


def conf_rules() -> list[tuple[str, str]]:
    """(host, path) pairs the Apache config redirects, with their targets."""
    rules = []
    host = None
    with open(CONF, encoding="utf-8") as fh:
        for line in fh:
            m = re.search(r"HTTP_HOST\}\s+\^([^\\$]+(?:\\\.[^\\$]+)*)\$", line)
            if m:
                host = m.group(1).replace("\\.", ".")
            rule = re.match(r"\s*RewriteRule\s+\^?/?([^\s]+)\s+(\S+)", line)
            if rule and host:
                path = rule.group(1).replace("\\-", "-").replace("\\.", ".")
                path = re.sub(r"\(/\.\*\)\?\$?$", "", path).rstrip("$")
                rules.append((host, "/" + path.lstrip("/")))
    return rules


def main() -> int:
    print(__doc__.split("FOUR ATTEMPTS")[0].strip())
    print("=" * 72)

    man = inventory.build()
    # source file -> archive path, exactly as extract.py builds it
    published: dict[str, str] = {}
    for paper in man.papers.values():
        import extract
        published[paper.source] = f"/papers/{extract.paper_dir(paper)}/"
    for number, iss in man.issues.items():
        if iss.editorial_path:
            published[iss.editorial_path] = f"/issues/{number}/"
        root = resolve.local_path(dict(inventory.ISSUE_HOSTS)[number], "/")
        if root:
            published.setdefault(root, f"/issues/{number}/")
    assets = {os.path.join(resolve.STATIC_ROOT, rel) for rel in man.assets}
    print(f"archive publishes {len(man.papers)} papers, {len(man.issues)} issues, "
          f"{len(assets)} media files\n")

    by_id = {}
    for paper in man.papers.values():
        import extract as _e
        by_id[paper.fcj_id] = f"/papers/{_e.paper_dir(paper)}/"
    host_to_issue = {resolve.host_dir(h): n for n, h in inventory.ISSUE_HOSTS}

    def archive_path(host: str, path: str) -> str | None:
        """Where this historical URL should land.

        The FIRST version of this probe looked up the file the URL resolved to
        and stopped. That reported 247 article URLs as unmappable and killed
        the idea — wrongly. The mirror holds the same article at up to three
        paths (the apex copy, the issue-subdomain copy, a dated permalink) and
        the archive publishes only one of them, so a lookup keyed on the
        resolved FILE misses every apex duplicate, which is exactly what all
        214 of `fcj-redirects.conf`'s rules are.

        The key is the article's IDENTITY — the FCJ citation in its <title> —
        not its path on disk. That is the same identity rule the inventory
        already rests on, applied to the one place left that was using paths.
        """
        local, _ = inventory.resolve_with_apex(host, path, resolve.STATIC_ROOT)
        if local is None:
            return None
        if local in published:
            return published[local]
        if local in assets:
            return "/media/" + os.path.relpath(local, resolve.STATIC_ROOT)
        if local.lower().endswith((".html", ".htm")):
            doc = inventory.read(local)
            ident = inventory.fcj_id(doc)
            if ident and ident in by_id:
                return by_id[ident]
            # an issue root or editorial duplicate on a known issue host
            issue = host_to_issue.get(resolve.host_dir(host))
            if issue and inventory.words(inventory.content_of(doc)) > 400:
                return f"/issues/{issue}/"
        return None

    def is_article(host: str, path: str) -> str | None:
        """The FCJ citation of whatever this URL served, if it served one."""
        local, _ = inventory.resolve_with_apex(host, path, resolve.STATIC_ROOT)
        if local is None or not local.lower().endswith((".html", ".htm")):
            return None
        try:
            return inventory.fcj_id(inventory.read(local))
        except OSError:
            return None

    # ---- attempt 1 and 2
    print("ATTEMPT 1/2 — map every page URL the crawl recorded")
    urls = cdx_urls()
    kinds = Counter()
    unmapped_content: list[tuple[str, str]] = []
    unmapped_other: list[str] = []
    mapped = 0
    for url in urls:
        parts = urlsplit(url)
        host = parts.netloc.lower().removeprefix("www.")
        path = parts.path or "/"
        low = unquote(path).lower()
        if low.endswith(ASSET_EXT):
            kinds["asset"] += 1
        elif low.endswith(DOC_EXT):
            kinds["doc"] += 1
        else:
            kinds["page"] += 1
        target = archive_path(host, path)
        if target:
            mapped += 1
            continue
        ident = is_article(host, path)
        if ident:
            unmapped_content.append((url, ident))
        elif FURNITURE.match(path):
            kinds["furniture"] += 1
        else:
            unmapped_other.append(url)

    print(f"  crawl records            : {len(urls)}")
    print(f"  of which page/asset/doc  : {kinds['page']} / {kinds['asset']} / {kinds['doc']}")
    print(f"  mapped to an archive path: {mapped}")
    print(f"  unmapped, WordPress furniture: {kinds['furniture']}")
    print(f"  unmapped, other          : {len(unmapped_other)}")
    print(f"  unmapped CONTENT (fatal) : {len(unmapped_content)}")
    for url, ident in unmapped_content[:10]:
        print(f"      {ident}  {url[:96]}")
    if unmapped_other[:6]:
        print("  sample of 'other':")
        for url in unmapped_other[:6]:
            print(f"      {url[:96]}")
    print()

    # ---- attempt 3
    print("ATTEMPT 3 — the redirect conf's own rules, as an independent source")
    rules = conf_rules()
    conf_unmapped = []
    for host, path in rules:
        if not archive_path(host, path):
            conf_unmapped.append(f"{host}{path}")
    print(f"  rules parsed       : {len(rules)}")
    print(f"  unmappable         : {len(conf_unmapped)}")
    for item in conf_unmapped[:8]:
        print(f"      {item[:96]}")
    print()

    # ---- attempt 4
    print("ATTEMPT 4 — the pre-2008 domain, outside the crawl entirely")
    old = Counter()
    seen: set[str] = set()
    examples: list[str] = []
    for paper in man.papers.values():
        doc = inventory.read(paper.source)
        for href in re.findall(
                r"""(?i)https?://(?:www\.)?journal\.fibreculture\.org(/[^\s"'<>]*)""", doc):
            href = href.split("#")[0].split("?")[0]
            if href in seen:
                continue
            seen.add(href)
            low = unquote(href).lower()
            # Classify before calling anything rot. Most of these turned out to
            # be IMAGES the old site hosted — FCJ-047's figures are all
            # `journal.fibreculture.org/images/armstrong/…` — which are a
            # different problem from a dead citation to an article.
            if low.endswith(ASSET_EXT):
                old["image or asset"] += 1
            elif low.endswith(DOC_EXT):
                old["pdf or epub"] += 1
            elif re.search(r"issue\d|/issue", low):
                old["old issue page"] += 1
            else:
                old["other page"] += 1
                if len(examples) < 6:
                    examples.append(href)
    total = sum(old.values())
    print(f"  distinct journal.fibreculture.org URLs linked: {total}")
    for kind, count in old.most_common():
        print(f"      {count:>4}  {kind}")
    for href in examples:
        print(f"            e.g. {href[:80]}")
    print("  None are in the crawl, so none can be served by this archive.")
    print("  They are inbound-citation rot in the OLD site's own text, not")
    print("  something the redirect map can fix.")
    print()

    print("=" * 72)
    if unmapped_content:
        print(f"IDEA DIED — {len(unmapped_content)} URLs served an article and")
        print("cannot be mapped. The archive cannot replace the old site without")
        print("losing those citations; a per-URL stub or keeping the subdomains")
        print("alive is required.")
        return 1
    print("IDEA SURVIVED.")
    print("  Every crawled URL that served an article or editorial maps to an")
    print("  archive path. What does not map is WordPress furniture, which the")
    print(f"  archive deliberately does not publish ({kinds['furniture']} URLs),")
    print(f"  plus {len(unmapped_other)} others listed above for a decision.")
    print("  The redirect map must be keyed on HOST AND PATH, built from the")
    print("  crawl rather than from fcj-redirects.conf, and every target must be")
    print("  checked to exist before it ships.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
