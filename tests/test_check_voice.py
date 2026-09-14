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


# ---------- source quotes (the owner's ruling, 2026-09-14) ----------
# A draft must quote each source verbatim, and a source that writes "rather
# than" used to fail this gate, so the only way to pass was to misquote.


def _piece(sources, body="Clean body."):
    return "\n".join(["---", "title: A piece", "sources:", *sources, "---", body])


def _lines(findings):
    return [f[0] for f in findings]


def test_a_source_quote_with_a_web_address_is_not_checked(tmp_path):
    findings = _check(tmp_path, _piece([
        "  - claim: Clean claim.",
        "    url: https://example.com/report",
        '    quote: "It was a pipeline rather than a person."',
    ]))

    assert findings == []


def test_a_quote_without_a_web_address_is_still_checked(tmp_path):
    """An empty url, ~, TODO or a relative path lets nobody check the quote."""
    for url in ("", " ~", " TODO", " /local/path", ' ""'):
        findings = _check(tmp_path, _piece([
            "  - claim: Clean claim.",
            f"    url:{url}",
            '    quote: "It was a pipeline rather than a person."',
        ]))
        assert _lines(findings) == [6], url


def test_the_claim_other_front_matter_and_the_body_are_still_checked(tmp_path):
    text = "\n".join([
        "---",
        "title: A title, not a claim",
        "sources:",
        "  - claim: A pipeline rather than a person.",
        "    url: https://example.com/report",
        '    quote: "A pipeline rather than a person."',
        "---",
        'The report says "a pipeline rather than a person".',
    ])

    assert _lines(_check(tmp_path, text)) == [2, 4, 8]


def test_a_continuation_is_skipped_only_while_deeper_than_the_key(tmp_path):
    findings = _check(tmp_path, _piece([
        "  - claim: Clean claim.",
        "    url: https://example.com/report",
        "    quote: >",
        "      It was a pipeline",
        "",
        "      rather than a person.",
        "    note: Kept, not a claim.",
    ]))

    assert _lines(findings) == [10]


def test_the_url_may_come_after_the_quote_in_its_entry(tmp_path):
    findings = _check(tmp_path, _piece([
        '  - quote: "A pipeline rather than a person."',
        "    url: https://example.com/report",
        '  - quote: "A pipeline rather than a person."',
        "    url: TODO",
    ]))

    assert _lines(findings) == [6]


def test_a_url_at_another_indent_does_not_count(tmp_path):
    findings = _check(tmp_path, _piece([
        '  - quote: "A pipeline rather than a person."',
        "    extra:",
        "      url: https://example.com/report",
    ]))

    assert _lines(findings) == [4]


def test_sources_written_as_a_mapping_are_still_checked(tmp_path):
    findings = _check(tmp_path, _piece([
        "  first:",
        "    url: https://example.com/report",
        '    quote: "A pipeline rather than a person."',
    ]))

    assert _lines(findings) == [6]


def test_a_quote_that_sets_an_anchor_is_still_checked(tmp_path):
    """An anchored quote's text could be reused in a checked field."""
    findings = _check(tmp_path, _piece([
        "  - url: https://example.com/report",
        '    quote: &q "A pipeline rather than a person."',
    ]))

    assert _lines(findings) == [5]


def test_front_matter_closes_at_three_dots_and_nothing_after_is_skipped(tmp_path):
    text = "\n".join([
        "---",
        "sources:",
        "  - url: https://example.com/report",
        '    quote: "A pipeline rather than a person."',
        "...",
        "sources:",
        "  - url: https://example.com/report",
        '    quote: "A pipeline rather than a person."',
    ])

    assert _lines(_check(tmp_path, text)) == [8]


def test_unclosed_front_matter_and_other_file_kinds_skip_nothing(tmp_path):
    entry = [
        "---",
        "sources:",
        "  - url: https://example.com/report",
        '    quote: "A pipeline rather than a person."',
    ]
    assert _lines(_check(tmp_path, "\n".join(entry))) == [4]

    other = tmp_path / "prompt.txt"
    other.write_text("\n".join(entry + ["---"]), encoding="utf-8")
    assert _lines(voice.check(other)) == [4]


def test_the_skipped_lines_are_printed(tmp_path, monkeypatch, capsys):
    """An exemption must never hide inside a clean run."""
    p = tmp_path / "piece.md"
    p.write_text(_piece([
        "  - url: https://example.com/a",
        '    quote: "A pipeline rather than a person."',
        "  - url: https://example.com/b",
        "    quote: >",
        "      A pipeline rather than a person.",
    ]), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["check_voice.py", str(p)])

    assert voice.main() == 0
    assert "3 source quote line(s) not checked, lines 5, 7-8" in capsys.readouterr().out
