"""The notifier's commentary section.

The owner wants a queue of subjects to write about rather than a blank page
each morning, delivered to his phone with the digest he already receives.
These tests lean on the cases where a wrong answer would be worse than
silence: a run that published nothing, and a file written by an older run.
"""

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "notify_telegram.py"


def _load():
    spec = importlib.util.spec_from_file_location("notify_telegram", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


notify = _load()

PROPOSAL = {
    "title": "Circuit-Discovery Claims Flip Under Analytic Variation",
    "theme": "Reliability & Assurance",
    "score": 7.0,
    "url": "https://arxiv.org/abs/2608.13754",
    "plain": "A pre-registered study ran 15,840 defensible analytic choices.",
    "angles": [
        {"heading": "Why circuit analysis is trusted as evidence", "note": "n"},
        {"heading": "Who is exposed", "note": "n"},
        {"heading": "What reduces the risk", "note": "n"},
    ],
}


def _write(tmp_path: Path, payload) -> Path:
    p = tmp_path / "commentary_proposal.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_the_section_carries_the_subject_and_its_angles(tmp_path):
    out = "\n".join(notify.commentary_lines("https://x", _write(tmp_path, PROPOSAL)))

    assert "Worth writing about" in out
    assert "Circuit-Discovery Claims Flip" in out
    assert "1. <b>Why circuit analysis is trusted as evidence</b>" in out
    assert "3. <b>What reduces the risk</b>" in out
    assert "arxiv.org/abs/2608.13754" in out


def test_the_theme_is_escaped_for_telegram_html(tmp_path):
    """Reliability & Assurance carries an ampersand, and the message is HTML."""
    out = "\n".join(notify.commentary_lines("https://x", _write(tmp_path, PROPOSAL)))

    assert "Reliability &amp; Assurance" in out
    assert "Reliability & Assurance" not in out


def test_a_missing_file_says_nothing(tmp_path):
    """A quiet run writes no proposal, and silence is the right answer."""
    assert notify.commentary_lines("https://x", tmp_path / "absent.json") == []


def test_a_proposal_with_no_subject_says_nothing(tmp_path):
    assert notify.commentary_lines("https://x", _write(tmp_path, {"angles": []})) == []


def test_a_corrupt_file_cannot_break_the_notification(tmp_path):
    """The notifier runs with if: always(); it must never be the thing that fails."""
    bad = tmp_path / "commentary_proposal.json"
    bad.write_text("{not json", encoding="utf-8")

    assert notify.commentary_lines("https://x", bad) == []
