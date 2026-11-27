#!/usr/bin/env python3
"""PROBE — idea at risk: that the four lost editorials can be recovered from
fcj2022.sql.gz AND attributed to the correct issue.

Why this could be wrong, and how this probe tries to kill it:

 1. ATTRIBUTION. The obvious attribution rule is "parse the issue number out of
    the slug" (issue-01-editorial -> issue 1). The mirror already contains a
    counter-example: nineteen.fibreculturejournal.org/issue-1-ubiquity is issue
    NINETEEN's editorial under a slug that reads as issue 1. If the dump offers
    no better handle than the slug, recovery can silently file editorials under
    the wrong issues, which is worse than leaving them missing.
    -> The probe asks whether the dump is a MULTISITE dump, i.e. whether posts
       sit in per-blog tables (wp_<n>_posts) that identify the issue independently
       of the slug.

 2. USABLE CONTENT. The row might hold an empty, truncated or revision-only
    post_content.
    -> The probe measures the content it can actually extract.

 3. CLEAN CONTENT. The dump is from 2022 and the WordPress site was compromised
    at an unknown date. If the dump's editorial text is ALSO spam-injected, then
    recovery does not yield clean text and the plan needs a different source.
    -> The probe greps recovered content for known injected domains.

Run: python3 -I proofs/editorial-recovery.py
Read-only. Touches nothing outside its own stdout.
"""
import gzip
import os
import re
import sys

# Derived, not written out, for the reason given in `build/resolve.py`
# (`SOURCE_ROOT`): a surviving probe is evidence, and a probe with a dead
# absolute path in it is no longer runnable evidence.
DUMP = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "source", "fcj-kit", "fcj2022.sql.gz")
SLUGS = ["issue-01-editorial", "issue-02-editorial", "issue-05-editorial",
         "issue-23-issues-events-1-digital-networked-media"]
# measured injections, from the apex/twin diffs recorded in fcj-problems.md P3
SPAM = ["instantcasino", "onlinecasinomaxi", "bestecasinozondercruks",
        "safecasinosnotongamstop", "sambaslots", "pokerscout", "exhalewell",
        "bestwallet", "joywallet", "99bitcoins", "casinoohnelimit"]

# The attribution answer this probe is testing: blog_id -> domain -> issue.
# Note the blog id is NOT the issue number (issue 1 is blog 6), so wp_blogs is
# required; arithmetic on the id would be wrong.
EXPECT = {
    "issue-01-editorial": "one.fibreculturejournal.org",
    "issue-02-editorial": "two.fibreculturejournal.org",
    "issue-05-editorial": "five.fibreculturejournal.org",
    "issue-23-issues-events-1-digital-networked-media": "twentythree.fibreculturejournal.org",
}

INSERT = re.compile(rb"INSERT INTO `([^`]+)`")
BLOGS = re.compile(rb"\((\d+),\d+,'([a-z0-9.]*fibreculturejournal\.org)'")
blogs = {}
tables_seen = set()
post_tables = set()
# slug -> {table -> [row lengths]}
hits = {s: {} for s in SLUGS}

with gzip.open(DUMP, "rb") as fh:
    table = b"?"
    for line in fh:
        m = INSERT.search(line)
        if m:
            table = m.group(1)
            tables_seen.add(table.decode("utf-8", "replace"))
            if table.endswith(b"posts"):
                post_tables.add(table.decode("utf-8", "replace"))
        if table == b"wp_blogs":
            for bid, dom in BLOGS.findall(line):
                blogs[int(bid)] = dom.decode("utf-8", "replace")
        for slug in SLUGS:
            needle = slug.encode()
            if needle not in line:
                continue
            # split the extended INSERT into row tuples; crude but enough to
            # size the row and spot spam inside it
            for row in line.split(b"),("):
                if needle not in row:
                    continue
                t = table.decode("utf-8", "replace")
                hits[slug].setdefault(t, []).append(row)

print("=== is this a multisite dump? (attribution independent of slug) ===")
print(f"tables in dump: {len(tables_seen)}")
numbered = sorted(t for t in post_tables if re.match(r"wp_\d+_posts$", t))
print(f"post tables: {sorted(post_tables)}")
print(f"per-blog post tables (wp_<n>_posts): {len(numbered)} -> {numbered[:8]}")
multisite = len(numbered) > 0
print(f"MULTISITE: {multisite}")

print("\n=== can each lost editorial be found, and where? ===")
survived = True
for slug in SLUGS:
    if not hits[slug]:
        print(f"  {slug:<52} NOT FOUND  <-- kills recovery for this issue")
        survived = False
        continue
    for t, rows in sorted(hits[slug].items()):
        longest = max(rows, key=len)
        words = len(re.sub(rb"<[^>]+>", b" ", longest).split())
        spam_in = [s for s in SPAM if s.encode() in longest.lower()]
        print(f"  {slug:<52} {t:<16} rows={len(rows):<3} "
              f"longest={len(longest):>7}B ~{words:>5}w spam={spam_in or 'none'}")
        if spam_in:
            survived = False

print("\n=== does blog_id -> domain attribute each editorial to the right issue? ===")
print(f"wp_blogs rows mapped: {len(blogs)}")
for slug, want in EXPECT.items():
    per_blog = [t for t in hits[slug] if re.match(r"wp_\d+_posts$", t)]
    got = {blogs.get(int(t.split("_")[1])) for t in per_blog}
    ok = want in got
    print(f"  {slug:<52} {sorted(x for x in got if x)} expected={want} {'OK' if ok else 'MISMATCH'}")
    if not ok:
        survived = False

print("\n=== verdict ===")
if not multisite:
    print("ATTRIBUTION UNPROVEN: no per-blog post tables, so the dump gives no")
    print("issue handle beyond the slug — and issue-1-ubiquity proves slugs lie.")
    print("Recovery needs a third source: which issue root LINKS to the slug.")
    survived = False
print("IDEA SURVIVED" if survived else "IDEA DID NOT SURVIVE AS STATED")
sys.exit(0)
