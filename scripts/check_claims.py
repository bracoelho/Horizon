#!/usr/bin/env python3
"""The rule: every claim a reader could check, the draft must let them check.

The owner's rule, 2026-09-06, stated first as "every number in a draft must
carry its source line" and broadened by him in the same conversation: numbers
are one example, the rule is that a claim about the world is verifiable by
someone who is not the author.

It was written after a published commentary was found citing "roughly 60
percent of runs ended in resolution by force" from a study containing no such
figure. The number was invented at the drafting step: the radar's own summary
of that study carried no percentage at all. An adversarial pass then flagged
the sentence and supplied a per-model breakdown the study also does not
contain, which made the original look sourced and hid it for two more days.

WHAT THIS PROGRAM CAN AND CANNOT DO, and read this before trusting a pass.

A program cannot find claims. It can find the SHAPES a claim usually wears:
a number, a direct quotation, an attribution, an obligation. It finds those
and asks for a source. Everything else, including every confident sentence
with no marker in it, is beyond it and stays the reader's job. **So a clean
run means "the shapes I can see are sourced", never "this piece is true", and
the program says so on every pass rather than printing a bare success.**

HOW A DRAFT DECLARES ITS SOURCES

In the front matter, which Jekyll does not render, so nothing reaches the page:

    sources:
      - claim: "98 percent"
        url: https://www.anthropic.com/research/multiagent-systems
        quote: "98% of Mythos 5 runs ended in truce"

`claim` is matched against the body, so it must appear as written. `quote`
must be the source's OWN sentence, verbatim: a paraphrase is exactly how the
error this exists for was introduced. `url` must be fetchable by someone other
than the author.

    uv run python scripts/check_claims.py docs/_commentary/*.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

SPELLED = (r"half|third|quarter|twice|double|triple|dozen|hundreds?|"
           r"thousands?|millions?|billions?")

# Each shape is (name, pattern, what a reader would want to check).
SHAPES: List[Tuple[str, re.Pattern, str]] = [
    ("number", re.compile(
        r"(?<![\w/.-])(\d{1,3}(?:,\d{3})+"
        r"|\d+(?:\.\d+)?\s*(?:percent|%|x|×)"
        r"|\d+(?:\.\d+)?|" + SPELLED + r")(?![\w/-])", re.I),
     "the figure"),
    # Quotations are paired in code rather than by a regex: a pattern matching
    # "open ... close" also matches the GAP between two quoted phrases on one
    # line, which reported ' on who does what, ' as a quotation on the first
    # run of this file.
    ("quotation", None, "the quoted words"),
    ("attribution", re.compile(
        r"\b(according to|the study (?:found|shows|says)|research (?:shows|finds)"
        r"|reported(?: that)?|announced|confirmed|acknowledged|admitted"
        r"|(?:they|he|she|it) said|say[s]? that)\b", re.I),
     "who said it and where"),
    # "must" and "should" are excluded deliberately. In this voice they are
    # almost always the author's own recommendation ("teams must decide who
    # owns the contract"), not a claim about an external obligation, and a
    # check that flags the author's argument teaches the author to ignore it.
    # What stays is language that asserts somebody ELSE imposes something.
    ("obligation", re.compile(
        r"\b(required to|obliged to|mandates?|comes? into force"
        r"|takes? effect|deadline|under the [A-Z])\b", re.I),
     "the instrument and the date"),
    ("superlative", re.compile(
        r"\b(first|only|never before|unprecedented|no other|the largest"
        r"|the fastest|the worst)\b", re.I),
     "the comparison it rests on"),
]

# Scare quotes and the author's own coinages are not citations. An exemption
# is explicit and COUNTED, never silent: the voice linter learned the same
# lesson, that a suppression which hides inside a clean run is worse than the
# finding it suppresses.
EXEMPT = re.compile(r"<!--\s*claim-ok(?::\s*(.*?))?\s*-->")

SKIP_LINE = re.compile(r"^\s*(date|item_url|permalink|published|layout|score|"
                       r"title|theme|item_title):", re.I)
SKIP_TOKEN = re.compile(r"^(19|20)\d\d$")
# A version string is a name, not a quantity: "Sonnet 4.6", "Claude 3", "v2".
VERSION = re.compile(r"(?:[A-Z][A-Za-z]+|\bv)\s*\d+(?:\.\d+)*$")
# Structure, not quantity: a heading, an ordered list marker, or a reference to
# the document's own parts. Found on the first run across the back catalogue,
# where section numbering produced most of the noise.
STRUCTURAL = re.compile(r"^\s*(#{1,6}\s|\d+\.\s|[-*]\s*\*\*\d)")
PART_OF_DOC = re.compile(r"\b(sections?|steps?|beats?|parts?|rungs?|stages?|"
                         r"clauses?|items?|chapters?|figures?|tables?)\s*$", re.I)
# "sections 2 through 6": the second number is structure too, and the first
# pattern only sees the word immediately before a number.
DOC_RANGE = re.compile(r"\b(sections?|steps?|beats?|parts?|clauses?)\s+\d+\s*"
                       r"(?:through|to|and|-|–)\s*\d+", re.I)


def split_front_matter(text: str) -> Tuple[str, str]:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[: end + 4], text[end + 4:]
    return "", text


def declared(front: str) -> List[Dict[str, str]]:
    """Parse the sources block without a YAML dependency.

    Strict about shape on purpose: a malformed entry is REPORTED, never
    skipped, because a source block that quietly fails to parse would make an
    unsourced claim look sourced, which is this check's own version of the
    defect it was built for.
    """
    out: List[Dict[str, str]] = []
    in_block = False
    current: Dict[str, str] = {}
    for raw in front.splitlines():
        if re.match(r"^sources:\s*$", raw):
            in_block = True
            continue
        if not in_block:
            continue
        if raw and not raw.startswith((" ", "\t", "-")):
            break
        item = re.match(r"^\s*-\s*(\w+):\s*(.+?)\s*$", raw)
        field = re.match(r"^\s+(\w+):\s*(.+?)\s*$", raw)
        if item:
            if current:
                out.append(current)
            current = {item.group(1): item.group(2).strip('"\'')}
        elif field:
            current[field.group(1)] = field.group(2).strip('"\'')
    if current:
        out.append(current)
    return out


def paired_quotes(line: str) -> List[Tuple[str, int]]:
    """Return quoted spans by pairing delimiters in order, never by regex."""
    out = []
    open_at = None
    for i, ch in enumerate(line):
        if ch in '"\u201c\u201d':
            if open_at is None:
                open_at = i
            else:
                inner = line[open_at + 1:i]
                if len(inner) >= 12:
                    out.append((inner, open_at))
                open_at = None
    return out


def check(path: Path) -> Tuple[List[str], Dict[str, int]]:
    text = path.read_text(encoding="utf-8")
    front, body = split_front_matter(text)
    # Line numbers must address the FILE, not the body, or every finding sends
    # the reader to the wrong line. Found while using this on its first real
    # retro-fit, which is the only way that class of defect gets found.
    offset = front.count("\n")
    sources = declared(front)
    problems: List[str] = []
    seen: Dict[str, int] = {name: 0 for name, _, _ in SHAPES}

    for n, source in enumerate(sources, 1):
        for required in ("claim", "url", "quote"):
            if not source.get(required):
                problems.append(
                    f"{path}: source {n} has no {required}. A declaration "
                    "needs the claim as written, a URL someone else can "
                    "fetch, and the source's OWN sentence.")
        quote = source.get("quote", "")
        if quote and quote.rstrip(".").endswith(("...", "…")):
            problems.append(
                f"{path}: source {n}'s quote is elided. Quote the sentence "
                "whole: the figure this check was built for survived because "
                "a paraphrase looked like a citation.")

    exempted = [0]
    covered = [s.get("claim", "").lower() for s in sources if s.get("claim")]
    for lineno, line in enumerate(body.splitlines(), 1 + offset):
        if SKIP_LINE.match(line) or line.lstrip().startswith(">"):
            continue
        if EXEMPT.search(line):
            exempted[0] += 1
            continue
        for name, pattern, wants in SHAPES:
            spans = (paired_quotes(line) if pattern is None
                     else [(m.group(1) if m.groups() else m.group(0), m.start())
                           for m in pattern.finditer(line)])
            for token, start in spans:
                if name == "number":
                    if SKIP_TOKEN.match(token.replace(",", "")):
                        continue
                    if STRUCTURAL.match(line):
                        continue
                    if PART_OF_DOC.search(line[:start]):
                        continue
                    if DOC_RANGE.search(line):
                        continue
                    if VERSION.search(line[:start] + token):
                        continue
                seen[name] += 1
                if any(token.lower() in c or c in token.lower()
                       for c in covered):
                    continue
                problems.append(
                    f"{path}:{lineno}: {name} '{token.strip()}' has no source "
                    f"line. A reader would want {wants}.")
    seen["exempted"] = exempted[0]
    return problems, seen


def main(argv: List[str]) -> int:
    paths = [Path(a) for a in argv[1:]]
    if not paths:
        print(__doc__)
        return 2
    problems: List[str] = []
    totals: Dict[str, int] = {}
    for path in paths:
        if not path.exists():
            print(f"no such file: {path}")
            return 2
        found, seen = check(path)
        problems.extend(found)
        for k, v in seen.items():
            totals[k] = totals.get(k, 0) + v

    for problem in problems:
        print(problem)

    counted = ", ".join(f"{v} {k}" for k, v in totals.items() if v)
    # Printed on success as well as failure, and this is deliberate. A bare
    # "passed" from a claim checker would create exactly the false confidence
    # that let an invented statistic stand for five days.
    exempt = totals.pop("exempted", 0)
    counted = ", ".join(f"{v} {k}" for k, v in totals.items() if v)
    print(f"\nShapes examined: {counted or 'none'}."
          + (f" {exempt} line(s) exempted with claim-ok." if exempt else ""))
    print("NOT CHECKED, and no run of this program ever checks it: whether a "
          "sourced claim is TRUE, whether a quoted source says what the draft "
          "says it says, and every confident sentence carrying no marker at "
          "all. This finds shapes, not claims.")
    if problems:
        print(f"\n{len(problems)} unsourced. The rule (owner, 2026-09-06): "
              "every claim a reader could check, the draft must let them "
              "check.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
