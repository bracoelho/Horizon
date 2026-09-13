"""The ladder's first stage records and never decides (NEWS-Radar N-344)."""

import asyncio

from src.selection import ladder as L
from src.selection.contract import Candidate


def cand(i, **kw):
    base = dict(id=f"id{i}", title=f"T{i}", summary="S", source="src", url="https://x", content="C" * 7000)
    base.update(kw)
    return Candidate(**base)


def test_the_item_prompt_never_carries_a_byline_or_the_scorers_summary_and_caps_content():
    text = L.item_user(cand(1, summary="The scorer says: headline only, no supporting detail"))
    assert "Author:" not in text
    assert "Summary" not in text and "no supporting detail" not in text
    assert text.endswith("C" * L.CONTENT_CHARS)
    assert "C" * (L.CONTENT_CHARS + 1) not in text


def test_the_vote_names_every_v2_3_theme_and_no_none_value():
    system = L.theme_system()
    for theme in L.TAXONOMY_V2_3:
        assert f"- {theme}: " in system
    assert len(L.TAXONOMY_V2_3) == 5
    assert '"theme": "<one of the ids above>"' in system


def test_tally_majority_margin_and_runner_up():
    answers = [{"theme": "security-adversarial"}] * 4 + [{"theme": "models-capability"}] * 2
    out = L.tally(answers)
    assert (out["theme"], out["margin"], out["tie"], out["runner_up"]) == ("security-adversarial", 4, False, "models-capability")


def test_tally_records_a_tie_and_breaks_it_by_run_order():
    answers = [{"theme": "vendor-dependency"}, {"theme": "governance-regulation"}] * 3
    out = L.tally(answers)
    assert out["tie"] is True and out["theme"] == "vendor-dependency" and out["margin"] == 3


def test_tally_unanimous_takes_the_runner_up_from_the_second_field():
    answers = [{"theme": "reliability-assurance", "second": "models-capability"}] * 6
    assert L.tally(answers)["runner_up"] == "models-capability"


def test_tally_counts_out_of_enum_and_missing_runs_apart():
    out = L.tally([{"theme": "none"}, None, {"theme": "reliability-assurance"}])
    assert out["answered"] == 1 and out["asked"] == 3 and out["outside_enum"] == ["none"]


def test_judgement_rejects_out_of_range_and_non_bool():
    assert L.judgement({"relevance": 11, "change_urgency": 1, "must_read_in_cluster": False})[0] is None
    assert L.judgement({"relevance": 3, "change_urgency": 1, "must_read_in_cluster": "yes"})[0] is None
    ok, flag = L.judgement({"relevance": 3, "change_urgency": 1, "must_read_in_cluster": True, "one_line": "x"})
    assert flag is None and ok["relevance"] == 3


class FakeBatchClient:
    def __init__(self):
        self.units = []
        self.last_batch_stops = {}

    async def complete_batch(self, units, **kwargs):
        self.units.extend(units)
        out = {}
        for u in units:
            if u.custom_id.startswith("a"):
                out[u.custom_id] = '{"theme": "governance-regulation", "second": "none", "why": "w"}'
            else:
                out[u.custom_id] = '```json\n{"relevance": 6, "change_urgency": 4, "must_read_in_cluster": true, "one_line": "l"}\n```'
            self.last_batch_stops[u.custom_id] = "end_turn"
        return out


def test_run_ladder_records_and_leaves_candidates_untouched():
    items = [cand(1), cand(2, summary="")]
    before = list(items)
    client = FakeBatchClient()
    block = asyncio.run(L.run_ladder(client, items, L.LadderSettings(runs=6, model="m")))
    assert items == before
    assert block["taxonomy"] == "v2.3" and block["seat"] == "cto"
    assert block["calls"] == {"vote_asked": 12, "vote_returned": 12, "judge_asked": 2, "judge_returned": 2}
    assert [r["theme"] for r in block["items"]] == ["governance-regulation"] * 2
    assert block["items"][0]["judgement"]["relevance"] == 6
    assert all(u.model == "m" for u in client.units)
    judge_systems = [u.system for u in client.units if u.custom_id.startswith("b")]
    assert all('The cluster is "governance-regulation"' in s for s in judge_systems)


def test_run_ladder_marks_items_whose_votes_never_came_back():
    class Empty(FakeBatchClient):
        async def complete_batch(self, units, **kwargs):
            return {}
    block = asyncio.run(L.run_ladder(Empty(), [cand(1)], L.LadderSettings(runs=2)))
    row = block["items"][0]
    assert row["theme"] is None and row["judgement"] is None and row["judgement_flag"] == "no cluster"
    assert block["calls"]["judge_asked"] == 0
