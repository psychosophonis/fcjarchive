#!/usr/bin/env python3
# Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
"""Build the historical-URL redirect map.

Governed by docs/architecture.md ("Redirects", invariant 5).

This is the piece that decides whether the archive can replace the live site
without damage. Every citation in the literature, every inbound link, every
search result points at one of 33 hostnames that are going away. A redirect map
that covers most of them looks finished and loses one citation in ten.

THE KEY IS THE ARTICLE'S IDENTITY, NOT THE FILE A URL RESOLVES TO.

`proofs/redirect-coverage.py` was written to show the mapping worked, and the
first version of it failed: 247 article URLs came out unmappable. The reason is
structural. The mirror holds the same article at up to three paths — the apex
copy, the issue-subdomain copy, and sometimes a dated permalink — and the
archive publishes only one. A lookup keyed on the resolved FILE therefore misses
every apex duplicate, which is precisely what all 214 rules in
`fcj-redirects.conf` are. Keyed on the FCJ citation in the page's `<title>`,
coverage of content is complete.

WHY THE CRAWL, NOT `fcj-redirects.conf`

The spec's invariant 5 was written around that conf, and it is too narrow. Its
214 rules redirect apex duplicates to issue subdomains: internal plumbing of the
OLD site, a 2026 patch over WordPress duplication. The authority on which URLs
existed is the crawl — 3,896 records, every one status 200, across 33 hosts,
1,678 of them pages. The conf is kept as a second, independent source, and its
rule TARGETS are used to break ties the crawl cannot: an apex copy of an issue
intro does not say which issue it belongs to, but the rule pointing at
`twentyone.fibreculturejournal.org` does.

SHAPE OF THE OUTPUT

An exact map for content, plus a per-host fallback for everything else. The
fallback matters: 2,311 crawled URLs are WordPress furniture — category
listings, author pages, feeds, date archives, paginated indexes — and writing
2,311 individual rules to say "go to the issue index" would be a worse artefact
than one rule per host.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit

import extract
import inventory
import resolve

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Both inputs are located through `resolve.SOURCE_ROOT` rather than re-derived
# from `HERE`, so there is exactly one answer in the build to "where are the
# read-only inputs". See the note on `SOURCE_ROOT` in `resolve.py`.
CDX = os.path.join(resolve.SOURCE_ROOT, "fcj-crawl", "fcj-clean.cdx")
CONF = os.path.join(resolve.SOURCE_ROOT, "fcj-redirects.conf")
CONTENT = os.path.join(HERE, "content")

CANONICAL_HOST = resolve.SITE

ASSET_EXT = (".jpg", ".jpeg", ".png", ".gif", ".css", ".js", ".ico", ".svg",
             ".woff", ".woff2", ".ttf", ".eot", ".webp", ".mp4", ".mp3", ".zip")
DOC_EXT = (".pdf", ".epub")
# WordPress derivative image names: `1_intro-300x225.jpg` beside `1_intro.jpg`.
THUMBNAIL = re.compile(r"^(.*)-\d{2,4}x\d{2,4}(\.[A-Za-z0-9]+)$")


@dataclass
class RedirectReport:
    exact: dict[str, str] = field(default_factory=dict)
    host_fallback: dict[str, str] = field(default_factory=dict)
    unmapped: list[str] = field(default_factory=list)
    kinds: Counter = field(default_factory=Counter)
    conf_rules: int = 0
    conf_unmapped: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# sources


def cdx_urls(cdx_path: str = CDX) -> list[str]:
    """Every URL the crawl recorded, in the order it recorded them."""
    urls: list[str] = []
    if not os.path.isfile(cdx_path):
        return urls
    with open(cdx_path, encoding="utf-8", errors="replace") as fh:
        fh.readline()                      # " CDX a b a m s k r M V g u"
        for line in fh:
            fields = line.split()
            if len(fields) > 2 and fields[2].startswith("http"):
                urls.append(fields[2])
    return urls


def conf_rules(conf_path: str = CONF) -> list[tuple[str, str, str]]:
    """(host, path, target_host) from the Apache config.

    The target host is the useful part: it names the issue subdomain holding the
    clean copy, which is the only thing that says which issue an apex duplicate
    of an issue intro belongs to.
    """
    rules: list[tuple[str, str, str]] = []
    host: str | None = None
    if not os.path.isfile(conf_path):
        return rules
    with open(conf_path, encoding="utf-8") as fh:
        for line in fh:
            cond = re.search(r"HTTP_HOST\}\s+\^([^\\$]+(?:\\\.[^\\$]+)*)\$", line)
            if cond:
                host = cond.group(1).replace("\\.", ".")
            rule = re.match(r"\s*RewriteRule\s+\^?/?(\S+)\s+(\S+)", line)
            if rule and host:
                path = rule.group(1).replace("\\-", "-").replace("\\.", ".")
                path = re.sub(r"\(/\.\*\)\?\$?$", "", path).rstrip("$")
                target = urlsplit(rule.group(2)).netloc.lower()
                rules.append((host, "/" + path.lstrip("/"), target))
    return rules


# --------------------------------------------------------------------------
# mapping


class Mapper:
    """Resolves a historical URL to an archive path."""

    def __init__(self, man: inventory.Manifest, static_root: str = resolve.STATIC_ROOT):
        self.man = man
        self.static_root = static_root
        self.by_id = {p.fcj_id: f"/papers/{extract.paper_dir(p)}/"
                      for p in man.papers.values()}
        self.by_source: dict[str, str] = {
            p.source: f"/papers/{extract.paper_dir(p)}/" for p in man.papers.values()}
        for number, iss in man.issues.items():
            if iss.editorial_path:
                self.by_source[iss.editorial_path] = f"/issues/{number}/"
            root = resolve.local_path(dict(inventory.ISSUE_HOSTS)[number], "/", static_root)
            if root:
                self.by_source.setdefault(root, f"/issues/{number}/")
        self.assets = {os.path.join(static_root, rel) for rel in man.assets}
        self.host_issue = {resolve.host_dir(h): n for n, h in inventory.ISSUE_HOSTS}

    def path_for(self, host: str, path: str, hint_host: str = "") -> str | None:
        """Where this URL should land, or None.

        `hint_host` is an issue host suggested by an external source (a redirect
        rule's target), used only when the page itself cannot say which issue it
        belongs to.
        """
        local, _ = inventory.resolve_with_apex(host, path, self.static_root)
        if local is None:
            local = self._thumbnail(host, path)
        if local is None:
            return None
        if local in self.by_source:
            return self.by_source[local]
        if local in self.assets:
            return "/media/" + os.path.relpath(local, self.static_root)
        if local.lower().endswith((".html", ".htm")):
            doc = inventory.read(local)
            ident = inventory.fcj_id(doc)
            if ident and ident in self.by_id:
                return self.by_id[ident]
            issue = self.host_issue.get(resolve.host_dir(host)) or \
                self.host_issue.get(resolve.host_dir(hint_host)) if hint_host else \
                self.host_issue.get(resolve.host_dir(host))
            if issue and inventory.words(inventory.content_of(doc)) > 400:
                return f"/issues/{issue}/"
        return None

    def _thumbnail(self, host: str, path: str) -> str | None:
        """WordPress derivative images resolve to the original.

        `11_ZWR-300x225.jpg` is a crop of `11_ZWR.jpg`, generated by WordPress
        and referenced by nothing the archive publishes. Sending it to the full
        image is better than a 404 for anyone who hotlinked a thumbnail.
        """
        m = THUMBNAIL.match(unquote(resolve.clean_href(path)))
        if not m:
            return None
        local, _ = inventory.resolve_with_apex(host, m.group(1) + m.group(2),
                                               self.static_root)
        return local


def _mirror_urls(static_root: str):
    """(host, canonical path, [URL variants]) for every HTML file in the mirror.

    Yields the forms a citation could plausibly use for the same file: the file
    path itself, the extensionless permalink WordPress served it under, and —
    for an `index.html` — the directory. Query-string duplicates
    (`index.html?p=13.html`) are skipped: they are WordPress artefacts of pages
    the archive already holds canonically, and the key format drops queries
    anyway, so including them would map two different old URLs onto one key.
    """
    if not os.path.isdir(static_root):
        return
    for host in sorted(os.listdir(static_root)):
        host_path = os.path.join(static_root, host)
        if not (host.endswith(resolve.SITE) and os.path.isdir(host_path)):
            continue
        for dirpath, _dirs, files in os.walk(host_path):
            for name in files:
                if not name.lower().endswith((".html", ".htm")) or "?" in name:
                    continue
                full = os.path.join(dirpath, name)
                rel = "/" + os.path.relpath(full, host_path).replace(os.sep, "/")
                variants = [rel]
                stem = re.sub(r"\.html?$", "", rel, flags=re.I)
                if name.lower() in ("index.html", "index.htm"):
                    directory = rel.rsplit("/", 1)[0] or "/"
                    variants.append(directory)
                elif stem != rel:
                    variants.append(stem)
                yield host, rel, variants


def _key(host: str, path: str) -> str:
    """The map key: host plus a normalised path.

    Normalised through `resolve.clean_href` and percent-decoding, reusing the
    resolver rather than re-implementing it — writing this logic a second time
    is exactly what produced two disagreeing resolvers earlier in this work.
    The trailing slash is dropped so that `/fcj-001` and `/fcj-001/` are one
    key; whatever serves this map must normalise the same way, which is stated
    in the output.
    """
    clean = unquote(resolve.clean_href(path)) or "/"
    clean = "/" + clean.lstrip("/")
    if len(clean) > 1:
        clean = clean.rstrip("/")
    return f"{host.lower().removeprefix('www.')}{clean}"


def build(man: inventory.Manifest | None = None,
          static_root: str = resolve.STATIC_ROOT) -> RedirectReport:
    man = man or inventory.build()
    mapper = Mapper(man, static_root)
    report = RedirectReport()

    # Per-host fallback first, so the exact map never needs to restate it.
    # A URL on an issue host that is not content belongs at that issue; on the
    # apex, at the front page.
    for number, prefix in inventory.ISSUE_HOSTS:
        report.host_fallback[resolve.host_dir(prefix)] = f"/issues/{number}/"
    report.host_fallback[CANONICAL_HOST] = "/"
    # Every other host the crawl touched gets the front page. There is one:
    # `dev.fibreculturejournal.org`, a staging copy holding 36 theme assets and
    # no articles. Without this it is the only part of the old site that would
    # answer with nothing at all, and a reader who followed an old link there
    # should land on the journal, not on an error.
    if os.path.isdir(static_root):
        for name in sorted(os.listdir(static_root)):
            if name.endswith(resolve.SITE) and os.path.isdir(
                    os.path.join(static_root, name)):
                report.host_fallback.setdefault(name, "/")

    for url in cdx_urls():
        parts = urlsplit(url)
        host = parts.netloc.lower().removeprefix("www.")
        path = parts.path or "/"
        low = unquote(path).lower()
        report.kinds["asset" if low.endswith(ASSET_EXT)
                     else "doc" if low.endswith(DOC_EXT) else "page"] += 1

        target = mapper.path_for(host, path)
        key = _key(host, path)
        if target:
            report.exact[key] = target
            report.kinds["mapped"] += 1
        elif report.host_fallback.get(host):
            report.kinds["fallback"] += 1
        else:
            report.unmapped.append(url)

    # The mirror's own file layout as a third source.
    #
    # The crawl records what the crawler fetched, which is not the same as what
    # a citation might say. `one.fibreculturejournal.org/fcj002.html` is a real
    # historical URL for FCJ-002 that the crawl did not happen to request, so a
    # map built from the crawl alone sent it to the issue fallback instead of to
    # the paper. Walking the files closes that gap and makes coverage
    # independent of the crawler's luck.
    #
    # Both URL forms are registered for each file, because the WordPress
    # permalink and the underlying file disagree: `/fcj-001` was served from
    # `fcj-001.html`, and either could appear in a citation.
    for host_dir, path, variants in _mirror_urls(static_root):
        target = mapper.path_for(host_dir, path)
        if not target:
            continue
        for variant in variants:
            key = _key(host_dir, variant)
            if key not in report.exact:
                report.exact[key] = target
                report.kinds["from_mirror"] += 1

    # The conf as an independent second source.
    for host, path, hint in conf_rules():
        report.conf_rules += 1
        key = _key(host, path)
        if key in report.exact:
            continue
        target = mapper.path_for(host, path, hint_host=hint)
        if target:
            report.exact[key] = target
        else:
            report.conf_unmapped.append(f"{host}{path}")

    return report


# --------------------------------------------------------------------------
# output


def as_json(report: RedirectReport) -> str:
    payload = {
        "canonical_host": CANONICAL_HOST,
        "note": ("Keys are host + path, lower-cased host, percent-decoded path, "
                 "no trailing slash, no query, no fragment. A consumer MUST "
                 "normalise an incoming URL the same way before lookup. Try "
                 "'exact' first; fall back to 'host_fallback' for the request's "
                 "host; otherwise 404."),
        "status": 301,
        "exact": dict(sorted(report.exact.items())),
        "host_fallback": dict(sorted(report.host_fallback.items())),
        "counts": {
            "exact": len(report.exact),
            "hosts_with_fallback": len(report.host_fallback),
            "crawled_urls": sum(report.kinds[k] for k in ("asset", "doc", "page")),
            "unmapped": len(report.unmapped),
        },
    }
    return json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def as_map(report: RedirectReport) -> str:
    """`host+path<TAB>target`, one per line.

    A plain-text form for whatever ends up serving this — a Caddy or nginx map
    file, or a CloudFront KeyValueStore import. Generated from the same build in
    the same call as the JSON, so the two cannot disagree.
    """
    lines = ["# host+path\ttarget\t(301). Generated by build/redirects.py.",
             f"# normalise: lower-case host, percent-decode, strip trailing slash,"
             f" drop query and fragment."]
    lines += [f"{k}\t{v}" for k, v in sorted(report.exact.items())]
    lines += [f"# fallback\t{h}\t{t}" for h, t in sorted(report.host_fallback.items())]
    return "\n".join(lines) + "\n"


def write(report: RedirectReport, out_dir: str = CONTENT) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "redirects.json"), "w", encoding="utf-8") as fh:
        fh.write(as_json(report))
    with open(os.path.join(out_dir, "redirects.map"), "w", encoding="utf-8") as fh:
        fh.write(as_map(report))


def _main() -> None:
    report = build()
    write(report)
    print(f"redirects: {len(report.exact)} exact rules, "
          f"{len(report.host_fallback)} host fallbacks")
    print(f"  crawled URLs      : {sum(report.kinds[k] for k in ('asset', 'doc', 'page'))}"
          f" ({report.kinds['page']} pages, {report.kinds['asset']} assets, "
          f"{report.kinds['doc']} docs)")
    print(f"  mapped exactly    : {report.kinds['mapped']}")
    print(f"  covered by a host fallback: {report.kinds['fallback']}")
    print(f"  unmapped          : {len(report.unmapped)}")
    for url in report.unmapped[:8]:
        print(f"      {url[:96]}")
    print(f"  conf rules        : {report.conf_rules}, "
          f"unmappable {len(report.conf_unmapped)}")
    for item in report.conf_unmapped[:6]:
        print(f"      {item[:96]}")
    print(f"  written to {os.path.join(CONTENT, 'redirects.json')} and redirects.map")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    _main()
