#!/usr/bin/env python3
# Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
"""Tests for build/audit_spam.py — docs/architecture.md, invariant 1.

Two failure modes, pulling in opposite directions:

  - a FALSE NEGATIVE publishes spam. 145 files are contaminated and the archive
    now takes one paper (FCJ-129) from the apex host, where all of it lives.
  - a FALSE POSITIVE forbids the archive from linking a source a paper really
    cites. That already happened once: `chcf.org`, the California Health Care
    Foundation, was flagged as injected into FCJ-144 because the author printed
    the URL as plain text in their reference list while the apex copy has it as
    a link.

So the rule tests below check both directions, and the guard is tested
explicitly rather than assumed.
"""
from __future__ import annotations

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "build"))

import audit_spam  # noqa: E402
import inventory  # noqa: E402
import resolve  # noqa: E402

CONTENT = os.path.join(ROOT, "content")
SITE = os.path.join(ROOT, "site")

HAVE_MIRROR = os.path.isdir(resolve.STATIC_ROOT)
HAVE_LIST = os.path.isfile(audit_spam.OUT)

needs_mirror = unittest.skipUnless(HAVE_MIRROR, "mirror not present")
needs_list = unittest.skipUnless(HAVE_LIST, "data/spam-domains.txt not built")


class TestHostExtraction(unittest.TestCase):
    """Pure."""

    def test_finds_linked_hosts_and_drops_www(self):
        html = '<p>see <a href="https://www.instantcasino.io/x">casino</a></p>'
        self.assertEqual(audit_spam.hosts_in(html), {"instantcasino.io"})

    def test_ignores_the_journals_own_hosts(self):
        html = ('<a href="https://one.fibreculturejournal.org/x">a</a>'
                '<a href="https://journal.fibreculture.org/y">b</a>')
        self.assertEqual(audit_spam.hosts_in(html), set())

    def test_ignores_theme_credit_links(self):
        """`themasterplan.in` is in 2,253 of the mirror's 2,278 files: the
        theme designer's credit, not an injection."""
        html = ('<a href="https://themasterplan.in/tma/">x</a>'
                '<a href="https://wordpress.org/">y</a>')
        self.assertEqual(audit_spam.hosts_in(html), set())

    def test_mentions_find_a_domain_that_is_not_a_link(self):
        """The guard must see a URL printed as plain text in a reference list.

        This is the chcf.org case: cited as text by the author, linked in the
        apex copy, and therefore not an injection.
        """
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                         encoding="utf-8") as fh:
            fh.write('<div class="post_text"><p>See http://www.chcf.org/report '
                     'for details.</p></div><div id="footer"></div>')
            path = fh.name
        try:
            self.assertIn("chcf.org", audit_spam._content_mentions(path))
            self.assertEqual(audit_spam._content_hosts(path), set())
        finally:
            os.unlink(path)


@needs_mirror
class TestTheDiscoveryRule(unittest.TestCase):
    report: audit_spam.SpamReport

    @classmethod
    def setUpClass(cls):
        cls.man = inventory.build()
        cls.report = audit_spam.build(man=cls.man)

    def test_it_compared_a_meaningful_number_of_twins(self):
        """The rule only works where an article exists twice. If this drops,
        the evidence base has shrunk and the list is weaker than it looks."""
        self.assertGreater(self.report.twins_compared, 150)

    def test_it_finds_the_domains_measured_by_hand(self):
        """The eight named in fcj-problems.md P1 and P3, found independently.

        Two of those eight — `bestecasinozondercruks.com` and
        `safecasinosnotongamstop.com` — are on apex pages with no clean twin,
        so the twin-diff cannot reach them; they must show up as unverifiable
        rather than silently vanish.
        """
        enforced = set(self.report.enforced)
        for domain in ("instantcasino.io", "onlinecasinomaxi.de", "bestwallet.com",
                       "exhalewell.com", "pokerscout.com"):
            self.assertIn(domain, enforced, domain)
        reachable = enforced | set(self.report.unverifiable)
        for domain in ("bestecasinozondercruks.com", "safecasinosnotongamstop.com",
                       "sambaslots.org"):
            self.assertIn(domain, reachable, f"{domain} unaccounted for")

    def test_a_domain_cited_on_an_issue_subdomain_is_never_enforced(self):
        """The guard. `chcf.org` is the measured case."""
        self.assertNotIn("chcf.org", self.report.enforced)
        self.assertIn("chcf.org", self.report.rejected)
        self.assertIn("subdomain", self.report.rejected["chcf.org"])

    def test_every_enforced_domain_carries_its_evidence(self):
        for domain in self.report.enforced:
            self.assertTrue(self.report.evidence.get(domain), domain)
            self.assertIn("not in", self.report.evidence[domain][0], domain)

    def test_the_list_is_sorted_and_deduplicated(self):
        self.assertEqual(self.report.enforced, sorted(set(self.report.enforced)))

    def test_the_build_is_deterministic(self):
        again = audit_spam.build(man=self.man)
        self.assertEqual(again.enforced, self.report.enforced)


@needs_list
class TestInvariantOne(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domains = audit_spam.load()
        cls.pattern = re.compile(
            r"(?i)\b(" + "|".join(re.escape(d) for d in cls.domains) + r")\b") \
            if cls.domains else None

    def test_the_generated_list_is_not_empty(self):
        self.assertGreater(len(self.domains), 50)

    def test_the_file_carries_its_provenance(self):
        with open(audit_spam.OUT, encoding="utf-8") as fh:
            head = fh.read(600)
        self.assertIn("GENERATED", head)
        self.assertIn("audit_spam.py", head)

    @unittest.skipUnless(os.path.isdir(os.path.join(CONTENT, "papers")),
                         "content/ not built")
    def test_no_file_in_the_archive_links_a_listed_domain(self):
        """Invariant 1 over `content/`, which is what people download."""
        hits = []
        for sub in ("papers", "issues"):
            directory = os.path.join(CONTENT, sub)
            for name in sorted(os.listdir(directory)):
                if not name.endswith(".md"):
                    continue
                text = inventory.read(os.path.join(directory, name))
                for match in self.pattern.finditer(text):
                    hits.append((name, match.group(0)))
        self.assertEqual(hits[:8], [], f"{len(hits)} spam references")

    @unittest.skipUnless(os.path.isfile(os.path.join(SITE, "index.html")),
                         "site/ not built")
    def test_no_published_page_links_a_listed_domain(self):
        """Invariant 1 over `site/`, which is what readers see."""
        hits = []
        for dirpath, _dirs, files in os.walk(SITE):
            if os.path.relpath(dirpath, SITE).split(os.sep)[0] == "media":
                continue
            for name in files:
                if not name.endswith(".html"):
                    continue
                path = os.path.join(dirpath, name)
                for match in self.pattern.finditer(inventory.read(path)):
                    hits.append((os.path.relpath(path, SITE), match.group(0)))
        self.assertEqual(hits[:8], [], f"{len(hits)} spam references")


if __name__ == "__main__":
    unittest.main()
