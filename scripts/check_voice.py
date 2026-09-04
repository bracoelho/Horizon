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

# ---------- registered names ----------
# The owner's ruling, 2026-09-04 (~/AI-Proj/OS/DOCTRINE-AUDIENCE.md): a style
# rule governs word choice in prose and never the name of a thing, and the
# accept list is the glossary read at check time so no copy can drift. Tenure's
# lint-voice.py does the same from the same file. The glossary is person-level
# and local-only by charter, so a CI runner does not have it: absent, this
# gate behaves exactly as it did before and says which list it used, because a
# check that quietly changes the rules it applied is worse than one that fails.
GLOSSARY_SOURCE = Path.home() / "AI-Proj/OS/GLOSSARY.md"


def load_registered_names() -> list:
    """First column of the glossary: names no style rule may touch."""
    if not GLOSSARY_SOURCE.exists():
        return []
    names = []
    for line in GLOSSARY_SOURCE.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("|") or line.startswith("|---") or "| Our name" in line:
            continue
        cell = line.split("|")[1].strip()
        if cell and not set(cell) <= set("-: "):
            names.append(cell)
    return names


def _mask_names(line: str, names: list) -> str:
    """Blank registered names before the patterns run, keeping the length so
    reported columns stay true. Longest first, so a name inside a longer name
    is masked once."""
    for name in sorted(names, key=len, reverse=True):
        line = re.sub(re.escape(name), lambda m: " " * len(m.group(0)), line, flags=re.I)
    return line


# An HTML comment never reaches a reader, so auditing one flags writing that
# was never published. This is not hypothetical: the audit's own findings now
# ride into a draft as a comment, and that comment explains the "rather than"
# rule using the words "rather than", so the first draft under the new scheme
# reported two findings that were its own note talking about itself.
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def _blank_comments(text: str) -> str:
    """Replace comment bodies with blank lines, keeping line numbers true."""
    return COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def check(path: Path, names: list = ()) -> list:
    findings = []
    # The suppression marker is read from the raw line and the prose from the
    # blanked one, because "<!-- lint-ignore -->" is itself a comment: blanking
    # first would delete the very marker that exempts the line.
    raw = path.read_text(encoding="utf-8").splitlines()
    scanned = _blank_comments("\n".join(raw)).splitlines()
    for n, (source, line) in enumerate(zip(raw, scanned), 1):
        if SKIP.search(source):
            continue
        if names:
            line = _mask_names(line, names)
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
    names = load_registered_names()
    total = 0
    for path in paths:
        if not path.exists():
            print(f"{path}: missing")
            return 2
        for n, name, found, remedy in check(path, names):
            total += 1
            print(f"{path}:{n}: [{name}] {found!r}. {remedy}")
    if total:
        note = (f" {len(names)} registered names accepted." if names
                else " No glossary on this machine, so no names accepted.")
        print(f"\n{total} voice violation(s).{note}")
        return 1
    print(
        f"Clean: {len(paths)} file(s) pass the STYLE.md audit. "
        + (f"{len(names)} registered names accepted." if names
           else "No glossary on this machine, so no names accepted.")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
