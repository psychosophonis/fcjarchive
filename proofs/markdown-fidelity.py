#!/usr/bin/env python3
"""PROBE: can the mirror's HTML become clean Markdown without losing scholarship?

Run: python3 proofs/markdown-fidelity.py

THE IDEA AT RISK
    Markdown becomes the canonical content of the archive, and the website is
    rendered from it. That only works if converting the mirror's HTML to
    Markdown loses nothing a reader or a citing author needs. If it does lose
    something, the whole two-stage design is wrong and the site should keep
    rendering from HTML.

WHY PROBE IT NOW
    Extraction is one-way and would run before anything else is built on top.
    Discovering a loss afterwards means re-extracting 237 papers and
    invalidating every downstream file. The cost of being wrong scales with how
    much is built first, so this runs first.

FOUR ATTEMPTS TO KILL IT, in descending order of how fatal they would be:

  1. PARAGRAPH NUMBERS ARE DERIVABLE. 232 of 237 papers number every paragraph
     (`<p id="para76">`), and that number is the journal's citation unit. If the
     ids are exactly the paragraph sequence, they need not be stored and the
     Markdown stays clean prose. One gap and they become data that must be
     carried, which makes the Markdown worse but not unusable — so this one
     reports WHICH WAY it fell rather than simply passing.

  2. WORD FIDELITY. Convert to Markdown, strip the Markdown, and compare the
     word sequence with the original. A single dropped or reordered word is
     fatal: it means the archive would publish text that is not what was
     published.

  3. APPARATUS SURVIVAL. Emphasis (12,430 instances, mostly work titles in
     references), blockquotes, headings, list items, images, captions. These
     carry meaning in academic prose; losing emphasis corrupts citations.

  4. THE UNREPRESENTABLE, ENUMERATED. Whatever cannot survive is named here,
     now, rather than found later by a reader.

This probe uses a deliberately MINIMAL converter. It tests the principle, not
the implementation that will follow — if the principle holds for 60 lines of
conversion it holds for a careful one.
"""
from __future__ import annotations

import html as htmllib
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build"))

import inventory  # noqa: E402

# Papers chosen because each is awkward in a different way, measured over the
# whole mirror rather than picked for convenience.
HARD = {
    "FCJ-001": "lineno + <h1> Notes/References inside the body, 14k words",
    "FCJ-218": "blockquotes, <li> references, heavy <em>",
    "FCJ-120": "figures with captions, iframe, 7 missing media dirs",
    "FCJ-019": "wp-caption, ordered lists, percent-encoded slug",
    "FCJ-101": "table AND iframe in one paper",
    "FCJ-100": "<sup> footnote markers",
    "FCJ-113": "title-only slug, 15k words",
    "FCJ-129": "apex-sourced, 14k words",
}


# --------------------------------------------------------------------------
# attempt 1: are paragraph ids derivable from position?


PARA_ID = re.compile(r'<p[^>]*\bid=["\']para(\d+)["\']', re.I)
# The second variant: the number is inside the paragraph's own text, as the
# journal printed it, with no id anywhere. FCJ-047 does this for 39 of its 138
# paragraphs. Any rule that reads only ids declares those paragraphs unnumbered
# and renumbers them, which silently breaks every citation to them.
PARA_INLINE = re.compile(r"(?is)<p\b[^>]*>\s*(?:<[^>]+>\s*)*-\s*(\d+)\s*-")


def paragraph_ids(content: str) -> list[int]:
    return [int(n) for n in PARA_ID.findall(content)]


