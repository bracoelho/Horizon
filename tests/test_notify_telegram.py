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

    joined = "\n".join(notify.commentary_lines("", p, stale=True))

    # It says so instead of disappearing: a section that vanishes reads as a
    # section that broke. The reason itself sits in the headline, once.
    assert "Nothing to write about" in joined
    assert "no angles" in joined
    assert "Yesterday's item" not in joined

    assert "Yesterday's item" in "\n".join(notify.commentary_lines("", p, stale=False))


def test_the_quiet_reason_names_the_stage_that_emptied_the_edition():
    """A quiet day and a broken stage must not read the same."""
    assert notify.why_nothing({"gated": 0}) == (
        "the gate kept nothing from the day's catch"
    )
    assert "too thin" in notify.why_nothing(
        {"gated": 43, "ranked": 20, "floor_rejected": 10}
    )
    assert "score floor" in notify.why_nothing(
        {"gated": 30, "ranked": 12, "floor_rejected": 8, "below_score": 4}
    )
    # No funnel at all still produces a sentence rather than an empty string.
    assert notify.why_nothing({}) == "nothing cleared selection"


def test_ranked_path_quiet_run_explains_and_offers_no_stale_angles(tmp_path, monkeypatch):
    """The ranked funnel has no "selected" key. Keying on it made the
    2026-08-30 23:26 message print "None cleared threshold" and re-offer
    Friday's angles. Quietness is about published, whatever the path."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "docs" / "_config.yml").write_text(
        "url: https://x.test\nbaseurl: ''\n", encoding="utf-8")
    (tmp_path / "data" / "commentary_proposal.json").write_text(json.dumps(
        {"title": "Friday leftover", "angles": [{"claim": "old"}]}),
        encoding="utf-8")
    health = {"totals": {"fetched": 117, "gated": 48, "analyzed": 48,
                         "ranked": 20, "floor_rejected": 10, "published": 0},
              "errors": 1, "warnings": 17, "posts": [],
              "finished_utc": "30 Aug 23:52"}

    msg = notify.build_message(health, "scheduled")

    assert "None" not in msg
    assert "Quiet edition." in msg
    assert "judged too thin" in msg
    assert "Friday leftover" not in msg
    assert "Nothing to write about" in msg


def test_ranked_path_with_items_leads_with_published(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "_config.yml").write_text(
        "url: https://x.test\nbaseurl: ''\n", encoding="utf-8")
    health = {"totals": {"gated": 43, "analyzed": 43, "ranked": 19,
                         "floor_rejected": 7, "published": 3},
              "errors": 0, "posts": [], "finished_utc": "x"}

    msg = notify.build_message(health, "scheduled")

    assert "3 published" in msg
    assert "None" not in msg
    assert "cleared threshold" not in msg


def test_item_pages_maps_source_links_to_radar_pages(tmp_path):
    """The map is read back from what the run wrote, never derived.

    Deriving a slug from the title produced URLs the site never served (the
    filename carries date, run time, index and language). The front-matter
    link is the join key.
    """
    items = tmp_path / "_items"
    items.mkdir()
    (items / "2026-09-01-2135-01-miso-rules-en.md").write_text(
        '---\nlayout: item\nlink: "https://example.com/story"\n---\nbody\n',
        encoding="utf-8",
    )
    pages = notify.item_pages("https://radar.example", items_dir=items)

    assert pages == {
        "https://example.com/story":
            "https://radar.example/item/2026-09-01-2135-01-miso-rules-en/"
    }


def test_the_section_links_the_radars_own_summary_when_a_page_exists(tmp_path):
    """The owner reads our summary before choosing an angle.

    The line resolves through the written pages and drops out entirely when
    no page matches, rather than shipping a guessed URL.
    """
    pages = {PROPOSAL["url"]: "https://radar.example/item/x-en/"}
    out = "\n".join(
        notify.commentary_lines(
            "https://radar.example", _write(tmp_path, PROPOSAL), pages=pages
        )
    )
    assert 'href="https://radar.example/item/x-en/">Our summary on the radar' in out

    out_no = "\n".join(
        notify.commentary_lines("https://radar.example", _write(tmp_path, PROPOSAL))
    )
    assert "Our summary on the radar" not in out_no
