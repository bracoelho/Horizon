"""Selection core: gate, rank, defend.

These tests lean on the failure modes rather than the happy path. A selector that
works when the model behaves is easy; the risk is silently losing items when it
does not.
"""

from __future__ import annotations

import asyncio
import json
from typing import Dict, List

import pytest

from src.selection import gate
from src.selection import rank as rank_mod
from src.selection.contract import Candidate, GateVerdict
from src.selection.defend import defend
from src.selection.pipeline import SelectionSettings, select

THEMES = {
    "practice": "What would a team do differently?",
    "horizon-research": "What would have to be true for this to matter?",
}


def _cands(n: int, prefix: str = "i") -> List[Candidate]:
    return [
        Candidate(
            id=f"{prefix}{k}",
            title=f"Item {k}",
            summary=f"Summary {k}",
            source="feed",
            url=f"https://example.com/{k}",
        )
        for k in range(n)
    ]


# ------------------------------------------------------------------- gate


def test_gate_batches_requests() -> None:
    reqs = gate.build_requests(_cands(95), THEMES, batch_size=40)
    assert [r[0] for r in reqs] == ["gate-0", "gate-1", "gate-2"]


def test_gate_collects_verdicts_by_id() -> None:
    cands = _cands(3)
    payload = json.dumps(
        {"verdicts": [
            {"id": "i2", "keep": True, "theme": "practice", "reason": "r"},
            {"id": "i0", "keep": False, "theme": "practice", "reason": "r"},
            {"id": "i1", "keep": True, "theme": "practice", "reason": "r"},
        ]}
    )
    verdicts = gate.collect({"gate-0": payload}, cands, THEMES)
    assert [(v.id, v.keep) for v in verdicts] == [
        ("i0", False), ("i1", True), ("i2", True)
    ]


def test_gate_keeps_items_it_never_ruled_on() -> None:
    """An unparsed response must not silently delete work."""
    cands = _cands(3)
    payload = json.dumps({"verdicts": [{"id": "i0", "keep": False, "theme": "practice", "reason": ""}]})
    verdicts = gate.collect({"gate-0": payload}, cands, THEMES)
    kept = {v.id: v.keep for v in verdicts}
    assert kept == {"i0": False, "i1": True, "i2": True}


def test_gate_survives_unparseable_output() -> None:
    cands = _cands(2)
    verdicts = gate.collect({"gate-0": "the model rambled"}, cands, THEMES)
    assert all(v.keep for v in verdicts)


def test_gate_extracts_json_wrapped_in_prose() -> None:
    cands = _cands(1)
    text = 'Sure!\n{"verdicts":[{"id":"i0","keep":false,"theme":"practice","reason":"x"}]}\nDone.'
    assert gate.collect({"g": text}, cands, THEMES)[0].keep is False


def test_gate_rejects_a_theme_that_does_not_exist() -> None:
    cands = _cands(1)
    text = json.dumps({"verdicts": [{"id": "i0", "keep": True, "theme": "invented", "reason": ""}]})
    assert gate.collect({"g": text}, cands, THEMES)[0].theme is None


def test_gate_ignores_ids_it_was_never_given() -> None:
    cands = _cands(1)
    text = json.dumps({"verdicts": [
        {"id": "i0", "keep": True, "theme": "practice", "reason": ""},
        {"id": "hallucinated", "keep": True, "theme": "practice", "reason": ""},
    ]})
    verdicts = gate.collect({"g": text}, cands, THEMES)
    assert [v.id for v in verdicts] == ["i0"]


def test_gate_apply_tags_the_theme() -> None:
    cands = _cands(2)
    verdicts = [
        GateVerdict("i0", True, "practice"),
        GateVerdict("i1", False, "practice"),
    ]
    kept = gate.apply(cands, verdicts)
    assert [(c.id, c.theme) for c in kept] == [("i0", "practice")]


# ------------------------------------------------------------------- rank


def _ranker(order_for):
    async def complete(system: str, user: str) -> str:
        ids = [line.split("]")[0][1:] for line in user.splitlines() if line.startswith("[")]
        return json.dumps({"order": order_for(ids), "note": "n"})
    return complete


def test_rank_applies_the_returned_order() -> None:
    cands = _cands(4)
    out = asyncio.run(rank_mod.rank(cands, _ranker(lambda ids: list(reversed(ids)))))
    assert [c.id for c in out] == ["i3", "i2", "i1", "i0"]


def test_rank_appends_ids_the_model_forgot() -> None:
    """Dropping an id must degrade to unranked, never to lost."""
    cands = _cands(4)
    out = asyncio.run(rank_mod.rank(cands, _ranker(lambda ids: ids[:2])))
    assert sorted(c.id for c in out) == ["i0", "i1", "i2", "i3"]
    assert [c.id for c in out[:2]] == ["i0", "i1"]