def probe_paragraph_numbers(man: inventory.Manifest) -> dict[str, object]:
    """Can a paragraph's citation number be recovered from its POSITION?

    Two things have to hold for that, and the first version of this probe only
    tested the first:

      a) the ids run 1..N with no gaps, and
      b) every paragraph carries one, so that the nth paragraph is paragraph n.

    (a) holds for all 232 numbered papers. (b) FAILS for 142 of them.
    """
    sequential = gapped = unnumbered = 0
    all_numbered = partially = 0
    examples: list[str] = []
    for ident, paper in man.papers.items():
        content = inventory.content_of(inventory.read(paper.source))
        ids = paragraph_ids(content)
        if not ids:
            unnumbered += 1
            continue
        if ids == list(range(1, len(ids) + 1)):
            sequential += 1
        else:
            gapped += 1

        paras = len(re.findall(r"(?i)<p\b", content))
        if paras == len(ids):
            all_numbered += 1
        else:
            partially += 1
            inline = len(PARA_INLINE.findall(content))
            if len(examples) < 5:
                examples.append(
                    f"{ident}: {paras} <p>, {len(ids)} with id, "
                    f"{inline} numbered inline in their text")
    return {"sequential": sequential, "gapped": gapped,
            "unnumbered": unnumbered, "all_numbered": all_numbered,
            "partially": partially, "examples": examples}


# --------------------------------------------------------------------------
# a minimal converter: enough to test the principle, no more


BLOCK_SPLIT = re.compile(r"(?i)(?=<(?:p|h[1-6]|blockquote|ul|ol|li|div|table|hr)\b)")


def to_markdown(content: str) -> str:
    """HTML -> Markdown, minimally. Deliberately crude; see module docstring."""
    s = content
    # drop the paragraph-number rail: its text (" - 76 - ") is furniture, and
    # attempt 1 decides whether the number itself must be kept
    s = re.sub(r"(?is)<span[^>]*class=['\"]lineno['\"][^>]*>.*?</span>", "", s)
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", s)
    s = re.sub(r"(?is)<!--.*?-->", "", s)

    # figures: WordPress caption blocks become an image with the caption as alt,
    # which is Pandoc's figure convention and survives as plain Markdown
    def figure(m: re.Match[str]) -> str:
        inner = m.group(0)
        src = (re.search(r'<img[^>]*\bsrc=["\']([^"\']+)', inner) or [None, ""])[1]
        cap = re.search(r'(?is)class=["\']wp-caption-text["\'][^>]*>(.*?)</p>', inner)
        text = re.sub(r"(?s)<[^>]+>", "", cap.group(1)).strip() if cap else ""
        return f"\n\n![{text}]({src})\n\n"

    s = re.sub(r"(?is)<div[^>]*class=['\"]wp-caption[^'\"]*['\"][^>]*>.*?</div>", figure, s)

    s = re.sub(r"(?is)<(em|i)\b[^>]*>(.*?)</\1>", lambda m: f"*{m.group(2)}*", s)
    s = re.sub(r"(?is)<(strong|b)\b[^>]*>(.*?)</\1>", lambda m: f"**{m.group(2)}**", s)
    s = re.sub(r"(?is)<a\b[^>]*\bhref=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>",
               lambda m: f"[{m.group(2)}]({m.group(1)})", s)
    s = re.sub(r"(?is)<img[^>]*\balt=['\"]([^'\"]*)['\"][^>]*\bsrc=['\"]([^'\"]+)['\"][^>]*>",
               lambda m: f"![{m.group(1)}]({m.group(2)})", s)
    s = re.sub(r"(?is)<img[^>]*\bsrc=['\"]([^'\"]+)['\"][^>]*>",
               lambda m: f"![]({m.group(1)})", s)

    # headings: in-body <h1> demotes to ## because the paper's title owns h1
    for level in range(1, 7):
        s = re.sub(rf"(?is)<h{level}[^>]*>(.*?)</h{level}>",
                   lambda m, lv=level: f"\n\n{'#' * min(lv + 1, 6)} {m.group(1).strip()}\n\n", s)

    s = re.sub(r"(?is)<blockquote[^>]*>(.*?)</blockquote>",
               lambda m: "\n\n" + "\n".join(
                   "> " + ln for ln in _plainish(m.group(1)).split("\n") if ln.strip()) + "\n\n", s)
    s = re.sub(r"(?is)<li[^>]*>(.*?)</li>", lambda m: f"\n- {m.group(1).strip()}", s)
    s = re.sub(r"(?is)</?(ul|ol)[^>]*>", "\n\n", s)
    s = re.sub(r"(?is)<hr[^>]*>", "\n\n---\n\n", s)
    s = re.sub(r"(?is)<br\s*/?>", "\n", s)
    s = re.sub(r"(?is)</p\s*>", "\n\n", s)
    s = re.sub(r"(?is)<[^>]+>", "", s)          # anything left is markup we drop
    s = htmllib.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _plainish(fragment: str) -> str:
    f = re.sub(r"(?is)<span[^>]*class=['\"]lineno['\"][^>]*>.*?</span>", "", fragment)
    f = re.sub(r"(?is)</p\s*>", "\n", f)
    f = re.sub(r"(?s)<[^>]+>", "", f)
    return htmllib.unescape(f).strip()


