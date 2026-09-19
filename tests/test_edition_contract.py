"""The edition contract writer against the invariants specs/EDITION-CONTRACT.json states."""
from __future__ import annotations

from src.edition_contract import build_edition, event_id, normalise_url

THEMES = {"practice": "Q1", "reliability-assurance": "Q2", "horizon-research": "Q3"}
ORDER = ["reliability-assurance", "practice", "horizon-research"]


def _pub(i, theme="practice", score=8.0):
    return {"id": f"c{i}", "title": f"T{i}", "url": f"https://x.example/{i}", "item_url": f"/item/{i}/",
            "source": "hn", "publisher": "P", "published_at": None, "theme": theme, "score": score}


def _build(published, ladder=None):
    return build_edition(run_id="1", night="2026-09-19", generated_at="2026-09-19T00:00:00+09:00",
                         fork_commit="0" * 40, taxonomy="v2_3", seat="production", themes=THEMES,
                         theme_order=ORDER, published=published, ladder=ladder, cost={"gate": {"calls": 1}})


def test_event_id_is_stable_across_tracking_parameters_and_case():
    assert normalise_url("HTTPS://X.Example/a/?utm_source=nl&b=1#frag") == "https://x.example/a?b=1"
    assert event_id("https://x.example/a?utm_source=nl") == event_id("https://x.example/a/")
    assert event_id("https://x.example/a") != event_id("https://x.example/b") and len(event_id("u")) == 16


def test_invariants_hold_with_no_ladder_and_carriers_are_the_article_itself():
    e = _build([_pub(0, score=7.5), _pub(1, "reliability-assurance", 9.0), _pub(2, score=8.0)])
    assert e["rank"] == ["c1", "c2", "c0"] and e["rank_basis"] == "analysis score"
    assert [s["theme"] for s in e["shelves"]] == ["reliability-assurance", "practice"], "order from config, empty shelves omitted"
    assert set(e["rank"]) == set(e["articles"]) and e["quiet"] is False and e["lead"] is None
    a = e["articles"]["c0"]
    assert a["carriers"] == [{"source": "hn", "url": "https://x.example/0", "publisher": "P", "id": "c0"}] and a["carrier_count"] == 1
    assert a["vote"] is None and a["judgement"] is None and a["labels"] is None and a["talk"] is None
    assert e["commentary"] == {"candidates": e["rank"], "proposal": None} and e["thread"] == {"refers_to": []}
    assert e["cost"] == {"gate": {"calls": 1}}


def test_a_shelf_shows_at_most_four_and_rank_keeps_them_all():
    e = _build([_pub(i, score=9 - i * 0.1) for i in range(6)])
    assert len(e["shelves"]) == 1 and e["shelves"][0]["articles"] == ["c0", "c1", "c2", "c3"] and len(e["rank"]) == 6


def test_ladder_rows_join_by_id_and_a_quiet_night_still_writes():
    ladder = {"runs": 3, "items": [
        {"id": "c0", "theme": "practice", "agree": 3, "judgement": {"relevance": 8, "urgency": 6, "line": "why"},
         "labels": {"form": "paper", "evidence": "e", "research_horizon": "near", "horizon_basis": "b",
                    "action_a_team_might_take": "a", "how_soon": "s", "topic": "t"}}]}
    e = _build([_pub(0), _pub(1, score=8.0)], ladder)
    assert e["rank_basis"] == "ladder judgement" and e["rank"][0] == "c0", "equal scores: urgency breaks the tie"
    a = e["articles"]["c0"]
    assert a["vote"] == {"theme": "practice", "runs": 3, "agree": 3} and a["talk"] == "why" and a["labels"]["form"] == "paper"
    assert e["articles"]["c1"]["labels"] is None
    q = _build([])
    assert q["quiet"] is True and q["rank"] == [] and q["shelves"] == [] and q["contract_version"] == 1