def test_rank_discards_invented_ids() -> None:
    cands = _cands(2)
    out = asyncio.run(rank_mod.rank(cands, _ranker(lambda ids: ["ghost"] + ids)))
    assert [c.id for c in out] == ["i0", "i1"]


def test_rank_ignores_a_repeated_id() -> None:
    cands = _cands(3)
    out = asyncio.run(rank_mod.rank(cands, _ranker(lambda ids: [ids[0], ids[0], ids[1], ids[2]])))
    assert [c.id for c in out] == ["i0", "i1", "i2"]


def test_rank_survives_unparseable_output() -> None:
    async def broken(system, user):
        return "no json here"
    cands = _cands(3)
    out = asyncio.run(rank_mod.rank(cands, broken))
    assert sorted(c.id for c in out) == ["i0", "i1", "i2"]


def test_rank_chunks_a_large_set_and_runs_the_winners_off() -> None:
    calls = []

    async def complete(system: str, user: str) -> str:
        ids = [line.split("]")[0][1:] for line in user.splitlines() if line.startswith("[")]
        calls.append(len(ids))
        return json.dumps({"order": ids, "note": "n"})

    out = asyncio.run(
        rank_mod.rank(_cands(60), complete, chunk_size=25, carry=5)
    )
    # three chunks of <=25, then one runoff over the 15 carried winners
    assert calls[:3] == [25, 25, 10]
    assert calls[3] == 15
    assert len(out) == 15


def test_rank_of_one_item_makes_no_call() -> None:
    async def explode(system, user):
        raise AssertionError("should not be called")
    assert len(asyncio.run(rank_mod.rank(_cands(1), explode))) == 1


# ----------------------------------------------------------------- defend


def _defender(decide):
    async def complete(system: str, user: str) -> str:
        title = user.splitlines()[0].removeprefix("Title: ")
        return json.dumps({"publish": decide(title), "why": "because"})
    return complete


def test_defend_filters_but_preserves_rank_order() -> None:
    cands = _cands(5)
    selected, verdicts = asyncio.run(
        defend(cands, _defender(lambda t: t in ("Item 0", "Item 3")), THEMES)
    )
    assert [c.id for c in selected] == ["i0", "i3"]
    assert len(verdicts) == 5


def test_defend_caps_the_edition() -> None:
    cands = _cands(10)
    selected, _ = asyncio.run(
        defend(cands, _defender(lambda t: True), THEMES, max_publish=3)
    )
    assert len(selected) == 3


def test_defend_only_reads_the_shortlist() -> None:
    seen = []

    async def complete(system, user):
        seen.append(user.splitlines()[0])
        return json.dumps({"publish": True, "why": ""})

    asyncio.run(defend(_cands(30), complete, THEMES, consider=4, max_publish=99))
    assert len(seen) == 4


def test_defend_rejects_when_the_call_fails() -> None:
    """A failed judgement must not default to publishing."""
    async def broken(system, user):
        raise RuntimeError("api down")
    selected, verdicts = asyncio.run(defend(_cands(2), broken, THEMES))
    assert selected == []
    assert all(not v.publish for v in verdicts)


def test_defend_rejects_when_no_verdict_is_returned() -> None:
    async def vague(system, user):
        return json.dumps({"why": "hmm"})
    selected, _ = asyncio.run(defend(_cands(2), vague, THEMES))
    assert selected == []


def test_defend_can_publish_nothing_on_a_quiet_day() -> None:
    selected, _ = asyncio.run(defend(_cands(5), _defender(lambda t: False), THEMES))
    assert selected == []


# --------------------------------------------------------------- pipeline


class _FakeClient:
    def __init__(self):
        self.batch_calls = 0

    async def complete(self, system, user, *, model=None, schema=None, effort=None):
        if "rank" in system.lower() and "order them" in user.lower():
            ids = [l.split("]")[0][1:] for l in user.splitlines() if l.startswith("[")]
            return json.dumps({"order": ids, "note": "n"})
        if user.startswith("Title:"):
            return json.dumps({"publish": True, "why": "w"})
        ids = [l.split("]")[0][1:] for l in user.splitlines() if l.startswith("[")]
        return json.dumps({"verdicts": [
            {"id": i, "keep": True, "theme": "practice", "reason": ""} for i in ids
        ]})

    async def complete_batch(self, requests, **kwargs):
        self.batch_calls += 1
        out = {}
        for r in requests:
            out[r.custom_id] = await self.complete(r.system, r.user)
        return out


def test_select_end_to_end_produces_a_capped_edition() -> None:
    client = _FakeClient()
    result = asyncio.run(
        select(_cands(30), client, THEMES, SelectionSettings(max_publish=4))
    )
    assert result.published_count == 4
    assert result.gate_kept == 30
    assert result.gate_dropped == 0
    assert client.batch_calls == 1


