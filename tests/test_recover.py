# Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
"""The recovered files are the archive's only content from outside the mirror.

Everything else here came off a crawl of the journal's own hosts. These 83
files came from the Wayback Machine, because the URLs that reference them point
at `journal.fibreculture.org` — the journal's pre-2008 domain, a different
domain from `fibreculturejournal.org`, never in the crawl's scope.

That makes provenance load-bearing rather than decorative, and these tests
check it: every file's bytes match the digest recorded for the snapshot they
came from, nothing arrived that is not media, and nothing is here that no
paper asks for.

No test in this file touches the network. Recovery is a deliberate act with a
record; the build and the suite work offline against what it brought back.
"""
from __future__ import annotations

import hashlib
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "build"))

import recover  # noqa: E402
import resolve  # noqa: E402

HAVE = os.path.isfile(recover.MANIFEST)
needs_recovered = unittest.skipUnless(
    HAVE, "recovered/ not populated; run build/recover.py")


class TestWhatToRecover(unittest.TestCase):
    """Pure: which references are recoveries and which are not."""

    def test_html_references_are_not_recoveries(self):
        """13 old-domain URLs are CITATIONS to the journal's own pre-2008
        articles — `issue1/issue1_barnet.html`. Those papers are already in
        this archive. Fetching them would publish a second copy of an article
        the archive holds, at a different URL, which is precisely the
        duplication this rebuild exists to clean up."""
        self.assertNotIn(".html", recover.RECOVER_EXT)
        self.assertNotIn(".htm", recover.RECOVER_EXT)

    def test_only_the_off_domain_host_is_fetched(self):
        """`wanted()` must not become a general link checker. It fetches from
        one named host the crawl could not reach — not from Wikipedia, Wired
        or any other site a paper happens to cite."""
        self.assertEqual(recover.OFF_DOMAIN, ("journal.fibreculture.org",))

    def test_a_recovered_path_cannot_escape_its_directory(self):
        for nasty in ("/../../etc/passwd", "/images/../../../x.jpg",
                      "/./images/./a.jpg/../../../../b.jpg"):
            got = recover.local_for("https://journal.fibreculture.org" + nasty)
            self.assertTrue(
                os.path.realpath(got).startswith(
                    os.path.realpath(recover.RECOVERED) + os.sep),
                f"{nasty} -> {got}")

    def test_percent_encoding_is_decoded_for_the_local_name(self):
        """One paper links `Beyond%20the%20Museum%20Walls.pdf`. Somebody
        looking for that file should find it under the name it has."""
        got = recover.local_for(
            "https://journal.fibreculture.org/issue7/"
            "issue7_ver2_Beyond%20the%20Museum%20Walls.pdf")
        self.assertTrue(got.endswith("Beyond the Museum Walls.pdf"), got)

    def test_only_media_types_are_accepted(self):
        """The soft-404 trap. The Wayback Machine can serve an HTML error page
        with status 200; written out as a `.jpg` it would look like a corrupt
        image forever after, with nothing to say why."""
        self.assertNotIn("text/html", recover.ALLOWED_TYPES)
        for allowed in ("image/", "application/pdf", "video/"):
            self.assertIn(allowed, recover.ALLOWED_TYPES)

    def test_extract_never_reaches_the_network(self):
        """A build has to be reproducible offline from the mirror plus
        `recovered/`.

        Checked against the network-CAPABLE names, not against `urllib`:
        `extract.py` legitimately uses `urllib.parse` to split and join URLs,
        which is string handling. An earlier version of this test banned
        `urllib` outright and failed on that — a test that is wrong about what
        it forbids teaches the wrong lesson about the boundary it guards.
        """
        with open(os.path.join(ROOT, "build", "extract.py"),
                  encoding="utf-8") as fh:
            source = fh.read()
        for forbidden in ("import recover", "urllib.request", "urlopen",
                          "import socket", "import http.client", "requests."):
            self.assertNotIn(forbidden, source,
                             f"extract.py must not reach the network: {forbidden}")

    def test_every_build_tool_but_recover_is_offline(self):
        """The boundary is worth asserting across the whole of `build/`, not
        only for `extract.py`: `recover.py` is the one place network access is
        allowed, and that is what makes everything else reproducible."""
        build = os.path.join(ROOT, "build")
        for name in sorted(os.listdir(build)):
            if not name.endswith(".py") or name == "recover.py":
                continue
            with open(os.path.join(build, name), encoding="utf-8") as fh:
                source = fh.read()
            for forbidden in ("urllib.request", "urlopen", "http.client"):
                self.assertNotIn(forbidden, source, f"{name}: {forbidden}")


