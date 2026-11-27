#!/usr/bin/env python3
# Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
"""Map a URL path on an archived host to a file in the crawled mirror.

Governed by docs/architecture.md ("API Contracts").

This is the single point of failure for the whole build: inventory, editorial
recovery, redirect generation and link rewriting all resolve URLs through here.
It earns its own module and its own tests because the mirror mixes five URL
conventions, sometimes inside one issue, and a resolver that silently returns
None under-counts content without failing. Two earlier throwaway versions of
this logic did exactly that, missing 46 references between them before the
discrepancy showed up in a report.

The conventions, all observed in fcj-static:

  1. flat file            one/fcj002.html
  2. extensionless URL    /fcj-001         served from fcj-001.html
  3. directory slug       /fcj-218-slug/   served from .../index.html
  4. dated permalink      /2016/03/21/<slug>/
  5. themed intro slug    /issue-21-affect-in-interaction/

Conventions 3-5 are the same mechanism (directory + index.html) and need no
separate code; they are listed because they look different in the spec and in
the redirect map, and a reader should know they are already covered.
"""
from __future__ import annotations

import html
import os
import unicodedata
from urllib.parse import unquote

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Where the read-only inputs live: the project's `source/` directory, beside
# this repository. See docs/architecture.md ("Inputs").
#
# Derived from `__file__` rather than written out as an absolute path. This
# held `/Users/.../webdev/fcj-static` until the project was consolidated under
# `~/webdev/fibreculture/`, which made relocating a directory a code change —
# and a SILENT one, because every mirror-dependent test is guarded by
# `skipUnless(os.path.isdir(STATIC_ROOT))`: a wrong path here drops 52 of 240
# tests and the suite still reports OK.
#
# One constant, not two: `redirects.py` needs the same answer for the crawl
# index and the redirect conf, and derived it independently from its own
# location. Two expressions of "where the inputs are", with nothing enforcing
# that they agree, is the thing that turned one move into four edits.
SOURCE_ROOT = os.path.join(os.path.dirname(_REPO), "source")
STATIC_ROOT = os.path.join(SOURCE_ROOT, "fcj-static")
SITE = "fibreculturejournal.org"

# A SECOND input root, for files the crawl could not reach. 85 references in
# the archive point at `journal.fibreculture.org`, the journal's pre-2008
# domain — a different domain, so never in the crawl's scope and absent from
# the mirror entirely. `build/recover.py` fetches those from the Wayback
# Machine into here, laid out exactly like the mirror.
#
# Read-only to the build, as `STATIC_ROOT` is. It lives inside the repository
# because these bytes exist nowhere else now, and every one of them carries a
# line in `recovered/MANIFEST.tsv` saying which snapshot it came from.
RECOVERED_ROOT = os.path.join(_REPO, "recovered")


def host_dir(host: str) -> str:
    """Directory name for a host, given either a bare prefix or a full domain.

    Accepts "one", "one.fibreculturejournal.org" and the apex
    "fibreculturejournal.org" so callers can pass whatever their source gave
    them: the mirror and the redirect map use full domains, while issue code is
    naturally written as a prefix.
    """
    host = host.strip().lower()
    if host == SITE:
        return SITE
    return host if host.endswith("." + SITE) else f"{host}.{SITE}"


def recovered_path(host: str, url_path: str,
                   recovered_root: str = RECOVERED_ROOT) -> str | None:
    """A recovered file for an off-domain URL, or None.

    Separate from `local_path` rather than folded into it: `local_path`
    implements the mirror's five naming conventions, and a recovered tree has
    exactly one. Keeping them apart means a lookup can never silently fall
    through from the mirror into recovered content, so "did this come off the
    crawl?" stays an answerable question.
    """
    if not host or not url_path:
        return None
    decoded = unquote(url_path).lstrip("/")
    segments = [s for s in decoded.split("/") if s not in ("", ".", "..")]
    if not segments:
        return None
    candidate = os.path.join(recovered_root, host.lower(), *segments)
    # The traversal guard the mirror resolver has, for the same reason.
    root = os.path.realpath(recovered_root)
    if not os.path.realpath(candidate).startswith(root + os.sep):
        return None
    return candidate if os.path.isfile(candidate) else None


def clean_href(raw: str) -> str:
    """Normalise an href/src attribute value into a bare URL path.

    Three real defects in the source HTML make this necessary:
      - the mesh theme emits hrefs with a trailing space inside the quotes,
        which resolve as 404s if passed through verbatim;
      - attribute values are HTML-escaped, so "&amp;" must become "&" before
        any path comparison;
      - fragments and query strings are not part of a file's identity.

    Dropping the query has a deliberate consequence: the mirror contains
    duplicate files literally named `index.html?p=13.html`, and stripping the
    query makes them unreachable through this resolver. That is wanted — they
    are WordPress duplicates of pages the archive already holds canonically —
    but it is a decision, not an accident, so it is recorded here.
    """
    s = html.unescape(raw.strip())
    s = s.split("#", 1)[0]
    s = s.split("?", 1)[0]
    return s


def _forms(path: str) -> list[str]:
    """The same path in every Unicode normalisation macOS might have stored.

    APFS preserves whatever byte sequence was written, so a slug containing a
    soft hyphen or a curly apostrophe may exist on disk in NFC while the URL
    carries NFD, or the reverse. Trying both is cheaper and more honest than
    assuming either. The order is fixed so that resolution is deterministic
    between runs.
    """
    seen: set[str] = set()
    out: list[str] = []
    for f in (path, unicodedata.normalize("NFC", path),
              unicodedata.normalize("NFD", path)):
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def candidates(host: str, url_path: str, static_root: str = STATIC_ROOT) -> list[str]:
    """Candidate files for a URL path, in the order they should be preferred.

    Kept separate from local_path so the ordering is testable without touching a
    filesystem. Order is: exact file, then directory index, then the
    extensionless-URL form. Exact-file-first matters because a single host can
    hold both `fcj-001.html` and a `fcj-001/` directory, and without a fixed
    order which one wins would vary with the mirror's layout.
    """
    base = os.path.join(static_root, host_dir(host))
    rel = unquote(clean_href(url_path)).lstrip("/")
    if not rel:
        return [os.path.join(base, "index.html")]
    out: list[str] = []
    for form in _forms(rel):
        out.append(os.path.join(base, form))                # 1: flat file
        out.append(os.path.join(base, form, "index.html"))  # 3-5: directory
        out.append(os.path.join(base, form + ".html"))      # 2: extensionless
    return out


def local_path(host: str, url_path: str, static_root: str = STATIC_ROOT) -> str | None:
    """First existing file for this URL path, or None if nothing matches.

    Returns None rather than guessing. Callers MUST record a None as an
    unresolved reference (docs/architecture.md, inventory contract) instead of
    dropping it: a silently discarded reference is how both earlier versions of
    this logic produced reports that looked complete and were not.

    The containment check is a path-traversal guard. The mirror's hrefs come
    from a WordPress site that was compromised, so `../` sequences in an
    attribute are not merely hypothetical, and a resolver that can be walked out
    of its host directory would let one host's build read another's files.
    """
    base = os.path.realpath(os.path.join(static_root, host_dir(host)))
    for cand in candidates(host, url_path, static_root):
        real = os.path.realpath(cand)
        if real != base and not real.startswith(base + os.sep):
            continue  # escaped the host directory; not a legitimate candidate
        if os.path.isfile(real):
            return real
    return None
