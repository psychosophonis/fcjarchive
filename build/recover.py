#!/usr/bin/env python3
# Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
"""Fetch files the crawl could not reach, and record where they came from.

116 references in `content/` point at `journal.fibreculture.org` — the
journal's pre-2008 domain. It is a DIFFERENT domain from
`fibreculturejournal.org`, so it was never in the crawl's scope, and nothing
under it is in the mirror.

Those files were not always missing. The WordPress migration imported some
images per page and left others as hand-written absolute URLs to the old
domain; on one page in FCJ-039 a migrated image carries `wp-image-109` while
the one beside it still points off-domain with its 2005 `width`/`height`. The
old domain still resolves, to the same failing host the archive exists to
replace, and now returns 503.

This fetches them from the Wayback Machine.

**It is the only writer of `recovered/`, and the only part of this archive that
reaches the network.** `extract.py` never calls it: recovery is a deliberate
act with a record, not a step in a build. Run it, commit what it brings back,
and the build is reproducible offline again.

Provenance is not optional here, because this is the archive's first content
from outside the crawled mirror. `recovered/MANIFEST.tsv` records for each file the
original URL, the Wayback timestamp the bytes came from, the sha256, the byte
count, and the papers that reference it — so a reader can tell a figure
recovered from a 2018 snapshot from one that came off the crawl.

    python3 build/recover.py --dry-run   # what is missing, and what is available
    python3 build/recover.py             # fetch it

Downloaded bytes are untrusted input. They land in their own directory, nothing
is executed, and a response that is not an image, PDF or video is REJECTED —
a Wayback soft-404 is an HTML error page served with status 200, which would
otherwise be written out as a .jpg.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content")
RECOVERED = os.path.join(ROOT, "recovered")
MANIFEST = os.path.join(RECOVERED, "MANIFEST.tsv")

# A generic client name. The journal's own details are not ours to put in a
# request to a third party.
AGENT = "fcj-archive-recovery/1.0"

# The host the crawl could not reach. A list, not a constant, because the next
# journal adopting this will have its own.
OFF_DOMAIN = ("journal.fibreculture.org",)

# Only media. An `.html` reference to this host is a CITATION to one of the
# journal's own pre-2008 articles — `issue1/issue1_barnet.html` — and that
# paper is already in this archive. Fetching it would publish a second copy of
# an article the archive already holds, under a different URL. Those need
# mapping to internal links, which is a different job from this one.
RECOVER_EXT = (".jpg", ".jpeg", ".png", ".gif", ".pdf", ".mov", ".mp4", ".mp3")

# What a recovered file is allowed to be, checked against the response's own
# Content-Type rather than its extension.
ALLOWED_TYPES = ("image/", "application/pdf", "video/", "audio/")

LINK = re.compile(r"!?\[[^\]]*\]\((https?://[^)\s]+)\)")
BARE = re.compile(r"(?<![(\w])(https?://[^\s)\]<>\"']+)")


@dataclass
class Want:
    url: str
    referrers: list[str] = field(default_factory=list)


def wanted(content_dir: str = CONTENT,
           manifest: str = MANIFEST) -> dict[str, Want]:
    """Every off-domain media URL this archive needs, and who referenced it.

    Read from `content/` AND from the manifest, because the two answer the
    question at different times. Once a file is recovered, `extract.py`
    repoints the Markdown at the local copy — so the original URL disappears
    from `content/` and a scan of it alone comes back almost empty. Recovery
    would then be a one-way door: nobody cloning the repository could re-derive
    what the archive depends on, or re-fetch a file that went missing.

    The manifest is what makes it repeatable. That is the second job of
    provenance, after saying where a file came from: saying what is still
    needed.
    """
    out: dict[str, Want] = {}
    for url, row in read_manifest(manifest).items():
        out.setdefault(url, Want(url)).referrers.extend(row["referrers"])
    for sub in ("papers", "issues", "pages"):
        directory = os.path.join(content_dir, sub)
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".md"):
                continue
            with open(os.path.join(directory, name), encoding="utf-8") as fh:
                text = fh.read()
            for url in set(LINK.findall(text)) | set(BARE.findall(text)):
                host = urllib.parse.urlsplit(url).netloc.lower()
                if host not in OFF_DOMAIN:
                    continue
                path = urllib.parse.urlsplit(url).path.lower()
                if not path.endswith(RECOVER_EXT):
                    continue
                out.setdefault(url, Want(url)).referrers.append(f"{sub}/{name}")
    return out


def local_for(url: str) -> str:
    """Where a recovered file lives: the mirror's own layout, one level up.

    Percent-decoded, because the mirror stores decoded names and a reader
    looking for `Beyond the Museum Walls.pdf` should find it under that name.
    """
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.unquote(parts.path).lstrip("/")
    # Refuse anything that could climb out of the directory.
    safe = [seg for seg in path.split("/") if seg not in ("", ".", "..")]
    return os.path.join(RECOVERED, parts.netloc.lower(), *safe)


def snapshot(url: str, timeout: int = 30) -> tuple[str, str] | None:
    """The closest Wayback snapshot that returned 200: (timestamp, raw url).

    The `id_` suffix asks for the original bytes rather than Wayback's
    rewritten page, which for an image is the difference between the file and
    an HTML viewer around it.
    """
    api = "https://archive.org/wayback/available?url=" + urllib.parse.quote(url, safe="")
    req = urllib.request.Request(api, headers={"User-Agent": AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            data = json.load(fh)
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None
    closest = data.get("archived_snapshots", {}).get("closest") or {}
    if closest.get("status") != "200" or not closest.get("timestamp"):
        return None
    stamp = closest["timestamp"]
    return stamp, f"https://web.archive.org/web/{stamp}id_/{url}"


def fetch(raw_url: str, timeout: int = 60) -> tuple[bytes | None, str] | None:
    """The bytes and the server's content type, or None on any failure.

    The exception list is deliberately broad. A narrow `(URLError,
    TimeoutError)` let an `http.client.IncompleteRead` — a response truncated
    partway through a 2 MB PDF — kill a run of 85 fetches on file 68. One
    flaky transfer must cost one file, not the whole job.
    """
    req = urllib.request.Request(raw_url, headers={"User-Agent": AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            declared = fh.headers.get("Content-Length")
            ctype = (fh.headers.get("Content-Type") or "").lower()
            body = fh.read()
    except http.client.IncompleteRead as short:
        # The snapshot is truncated AT SOURCE and the server still declares
        # the full length, so the read raises rather than returning short.
        # `.partial` holds what the Internet Archive actually has.
        return None, (f"truncated snapshot: {len(short.partial)} of "
                      f"{len(short.partial) + short.expected} bytes")
    except Exception:          # noqa: BLE001 - see docstring
        return None
    # A snapshot can be TRUNCATED AT SOURCE. One 2.2 MB PDF is held by the
    # Internet Archive as 130,710 bytes — 6% of the document — and the server
    # still declares the full length, which is what raised IncompleteRead.
    #
    # 6% of a PDF is not the PDF. Writing it out would put a file in the
    # archive that claims to be a document and cannot open, which is the same
    # failure as the soft-404 and worse than the gap it fills.
    if declared and declared.isdigit() and len(body) < int(declared):
        return None, f"truncated snapshot: {len(body)} of {declared} bytes"
    return body, ctype


def read_manifest(path: str = MANIFEST) -> dict[str, dict]:
    if not os.path.isfile(path):
        return {}
    rows = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5:
                continue
            url, stamp, digest, size, refs = parts[:5]
            rows[url] = {"timestamp": stamp, "sha256": digest,
                         "bytes": int(size), "referrers": refs.split(",")}
    return rows


def write_manifest(rows: dict[str, dict], path: str = MANIFEST) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [
        "# Files recovered from the Wayback Machine, which the crawl could not",
        "# reach. These are the archive's only content from outside the mirror.",
        "# Written by build/recover.py. Do not edit by hand.",
        "#",
        "# url\twayback_timestamp\tsha256\tbytes\treferenced_by",
    ]
    for url in sorted(rows):
        row = rows[url]
        lines.append("\t".join([
            url, row["timestamp"], row["sha256"], str(row["bytes"]),
            ",".join(sorted(set(row["referrers"]))),
        ]))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def recover(dry_run: bool = False, pause: float = 0.4) -> dict:
    want = wanted()
    rows = read_manifest()
    stats = {"wanted": len(want), "already": 0, "fetched": 0,
             "unavailable": [], "rejected": [], "failed": [],
             "truncated": []}

    for url, item in sorted(want.items()):
        target = local_for(url)
        # Idempotent: a file whose bytes already match its manifest line is
        # not re-fetched. Recovery runs against a third party; it should cost
        # one request per file, once.
        if url in rows and os.path.isfile(target):
            with open(target, "rb") as fh:
                if hashlib.sha256(fh.read()).hexdigest() == rows[url]["sha256"]:
                    rows[url]["referrers"] = item.referrers
                    stats["already"] += 1
                    continue

        found = snapshot(url)
        if found is None:
            stats["unavailable"].append(url)
            continue
        stamp, raw = found
        if dry_run:
            stats["fetched"] += 1
            continue

        got = fetch(raw)
        time.sleep(pause)
        if got is None:
            stats["failed"].append(url)
            continue
        body, ctype = got
        if body is None:                      # truncated at source
            stats["truncated"].append(f"{url} ({ctype})")
            continue
        # The soft-404 trap: Wayback can serve an HTML error page with status
        # 200, which would be written out as a .jpg and look like a corrupt
        # image forever after.
        if not any(ctype.startswith(t) for t in ALLOWED_TYPES) or not body:
            stats["rejected"].append(f"{url} ({ctype or 'no type'}, {len(body)}B)")
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as fh:
            fh.write(body)
        rows[url] = {"timestamp": stamp,
                     "sha256": hashlib.sha256(body).hexdigest(),
                     "bytes": len(body),
                     "referrers": item.referrers}
        stats["fetched"] += 1
        # Written after EVERY fetch, not once at the end. The manifest is the
        # provenance record: a crash partway through a long network job must
        # not leave files on disk whose origin nothing records. That happened
        # — 67 files, no manifest — and a file of unknown origin is worse in
        # an archive than a missing one.
        write_manifest(rows)

    if not dry_run:
        write_manifest(rows)
    stats["manifest"] = len(rows)
    return stats


def _main() -> int:
    dry = "--dry-run" in sys.argv
    stats = recover(dry_run=dry)
    print(f"{'would fetch' if dry else 'recovered/'}: "
          f"{stats['wanted']} referenced, {stats['already']} already present, "
          f"{stats['fetched']} {'available' if dry else 'fetched'}")
    for key in ("unavailable", "truncated", "rejected", "failed"):
        if stats[key]:
            print(f"  {key}: {len(stats[key])}")
            for item in stats[key][:10]:
                print(f"    {item}")
    if not dry:
        print(f"  manifest: {stats['manifest']} files in {MANIFEST}")
    return 1 if stats["failed"] or stats["rejected"] else 0


if __name__ == "__main__":
    sys.exit(_main())
