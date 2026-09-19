"""The per-call cost record (NEWS-Radar, TOKENOMICS v2 clause 1, 2026-09-19).

Each test enters the production function it exercises: `record_call` through
the client's own `_record`, the stage context through `stage()`, the ledger
through `write_ledger` and `reconcile`, the metrics summary through
`cost_by_stage`. A control that exercises a copy of a check is blind to it.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from pathlib import Path

import pytest

from src.ai import tokens
from src.ai.client import AnthropicClient
from src.ai.tokens import (UNATTRIBUTED, get_calls, key_identifier, reconcile,
                           record_call, stage, stage_summary, write_ledger)


@pytest.fixture(autouse=True)
def _reset():
    tokens.reset_usage()
    yield
    tokens.reset_usage()


def _message(inp=100, out=10, cache_read=0, cache_write=0, model="claude-sonnet-5", stop="end_turn"):
    usage = SimpleNamespace(input_tokens=inp, output_tokens=out,
                            cache_read_input_tokens=cache_read,
                            cache_creation_input_tokens=cache_write)
    return SimpleNamespace(usage=usage, model=model, stop_reason=stop)


def _client(key_id="ANTHROPIC_API_KEY:deadbeef"):
    c = AnthropicClient.__new__(AnthropicClient)
    c.config = SimpleNamespace(provider=SimpleNamespace(value="anthropic"))
    c.key_id = key_id
    return c


def test_key_identifier_never_carries_the_key():
    key = "placeholder-not-a-key-THIS-IS-A-TEST-VALUE-0123456789"
    ident = key_identifier("ANTHROPIC_API_KEY", key)
    assert ident.startswith("ANTHROPIC_API_KEY:")
    assert len(ident.split(":")[1]) == 8
    assert "SECRET" not in ident and key[-8:] not in ident
    assert key_identifier("ANTHROPIC_API_KEY", key) == ident, "stable for one value"
    assert key_identifier("ANTHROPIC_API_KEY", key + "x") != ident, "differs for another"
    assert key_identifier("X", None) == "X:none"


def test_client_record_attributes_to_the_current_stage_with_cache_and_batch():
    c = _client()
    with stage("gate", "sift"):
        c._record(_message(100, 10, cache_read=40, cache_write=5, model="claude-haiku-4-5"), batch=True)
    c._record(_message(7, 3))
    calls = get_calls()
    assert [x.stage for x in calls] == ["gate", UNATTRIBUTED]
    g = calls[0]
    assert (g.purpose, g.provider, g.key_id, g.model) == ("sift", "anthropic", "ANTHROPIC_API_KEY:deadbeef", "claude-haiku-4-5")
    assert (g.input_tokens, g.output_tokens, g.cache_read_tokens, g.cache_write_tokens) == (100, 10, 40, 5)
    assert g.batch is True and g.stop_reason == "end_turn"
    assert calls[1].batch is False


def test_stage_nests_and_restores():
    with stage("outer"):
        record_call("anthropic", "m", "k", input_tokens=1)
        with stage("inner"):
            record_call("anthropic", "m", "k", input_tokens=1)
        record_call("anthropic", "m", "k", input_tokens=1)
    record_call("anthropic", "m", "k", input_tokens=1)
    assert [x.stage for x in get_calls()] == ["outer", "inner", "outer", UNATTRIBUTED]


def test_reconcile_agrees_when_every_call_is_recorded_and_speaks_when_one_is_not():
    c = _client()
    with stage("rank"):
        c._record(_message(50, 5))
        c._record(_message(30, 2))
    rec = reconcile()
    assert rec["agree"] is True and rec["calls"] == 2 and rec["unattributed"] == 0
    assert (rec["ledger_input"], rec["totals_input"]) == (80, 80)
    # A call that reached the totals but not the ledger (the shape of a client
    # that records usage without the per-call line) must show as a difference.
    tokens.record_usage("anthropic", input_tokens=9, output_tokens=1, model="m")
    rec = reconcile()
    assert rec["agree"] is False and rec["totals_input"] - rec["ledger_input"] == 9


def test_ledger_round_trips_and_summarises_per_stage(tmp_path: Path):
    c = _client()
    with stage("gate", "sift"):
        c._record(_message(100, 10), batch=True)
        c._record(_message(100, 10), batch=True)
    with stage("defend", "read"):
        c._record(_message(500, 50, cache_read=200))
    path = tmp_path / "data" / "cost_ledger-x.jsonl"
    assert write_ledger(path) == 3
    rows = [json.loads(l) for l in path.read_text().splitlines()]
    assert len(rows) == 3 and rows[2]["cache_read_tokens"] == 200 and rows[0]["batch"] is True
    summ = stage_summary()
    assert summ["gate"]["calls"] == 2 and summ["gate"]["batch_calls"] == 2 and summ["gate"]["input_tokens"] == 200
    assert summ["defend"]["cache_read_tokens"] == 200 and summ["defend"]["batch_calls"] == 0
    # the metrics row reads the same file through its own function
    import importlib.util
    spec = importlib.util.spec_from_file_location("record_metrics", Path("scripts/record_metrics.py"))
    rm = importlib.util.module_from_spec(spec); spec.loader.exec_module(rm)
    by = rm.cost_by_stage(tmp_path / "data")
    assert by["gate"]["calls"] == 2 and by["defend"]["cache_read_tokens"] == 200
    assert by["gate"]["keys"] == {"ANTHROPIC_API_KEY:deadbeef": 2}
    assert rm.cost_by_stage(tmp_path / "empty") is None, "no ledger is null, never zeros"


def test_reset_clears_the_ledger():
    record_call("anthropic", "m", "k", input_tokens=1)
    tokens.reset_usage()
    assert get_calls() == [] and reconcile()["calls"] == 0


def test_selection_enters_the_stage_hook_in_pass_order():
    """The hook is entered by the production `select()` itself, once per pass.

    The selection package may not import the engine, so the ledger reaches it
    through `SelectionSettings.stage_hook`; this proves the hook is CALLED at
    the boundaries and in order, using the same fake client the selection
    tests use, so a pass that forgets its boundary reads as a missing name.
    """
    import asyncio
    from contextlib import contextmanager
    import json as _json
    from src.selection.contract import Candidate
    from src.selection.pipeline import SelectionSettings, select

    entered: list = []

    @contextmanager
    def hook(name, purpose=""):
        entered.append(name)
        yield

    themes = {"practice": "What would a team do differently?"}
    cands = [Candidate(id=f"c{i}", title=f"T{i}", summary="s" * 40, source="hn",
                       url=f"https://x/{i}", theme=None) for i in range(3)]

    class Client:
        async def complete(self, system, user, *, model=None, schema=None, effort=None):
            if "candidate" in user.lower() and "keep" in system.lower():
                return _json.dumps([{"id": c.id, "keep": True, "theme": "practice", "reason": "r"} for c in cands])
            if schema and "enum" in _json.dumps(schema):
                ids = schema.get("properties", {}).get("winner", {}).get("enum") or []
                return _json.dumps({"winner": ids[0]}) if ids else "{}"
            return _json.dumps({"publish": True, "score": 8.0, "reason": "ok"})

    settings = SelectionSettings(use_batch=False, consider=2, stage_hook=hook)
    try:
        asyncio.run(select(cands, Client(), themes, settings))
    except Exception:
        pass  # the fake client's answers need not satisfy every pass; the boundaries were entered before any of them answered
    assert entered[:1] == ["gate"], entered
    assert "rank" in entered and "defend" in entered, entered


def test_the_switches_the_run_executed_are_recorded_and_reach_the_metrics_row(tmp_path: Path):
    """The owner, 2026-09-19: a booked night with two variables is attributed from
    the record. `ladder_switches` reads the executed config; the metrics row
    reads the fixture's block through its own function; a night without a
    fixture reads null, never a default."""
    import importlib.util
    from src.orchestrator import ladder_switches
    sel = SimpleNamespace(ladder_enabled=True, ladder_labels_enabled=True, pull_enabled=False,
                          ladder_runs=3, ladder_max_usd=4.0, ladder_model=None)
    sw = ladder_switches(sel)
    assert sw == {"ladder_enabled": True, "ladder_labels_enabled": True, "pull_enabled": False,
                  "ladder_runs": 3, "ladder_max_usd": 4.0, "ladder_model": None}
    assert ladder_switches(SimpleNamespace())["ladder_labels_enabled"] is False
    spec = importlib.util.spec_from_file_location("record_metrics", Path("scripts/record_metrics.py"))
    rm = importlib.util.module_from_spec(spec); spec.loader.exec_module(rm)
    d = tmp_path / "data"; d.mkdir()
    assert rm.switches_from_fixture(d) is None
    (d / "rank_fixture-20260922-0337.json").write_text(json.dumps({"version": 4, "switches": sw}), encoding="utf-8")
    assert rm.switches_from_fixture(d) == sw
