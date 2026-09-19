"""Pass L, the labels (NEWS-Radar, 2026-09-19): majority per field, the prompt
file as the only source of the system text, the estimator's labels term."""
from __future__ import annotations

import asyncio
import json

import pytest

from src.selection import ladder as L
from src.selection.contract import Candidate

SEVEN = {"form": "paper", "evidence": "actor-statement", "research_horizon": "near",
         "horizon_basis": "quoted words", "action_a_team_might_take": "Pilot it.",
         "how_soon": "this-quarter", "topic": "agents"}


def _cands(n=2):
    return [Candidate(id=f"c{i}", title=f"T{i}", summary="", source="hn", url=f"https://x/{i}", content="body") for i in range(n)]


def test_label_tally_majority_per_categorical_field_and_free_text_from_the_agreeing_run():
    a = dict(SEVEN); b = dict(SEVEN, form="release", horizon_basis="other words"); c = dict(SEVEN, how_soon="this-year")
    out = L.label_tally([a, b, c])
    assert out["labels"]["form"] == "paper" and out["labels"]["how_soon"] == "this-quarter"
    assert out["labels"]["horizon_basis"] == "quoted words", "free text from the run that agrees on every category"
    assert out["label_runs"] == 3 and out["label_agree"] == pytest.approx(2 / 3)


def test_label_tally_is_null_never_partial_when_no_run_carries_all_seven_keys():
    out = L.label_tally([{"form": "paper"}, None, None])
    assert out == {"labels": None, "label_runs": 1, "label_agree": None}


def test_label_user_carries_the_byline_and_item_user_does_not():
    c = _cands(1)[0]
    assert "Author: Jane" in L.label_user(c, "Jane") and "Author:" not in L.item_user(c)
    assert "Summary" not in L.label_user(c, "Jane")


def test_the_estimate_gains_a_labels_term_only_when_asked_and_the_rate_is_e42s_receipt():
    assert L.USD_PER_CANDIDATE_LABEL_RUN == pytest.approx(2.244 / 351)
    base = L.estimate_usd(100, 3)
    assert L.estimate_usd(100, 3, labels=False) == base
    assert L.estimate_usd(100, 3, labels=True) == pytest.approx(base + 100 * 3 * L.USD_PER_CANDIDATE_LABEL_RUN)


class _Client:
    def __init__(self):
        self.systems = []

    async def complete(self, system, user, *, model=None, schema=None, effort=None):
        self.systems.append(system)
        if system == L.theme_system():
            return json.dumps({"theme": next(iter(L.TAXONOMY_V2_3)), "second": "none", "why": "w"})
        if "LABELS" in system:
            return json.dumps(SEVEN)
        return json.dumps({"relevance": 7, "urgency": 5, "must_read": False, "line": "x"})


def test_pass_l_is_skipped_and_null_when_the_prompt_file_is_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(L, "LABEL_PROMPT_PATH", tmp_path / "absent.txt")
    client = _Client()
    block = asyncio.run(L.run_ladder(client, _cands(), L.LadderSettings(runs=1, use_batch=False, labels_enabled=True)))
    assert block["labels"].startswith("skipped:") and block["calls"]["label_asked"] == 0
    assert all(r["labels"] is None for r in block["items"])
    assert not any("LABELS" in s for s in client.systems)


def test_pass_l_sends_the_file_bytes_once_per_item_per_run_and_records_the_majority(monkeypatch, tmp_path):
    prompt = tmp_path / "ladder_labels.txt"
    prompt.write_text("lLABELS system text\n", encoding="utf-8")
    monkeypatch.setattr(L, "LABEL_PROMPT_PATH", prompt)
    entered = []
    from contextlib import contextmanager

    @contextmanager
    def hook(name, purpose=""):
        entered.append(name); yield

    client = _Client()
    settings = L.LadderSettings(runs=3, use_batch=False, labels_enabled=True, stage_hook=hook)
    block = asyncio.run(L.run_ladder(client, _cands(2), settings, authors={"c0": "Jane"}))
    assert block["labels"].startswith("prompt md5 ") and block["calls"] == {
        "vote_asked": 6, "vote_returned": 6, "judge_asked": 2, "judge_returned": 2, "label_asked": 6, "label_returned": 6}
    assert [r["labels"] for r in block["items"]] == [SEVEN, SEVEN]
    assert entered == ["ladder_vote", "ladder_judge", "ladder_label"]
    assert sum(1 for s in client.systems if s == prompt.read_text(encoding="utf-8")) == 6, "the file's bytes, unchanged"


def test_pass_l_off_by_default_records_null_and_no_calls():
    block = asyncio.run(L.run_ladder(_Client(), _cands(), L.LadderSettings(runs=1, use_batch=False)))
    assert block["labels"] == "off" and block["calls"]["label_asked"] == 0 and block["items"][0]["labels"] is None


def test_the_labels_prompt_file_is_the_lab_commit_byte_for_byte():
    """The file is a copy of OS research/ladder-lab/NIGHT-A-PASS-L-PROMPT-SHIPPED.txt's
    body (OS commit 71377ec, 2026-09-19), whose generator night_a_prompt.py is the
    master. The md5 is the one that commit's header states; the radar's
    tools/replay_ladder.py --check-prompts compares the live bytes against the
    generator, and this test only says the copy has not moved since it landed."""
    import hashlib
    body = L.LABEL_PROMPT_PATH.read_bytes()
    assert len(body) == 5352 and hashlib.md5(body).hexdigest() == "cb8bb22f1b8cab894225e397543dd860"
    assert b"confirmed = an independent party" in body, "sitting 2.9c kept confirmed"
    assert L.label_system() == body.decode("utf-8")
