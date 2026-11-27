#!/usr/bin/env python3
# Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
"""Tests for build/redirects.py — docs/architecture.md, invariant 5.

The failure mode here is specific and silent: a map that covers most URLs looks
finished and loses one citation in ten. So the tests are about COVERAGE and
about targets existing, not about the mapping function's internals.

A redirect into nothing is worse than a 404, because it looks like the archive
answered. `test_every_target_exists_in_the_output` is the one that matters most.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "build"))

import inventory  # noqa: E402
import redirects  # noqa: E402
import resolve  # noqa: E402

SITE_DIR = os.path.join(ROOT, "site")
CONTENT = os.path.join(ROOT, "content")
MAP_FILE = os.path.join(CONTENT, "redirects.json")

HAVE_MIRROR = os.path.isdir(resolve.STATIC_ROOT)
HAVE_CDX = os.path.isfile(redirects.CDX)
HAVE_MAP = os.path.isfile(MAP_FILE)

needs_mirror = unittest.skipUnless(HAVE_MIRROR and HAVE_CDX,
                                  "mirror or crawl index not present")
needs_map = unittest.skipUnless(HAVE_MAP, "content/redirects.json not built")


class TestKeyNormalisation(unittest.TestCase):
    """Pure. The key format is a contract with whatever serves the map."""

    def test_trailing_slash_is_not_part_of_the_key(self):
        self.assertEqual(redirects._key("one.fibreculturejournal.org", "/fcj-001"),
                         redirects._key("one.fibreculturejournal.org", "/fcj-001/"))

    def test_percent_encoding_is_decoded(self):
        a = redirects._key("four.fibreculturejournal.org", "/fcj-019-a%E2%80%93b/")
        b = redirects._key("four.fibreculturejournal.org", "/fcj-019-a–b")
        self.assertEqual(a, b)

    def test_host_case_and_www_are_normalised(self):
        self.assertEqual(redirects._key("WWW.One.FibrecultureJournal.Org", "/x"),
                         redirects._key("one.fibreculturejournal.org", "/x"))

    def test_query_and_fragment_are_dropped(self):
        self.assertEqual(redirects._key("one.fibreculturejournal.org", "/x?p=3#a"),
                         redirects._key("one.fibreculturejournal.org", "/x"))

    def test_root_keeps_its_slash(self):
        self.assertTrue(redirects._key("one.fibreculturejournal.org", "/")
                        .endswith("/"))

    def test_host_is_part_of_the_key(self):
        """`/fcj-001` existed on the apex AND on `one.`, and they are different
        historical URLs that may land in different places."""
        self.assertNotEqual(redirects._key("one.fibreculturejournal.org", "/fcj-001"),
                            redirects._key("fibreculturejournal.org", "/fcj-001"))


class TestConfParsing(unittest.TestCase):
    @needs_mirror
    def test_all_214_rules_parse(self):
        """207 rules redirect; 7 serve a 503 and so name no target at all.

        Those seven are the held-back articles in fcj-problems.md P1. They
        legitimately have an empty target host, and the map still resolves them
        because it works from the article's identity rather than from the rule.
        """
        rules = redirects.conf_rules()
        self.assertEqual(len(rules), 214)
        with_target = [r for r in rules if r[2]]
        self.assertEqual(len(with_target), 207)
        self.assertEqual(len(rules) - len(with_target), 7)
        for host, path, target in rules:
            self.assertTrue(path.startswith("/"), path)
            self.assertTrue(not target or target.endswith(resolve.SITE), target)


@needs_mirror
class TestCoverage(unittest.TestCase):
    report: redirects.RedirectReport

    @classmethod
    def setUpClass(cls):
        cls.man = inventory.build()
        cls.report = redirects.build(cls.man)

    def test_every_crawled_url_that_served_an_article_is_mapped(self):
        """Invariant 5, as the probe restated it.

        The crawl is the authority on which URLs existed: 3,896 records, all
        status 200. An unmapped URL that served an article is a citation the
        archive breaks, so the assertion is zero, not "few".
        """
        unmapped_content = []
        for url in self.report.unmapped:
            from urllib.parse import urlsplit
            parts = urlsplit(url)
            local, _ = inventory.resolve_with_apex(
                parts.netloc.lower().removeprefix("www."), parts.path or "/",
                resolve.STATIC_ROOT)
            if local and local.lower().endswith((".html", ".htm")):
                if inventory.fcj_id(inventory.read(local)):
                    unmapped_content.append(url)
        self.assertEqual(unmapped_content, [])

    def test_every_paper_is_reachable_from_at_least_one_old_url(self):
        """Coverage from the other direction.

        The test above asks whether every old URL leads somewhere. This asks
        whether every paper can still be FOUND by an old URL — the two can both
        look fine while a paper has quietly become unreachable from the
        historical web.
        """
        targets = set(self.report.exact.values())
        import extract
        missing = [p.fcj_id for p in self.man.papers.values()
                   if f"/papers/{extract.paper_dir(p)}/" not in targets]
        self.assertEqual(missing, [])

    def test_all_214_conf_rules_are_covered(self):
        self.assertEqual(self.report.conf_unmapped, [])
        self.assertEqual(self.report.conf_rules, 214)

    def test_the_seven_held_back_articles_map_to_their_clean_copies(self):
        """fcj-problems.md P1: seven rules served 503 on a false premise.

        All five articles have clean twins on their issue subdomains. The map
        must send those apex URLs to the papers, which is the whole fix.
        """
        for ident in ("FCJ-004", "FCJ-138", "FCJ-198", "FCJ-199", "FCJ-202"):
            paper = self.man.papers[ident]
            import extract
            expected = f"/papers/{extract.paper_dir(paper)}/"
            self.assertIn(expected, self.report.exact.values(), ident)

    def test_every_host_in_the_mirror_has_a_fallback(self):
        for name in os.listdir(resolve.STATIC_ROOT):
            if name.endswith(resolve.SITE) and os.path.isdir(
                    os.path.join(resolve.STATIC_ROOT, name)):
                self.assertIn(name, self.report.host_fallback, name)

    def test_every_target_is_a_root_relative_path(self):
        """No target may be an absolute URL.

        A media target legitimately CONTAINS a host name, because the media
        tree keeps the mirror's own layout — `/media/eighteen.fibreculture…
        /files/2011/09/11_ZWR.jpg`. That is a path segment, not a host, so the
        test is about the shape of the target, not about the string appearing
        in it.
        """
        for key, target in self.report.exact.items():
            self.assertTrue(target.startswith("/"), f"{key} -> {target}")
            self.assertNotIn("://", target, f"{key} -> {target}")
            self.assertFalse(target.startswith("//"), f"{key} -> {target}")

    def test_the_build_is_deterministic(self):
        again = redirects.build(self.man)
        self.assertEqual(redirects.as_json(self.report), redirects.as_json(again))

    def test_apex_and_subdomain_copies_agree_on_the_paper(self):
        """The finding the probe produced, as a test.

        The mirror holds the same article at the apex and on its issue
        subdomain. A map keyed on the resolved FILE sent the apex copy nowhere,
        because the archive publishes only the subdomain copy — 247 article URLs
        unmapped. Keyed on the FCJ citation, both land on the same paper.
        """
        paper = self.man.papers["FCJ-004"]
        import extract
        expected = f"/papers/{extract.paper_dir(paper)}/"
        apex = self.report.exact.get(redirects._key(
            resolve.SITE, "/fcj-004-the-military-entertainment-complex-a-new-facet-of-information-warfare"))
        self.assertEqual(apex, expected)


@needs_map
class TestTheWrittenMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(MAP_FILE, encoding="utf-8") as fh:
            cls.payload = json.load(fh)

    def test_it_states_how_to_normalise_a_lookup(self):
        """The key format is a contract. A consumer that normalises differently
        gets silent misses, so the file has to say what the rule is."""
        note = self.payload["note"].lower()
        for word in ("host", "percent-decode", "trailing slash", "query"):
            self.assertIn(word, note)

    def test_it_declares_a_301(self):
        self.assertEqual(self.payload["status"], 301)

    @unittest.skipUnless(os.path.isdir(SITE_DIR), "site/ not built")
    def test_every_target_exists_in_the_output(self):
        """A redirect into nothing is worse than a 404: it looks like an answer.

        This is the test that has to hold before any DNS change.
        """
        broken = []
        for key, target in list(self.payload["exact"].items()) + \
                list(self.payload["host_fallback"].items()):
            path = target.lstrip("/")
            candidate = os.path.join(SITE_DIR, path)
            if os.path.isdir(candidate):
                candidate = os.path.join(candidate, "index.html")
            elif not path:
                candidate = os.path.join(SITE_DIR, "index.html")
            if not os.path.isfile(candidate):
                broken.append((key, target))
        self.assertEqual(broken[:10], [], f"{len(broken)} redirects into nothing")

    def test_the_map_file_and_the_json_agree(self):
        """Two artefacts that must match, so something has to check them."""
        with open(os.path.join(CONTENT, "redirects.map"), encoding="utf-8") as fh:
            lines = [ln for ln in fh.read().splitlines()
                     if ln and not ln.startswith("#")]
        pairs = dict(ln.split("\t", 1) for ln in lines)
        self.assertEqual(pairs, self.payload["exact"])


if __name__ == "__main__":
    unittest.main()
