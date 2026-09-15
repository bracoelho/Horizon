"""The orchestrator's routing between threshold selection and ranking."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import pytest

from src.models import ContentItem, SourceType
from src.orchestrator import HorizonOrchestrator
from src.storage.manager import StorageManager


def _items(n):
    return [
        ContentItem(
            id=f"i{k}",
            source_type=SourceType.RSS,
            title=f"Item {k}",
            url=f"https://example.com/{k}",
            content=f"body {k}",
            published_at=datetime(2026, 8, 18, tzinfo=timezone.utc),
            metadata={"feed_name": "Utility Dive"},
        )
        for k in range(n)
    ]


def _analysis(score):
    """Minimal processing block carrying a score, which is all the floor reads."""
    from src.models import ClassificationResult, ContentAnalysis, ProcessingResult

    return ProcessingResult(
        classification=ClassificationResult(profile="practice", method="ai_match"),
        analysis=ContentAnalysis(score=score, reason="test", summary="test"),
    )


@pytest.fixture()
def orchestrator(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    storage = StorageManager()
    config = storage.load_config()
    return HorizonOrchestrator(config, storage)


def test_selection_is_on_and_synthesis_is_not(orchestrator) -> None:
    """Pins the deliberate state, so a change to either is a decision.

    Selection is on from the 2026-08-26 run. It was verified on 2026-08-22,
    when the gate filtered 141 items to 13 against 247 to 247 while every
    batch entry was erroring, then held off while the only runs available were
    a Saturday and a Sunday with arXiv quiet. The hold outlasted its reason:
    Monday's run went by on the threshold path, so the weekday test it was
    waiting for never happened.

    To turn it off again: set `selection.enabled` false in
    `data/config.github.json`, mirror it in the NEWS-Radar repo, and confirm
    with `python3 check_mirror.py` there.

    Synthesis stays off regardless.
    """
    assert orchestrator.config.selection.enabled is True
    assert orchestrator.config.digest.synthesis_enabled is False

    # A floor that could publish an unbounded edition would defeat the point.
    assert orchestrator.config.selection.max_publish <= 10
    assert (
        orchestrator.config.selection.consider
        >= orchestrator.config.selection.max_publish
    )

    # A floor that could publish an unbounded edition would defeat the point.
    assert orchestrator.config.selection.max_publish <= 10
    assert (
        orchestrator.config.selection.consider
        >= orchestrator.config.selection.max_publish
    )


def test_settings_map_config_onto_the_selection_module(orchestrator) -> None:
    settings = orchestrator._selection_settings()
    assert settings.gate_model == "claude-haiku-4-5"
    assert settings.max_publish == orchestrator.config.selection.max_publish
    assert settings.use_batch is True


def test_theme_questions_come_from_the_profiles(orchestrator) -> None:
    questions = orchestrator._theme_questions()
    assert set(questions) == set(orchestrator.config.processing.profile_settings)
    assert all(text for text in questions.values())


def test_ranking_maps_results_back_onto_pipeline_items(orchestrator, monkeypatch) -> None:
    """Selection speaks its own type; the ids are the join back to the pipeline."""
    from src.selection.contract import Candidate, SelectionResult

    items = _items(5)

    async def fake_select(candidates, client, themes, settings, after_gate=None):
        chosen = [
            Candidate(
                id=c.id, title=c.title, summary="", source="", url="",
                theme="practice",
            )
            for c in list(candidates)[:2]
        ]
        return SelectionResult(
            selected=chosen,
            ranked_ids=[c.id for c in candidates],
            gate_kept=len(candidates),
        )

    monkeypatch.setattr("src.orchestrator.run_selection", fake_select)
    monkeypatch.setattr("src.orchestrator.create_ai_client", lambda cfg: object())

    selected, result = asyncio.run(orchestrator.select_by_ranking(items))
    assert [i.id for i in selected] == ["i0", "i1"]
    assert all(isinstance(i, ContentItem) for i in selected)
    assert result.gate_kept == 5


def test_ranking_drops_ids_that_do_not_map_back(orchestrator, monkeypatch) -> None:
    from src.selection.contract import Candidate, SelectionResult

    async def fake_select(candidates, client, themes, settings, after_gate=None):
        return SelectionResult(
            selected=[Candidate(id="ghost", title="", summary="", source="", url="")]
        )

    monkeypatch.setattr("src.orchestrator.run_selection", fake_select)
    monkeypatch.setattr("src.orchestrator.create_ai_client", lambda cfg: object())

    selected, _ = asyncio.run(orchestrator.select_by_ranking(_items(3)))
    assert selected == []


def test_ranking_records_the_theme_the_gate_chose(orchestrator, monkeypatch) -> None:
    from src.selection.contract import Candidate, SelectionResult
    from src.models import ClassificationResult, ProcessingResult

    items = _items(1)
    items[0].processing = ProcessingResult(
        classification=ClassificationResult(profile="practice", method="ai_match")
    )

    async def fake_select(candidates, client, themes, settings, after_gate=None):
        return SelectionResult(
            selected=[Candidate(
                id="i0", title="", summary="", source="", url="",
                theme="critical-infrastructure",
            )]
        )

    monkeypatch.setattr("src.orchestrator.run_selection", fake_select)
    monkeypatch.setattr("src.orchestrator.create_ai_client", lambda cfg: object())

    selected, _ = asyncio.run(orchestrator.select_by_ranking(items))
    assert selected[0].processing.classification.profile == "critical-infrastructure"


def _scored(items, scores):
    """Give each item an analysis carrying the score, or none at all."""
    from src.models import ClassificationResult, ContentAnalysis, ProcessingResult

    for item, score in zip(items, scores):
        item.processing = ProcessingResult(
            classification=ClassificationResult(
                profile="practice", method="ai_match"
            ),
            analysis=(
                None if score is None
                else ContentAnalysis(score=score, reason="t", summary=item.id)
            ),
        )
    return items


def _passthrough(monkeypatch):
    """Rank everything handed in, in order, so only the floor decides."""
    from src.selection.contract import Candidate, SelectionResult

    async def fake_select(candidates, client, themes, settings, after_gate=None):
        cands = list(candidates)
        return SelectionResult(
            selected=[
                Candidate(
                    id=c.id, title=c.title, summary="", source="", url="",
                    theme="practice",
                )
                for c in cands
            ],
            ranked_ids=[c.id for c in cands],
            gate_kept=len(cands),
        )

    monkeypatch.setattr("src.orchestrator.run_selection", fake_select)
    monkeypatch.setattr("src.orchestrator.create_ai_client", lambda cfg: object())


def test_the_floor_drops_what_ranked_in_but_scored_under_it(
    orchestrator, monkeypatch
) -> None:
    """Ranking is comparative, so the best of a weak set still ranks first.

    Turning on ranked selection retired the per-theme thresholds without
    replacing them, and a 5.0 published under a heading advertising 7.0. The
    floor is the one absolute statement on that path.
    """
    orchestrator.config.selection.min_score = 6.0
    _passthrough(monkeypatch)
    items = _scored(_items(4), [8.0, 5.0, 6.0, 5.9])

    selected, _ = asyncio.run(orchestrator.select_by_ranking(items))

    # 6.0 is kept: the floor is the lowest publishable score, not the lowest
    # rejected one, and an off-by-one here silently loses a whole score band.
    assert [i.id for i in selected] == ["i0", "i2"]


def test_an_unscored_item_is_unknown_rather_than_weak(
    orchestrator, monkeypatch
) -> None:
    """A gap in the scoring pass must not quietly empty an edition."""
    orchestrator.config.selection.min_score = 6.0
    _passthrough(monkeypatch)
    items = _scored(_items(2), [None, 4.0])

    selected, _ = asyncio.run(orchestrator.select_by_ranking(items))

    assert [i.id for i in selected] == ["i0"]


def test_the_floor_can_be_turned_off(orchestrator, monkeypatch) -> None:
    """Null means ranking alone decides, which is the behaviour before today."""
    orchestrator.config.selection.min_score = None
    _passthrough(monkeypatch)
    items = _scored(_items(3), [9.0, 2.0, 5.0])

    selected, _ = asyncio.run(orchestrator.select_by_ranking(items))

    assert len(selected) == 3


def test_fixture_records_the_decisions_not_only_the_field(
    orchestrator, monkeypatch, tmp_path
) -> None:
    """The fixture's second write must run, and must run AFTER the floor.

    Written for NEWS-Radar N-025, from a night that lost its whole audit. The
    block that appends the shortlist, the defender's verdicts and the published
    ids was placed at the top of `select_by_ranking`, above the line that sets
    `_fixture_path`, so its guard was false on every run: it recorded nothing
    and said nothing, in either branch. The 5-6 Sep fixture reached the
    archive as version 2 with three empty lists, and the defender audit that
    was queued behind it had nothing to read.

    So this test asserts placement, not just behaviour: `published` holds what
    survived the score floor, which is only true if the write happens after it.
    """
    from src.selection.contract import Candidate, DefendVerdict, SelectionResult

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()

    items = _items(3)
    for k, item in enumerate(items):
        item.processing = None
    orchestrator.config.selection.min_score = 7.0

    async def fake_analyze(subjects):
        for k, item in enumerate(subjects):
            item.processing = _analysis(6.0 if k == 0 else 8.0)

    monkeypatch.setattr(orchestrator, "analyze_items", fake_analyze)
    monkeypatch.setattr("src.orchestrator.create_ai_client", lambda cfg: object())
    shown = {}

    async def fake_select(candidates, client, questions, settings, after_gate=None):
        # what the gate is handed, before any analysis: its title, source and brief
        shown.update({c.id: (c.title, c.source, c.brief()) for c in candidates})
        kept = list(candidates)
        if after_gate is not None:
            kept = await after_gate(kept)
        return SelectionResult(
            selected=list(kept),
            ranked_ids=[c.id for c in kept],
            gate_kept=len(kept),
            gate_dropped=0,
            defend_rejected=0,
            defend_verdicts=[
                DefendVerdict(id=c.id, publish=True, why="fine", ai_nexus="about-ai")
                for c in kept
            ],
        )

    monkeypatch.setattr("src.orchestrator.run_selection", fake_select)

    selected, _ = asyncio.run(orchestrator.select_by_ranking(items))

    written = list((tmp_path / "data").glob("rank_fixture-*.json"))
    assert len(written) == 1
    record = json.loads(written[0].read_text(encoding="utf-8"))
    # Version 3 since 2026-09-06 (N-041, N-042, N-058): the field gained the
    # full fetched list, the analysis score, and the gate's verdict for every
    # item it saw. All three are recording only. The assertion is kept on the
    # exact version rather than loosened to ">= 2", because a silent version
    # drift is how a reader ends up parsing a shape nobody declared.
    assert record["version"] == 3
    assert "fetched" in record and isinstance(record["fetched"], list)
    assert "gate" in record and isinstance(record["gate"], list)
    assert all("score" in c for c in record["candidates"])
    assert "rank_rounds" in record and isinstance(record["rank_rounds"], list)
    assert all("content" in c for c in record["candidates"])
    assert len(record["candidates"]) == 3
    assert record["shortlist"], "the shortlist was not recorded"
    assert len(record["defend"]) == 3, "the defender's verdicts were not recorded"
    # i0 scored 6.0 against a floor of 7.0. The defender passed all three, so a
    # `published` of three would mean the write ran before the floor.
    assert record["published"] == [item.id for item in selected]
    assert record["shortlist"] == [v["id"] for v in record["defend"]], (
        "shortlist must be what the defender read, not the pre-lead-filter top N"
    )
    assert record["ranked"], "the full ranked list must survive alongside it"
    assert len(record["published"]) == 2
    # NEWS-Radar N-281: every fetched entry names what the gate was shown, from the
    # candidates it judged, so a replay never rebuilds the sift's input from `summary`
    assert {e["id"]: (e["sift_input"]["title"], e["sift_input"]["source"], e["sift_input"]["brief"])
            for e in record["fetched"]} == shown


# NEWS-Radar N-341 (the record carries no item dates). Recording only: each
# fetched entry gains `published_at` and the contract gains the window's bounds.
# The keys a fixture carried before it, so a test can say nothing else moved.
_FIXTURE_KEYS = {"version", "contract", "fetched", "candidates", "gate",
                 "ranked", "shortlist", "defend", "published", "rank_rounds"}
_RECORDED_KEYS = _FIXTURE_KEYS - {"version", "contract"}
_FETCHED_ENTRY_KEYS = {"id", "title", "source", "url", "author", "summary",
                       "sift_input", "content"}


def _record_a_night(orchestrator, monkeypatch, directory, items):
    """Run ranked selection over `items` with stand-in stages; return (ids, result, record).

    The gate keeps all but the last item, the defender refuses the first it
    reads, and the analysis scores every survivor 8.0, so the funnel has a cut
    at each stage for a comparison to notice.
    """
    from src.selection.contract import DefendVerdict, GateVerdict, SelectionResult

    monkeypatch.chdir(directory)
    (directory / "data").mkdir(exist_ok=True)
    orchestrator.config.selection.min_score = 7.0

    async def fake_analyze(subjects):
        for item in subjects:
            item.processing = _analysis(8.0)

    async def fake_select(candidates, client, questions, settings, after_gate=None):
        cands = list(candidates)
        verdicts = [GateVerdict(id=c.id, keep=k < len(cands) - 1, theme="practice",
                                reason="kept" if k < len(cands) - 1 else "dropped")
                    for k, c in enumerate(cands)]
        kept = cands[:-1]
        if after_gate is not None:
            kept = await after_gate(kept)
        defended = [DefendVerdict(id=c.id, publish=k > 0, why="w", ai_nexus="about-ai")
                    for k, c in enumerate(kept)]
        return SelectionResult(
            selected=[c for c, v in zip(kept, defended) if v.publish],
            ranked_ids=[c.id for c in kept],
            gate_kept=len(kept),
            gate_dropped=len(cands) - len(kept),
            defend_rejected=sum(1 for v in defended if not v.publish),
            defend_verdicts=defended,
            gate_verdicts=verdicts,
            rank_rounds=[{"group": [c.id for c in kept], "winner": kept[0].id, "how": "first"}],
        )

    monkeypatch.setattr(orchestrator, "analyze_items", fake_analyze)
    monkeypatch.setattr("src.orchestrator.create_ai_client", lambda cfg: object())
    monkeypatch.setattr("src.orchestrator.run_selection", fake_select)

    selected, result = asyncio.run(orchestrator.select_by_ranking(items))
    written = list((directory / "data").glob("rank_fixture-*.json"))
    assert len(written) == 1
    return [i.id for i in selected], result, json.loads(written[0].read_text(encoding="utf-8"))


def _dated_items(first, second):
    """Three items: one dated in UTC, one in another zone, one with no date at all."""
    from datetime import timedelta

    items = _items(2)
    items[0].published_at = first
    items[1].published_at = second
    undated = ContentItem.model_construct(
        id="i2", source_type=SourceType.RSS, title="Item 2",
        url="https://example.com/2", content="body 2",
        metadata={"feed_name": "Utility Dive"}, profile=None, processing=None,
    )
    assert not hasattr(undated, "published_at")
    return items + [undated]


def test_every_fetched_entry_records_its_publication_time(
    orchestrator, monkeypatch, tmp_path
) -> None:
    """(a) Each fetched entry carries `published_at`, in UTC, and null when the item has none."""
    from datetime import timedelta

    tokyo = timezone(timedelta(hours=9))
    items = _dated_items(datetime(2026, 9, 14, 21, 0, tzinfo=timezone.utc),
                         datetime(2026, 9, 14, 21, 0, tzinfo=tokyo))
    _, _, record = _record_a_night(orchestrator, monkeypatch, tmp_path, items)

    assert all("published_at" in e for e in record["fetched"])
    by_id = {e["id"]: e["published_at"] for e in record["fetched"]}
    assert by_id == {"i0": "2026-09-14T21:00:00+00:00",
                     "i1": "2026-09-14T12:00:00+00:00",
                     "i2": None}
    for value in filter(None, by_id.values()):
        assert datetime.fromisoformat(value).utcoffset() == timedelta(0)
    # No window was computed on a direct call, so the bounds are null, not now.
    assert record["contract"]["window_start"] is None
    assert record["contract"]["window_end"] is None


def test_the_contract_records_the_window_the_fetch_used(
    orchestrator, monkeypatch, tmp_path
) -> None:
    """(b) window_start <= window_end, both parseable, and start is the `since` handed to the fetch."""
    from datetime import timedelta

    since = orchestrator._determine_time_window(force_hours=30)
    items = _dated_items(datetime(2026, 9, 14, tzinfo=timezone.utc),
                         datetime(2026, 9, 14, tzinfo=timezone.utc))
    _, _, record = _record_a_night(orchestrator, monkeypatch, tmp_path, items)

    start = datetime.fromisoformat(record["contract"]["window_start"])
    end = datetime.fromisoformat(record["contract"]["window_end"])
    assert start <= end
    assert start == since
    assert end - start == timedelta(hours=30)
    assert start.utcoffset() == end.utcoffset() == timedelta(0)
    assert set(record["contract"]["stamps"]) == {"window_start", "window_end"}


def test_the_dates_change_no_other_key_and_no_funnel_value(
    orchestrator, monkeypatch, tmp_path
) -> None:
    """(c) Recording only: wildly different dates and windows leave every decision and every other key alone."""
    from datetime import timedelta

    def strip(record):
        record = json.loads(json.dumps(record))
        for key in ("written_at", "window_start", "window_end", "stamps"):
            record["contract"].pop(key)
        for entry in record["fetched"]:
            entry.pop("published_at")
        return record

    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    orchestrator._determine_time_window(force_hours=30)
    ids_a, result_a, record_a = _record_a_night(
        orchestrator, monkeypatch, tmp_path / "a",
        _dated_items(datetime(2026, 9, 14, tzinfo=timezone.utc),
                     datetime(2026, 9, 14, tzinfo=timezone(timedelta(hours=9)))))
    orchestrator._determine_time_window(force_hours=1)
    ids_b, result_b, record_b = _record_a_night(
        orchestrator, monkeypatch, tmp_path / "b",
        _dated_items(datetime(1999, 1, 1, tzinfo=timezone.utc),
                     datetime(2031, 6, 30, tzinfo=timezone.utc)))

    # The funnel: the same items published, gated, ranked, refused.
    assert ids_a == ids_b == ["i1"]
    assert (result_a.gate_kept, result_a.gate_dropped, result_a.defend_rejected,
            result_a.ranked_ids) == (result_b.gate_kept, result_b.gate_dropped,
                                     result_b.defend_rejected, result_b.ranked_ids)
    # The record, less the new fields and the clock stamp, is identical.
    assert record_a["contract"]["window_start"] != record_b["contract"]["window_start"]
    assert strip(record_a) == strip(record_b)
    # And its shape is the shape it had before N-341, plus exactly the new fields.
    assert set(record_a) == _FIXTURE_KEYS
    assert record_a["version"] == 3 and record_a["contract"]["version"] == 4
    assert set(record_a["contract"]) == {"version", "written_at", "records",
                                         "window_start", "window_end", "stamps"}
    assert set(record_a["contract"]["records"]) == _RECORDED_KEYS
    assert all(set(e) == _FETCHED_ENTRY_KEYS | {"published_at"}
               for e in record_a["fetched"])


def test_the_recorded_time_is_utc_or_null_and_never_raises() -> None:
    """The helper sits inside a write that catches only OSError, so it must not raise."""
    from datetime import timedelta

    from src.orchestrator import _fixture_time

    assert _fixture_time(datetime(2026, 9, 14, 21, 0, tzinfo=timezone(timedelta(hours=9)))) \
        == "2026-09-14T12:00:00+00:00"
    assert _fixture_time(datetime(2026, 9, 14, 21, 0)) == "2026-09-14T21:00:00+00:00"
    assert _fixture_time(None) is None
    assert _fixture_time("2026-09-14") is None
    assert _fixture_time(datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=9)))) is None