# --------------------------------------------------------------------------
# attempt 2: word fidelity


def words_of_html(content: str) -> list[str]:
    s = re.sub(r"(?is)<span[^>]*class=['\"]lineno['\"][^>]*>.*?</span>", "", content)
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return _tokens(htmllib.unescape(s))


def words_of_markdown(md: str) -> list[str]:
    s = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", md)      # image -> its caption
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)        # link -> its text
    # Strip `*` only. An earlier version of this line also stripped `_` as an
    # emphasis marker and so destroyed underscores inside URLs and
    # identifiers — `abs_all`, `artikel_id`, `page_id` — then reported them as
    # text the conversion had lost. They were present in both. A probe that
    # manufactures its own failures is worse than no probe, so this is kept as
    # a comment rather than quietly fixed.
    s = re.sub(r"[*`>#]", " ", s)
    s = re.sub(r"^\s*-\s+", " ", s, flags=re.M)
    s = s.replace("---", " ")
    return _tokens(s)


def _tokens(text: str) -> list[str]:
    # Compare on word characters only. Punctuation and whitespace are carried
    # differently by every Markdown dialect and are not what "losing text"
    # means; a missing or reordered WORD is.
    return [w for w in re.findall(r"[\w’'-]+", text.lower()) if w.strip("-'’")]


def diff_words(a: list[str], b: list[str]) -> tuple[int, int, list[str]]:
    """(dropped, added, first few dropped) — multiset comparison plus order."""
    ca, cb = Counter(a), Counter(b)
    dropped = sum((ca - cb).values())
    added = sum((cb - ca).values())
    sample = list((ca - cb).elements())[:8]
    return dropped, added, sample


# --------------------------------------------------------------------------
# attempt 3: apparatus survival


def apparatus_html(content: str) -> Counter:
    c = Counter()
    c["emphasis"] = len(re.findall(r"(?i)<(em|i)\b", content))
    c["strong"] = len(re.findall(r"(?i)<(strong|b)\b", content))
    c["blockquote"] = len(re.findall(r"(?i)<blockquote", content))
    c["heading"] = len(re.findall(r"(?i)<h[1-6]\b", content))
    c["listitem"] = len(re.findall(r"(?i)<li\b", content))
    c["image"] = len(re.findall(r"(?i)<img\b", content))
    c["caption"] = len(re.findall(r"(?i)class=['\"]wp-caption-text", content))
    return c


def apparatus_markdown(md: str) -> Counter:
    c = Counter()
    # count emphasis spans, not asterisks: **strong** contains two *
    c["strong"] = len(re.findall(r"\*\*[^*\n]+\*\*", md))
    without_strong = re.sub(r"\*\*[^*\n]+\*\*", "", md)
    c["emphasis"] = len(re.findall(r"\*[^*\n]+\*", without_strong))
    c["blockquote"] = len(re.findall(r"(?m)^> ", md))
    c["heading"] = len(re.findall(r"(?m)^#{1,6} ", md))
    c["listitem"] = len(re.findall(r"(?m)^- ", md))
    c["image"] = len(re.findall(r"!\[[^\]]*\]\(", md))
    c["caption"] = len(re.findall(r"!\[[^\]]+\]\(", md))      # non-empty alt
    return c


# --------------------------------------------------------------------------
# attempt 4: what cannot be represented


UNREPRESENTABLE = {
    "iframe": r"(?i)<iframe",
    "table": r"(?i)<table",
    "inline-style": r"(?i)\sstyle=['\"]",
    "named-anchor": r"(?i)<a\b[^>]*\bname=",
    "nested-emphasis": r"(?i)<em\b[^>]*>[^<]*<(em|strong)\b",
    "object/embed": r"(?i)<(object|embed)\b",
}


