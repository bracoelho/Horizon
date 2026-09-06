#!/usr/bin/env python3
"""Replay a recorded night's selection against a configuration.

Stages S-A and S-B of NEWS-Radar's PLAN-REPLAY. The radar learns one thing a
night because production is the only place a change can be observed, and that is
a rate limit rather than a safety rule. This lifts it for the selection stages:
a recorded field, the real gate, ranker and defender, no publishing.

What it does NOT do, and the limit is structural rather than unfinished work: a
fixture holds the candidates the ranker saw, so collection, the window, source
health and the analysis pass are all outside it. A replay says what selection
would have decided, never what the night would have contained.

The rule the design rests on: this reads the SAME configuration file production
reads, and never gets a copy of its own. Overrides arrive as `--set` flags and
every one of them is printed in the report's header, because a run whose
configuration cannot be read off its own output is not evidence.

Runs on the experiments purse. Set ANTHROPIC_API_KEY_EXPERIMENTS and it is used
in preference to ANTHROPIC_API_KEY, so a replay can never be billed to the key
that pays for the nightly run:

    export ANTHROPIC_API_KEY_EXPERIMENTS=$(security find-generic-password \
        -s ANTHROPIC_API_KEY_EXPERIMENTS -w)
    uv run python scripts/replay.py fixtures/rank_fixture-20260906-0337.json
    uv run python scripts/replay.py <fixture> --set selection.lead_sources='["Google News"]'
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ai.client import create_ai_client  # noqa: E402
from src.orchestrator import HorizonOrchestrator  # noqa: E402
from src.selection import Candidate, select as run_selection  # noqa: E402
from src.ai.tokens import get_usage_snapshot  # noqa: E402
from src.storage.manager import StorageManager  # noqa: E402


def load_fixture(path: Path) -> Dict[str, Any]:
    """Read either fixture shape, and say which one plainly.

    Version 1 is a bare list of candidates. Version 2 adds the decisions taken
    on them. Both are replayable; only version 2 can be compared against what
    the night actually decided, which is the whole point of the comparison and
    the reason nothing before 2026-09-06 can serve as a baseline.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return {"version": 1, "candidates": raw, "shortlist": [], "defend": [],
                "published": []}
    return raw


def scores_of(record: Dict[str, Any]) -> Dict[str, float]:
    """The analysis score per id, when the fixture is version 3 or later.

    Before 2026-09-06 the score was never written down (NEWS-Radar N-042), so a
    replay could only ever report a PRE-FLOOR set and call it the edition. This
    returns an empty map for those nights, and every caller must say so rather
    than quietly presenting a pre-floor result as a published one.
    """
    out: Dict[str, float] = {}
    for c in record.get("candidates", []):
        value = c.get("score")
        if isinstance(value, (int, float)):
            out[str(c["id"])] = float(value)
    return out


def to_candidates(record: Dict[str, Any]) -> List[Candidate]:
    return [
        Candidate(
            id=c["id"],
            title=c.get("title", ""),
            summary=c.get("summary", "") or "",
            source=c.get("source", "") or "",
            url=c.get("url", "") or "",
            theme=c.get("theme"),
        )
        for c in record.get("candidates", [])
    ]


def apply_overrides(config, assignments: List[str]) -> List[str]:
    """Apply `--set dotted.path=json` to the loaded config, in memory only.

    JSON first, bare string second, so `--set selection.consider=12` gives an
    integer and `--set selection.rank_mode=setwise` gives a string without
    needing quotes around it.
    """
    applied = []
    for assignment in assignments:
        if "=" not in assignment:
            raise SystemExit(f"--set needs key=value, got {assignment!r}")
        path, _, literal = assignment.partition("=")
        try:
            value = json.loads(literal)
        except json.JSONDecodeError:
            value = literal
        target = config
        parts = path.split(".")
        for part in parts[:-1]:
            target = getattr(target, part)
        if not hasattr(target, parts[-1]):
            raise SystemExit(f"--set: no such config key: {path}")
        before = getattr(target, parts[-1])
        setattr(target, parts[-1], value)
        applied.append(f"{path}: {before!r} -> {value!r}")
    return applied


