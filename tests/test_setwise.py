"""The setwise tournament: correctness with a scripted judge, failure isolation."""

import asyncio
import json

import pytest

from src.selection.contract import Candidate
from src.selection.setwise import PickStats, setwise_rank


def _cands(n):
    # ids c00..cNN; the scripted judge prefers HIGHER ids, so the true
    # ranking is reverse-lexicographic: c09 > c08 > ... > c00.
    return [Candidate(id=f"c{i:02d}", title=f"t{i}", summary="s", source="src",
                      url="u") for i in range(n)]


def _judge(fail_ids=(), calls=None):
    """Completer that picks the max id in the set; can be told to fail when
    a specific id is present in the group (to test fallback isolation)."""
    async def complete(system, user, schema):
        if calls is not None:
            calls.append(sorted(schema["properties"]["best"]["enum"]))
        ids = schema["properties"]["best"]["enum"]
        if any(f in ids for f in fail_ids):
            return "garbage"
        return json.dumps({"best": max(ids)})
    return complete


def test_full_extraction_yields_exact_descending_order():
    cands = _cands(10)
    out = asyncio.run(setwise_rank(cands, _judge(), set_size=3))
    assert [c.id for c in out] == [f"c{i:02d}" for i in range(9, -1, -1)]


def test_partial_need_orders_head_and_keeps_remainder_stable():
    cands = _cands(12)
    out = asyncio.run(setwise_rank(cands, _judge(), set_size=4, need=3))
    assert [c.id for c in out[:3]] == ["c11", "c10", "c09"]
    # remainder in original stable order, nothing lost
    assert [c.id for c in out[3:]] == [f"c{i:02d}" for i in range(9)]
    assert len(out) == 12


def test_pool_smaller_than_set_size():
    cands = _cands(3)
    out = asyncio.run(setwise_rank(cands, _judge(), set_size=7))
    assert [c.id for c in out] == ["c02", "c01", "c00"]


def test_need_larger_than_pool_returns_everything_ordered():
    cands = _cands(4)
    out = asyncio.run(setwise_rank(cands, _judge(), set_size=2, need=99))
    assert [c.id for c in out] == ["c03", "c02", "c01", "c00"]


def test_a_failing_group_falls_back_and_touches_nothing_else():
    """Groups containing c01 fail; the fallback affects only that group's
    pick, every other candidate still ranks by merit, nothing is lost."""
    cands = _cands(9)
    stats = PickStats()
    out = asyncio.run(setwise_rank(
        cands, _judge(fail_ids=("c01",)), set_size=3, stats=stats))
    assert stats.fallbacks >= 1
    assert sorted(c.id for c in out) == sorted(c.id for c in cands)
    # c08 must still win overall: its groups never contained c01 at build.
    assert out[0].id == "c08"


def test_determinism_two_runs_identical():
    cands = _cands(11)
    a = asyncio.run(setwise_rank(cands, _judge(), set_size=4))
    b = asyncio.run(setwise_rank(cands, _judge(), set_size=4))
    assert [c.id for c in a] == [c.id for c in b]


def test_call_count_is_tournament_shaped_not_quadratic():
    cands = _cands(20)
    calls = []
    asyncio.run(setwise_rank(cands, _judge(calls=calls), set_size=5, need=6))
    # naive rebuild-per-extraction would be ~6*(5)=30+; the bracket with
    # path replay should stay well under that.
    assert len(calls) < 26, len(calls)
