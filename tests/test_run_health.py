"""Tests for the post-run health check.

The script gates the build, so both directions matter equally: a run that
published a complete digest must stay green, and a run where a stage silently
produced nothing must go red. Getting the first wrong makes the red X
meaningless; getting the second wrong is the failure the script exists for.
"""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_run_health.py"


def _load():
    spec = importlib.util.spec_from_file_location("run_health", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


health = _load()


def _parse(tmp_path: Path, body: str):
    log = tmp_path / "run.log"
    log.write_text(body, encoding="utf-8")
    return health.parse_log(log)


HEALTHY = """\
📥 Fetched 222 items from all sources
🤖 Analyzed 222 items with AI
⭐️ Selected 13 items with profile filters
⚖️ Balanced digest selected 13/13 items
   Enriched 13/13 items
🧮 Token usage this run: 100 tokens (input: 80, output: 20)
"""


def test_a_healthy_run_reports_nothing_collapsed(tmp_path):
    *_, collapsed = _parse(tmp_path, HEALTHY)
    assert collapsed == []


def test_a_gate_that_returned_no_verdict_is_fatal(tmp_path):
    body = HEALTHY + (
        "[08/20/26 21:54:09] WARNING  Gate returned no verdict for 247 of 247 "
        "items; keeping them for the ranker\n"
    )
    *_, collapsed = _parse(tmp_path, body)
    assert len(collapsed) == 1
    assert "gate did not run" in collapsed[0][1]


def test_a_batch_returning_nothing_is_fatal(tmp_path):
    body = HEALTHY + (
        "[08/20/26 21:54:09] WARNING  Batch msgbatch_01GAJX returned 0 of 7 "
        "results\n"
    )
    *_, collapsed = _parse(tmp_path, body)
    assert len(collapsed) == 1
    assert "Every entry in it failed" in collapsed[0][1]


def test_only_a_wholly_empty_ranking_chunk_is_fatal(tmp_path):
    """A ranker dropping one id of twenty-five is sloppiness, not a failure.

    Failing the build on that would make the signal unreadable again, which is
    the mistake this check was corrected for once already.
    """
    body = HEALTHY + (
        "[08/20/26 21:54:15] WARNING  Ranker omitted 1 of 25 ids; appending "
        "them unranked\n"
        "[08/20/26 21:55:56] WARNING  Ranker omitted 25 of 25 ids; appending "
        "them unranked\n"
    )
    *_, collapsed = _parse(tmp_path, body)
    assert len(collapsed) == 1
    assert "whole ranking chunk" in collapsed[0][1]


def test_an_enrichment_failure_alone_stays_green(tmp_path):
    """The item published; only its depth was lost. This must not go red."""
    body = HEALTHY.replace("Enriched 13/13", "Enriched 12/13") + (
        "[08/20/26 21:55:00] ERROR    Error enriching item rss:x:abc: "
        "Invalid enrichment artifact\n"
    )
    _, _, totals, errors, _, collapsed = _parse(tmp_path, body)
    fatal, degrading, escalated = health.split_by_severity(
        health.group_errors(errors), totals
    )
    assert collapsed == []
    assert fatal == []
    assert escalated is False
    assert sum(c for _, c in degrading) == 1


def test_analysis_collapsing_on_every_item_stays_fatal(tmp_path):
    body = HEALTHY + "".join(
        f"[08/20/26 21:55:00] ERROR    Error analyzing item rss:x:{i}: "
        "BadRequestError 400\n"
        for i in range(30)
    )
    _, _, totals, errors, _, _ = _parse(tmp_path, body)
    fatal, _, _ = health.split_by_severity(health.group_errors(errors), totals)
    assert sum(c for _, c in fatal) == 30


def test_a_dedup_failure_is_fatal_even_though_it_has_no_log_level(tmp_path):
    """Topic dedup announces its own failure through console.print.

    That line carries no WARNING column, so matching on the log level alone
    missed it entirely. It is on the live threshold path, so this is the one
    of these that can fire on an ordinary run.
    """
    body = HEALTHY + "   dedup: AI call failed (timeout), skipping\n"
    *_, collapsed = _parse(tmp_path, body)
    assert len(collapsed) == 1
    assert "never looked for" in collapsed[0][1]


def test_an_unparsed_dedup_response_is_fatal(tmp_path):
    body = HEALTHY + "   dedup: could not parse AI response, skipping\n"
    *_, collapsed = _parse(tmp_path, body)
    assert len(collapsed) == 1


def test_a_normal_dedup_line_is_not_a_failure(tmp_path):
    """Dedup logs each merge it makes. Those must not trip the check."""
    body = HEALTHY + (
        "   dedup: keep [11] WeSCE: A Benchmark for Measuring Security Drift\n"
        "          drop [25] WeSCE: A Benchmark for Measuring Security Drift\n"
        "🧹 Removed 2 topic duplicates → 45 unique items\n"
    )
    *_, collapsed = _parse(tmp_path, body)
    assert collapsed == []


def test_a_partial_gate_gap_is_not_fatal(tmp_path):
    """A gate that missed two items still ran.

    The run of 2026-08-22 filtered 141 items down to 13 and went red anyway,
    reporting "the gate did not run", because the pattern matched a bare count
    with nothing to compare it against. A build that is red on a healthy run is
    the failure this script exists to prevent, reintroduced one level up.
    """
    body = HEALTHY + (
        "[08/22/26 08:20:20] WARNING  Gate returned no verdict for 2 of 141 "
        "items; keeping them for the ranker\n"
    )
    *_, collapsed = _parse(tmp_path, body)
    assert collapsed == []


def test_the_selection_funnel_accounts_for_every_item(tmp_path):
    """13 kept, 10 rejected, 0 published leaves three unexplained.

    They were ranked below the shortlist the floor reads. Without that stage
    the line reads as three items silently lost, which is the same defect the
    cross-source and digest-cap stages had before they were added.
    """
    body = (
        "📥 Fetched 141 items from all sources\n"
        "🤖 Analyzed 141 items with AI\n"
        "⭐️ Selection: 141 gated to 13, 13 ranked, 10 rejected by floor, 0 published\n"
    )
    _, _, totals, _, _, _ = _parse(tmp_path, body)
    line = health.funnel(totals)
    assert "13 ranked" in line
    assert "3 below the shortlist cut" in line
    # The arithmetic the reader will do must work out.
    assert totals["ranked"] == 3 + totals["floor_rejected"] + totals["published"]


def test_the_funnel_follows_the_order_the_pipeline_actually_ran(tmp_path):
    """Ranking gates first and scores the survivors; thresholds score first.

    A fixed print order would misreport whichever path it was not written for,
    and the funnel's whole job is to reconcile with the page it sits on.
    """
    ranked = (
        "📥 Fetched 212 items from all sources\n"
        "🔗 Merged 1 cross-source duplicates → 211 unique items\n"
        "🤖 Analyzed 64 items with AI\n"
        "⭐️ Selection: 211 gated to 64, 15 ranked, 9 rejected by floor, 6 published\n"
    )
    _, _, totals, _, _, _ = _parse(tmp_path, ranked)
    line = health.funnel(totals)
    assert line.index("kept by the gate") < line.index("analyzed")
    assert "64 analyzed (the survivors)" in line

    threshold = (
        "📥 Fetched 222 items from all sources\n"
        "🤖 Analyzed 222 items with AI\n"
        "⭐️ Selected 13 items with profile filters\n"
        "⚖️ Balanced digest selected 13/13 items\n"
    )
    _, _, totals, _, _, _ = _parse(tmp_path, threshold)
    line = health.funnel(totals)
    assert "222 analyzed" in line
    assert "the survivors" not in line
    assert "kept by the gate" not in line


def test_the_score_floor_is_its_own_stage_and_does_not_inflate_the_shortlist(tmp_path):
    """The floored items were ranked, so counting them as ranked out is wrong.

    Without this the funnel reads "4 below the shortlist cut" on a run where
    two items were ranked in and then dropped for scoring under the floor,
    which sends whoever reads it looking at the ranker.
    """
    log = (
        "📥 Fetched 103 items from all sources\n"
        "⭐️ Selection: 103 gated to 19, 15 ranked, 5 rejected by floor, "
        "2 below the score floor, 6 published\n"
    )
    _, _, totals, _, _, _ = _parse(tmp_path, log)
    line = health.funnel(totals)

    assert totals["below_score"] == 2
    assert totals["published"] == 6
    assert "2 under the score floor" in line
    assert "2 below the shortlist cut" in line  # 15 ranked - (5 + 2 + 6)


def test_a_log_written_before_the_score_floor_existed_still_parses(tmp_path):
    """Old logs are exactly the ones somebody reads to understand a past run."""
    log = (
        "📥 Fetched 212 items from all sources\n"
        "⭐️ Selection: 211 gated to 64, 15 ranked, 9 rejected by floor, 6 published\n"
    )
    _, _, totals, _, _, _ = _parse(tmp_path, log)

    assert totals["published"] == 6
    assert totals["floor_rejected"] == 9
    assert totals["below_score"] == 0
    assert "score floor" not in health.funnel(totals)


def test_setwise_stats_land_in_totals_and_partial_fallback_stays_green(tmp_path):
    log = (
        "📥 Fetched 100 items from all sources\n"
        "Setwise: 40 picks, 2 retried, 1 fell back\n"
        "⭐️ Selection: 100 gated to 40, 20 ranked, 5 rejected by floor, "
        "0 below the score floor, 3 published\n"
    )
    _, _, totals, errors, _, collapsed = _parse(tmp_path, log)

    assert totals["setwise"] == {"picks": 40, "retried": 2, "fallbacks": 1}
    assert collapsed == []


def test_setwise_collapse_goes_red(tmp_path):
    log = (
        "📥 Fetched 100 items from all sources\n"
        "[09/01/26 10:00:00] WARNING  Setwise collapse: 20 of 40 picks fell back\n"
    )
    *_, collapsed = _parse(tmp_path, log)

    assert len(collapsed) == 1
    assert "setwise ranker collapsed" in collapsed[0][1]
