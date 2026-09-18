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
    block = asyncio.run(L.run_ladder(client, items, L.LadderSettings(runs=6, model="m", vote_use_batch=True)))
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
    block = asyncio.run(L.run_ladder(Empty(), [cand(1)], L.LadderSettings(runs=2, vote_use_batch=True)))
    row = block["items"][0]
    assert row["theme"] is None and row["judgement"] is None and row["judgement_flag"] == "no cluster"
    assert block["calls"]["judge_asked"] == 0


def test_the_vote_goes_synchronously_by_default_and_the_judgement_by_batch():
    class Both(FakeBatchClient):
        def __init__(self):
            super().__init__(); self.sync_ids = []
        async def complete(self, system, user, **kwargs):
            self.sync_ids.append(system[:20])
            return '{"theme": "vendor-dependency", "second": "none", "why": "w"}'
    client = Both()
    block = asyncio.run(L.run_ladder(client, [cand(1)], L.LadderSettings(runs=3)))
    assert len(client.sync_ids) == 3
    assert [u.custom_id for u in client.units] == ["b0000"]
    assert block["paths"] == {"vote": "synchronous", "judge": "batch"}
    assert block["items"][0]["theme"] == "vendor-dependency"


# The per-leg ceiling (NEWS-Radar N-485, the owner's word "4 USD per leg"; N-484,
# this leg carried no stop at all until now). Each of these was proven able to
# fail before it was believed: see the controls run in the radar's session record.


def test_the_estimate_reproduces_the_recorded_night_it_was_measured_on():
    # 16 September: 117 candidates at six vote runs cost 3.471 USD by its own
    # receipt (research/replays/nightly/ladder-20260916-2147.json). The estimator
    # is deliberately conservative, so it must land at or above that, and within
    # ten per cent of it rather than anywhere above.
    got = L.estimate_usd(117, 6)
    assert got >= 3.471, f"the estimate must not read below a night that really cost 3.471: {got}"
    assert got < 3.471 * 1.10, f"conservative is not the same as useless: {got}"


def test_the_estimate_knows_the_run_count_and_does_not_read_a_flat_rate():
    # The whole reason the estimator takes `runs`: the vote is asked once per run
    # and the judgement once per candidate, so three runs is a little over half of
    # six and nowhere near equal to it. A flat per-candidate rate measured at six
    # runs reads 3.64 on this field where the truth is about 1.94.
    six, three = L.estimate_usd(117, 6), L.estimate_usd(117, 3)
    assert three < six / 1.7, f"three runs must be well under half of six: {three} against {six}"
    assert three > six / 2.2, f"the judgement does not halve with the runs: {three} against {six}"


def test_the_estimate_is_zero_for_an_empty_or_impossible_leg():
    assert L.estimate_usd(0, 6) == 0.0
    assert L.estimate_usd(117, 0) == 0.0
    assert L.estimate_usd(-1, 6) == 0.0


def test_the_ceiling_defaults_to_the_ceiling_and_never_to_unlimited():
    # A guard whose default is no guard is not a guard. The owner set 4 USD.
    from src.models import SelectionConfig

    assert SelectionConfig().ladder_max_usd == 4.0


def test_the_run_count_carries_the_owners_decision_so_night_a_needs_one_key():
    # "three runs with Night A" (the owner, 2026-09-18; NEWS-Radar N-492), on
    # E39's measured 0.9652 agreement against the shipped six-run majority.
    #
    # The default is where the decision lives, and that is deliberate: Night A
    # turns the ladder on with ONE config key, so the night keeps its
    # one-variable rule. A silent return to six would spend the night's rule a
    # second time without anyone declaring it, and this test is what refuses it.
    from src.models import SelectionConfig

    assert SelectionConfig().ladder_runs == 3


def test_three_runs_is_what_makes_the_ceiling_independent_of_the_price_table():
    # N-491: both rates rest on a price table no bill anchors, and the lab
    # prices the same model 1.5x higher. At the DEFAULT run count the ceiling
    # must hold under BOTH tables, or the guard's firing depends on an
    # unanswered question rather than on the field.
    from src.models import SelectionConfig

    runs = SelectionConfig().ladder_runs
    ceiling = SelectionConfig().ladder_max_usd
    largest_on_record = 144
    assert L.estimate_usd(largest_on_record, runs) <= ceiling
    # The same leg priced at the lab's table, which is exactly 1.5 times ours.
    assert L.estimate_usd(largest_on_record, runs) * 1.5 <= ceiling


def test_the_ceiling_admits_every_recent_field_and_refuses_the_largest_on_record():
    # Measured across the retained fixtures: recent nights run 23 to 117
    # candidates and early September reached 144. At six runs the ceiling must
    # clear the first and refuse the second, which is what the owner was told.
    assert L.estimate_usd(117, 6) <= 4.0
    assert L.estimate_usd(144, 6) > 4.0
    # And once E39's three runs land, the same 144-candidate night fits.
    assert L.estimate_usd(144, 3) <= 4.0
