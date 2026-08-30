#!/usr/bin/env python3
"""The STYLE.md grep audit, as a gate.

Tenure's lint-voice.py is the canonical checker and lives in the owner's design
project, which a CI runner does not have. This is the subset that can run here,
implementing the patterns STYLE.md documents in this repository.

It exists because the two do not overlap. A drafted piece passed lint-voice
cleanly while breaking the negative-to-positive rule three times, and nothing
caught it until the file was read by hand.

Usage:
  python scripts/check_voice.py docs/_commentary/some-piece.md
"""

import re
import sys
from pathlib import Path

CHECKS = [
    (
        "em dash",
        re.compile(r"[—]|\s–\s"),
        "Use a colon, a full stop or parentheses.",
    ),
    (
        "negative to positive",
        re.compile(
            r"\bnot (just|only|merely)\b|, not |\brather than\b|\binstead of\b",
            re.I,
        ),
        "Cut the negative half and state the positive claim.",
    ),
    (
        "promotional register",
        re.compile(
            r"\b(crucial|pivotal|game.?chang\w*|landscape|delve|unlock\w*|"
            r"leverag\w*|seamless|robust|elevate|empower\w*|harness|"
            r"streamline|holistic|synergy|tapestry|testament|vibrant)\b",
            re.I,
        ),
        "Use the plain word.",
    ),
]

# A line teaching a banned pattern is the one legitimate exception.
SKIP = re.compile(r"lint-ignore|data-lint=\"off\"")


# An HTML comment never reaches a reader, so auditing one flags writing that
# was never published. This is not hypothetical: the audit's own findings now
# ride into a draft as a comment, and that comment explains the "rather than"
# rule using the words "rather than", so the first draft under the new scheme
# reported two findings that were its own note talking about itself.
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def _blank_comments(text: str) -> str:
    """Replace comment bodies with blank lines, keeping line numbers true."""
    return COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def check(path: Path) -> list:
    findings = []
    body = _blank_comments(path.read_text(encoding="utf-8"))
    for n, line in enumerate(body.splitlines(), 1):
        if SKIP.search(line):
            continue
        for name, pattern, remedy in CHECKS:
            m = pattern.search(line)
            if m:
                findings.append((n, name, m.group(0).strip(), remedy))
    return findings


def main() -> int:
    paths = [Path(a) for a in sys.argv[1:]]
    if not paths:
        print("usage: check_voice.py FILE [FILE...]")
        return 2
    total = 0
    for path in paths:
        if not path.exists():
            print(f"{path}: missing")
            return 2
        for n, name, found, remedy in check(path):
            total += 1
            print(f"{path}:{n}: [{name}] {found!r}. {remedy}")
    if total:
        print(f"\n{total} voice violation(s).")
        return 1
    print(f"Clean: {len(paths)} file(s) pass the STYLE.md audit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
