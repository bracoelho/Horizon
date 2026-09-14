#!/usr/bin/env python3
"""The STYLE.md grep audit, as a gate.

Tenure's lint-voice.py is the canonical checker and lives in the owner's design
project, which a CI runner does not have. This is the subset that can run here,
implementing the patterns STYLE.md documents in this repository.

It exists because the two do not overlap. A drafted piece passed lint-voice
cleanly while breaking the negative-to-positive rule three times, and nothing
caught it until the file was read by hand.

A source's exact words are not the author's, so a `quote:` in the front
matter's `sources:` list is not checked when its entry carries a web address;
every claim and the body still are, and the skipped lines are printed.

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


# ---------- source quotes ----------
# A source's exact words are not the author's, so they are not checked. The
# claims check asks a draft to quote each source verbatim, and a verbatim quote
# of a source that writes "rather than" failed this gate, so the only way to
# pass was to misquote. The owner's ruling, 2026-09-14 (design N-011, radar
# N-352), is the rule Tenure's lint-voice.py carries since v1.4, repeated here
# because a CI runner does not have that file. It errs toward checking: only a
# `quote:` in a list entry of the front matter's `sources:` block is skipped,
# and only when the same entry carries a web address anyone can open to check
# the quote. Every `claim:` and the whole body are still checked, and the
# skipped line numbers are printed so an exemption cannot hide in a clean run.
YAML_KEY = re.compile(r"^(\s*)(-\s+)?([A-Za-z_][\w-]*)\s*:(\s|$)")
WEB_URL = re.compile(r"^\s*(?:-\s+)?url\s*:\s*[\"']?https?://\S+")


def source_quote_lines(lines: list) -> set:
    """Line numbers of source quotes in a Markdown file's front matter.

    The front matter opens on the first line and closes at the first `---` or
    `...`. Inside its `sources:` block, a list entry's `quote:` is skipped when
    the same entry has, at the same indent, a `url:` that is an http or https
    address (an empty url, `~` or `TODO` does not count). The quote's
    continuation lines are skipped only while they sit deeper than the `quote:`
    key, so the next key ends it. Still checked: sources written as a mapping
    rather than a list, a quote that sets a YAML anchor (its text could be
    reused in a checked field), and anything outside the front matter.
    """
    if not lines or lines[0].strip() != "---":
        return set()
    end = next((k for k in range(1, len(lines)) if lines[k].strip() in ("---", "...")), None)
    if end is None:
        return set()
    skip = set()

    def key_of(text):
        m = YAML_KEY.match(text)
        return (len(m.group(1)) + len(m.group(2) or ""), m.group(3)) if m else (None, None)

    def close(entry):
        cols = [c for c, k in (key_of(t) for _, t in entry) if k == "quote"]
        if not cols:
            return
        qc = cols[0]
        if not any(WEB_URL.match(t) and key_of(t)[0] == qc for _, t in entry):
            return
        quoting = False
        for n, t in entry:
            c, k = key_of(t)
            if k == "quote" and c == qc:
                quoting = not re.match(r"^\s*(?:-\s+)?quote\s*:\s*&", t)
                if quoting:
                    skip.add(n)
            elif quoting and not t.strip():
                continue
            elif quoting and len(t) - len(t.lstrip(" \t")) > qc:
                skip.add(n)
            else:
                quoting = False

    k = 1
    while k < end:
        if re.match(r"^sources\s*:\s*$", lines[k]):
            k += 1
            entry, started = [], False
            while k < end and (lines[k][:1] in (" ", "\t", "-") or not lines[k].strip()):
                if re.match(r"^\s*-(\s|$)", lines[k]):
                    if started:
                        close(entry)
                    entry, started = [], True
                if started:
                    entry.append((k + 1, lines[k]))
                k += 1
            if started:
                close(entry)
            continue
        k += 1
    return skip


def quoted_lines(path: Path) -> set:
    """The source quote lines of a Markdown file; none for any other kind."""
    if path.suffix.lower() not in {".md", ".markdown"}:
        return set()
    return source_quote_lines(path.read_text(encoding="utf-8").splitlines())


def line_ranges(ns) -> str:
    """1, 2, 3, 7 becomes "1-3, 7"."""
    out = []
    for n in sorted(ns):
        if out and n == out[-1][1] + 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in out)


def check(path: Path, names: list = ()) -> list:
    findings = []
    # The suppression marker is read from the raw line and the prose from the
    # blanked one, because "<!-- lint-ignore -->" is itself a comment: blanking
    # first would delete the very marker that exempts the line.
    raw = path.read_text(encoding="utf-8").splitlines()
    scanned = _blank_comments("\n".join(raw)).splitlines()
    quoted = quoted_lines(path)
    for n, (source, line) in enumerate(zip(raw, scanned), 1):
        if SKIP.search(source) or n in quoted:
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
        quoted = quoted_lines(path)
        if quoted:
            print(f"{path}: {len(quoted)} source quote line(s) not checked, "
                  f"lines {line_ranges(quoted)}: each is a sources: quote "
                  f"with a web address beside it.")
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
