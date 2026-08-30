"""The STYLE.md audit as a gate.

It exists because Tenure's linter and this audit do not overlap. The first
drafted commentary passed lint-voice cleanly while breaking the
negative-to-positive rule three times, and nothing caught it until a person
read the file.
"""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_voice.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_voice", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


voice = _load()


def _check(tmp_path, text):
    p = tmp_path / "piece.md"
    p.write_text(text, encoding="utf-8")
    return voice.check(p)


def test_it_catches_the_turns_the_model_kept_writing(tmp_path):
    """All three came from one generated draft."""
    findings = _check(tmp_path, "\n".join([
        "an 11-week notice period rather than an immediate cutoff",
        "because of a change in ownership, not because of anything it did",
        "procurement finds out from a support ticket instead of a plan",
    ]))

    assert len(findings) == 3
    assert all(f[1] == "negative to positive" for f in findings)


def test_it_catches_em_dashes_and_promotional_words(tmp_path):
    findings = _check(tmp_path, "This is a crucial shift — and a robust one.")

    kinds = {f[1] for f in findings}
    assert "em dash" in kinds
    assert "promotional register" in kinds


def test_prose_that_follows_the_standard_passes(tmp_path):
    """The piece written with the owner, which must not trip the gate."""
    findings = _check(tmp_path, "\n".join([
        "Coordinated disclosure has no window left. It gives maintainers days",
        "to weeks because an attacker was assumed to need comparable time.",
        "At ten minutes that assumption is gone.",
    ]))

    assert findings == []


def test_a_line_teaching_a_banned_pattern_is_exempt(tmp_path):
    """The standard has to be able to quote what it bans."""
    findings = _check(
        tmp_path, 'Never write "X, not Y" as a flourish. <!-- lint-ignore -->'
    )

    assert findings == []


def test_a_comment_is_not_audited_but_still_counts_its_lines(tmp_path):
    """The audit's own note rides in as a comment and must not read itself."""
    findings = _check(
        tmp_path,
        'Clean opening line.\n<!-- a rhetorical rather than b -->\nA title, not a claim.',
    )

    assert [f[0] for f in findings] == [3]