def test_select_uses_batch_when_enabled_and_live_calls_when_not() -> None:
    client = _FakeClient()
    asyncio.run(select(_cands(5), client, THEMES, SelectionSettings(use_batch=False)))
    assert client.batch_calls == 0


def test_select_on_empty_input_does_nothing() -> None:
    result = asyncio.run(select([], _FakeClient(), THEMES))
    assert result.published_count == 0


def test_select_stops_when_the_gate_drops_everything() -> None:
    class _DropAll(_FakeClient):
        async def complete(self, system, user, *, model=None, schema=None, effort=None):
            ids = [l.split("]")[0][1:] for l in user.splitlines() if l.startswith("[")]
            return json.dumps({"verdicts": [
                {"id": i, "keep": False, "theme": "practice", "reason": ""} for i in ids
            ]})

    result = asyncio.run(select(_cands(10), _DropAll(), THEMES))
    assert result.published_count == 0
    assert result.gate_dropped == 10


# ------------------------------------------------------------- portability


def test_selection_imports_nothing_from_the_engine() -> None:
    """The break-away seam, pinned.

    Selection is the module this project intends to own and eventually move. If
    it grows an engine import, it stops being portable and nothing else would
    notice until the move failed. Only `adapter.py` may know about the pipeline,
    and it does so by duck typing rather than by importing.
    """
    import pathlib
    import re

    package = pathlib.Path("src/selection")
    offenders = {}
    pattern = re.compile(r"^\s*(from\s+\.\.|from\s+src[\. ]|import\s+src[\. ])", re.M)
    for path in package.glob("*.py"):
        hits = pattern.findall(path.read_text())
        if hits:
            offenders[path.name] = hits
    assert offenders == {}, f"selection gained engine imports: {offenders}"


def test_adapter_converts_a_pipeline_item_without_importing_its_type() -> None:
    from types import SimpleNamespace

    from src.selection import to_candidate

    item = SimpleNamespace(
        id="x1",
        title="Grid operator deploys forecasting",
        url="https://example.com/x1",
        content="full body text",
        published_at=None,
        source_type=SimpleNamespace(value="rss"),
        metadata={"feed_name": "Utility Dive"},
        processing=SimpleNamespace(analysis=SimpleNamespace(summary="a summary")),
    )
    candidate = to_candidate(item)
    assert candidate.id == "x1"
    assert candidate.source == "Utility Dive"
    assert candidate.summary == "a summary"
    assert candidate.content == "full body text"


def test_adapter_falls_back_when_fields_are_missing() -> None:
    from types import SimpleNamespace

    from src.selection import to_candidate

    bare = SimpleNamespace(id="x2", url="u", metadata={}, processing=None)
    candidate = to_candidate(bare)
    assert candidate.title == "Untitled"
    assert candidate.source == "unknown"


def test_ranker_logs_what_it_could_not_read(caplog):
    """A parse failure and a call failure used to look identical.

    _parse_order discards the text it cannot read, so an unreadable response
    surfaced only as "omitted N of N ids". That gave no way to tell malformed
    JSON from a truncation from a model answering in prose, which is exactly
    what was needed on the runs of 2026-08-27 and 2026-08-29.
    """
    cands = _cands(3)

    async def prose(system: str, user: str) -> str:
        return "Here are the items ranked by importance, most important first."

    with caplog.at_level("WARNING"):
        result = asyncio.run(rank_mod.rank(cands, prose))

    assert [c.id for c in result] == [c.id for c in cands]  # nothing lost
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "could not read the response" in logged
    assert "Here are the items ranked" in logged  # the raw text is there


def test_ranker_retries_once_before_giving_up():
    """A chunk that cannot be read promotes items on arbitrary order.

    Those go on to displace genuinely ranked items in the runoff, so one retry
    is worth more here than it would be on a stage whose failure is contained.
    """
    calls: List[int] = []
    cands = _cands(3)

    async def flaky(system: str, user: str) -> str:
        calls.append(1)
        if len(calls) == 1:
            return "not json at all"
        return json.dumps({"order": [c.id for c in reversed(cands)]})

    result = asyncio.run(rank_mod.rank(cands, flaky))

    assert len(calls) == 2
    assert [c.id for c in result] == [c.id for c in reversed(cands)]


def test_ranker_stops_after_the_retry():
    """Two attempts, not an unbounded loop, and the items survive unranked."""
    calls: List[int] = []
    cands = _cands(4)

    async def never(system: str, user: str) -> str:
        calls.append(1)
        return "{}"

    result = asyncio.run(rank_mod.rank(cands, never))

    assert len(calls) == 2
    assert sorted(c.id for c in result) == sorted(c.id for c in cands)