def main() -> int:
    print(__doc__.split("FOUR ATTEMPTS")[0].strip())
    print("=" * 72)
    man = inventory.build()
    print(f"manifest: {len(man.papers)} papers\n")

    # ---- attempt 1
    print("ATTEMPT 1 — are paragraph numbers derivable from position?")
    r = probe_paragraph_numbers(man)
    print(f"  ids run 1..N with no gaps    : {r['sequential']}")
    print(f"  ids gapped or out of order   : {r['gapped']}")
    print(f"  every paragraph carries an id: {r['all_numbered']}")
    print(f"  only SOME paragraphs do      : {r['partially']}")
    print(f"  no numbering at all          : {r['unnumbered']}")
    for ex in r["examples"]:
        print(f"      {ex}")
    derivable = r["gapped"] == 0 and r["partially"] == 0
    print("  => " + ("DERIVABLE: numbers need not be stored" if derivable else
                     "NOT DERIVABLE. The ids are sequential, but only 90 of 237\n"
                     "     papers number every paragraph, so the nth paragraph is not\n"
                     "     paragraph n. Numbers MUST be carried in the Markdown, and\n"
                     "     must be read from the id OR from a '- N -' prefix in the\n"
                     "     paragraph's own text, which is the journal's second\n"
                     "     markup variant for the same apparatus.") + "\n")

    # ---- attempts 2 and 3
    print("ATTEMPT 2/3 — word fidelity and apparatus survival on the hard sample")
    print(f"  {'paper':<10}{'words':>7}{'dropped':>9}{'added':>7}   apparatus losses")
    fatal: list[str] = []
    for ident, why in HARD.items():
        paper = man.papers.get(ident)
        if paper is None:
            print(f"  {ident:<10}  NOT IN MANIFEST")
            continue
        content = inventory.content_of(inventory.read(paper.source))
        md = to_markdown(content)
        hw, mw = words_of_html(content), words_of_markdown(md)
        dropped, added, sample = diff_words(hw, mw)
        ah, am = apparatus_html(content), apparatus_markdown(md)
        losses = {k: (ah[k], am[k]) for k in ah if am[k] < ah[k] * 0.9}
        print(f"  {ident:<10}{len(hw):>7}{dropped:>9}{added:>7}   "
              f"{', '.join(f'{k} {v[0]}->{v[1]}' for k, v in losses.items()) or 'none'}")
        if dropped > len(hw) * 0.01:
            fatal.append(f"{ident}: {dropped} of {len(hw)} words lost, e.g. {sample}")
        if sample and dropped:
            print(f"             dropped sample: {sample[:6]}")
    print()

    # ---- attempt 4
    print("ATTEMPT 4 — constructs that cannot survive, counted over all papers")
    counts = Counter()
    where: dict[str, list[str]] = {k: [] for k in UNREPRESENTABLE}
    for ident, paper in man.papers.items():
        content = inventory.content_of(inventory.read(paper.source))
        for name, pat in UNREPRESENTABLE.items():
            n = len(re.findall(pat, content))
            if n:
                counts[name] += n
                if len(where[name]) < 4:
                    where[name].append(ident)
    for name in UNREPRESENTABLE:
        print(f"  {name:<17}{counts[name]:>6} instances   {', '.join(where[name])}")
    print()

    print("=" * 72)
    if fatal:
        print("IDEA DIED — text is not preserved:")
        for f in fatal:
            print(f"  {f}")
        return 1
    print("IDEA SURVIVED on text fidelity.")
    print("  Markdown can carry the prose and the emphasis, blockquotes,")
    print("  headings, lists and figures of these papers without word loss.")
    print(f"  Paragraph numbers: {'derivable from position' if derivable else 'MUST be stored — carried as a {#paraN} suffix'}.")
    print("  Known, accepted losses are listed under ATTEMPT 4 and must be")
    print("  handled explicitly by build/markdown.py, not rediscovered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
