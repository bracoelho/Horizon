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
        {"claim": "Interpretability output is a finding, so an Annex IV file "
                  "rests on one analyst's choices.",
         "audience": "boards", "rank_reason": "Changes a filing decision."},
        {"claim": "Ask a vendor to have two teams run it independently.",
         "audience": "procurement", "rank_reason": "Usable, and narrower."},
        {"claim": "A second gap sits beside the one you already named.",
         "audience": "engineers", "rank_reason": "Observes more than it decides."},
    ],
}


def _write(tmp_path: Path, payload) -> Path:
    p = tmp_path / "commentary_proposal.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_the_section_offers_a_way_to_act_on_it(tmp_path):
    """Two taps from here to a draft.

    GitHub renders the workflow's `angle` input as a dropdown on mobile web,
    so the choice needs no typing and nothing listening for a reply. The link
    is the whole interaction.
    """
    out = "\n".join(notify.commentary_lines("https://x", _write(tmp_path, PROPOSAL)))

    assert "actions/workflows/draft-commentary.yml" in out
    assert "Draft one of these" in out


def test_the_section_carries_the_subject_and_its_angles(tmp_path):
    out = "\n".join(notify.commentary_lines("https://x", _write(tmp_path, PROPOSAL)))

    assert "Worth writing about" in out
    assert "Circuit-Discovery Claims Flip" in out
    # A claim, who it is for, and why it ranks there. Section headings were
    # the first attempt and stopped working the day they were fixed per theme.
    assert "1. <b>Interpretability output is a finding" in out
    assert "<i>For boards.</i>" in out
    assert "Changes a filing decision." in out
    assert out.index("1. <b>") < out.index("3. <b>")
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


def test_a_run_that_published_nothing_offers_no_angles(tmp_path):
    """The proposal file outlives the run that wrote it.

    The 2026-08-30 zero-item run left the previous run's proposal in place,
    so the message would have offered angles the radar had not just found.
    """
    p = tmp_path / "commentary_proposal.json"
    p.write_text(json.dumps({
        "title": "Yesterday's item",
        "theme": "Business & Markets",
        "angles": [{"claim": "old", "audience": "old", "rank_reason": "old"}],
    }), encoding="utf-8")

    assert notify.commentary_lines("", p, stale=True) == []
    assert notify.commentary_lines("", p, stale=False) != []
