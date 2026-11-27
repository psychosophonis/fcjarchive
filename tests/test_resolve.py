#!/usr/bin/env python3
# Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
"""Tests for build/resolve.py — docs/architecture.md, "API Contracts".

These run against the real mirror rather than fixtures. The five URL conventions
are facts about fcj-static, not properties of an abstraction, so a fixture that
I built would only test my own belief about the mirror — which is exactly what
was wrong twice today. Where a test needs no filesystem (ordering, href
cleaning) it is written as a pure unit test.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build"))

import resolve  # noqa: E402

HAVE_MIRROR = os.path.isdir(resolve.STATIC_ROOT)
needs_mirror = unittest.skipUnless(HAVE_MIRROR, f"mirror not at {resolve.STATIC_ROOT}")


class TestHrefCleaning(unittest.TestCase):
    """No filesystem: normalising what the source HTML actually contains."""

    def test_strips_trailing_space(self):
        # the mesh theme emits hrefs with a space inside the quotes
        self.assertEqual(clean := resolve.clean_href("/fcjmesh-002-x/ "), "/fcjmesh-002-x/")
        self.assertNotIn(" ", clean)

    def test_unescapes_entities(self):
        self.assertEqual(resolve.clean_href("/a&amp;b"), "/a&b")

    def test_drops_fragment_and_query(self):
        self.assertEqual(resolve.clean_href("/paper/#footnote-3"), "/paper/")
        self.assertEqual(resolve.clean_href("/index.html?p=13"), "/index.html")


class TestHostForms(unittest.TestCase):
    def test_accepts_prefix_and_full_domain(self):
        self.assertEqual(resolve.host_dir("one"), "one.fibreculturejournal.org")
        self.assertEqual(resolve.host_dir("one.fibreculturejournal.org"),
                         "one.fibreculturejournal.org")

    def test_apex_is_not_double_suffixed(self):
        self.assertEqual(resolve.host_dir("fibreculturejournal.org"),
                         "fibreculturejournal.org")


class TestCandidateOrdering(unittest.TestCase):
    """No filesystem: order must be fixed, because a host can hold both
    `fcj-001.html` and a `fcj-001/` directory."""

    def test_exact_file_before_directory_before_extensionless(self):
        c = resolve.candidates("one", "/fcj-001", static_root="/mirror")
        self.assertEqual(c[0], "/mirror/one.fibreculturejournal.org/fcj-001")
        self.assertEqual(c[1], "/mirror/one.fibreculturejournal.org/fcj-001/index.html")
        self.assertEqual(c[2], "/mirror/one.fibreculturejournal.org/fcj-001.html")

    def test_root_resolves_to_index(self):
        self.assertEqual(resolve.candidates("mesh", "/", static_root="/mirror"),
                         ["/mirror/mesh.fibreculturejournal.org/index.html"])


@needs_mirror
class TestTheFiveConventions(unittest.TestCase):
    def test_1_flat_file(self):
        p = resolve.local_path("one", "/fcj002.html")
        self.assertIsNotNone(p, "issue 1 stores papers as flat files")
        self.assertTrue(p.endswith("one.fibreculturejournal.org/fcj002.html"))

    def test_2_extensionless_url(self):
        # issue 1's own root links to /fcj-001; the file is fcj-001.html
        p = resolve.local_path("one", "/fcj-001")
        self.assertIsNotNone(p, "extensionless URLs are served from <slug>.html")
        self.assertTrue(p.endswith("fcj-001.html"))

    def test_3_directory_slug(self):
        p = resolve.local_path(
            "twentynine",
            "/fcj-218-train-ticket-sharing-alternative-forms-of-computing-in-the-city/")
        self.assertIsNotNone(p)
        self.assertTrue(p.endswith("index.html"))

    def test_4_dated_permalink(self):
        p = resolve.local_path(
            "twentyseven", "/2016/03/21/fcj-202-simulated-wars-virtual-engagements/")
        self.assertIsNotNone(p, "issue 27 uses dated permalinks")
        self.assertTrue(p.endswith("index.html"))

    def test_5_themed_intro_slug(self):
        p = resolve.local_path("twentyone", "/issue-21-affect-in-interaction/")
        self.assertIsNotNone(p, "issue intros use themed slugs")
        self.assertTrue(p.endswith("index.html"))


@needs_mirror
class TestTheKnownTraps(unittest.TestCase):
    def test_percent_encoded_utf8(self):
        # the en-dash in this slug is %E2%80%93 in every link that points at it
        p = resolve.local_path(
            "four",
            "/fcj-019-digital-monsters-binary-aliens-%E2%80%93-computer-viruses-"
            "capitalism-and-the-flow-of-information/")
        self.assertIsNotNone(p, "percent-encoded UTF-8 must be decoded before lookup")

    def test_unicode_normalisation(self):
        # trailing soft hyphen (%C2%AD); on disk it may be NFC or NFD
        p = resolve.local_path(
            "twentynine",
            "/fcj-221-collecting-elements-of-a-minor-future-commoning-in-"
            "alphabet-city%C2%AD/")
        self.assertIsNotNone(p, "must try NFC and NFD forms")

    def test_trailing_space_in_href(self):
        p = resolve.local_path(
            "mesh", "/fcjmesh-002-on-networked-utopias-and-speculative-futures/ ")
        self.assertIsNotNone(p, "mesh hrefs carry a trailing space inside the quotes")

    def test_prefix_and_full_domain_agree(self):
        self.assertEqual(resolve.local_path("one", "/fcj002.html"),
                         resolve.local_path("one.fibreculturejournal.org", "/fcj002.html"))


@needs_mirror
class TestFailureIsExplicit(unittest.TestCase):
    def test_unresolvable_returns_none(self):
        self.assertIsNone(resolve.local_path("one", "/no-such-paper-exists/"))

    def test_traversal_cannot_escape_host_dir(self):
        # the mirror comes from a compromised WordPress site, so ../ in an
        # attribute is not hypothetical
        self.assertIsNone(
            resolve.local_path("one", "/../twentynine.fibreculturejournal.org/index.html"))

    def test_apex_root_resolves(self):
        p = resolve.local_path("fibreculturejournal.org", "/")
        self.assertIsNotNone(p)
        self.assertTrue(p.endswith("fibreculturejournal.org/index.html"))


if __name__ == "__main__":
    unittest.main()