@needs_recovered
class TestWhatWasRecovered(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rows = recover.read_manifest()
        cls.want = recover.wanted()

    def test_every_file_matches_its_recorded_digest(self):
        """The whole provenance claim rests on this. If the bytes on disk do
        not match the digest written when they were fetched, the manifest is
        describing a file that is no longer there."""
        bad = []
        for url, row in self.rows.items():
            path = recover.local_for(url)
            if not os.path.isfile(path):
                bad.append(f"missing: {url}")
                continue
            with open(path, "rb") as fh:
                data = fh.read()
            if hashlib.sha256(data).hexdigest() != row["sha256"]:
                bad.append(f"digest: {url}")
            elif len(data) != row["bytes"]:
                bad.append(f"size: {url}")
        self.assertEqual(bad, [])

    def test_every_recovered_file_records_its_snapshot(self):
        """A recovered file without a timestamp is a file of unknown origin,
        which is worse than a missing one."""
        for url, row in self.rows.items():
            self.assertRegex(row["timestamp"], r"^\d{14}$", url)
            self.assertTrue(row["referrers"], f"{url} referenced by nothing")

    def test_nothing_recovered_is_html(self):
        """Caught by content type at fetch time; asserted here on the bytes,
        because that check is the only thing standing between the archive and
        83 HTML error pages named `.jpg`."""
        for url in self.rows:
            path = recover.local_for(url)
            with open(path, "rb") as fh:
                head = fh.read(512).lstrip().lower()
            self.assertFalse(head.startswith(b"<!doctype html"), url)
            self.assertFalse(head.startswith(b"<html"), url)

    def test_every_recovered_file_is_actually_used(self):
        """`recovered/` is not a general cache: every file in it exists
        because the archive's text references it.

        Checked on the LOCAL path, not the original URL. `wanted()` now reads
        the manifest as well as `content/` — it has to, or recovery would be a
        one-way door, since `extract.py` repoints the Markdown at the local
        copy and the original URL vanishes. That makes "is this URL wanted?"
        trivially true for anything in the manifest, so the question worth
        asking is whether the recovered FILE reached the archive and is
        referenced by something.
        """
        content = os.path.join(ROOT, "content")
        text = []
        for sub in ("papers", "issues", "pages"):
            directory = os.path.join(content, sub)
            if not os.path.isdir(directory):
                continue
            for name in sorted(os.listdir(directory)):
                if name.endswith(".md"):
                    with open(os.path.join(directory, name),
                              encoding="utf-8") as fh:
                        text.append(fh.read())
        blob = "\n".join(text)
        unused = []
        for url in self.rows:
            rel = os.path.relpath(recover.local_for(url), recover.RECOVERED)
            if f"media/{rel}" not in blob:
                unused.append(url)
            elif not os.path.isfile(os.path.join(content, "media", rel)):
                unused.append(f"not copied: {url}")
        self.assertEqual(unused, [])

    def test_resolve_finds_a_recovered_file_and_refuses_a_missing_one(self):
        sample = next(iter(sorted(self.rows)))
        from urllib.parse import urlsplit
        parts = urlsplit(sample)
        self.assertIsNotNone(
            resolve.recovered_path(parts.netloc, parts.path), sample)
        self.assertIsNone(resolve.recovered_path(
            "journal.fibreculture.org", "/images/not-a-real-file.jpg"))

    def test_the_mirror_is_a_separate_lookup(self):
        """`local_path` and `recovered_path` are deliberately distinct, so a
        lookup can never fall through from the mirror into recovered content.
        "Did this come off the crawl?" has to stay answerable."""
        self.assertIsNone(resolve.recovered_path(
            "fibreculturejournal.org", "/files/2009/11/lockss.gif"))


if __name__ == "__main__":
    unittest.main()
