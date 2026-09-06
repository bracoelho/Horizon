#!/usr/bin/env python3
"""Run a proposed selection change against recorded nights before it ships.

Stage S-D of NEWS-Radar's PLAN-REPLAY, and the reason the whole harness exists.
On 2026-09-06 a one-word mismatch in a filter's configuration cost a full night
of trial: the change shipped, a rubric was registered, the night ran, and the
morning's answer was "the trial did not run." This would have said so in a
minute, from a recording, for about a dollar.

It does three things a single replay cannot.

1. It runs the SAME fixture twice, once as production is configured today and
   once with the proposed change, so the difference is the change and not the
   night.
2. It applies a NOISE FLOOR measured rather than assumed (N-033, 2026-09-06:
   three replays of one unchanged configuration shared 9 of 10 shortlist items
   and agreed 9 of 9 on the defender's verdicts). A shortlist difference of one
   item is what this pipeline does when nothing changes at all, so the gate
   reports it as indistinguishable from noise rather than as an effect.
3. It takes the expectations as arguments, so a rubric becomes something a
   program checks instead of something a morning remembers.

    uv run python scripts/preflight.py \
        --set selection.lead_sources='["Google News","google_news"]' \
        --expect leads_held '>' 10 \
        --fixture ../NEWS-Radar/fixtures/rank_fixture-20260905-2044.json

Baselines are cached by fixture and configuration, so re-running a gate after
editing the proposal pays for the proposed side only.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ai.client import create_ai_client  # noqa: E402
from src.orchestrator import HorizonOrchestrator  # noqa: E402
from src.selection import select as run_selection  # noqa: E402
from src.storage.manager import StorageManager  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay import apply_overrides, load_fixture, to_candidates  # noqa: E402

# Measured, not assumed. N-033: three replays, unchanged configuration, one
# fixture. Raise this only with a bigger measurement behind it, and say which.
NOISE_SHORTLIST_ITEMS = 1
NOISE_NOTE = ("N-033, 2026-09-06: three replays of an unchanged configuration "
              "shared 9 of 10 shortlist items and agreed 9 of 9 on verdicts")

CACHE = Path(".preflight-cache")


def _key(fixture: Path, overrides: List[str]) -> str:
    payload = fixture.name + "|" + "|".join(sorted(overrides))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


async def one_side(fixture: Path, overrides: List[str], *, use_cache: bool
                   ) -> Dict[str, Any]:
    """Run selection over one fixture under one configuration."""
    CACHE.mkdir(exist_ok=True)
    cached = CACHE / f"{_key(fixture, overrides)}.json"
    if use_cache and cached.exists():
        out = json.loads(cached.read_text(encoding="utf-8"))
        out["cached"] = True
        return out

    storage = StorageManager()
    config = storage.load_config()
    apply_overrides(config, overrides)
    orchestrator = HorizonOrchestrator(config, storage)
    record = load_fixture(fixture)
    candidates = to_candidates(record)
    settings = orchestrator._selection_settings()

    result = await run_selection(
        candidates,
        create_ai_client(config.ai),
        orchestrator._theme_questions(),
        settings,
        skip_gate=True,
    )
    shortlist = [v.id for v in result.defend_verdicts]

    # Two different lead counts, and conflating them is easy. `leads_total` is
    # every lead anywhere in the ranked list, which is what the run's log line
    # prints. `leads_above_cut` is the number that would otherwise have taken a
    # shortlist slot, which is the only one that changes an edition. The gate
    # grades on the second and reports both. The first draft of this function
    # derived it by subtracting list lengths, which was unreadable and
    # therefore untrustworthy; both are now counted directly.
    needles = [n.lower() for n in settings.lead_sources]
    source_of = {c.id: (c.source or "").lower() for c in candidates}
    is_lead = {i: any(n in source_of.get(i, "") for n in needles)
               for i in result.ranked_ids}
    leads_total = sum(1 for i in result.ranked_ids if is_lead[i])
    if shortlist:
        position = {i: k for k, i in enumerate(result.ranked_ids)}
        last = max(position[i] for i in shortlist if i in position)
        leads_above_cut = (last + 1) - len(shortlist)
    else:
        leads_above_cut = 0

    out = {
        "fixture": fixture.name,
        "overrides": overrides,
        "candidates": len(candidates),
        "ranked": len(result.ranked_ids),
        "leads_total": leads_total,
        "leads_held": leads_above_cut,
        "shortlist": shortlist,
        "refused": sum(1 for v in result.defend_verdicts if not v.publish),
        "published": [c.id for c in result.selected],
        "cached": False,
    }
    cached.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    return out


def compare(base: Dict[str, Any], prop: Dict[str, Any]) -> Dict[str, Any]:
    b, p = set(base["shortlist"]), set(prop["shortlist"])
    changed = len(b ^ p) // 2 if len(b) == len(p) else len(b ^ p)
    return {
        "shortlist_changed": changed,
        "within_noise": changed <= NOISE_SHORTLIST_ITEMS,
        "leads_held": (base["leads_held"], prop["leads_held"]),
        "refused": (base["refused"], prop["refused"]),
        "published": (len(base["published"]), len(prop["published"])),
        "gained": sorted(p - b),
        "lost": sorted(b - p),
    }


def check_expectations(cmp: Dict[str, Any], prop: Dict[str, Any],
                       expectations: List[Tuple[str, str, float]]
                       ) -> List[Tuple[str, bool, str]]:
    """Grade the rubric the change was proposed under. No expectation, no pass."""
    ops = {">": lambda a, b: a > b, "<": lambda a, b: a < b,
           ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
           "==": lambda a, b: a == b, "!=": lambda a, b: a != b}
    results = []
    for key, op, want in expectations:
        if key == "shortlist_changed":
            actual: Optional[float] = cmp["shortlist_changed"]
        elif key in ("leads_held", "refused"):
            actual = cmp[key][1]
        elif key == "published":
            actual = cmp["published"][1]
        else:
            results.append((f"{key} {op} {want}", False,
                            f"unknown measure {key!r}"))
            continue
        ok = ops[op](actual, want)
        results.append((f"{key} {op} {want}", ok, f"actual {actual}"))
    return results


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", dest="overrides", action="append", default=[],
                        required=True, help="the proposed change. Repeatable.")
    parser.add_argument("--fixture", dest="fixtures", action="append",
                        type=Path, default=[], required=True,
                        help="a recorded night. Repeatable; three spanning "
                             "different shapes beats the three most recent.")
    parser.add_argument("--expect", nargs=3, action="append", default=[],
                        metavar=("MEASURE", "OP", "VALUE"),
                        help="e.g. --expect leads_held '>' 10")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    key = os.environ.get("ANTHROPIC_API_KEY_EXPERIMENTS")
    if not key:
        raise SystemExit("set ANTHROPIC_API_KEY_EXPERIMENTS: a pre-flight "
                         "never runs on the key that pays for the nightly run")
    os.environ["ANTHROPIC_API_KEY"] = key

    expectations = [(m, o, float(v)) for m, o, v in args.expect]

    print("=" * 72)
    print("PRE-FLIGHT")
    print(f"  proposed        {args.overrides}")
    print(f"  fixtures        {len(args.fixtures)}")
    print(f"  noise floor     {NOISE_SHORTLIST_ITEMS} shortlist item")
    print(f"                  ({NOISE_NOTE})")
    if not expectations:
        print("  ! NO EXPECTATIONS GIVEN. This will report what changed and "
              "cannot say whether that is what you predicted.")
    print("=" * 72)

    verdicts = []
    for fixture in args.fixtures:
        base = await one_side(fixture, [], use_cache=not args.no_cache)
        prop = await one_side(fixture, args.overrides,
                              use_cache=not args.no_cache)
        cmp = compare(base, prop)
        graded = check_expectations(cmp, prop, expectations)
        verdicts.append((fixture, cmp, graded))

        tag = " (baseline cached)" if base.get("cached") else ""
        print(f"\n{fixture.name}{tag}")
        print(f"  leads above cut   {cmp['leads_held'][0]} -> "
              f"{cmp['leads_held'][1]}   (all leads ranked: "
              f"{base['leads_total']} -> {prop['leads_total']})")
        print(f"  refused           {cmp['refused'][0]} -> {cmp['refused'][1]}")
        print(f"  published         {cmp['published'][0]} -> "
              f"{cmp['published'][1]}")
        print(f"  shortlist changed {cmp['shortlist_changed']} item(s)"
              + ("   WITHIN NOISE: this is what the pipeline does when nothing "
                 "changes" if cmp["within_noise"] else ""))
        for item_id in cmp["lost"][:4]:
            print(f"    out  {item_id[:64]}")
        for item_id in cmp["gained"][:4]:
            print(f"    in   {item_id[:64]}")
        for text, ok, detail in graded:
            print(f"  [{'PASS' if ok else 'FAIL'}] {text}   ({detail})")

    failed = [(f, g) for f, _, gs in verdicts for g in gs if not g[1]]
    noisy = [f for f, c, _ in verdicts if c["within_noise"]]

    print("\n" + "=" * 72)
    if expectations and failed:
        print(f"REFUSED: {len(failed)} expectation(s) failed. The change does "
              "not do on a recorded night what it was proposed to do.")
        return 1
    if len(noisy) == len(verdicts):
        print("REFUSED: every fixture's difference is within the measured "
              "noise floor. This change is indistinguishable from running the "
              "same configuration twice, so a live night cannot test it "
              "either.")
        return 1
    if not expectations:
        print("REPORTED, NOT GRADED: no expectations were given, so nothing "
              "here passed or failed. Write the prediction first.")
        return 0
    print("CLEARED: every expectation held on every fixture, and at least one "
          "difference is larger than noise.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
