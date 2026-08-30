"""The replay harness's pure parts: fixture loading and the agreement metric."""

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "replay_rank.py"


def _load():
    spec = importlib.util.spec_from_file_location("replay_rank", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rr = _load()


def test_fixture_round_trips_into_candidates(tmp_path):
    p = tmp_path / "f.json"
    p.write_text(json.dumps([
        {"id": "a", "title": "T", "summary": "S", "source": "src",
         "url": "u", "theme": "practice"},
        {"id": "b", "title": "T2", "summary": "", "source": "", "url": ""},
    ]), encoding="utf-8")

    cands = rr.load_fixture(p)

    assert [c.id for c in cands] == ["a", "b"]
    assert cands[0].theme == "practice"
    assert cands[1].theme is None


def test_head_agreement_is_one_for_identical_heads():
    assert rr.head_agreement([["a", "b", "c"]] * 3 ) == 1.0


def test_head_agreement_penalises_divergence():
    same = rr.head_agreement([["a", "b"], ["a", "b"]])
    half = rr.head_agreement([["a", "b"], ["a", "x"]])
    none = rr.head_agreement([["a", "b"], ["x", "y"]])

    assert same == 1.0
    assert half == 0.5
    assert none == 0.0


def test_an_empty_head_counts_as_total_disagreement():
    """A pass that returned nothing must not inflate stability."""
    assert rr.head_agreement([["a"], []]) == 0.0
