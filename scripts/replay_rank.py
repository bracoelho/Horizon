#!/usr/bin/env python3
"""Replay a recorded rank fixture through the ranker, repeatedly, and report.

The attribution instrument from PLAN-S1: same input, any ranker mode, any
model, repeated, so a change to ranking is measured instead of believed.
Runs wherever ANTHROPIC_API_KEY exists; the Replay Rank workflow runs it in
CI, where the key already lives.

Reports, per repeat: the head of the order (top `consider`), fallback and
omission counts parsed from the ranker's own warnings, and token cost.
Across repeats: pairwise agreement of the heads (how stable is the order
when nothing changed but sampling), which is the baseline any challenger
has to beat.
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import AIConfig  # noqa: E402
from src.selection.contract import Candidate  # noqa: E402
from src.selection import rank as rank_mod  # noqa: E402
from src.selection.prompts import RANK_SCHEMA  # noqa: E402


class WarningCounter(logging.Handler):
    """Counts the ranker's own warnings instead of re-deriving failure."""

    def __init__(self) -> None:
        super().__init__()
        self.omitted_total = 0
        self.chunks_failed = 0

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        if "omitted" in msg:
            self.chunks_failed += 1
        if "could not read" in msg:
            self.omitted_total += 1


def load_fixture(path: Path) -> list[Candidate]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [
        Candidate(
            id=r["id"], title=r.get("title", ""), summary=r.get("summary", ""),
            source=r.get("source", ""), url=r.get("url", ""),
            theme=r.get("theme"),
        )
        for r in rows
    ]


def head_agreement(heads: list[list[str]]) -> float:
    """Mean pairwise overlap of the heads, 0..1. Order-insensitive on
    membership, which is what the defend stage actually consumes."""
    if len(heads) < 2:
        return 1.0
    scores = []
    for a, b in itertools.combinations(heads, 2):
        if not a or not b:
            scores.append(0.0)
            continue
        k = min(len(a), len(b))
        scores.append(len(set(a[:k]) & set(b[:k])) / k)
    return sum(scores) / len(scores)


async def one_pass(candidates, client, args, counter):
    # Replicate the live pipeline's call exactly: model override, the rank
    # schema, and the effort setting. The first baseline ran the bare
    # completer and collapsed every chunk, which measured the harness gap
    # instead of the ranker; attribution demands the identical call.
    async def rank_complete(system: str, user: str) -> str:
        return await client.complete(
            system, user,
            model=args.model or "claude-sonnet-5",
            schema=RANK_SCHEMA,
            effort=args.effort,
        )

    started = time.monotonic()
    if args.mode == "setwise":
        from src.selection.setwise import PickStats, setwise_rank

        async def structured(system, user, schema):
            return await client.complete(
                system, user,
                model=args.model or "claude-sonnet-5",
                schema=schema,
                effort=args.effort,
            )

        stats = PickStats()
        ordered = await setwise_rank(
            candidates, structured, set_size=7,
            need=args.consider + 5, stats=stats,
        )
        print(f"  setwise: {stats.picks} picks, {stats.retried} retried, "
              f"{stats.fallbacks} fell back")
        counter.chunks_failed += stats.fallbacks
    else:
        ordered = await rank_mod.rank(
            candidates,
            rank_complete,
            chunk_size=args.chunk_size,
            carry=args.carry,
        )
    return ordered, time.monotonic() - started


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", type=Path, required=True)
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--consider", type=int, default=10)
    ap.add_argument("--chunk-size", type=int, default=25)
    ap.add_argument("--carry", type=int, default=10)
    ap.add_argument("--mode", default="listwise",
                    choices=["listwise", "setwise"],
                    help="which ranker to replay")
    ap.add_argument("--effort", default="high",
                    help="rank effort, matching selection.rank_effort")
    ap.add_argument("--model", default=None,
                    help="override the rank model (BACKLOG #45 experiments)")
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set; a replay needs the live model.")
        return 2

    candidates = load_fixture(args.fixture)
    print(f"Fixture: {args.fixture.name}, {len(candidates)} candidates")

    from src.ai.client import create_ai_client
    config = AIConfig(provider="anthropic",
                      model=args.model or "claude-sonnet-5",
                      api_key_env="ANTHROPIC_API_KEY",
                      temperature=1.0)
    client = create_ai_client(config)

    # A stream handler as well as the counter: the first baseline swallowed
    # every warning into the counter, so the returned-ids diagnosis never
    # reached the CI log.
    logging.basicConfig(level=logging.WARNING,
                        format="%(levelname)s %(message)s")
    counter = WarningCounter()
    logging.getLogger().addHandler(counter)

    heads: list[list[str]] = []
    for n in range(1, args.repeat + 1):
        before_failed = counter.chunks_failed
        ordered, seconds = await one_pass(candidates, client, args, counter)
        head = [c.id for c in ordered[: args.consider]]
        heads.append(head)
        failed = counter.chunks_failed - before_failed
        print(f"pass {n}: {seconds:5.1f}s, chunks-failed={failed}, "
              f"head={[h.split(':')[-1][:8] for h in head]}")

    print(f"\nhead agreement across {args.repeat} passes: "
          f"{head_agreement(heads):.2f}")
    print(f"total failed chunks: {counter.chunks_failed} "
          f"(the incumbent's number to beat is 0)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