def check_premise(record: Dict[str, Any], orchestrator) -> List[str]:
    """Warn where a replay's premise may not hold. Loud, never silent.

    A replay reads recorded candidate summaries, which the analysis pass wrote.
    Change that prompt and every replay result becomes invalid without looking
    any different, which is the failure mode this project would otherwise meet
    once and not recognise. The fixture does not yet carry the prompt's hash;
    the producer side of this guard is NEWS-Radar N-031, held for a night with
    no registered rubric. Until it lands the check cannot pass, so it says so
    rather than staying quiet and being mistaken for a pass.
    """
    warnings = []
    if "analysis_prompt_sha" not in record:
        warnings.append(
            "PREMISE UNCHECKED: this fixture carries no analysis-prompt hash, so "
            "nothing here can tell whether the summaries it holds were written by "
            "today's prompt. Treat a result as provisional (N-031)."
        )
    if record.get("version", 1) < 2:
        warnings.append(
            "VERSION 1 FIXTURE: the field only. There is nothing recorded to "
            "compare this replay against, so it can show what a configuration "
            "does and never whether it does better."
        )
    elif not record.get("defend"):
        warnings.append(
            "VERSION 2 FIXTURE WITH NO DECISIONS: this is the N-025 defect, "
            "fixed on 2026-09-06. Comparison against the night is unavailable."
        )
    return warnings


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument(
        "--set", dest="overrides", action="append", default=[],
        help="config override, e.g. selection.consider=12. Repeatable.",
    )
    parser.add_argument(
        "--with-gate", action="store_true",
        help="re-run the gate. Off by default: a fixture holds the gate's "
             "survivors, and the gate judges a batch of 40 in one request, so "
             "re-gating asks a different question and its numbers are not "
             "comparable to the night's.",
    )
    parser.add_argument(
        "--json", dest="json_out", type=Path,
        help="also write the decisions here, for comparison across runs",
    )
    args = parser.parse_args()

    if not args.fixture.exists():
        raise SystemExit(f"no such fixture: {args.fixture}")

    experiments = os.environ.get("ANTHROPIC_API_KEY_EXPERIMENTS")
    if experiments:
        os.environ["ANTHROPIC_API_KEY"] = experiments
        purse = "experiments"
    elif os.environ.get("ANTHROPIC_API_KEY"):
        purse = "DEFAULT KEY, which may be the one that pays for the nightly run"
    else:
        raise SystemExit(
            "no API key: set ANTHROPIC_API_KEY_EXPERIMENTS (preferred) or "
            "ANTHROPIC_API_KEY"
        )

    storage = StorageManager()
    config = storage.load_config()
    applied = apply_overrides(config, args.overrides)
    orchestrator = HorizonOrchestrator(config, storage)

    record = load_fixture(args.fixture)
    candidates = to_candidates(record)
    if not candidates:
        raise SystemExit("fixture holds no candidates")

    settings = orchestrator._selection_settings()

    print("=" * 72)
    print(f"REPLAY  {args.fixture.name}")
    print(f"  fixture version {record.get('version', 1)}, "
          f"{len(candidates)} candidates")
    print(f"  purse           {purse}")
    print(f"  config          data/config.json (the file production reads)")
    print(f"  rank_mode       {settings.rank_mode}   consider {settings.consider}   "
          f"max_publish {settings.max_publish}")
    print(f"  lead_sources    {settings.lead_sources}")
    print(f"  gate            {'RE-RUN' if args.with_gate else 'skipped (fixture holds survivors)'}")
    print(f"  min_score       {config.selection.min_score}")
    if applied:
        print("  OVERRIDES APPLIED:")
        for line in applied:
            print(f"    {line}")
    else:
        print("  overrides       none")
    for warning in check_premise(record, orchestrator):
        print(f"  ! {warning}")
    print("=" * 72)

    started = time.time()
    result = await run_selection(
        candidates,
        create_ai_client(config.ai),
        orchestrator._theme_questions(),
        settings,
        skip_gate=not args.with_gate,
    )

    # The score floor is the orchestrator's, not selection's, and a replay that
    # skipped it would report a different edition from the one the night would
    # have published. Fixtures before version 3 carry no scores and the floor
    # cannot run at all on them; saying so is better than quietly reporting a
    # pre-floor set as the edition (NEWS-Radar N-042, closed 2026-09-06).
    scores = scores_of(record)
    floored: List[str] = []
    if scores:
        floor = config.selection.min_score
        # An item with no score counts as UNKNOWN and is KEPT, which is the
        # production rule: a gap in scoring must not empty an edition.
        floored = [c.id for c in result.selected
                   if c.id in scores and scores[c.id] < floor]
        floor_note = (
            f"applied: {len(floored)} of {len(result.selected)} fell below "
            f"{floor}, leaving {len(result.selected) - len(floored)}. "
            f"{sum(1 for c in result.selected if c.id not in scores)} had no "
            "score and were kept, as production keeps them."
        )
    else:
        floor_note = (
            f"NOT APPLIED: this fixture predates version 3 and carries no "
            f"scores, so the {config.selection.min_score} floor cannot run "
            "here. The published set below is pre-floor and is an upper bound "
            "on what the night would have published."
        )

    by_id = {c.id: c for c in candidates}
    print()
    print(f"Selection: {len(candidates)} gated to {result.gate_kept}, "
          f"{len(result.ranked_ids)} ranked, {result.defend_rejected} rejected by "
          f"floor, {len(floored)} below the score floor, "
          f"{len(result.selected) - len(floored)} published")
    print(f"Score floor: {floor_note}")
    print(f"Elapsed: {time.time() - started:.1f}s")
    # A harness built to price a change must price itself. Added 2026-09-06
    # after the Editor asked what a day of these cost and the honest answer
    # was that eight replays had run without any of them recording a number.
    usage = get_usage_snapshot()
    print(f"Tokens: {usage.total_tokens:,} "
          f"({usage.total_input_tokens:,} in / {usage.total_output_tokens:,} "
          f"out) on the {purse} purse")

    # What the defender actually read, which is NOT ranked_ids[:consider]: that
    # list is pre-lead-filter and keeps every held lead. Printing it as "the
    # shortlist" showed three Google News items on a shortlist the defender
    # never saw them on, which is the same shape of defect this harness exists
    # to catch, found in this harness on its first run.
    print("\nShortlist, in rank order (what the defender read):")
    for position, item_id in enumerate([v.id for v in result.defend_verdicts], 1):
        candidate = by_id.get(item_id)
        source = candidate.source if candidate else "?"
        title = (candidate.title if candidate else item_id)[:64]
        print(f"  {position:>2}. [{source}] {title}")

    print("\nDefender verdicts:")
    for verdict in result.defend_verdicts:
        candidate = by_id.get(verdict.id)
        mark = "PUBLISH" if verdict.publish else "refuse "
        title = (candidate.title if candidate else verdict.id)[:52]
        print(f"  {mark} [{verdict.ai_nexus or '?'}] {title}")
        print(f"          {(verdict.why or '')[:150]}")

    if record.get("defend"):
        recorded = {d["id"]: d for d in record["defend"]}
        agreed = sum(
            1 for v in result.defend_verdicts
            if v.id in recorded and recorded[v.id]["publish"] == v.publish
        )
        overlap = sum(1 for v in result.defend_verdicts if v.id in recorded)
        print(f"\nAgainst the recorded night: {agreed} of {overlap} verdicts agree.")
        print("  A disagreement is not yet a finding. The model is not "
              "deterministic, so its own variance has to be measured on an "
              "unchanged configuration before any difference is read as an "
              "effect (PLAN-REPLAY D6).")

    if args.json_out:
        args.json_out.write_text(json.dumps({
            "fixture": args.fixture.name,
            "at": datetime.now().isoformat(timespec="seconds"),
            "overrides": applied,
            "gate_kept": result.gate_kept,
            "ranked": list(result.ranked_ids),
            # What the defender read, NOT ranked_ids[:consider]. The same wrong
            # expression was written in three places (the fixture, this report's
            # display, and here) and fixing two of them was how the third
            # survived long enough to be found separately.
            "shortlist": [v.id for v in result.defend_verdicts],
            "defend": [
                {"id": v.id, "publish": v.publish, "why": v.why,
                 "ai_nexus": v.ai_nexus}
                for v in result.defend_verdicts
            ],
            "published": [c.id for c in result.selected],
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nDecisions written to {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
