"""Compose gate, rank and defend into one selection run."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, List, Optional, Protocol, Sequence

from .contract import BatchUnit, Candidate, SelectionResult
from .defend import defend as defend_pass
from .gate import apply as apply_gate
from .gate import build_requests as build_gate_requests
from .gate import collect as collect_gate
from .prompts import DEFEND_SCHEMA, GATE_SCHEMA, RANK_SCHEMA
from .rank import rank as rank_pass
from .setwise import PickStats, setwise_rank

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SelectionSettings:
    """Per-stage models and sizes.

    Models differ per stage on purpose: routing several hundred items is a cheap
    task, ordering a shortlist is not, and the floor reads full documents.
    """

    gate_model: Optional[str] = None
    rank_model: Optional[str] = None
    defend_model: Optional[str] = None
    gate_effort: str = "low"
    rank_effort: str = "high"
    defend_effort: str = "high"
    gate_batch_size: int = 40
    rank_chunk_size: int = 25
    rank_carry: int = 10
    rank_mode: str = "listwise"
    rank_set_size: int = 7
    consider: int = 10
    max_publish: int = 6
    defend_concurrency: int = 4
    use_batch: bool = True


class SelectionClient(Protocol):
    """The narrow slice of an AI client that selection needs."""

    async def complete(
        self, system: str, user: str, *, model=None, schema=None, effort=None
    ) -> str: ...

    async def complete_batch(self, requests, **kwargs) -> Dict[str, str]: ...


async def select(
    candidates: Sequence[Candidate],
    client: "SelectionClient",
    themes: Dict[str, str],
    settings: Optional[SelectionSettings] = None,
    after_gate: Optional[
        Callable[[List[Candidate]], Awaitable[List[Candidate]]]
    ] = None,
) -> SelectionResult:
    """Run the full selection and return what survived, with the counts.

    `after_gate` runs once, on the items the gate kept, and returns them
    possibly enriched. It exists so the engine can do expensive per-item work
    on the survivors rather than on everything: scoring every fetched item
    before the cheap gate filtered them was costing roughly three times what
    it needed to. The hook is a callback rather than an import so this module
    still knows nothing about the pipeline around it.
    """
    settings = settings or SelectionSettings()
    items = list(candidates)
    if not items:
        return SelectionResult()

    # --- pass one: gate -----------------------------------------------------
    requests = build_gate_requests(
        items, themes, batch_size=settings.gate_batch_size
    )
    responses: Dict[str, str] = {}

    if settings.use_batch and hasattr(client, "complete_batch"):
        responses = await client.complete_batch(
            [
                BatchUnit(
                    custom_id=custom_id,
                    system=system,
                    user=user,
                    schema=GATE_SCHEMA,
                    effort=settings.gate_effort,
                    model=settings.gate_model,
                )
                for custom_id, system, user in requests
            ]
        )
    else:
        for custom_id, system, user in requests:
            responses[custom_id] = await client.complete(
                system,
                user,
                model=settings.gate_model,
                schema=GATE_SCHEMA,
                effort=settings.gate_effort,
            )

    verdicts = collect_gate(responses, items, themes)
    kept = apply_gate(items, verdicts)
    logger.info("Gate kept %d of %d items", len(kept), len(items))

    if not kept:
        return SelectionResult(gate_kept=0, gate_dropped=len(items))

    if after_gate is not None:
        refreshed = await after_gate(kept)
        # Defensive: a hook that loses or invents items would corrupt the
        # counts reported downstream, so fall back rather than trust it.
        if refreshed and len(refreshed) == len(kept):
            kept = refreshed
        else:
            logger.warning(
                "after_gate returned %s items for %d; keeping the originals",
                len(refreshed) if refreshed else 0,
                len(kept),
            )

    # --- pass two: rank -----------------------------------------------------
    async def rank_complete(system: str, user: str) -> str:
        return await client.complete(
            system,
            user,
            model=settings.rank_model,
            schema=RANK_SCHEMA,
            effort=settings.rank_effort,
        )

    if settings.rank_mode == "setwise":
        # S1: per-call schema (an enum of the set's ids) needs a structured
        # completer; the listwise path keeps its fixed schema untouched.
        async def setwise_complete(system: str, user: str, schema) -> str:
            return await client.complete(
                system,
                user,
                model=settings.rank_model,
                schema=schema,
                effort=settings.rank_effort,
            )

        pick_stats = PickStats()
        ranked = await setwise_rank(
            kept,
            setwise_complete,
            set_size=settings.rank_set_size,
            need=settings.consider + 5,
            stats=pick_stats,
        )
        logger.info(
            "Setwise: %d picks, %d retried, %d fell back",
            pick_stats.picks, pick_stats.retried, pick_stats.fallbacks,
        )
        if pick_stats.fallbacks and pick_stats.fallbacks * 2 >= pick_stats.picks:
            logger.warning(
                "Setwise collapse: %d of %d picks fell back",
                pick_stats.fallbacks, pick_stats.picks,
            )
    else:
        ranked = await rank_pass(
            kept,
            rank_complete,
            chunk_size=settings.rank_chunk_size,
            carry=settings.rank_carry,
        )

    # --- pass three: defend -------------------------------------------------
    async def defend_complete(system: str, user: str) -> str:
        return await client.complete(
            system,
            user,
            model=settings.defend_model,
            schema=DEFEND_SCHEMA,
            effort=settings.defend_effort,
        )

    selected, defend_verdicts = await defend_pass(
        ranked,
        defend_complete,
        themes,
        consider=settings.consider,
        max_publish=settings.max_publish,
        concurrency=settings.defend_concurrency,
    )
    rejected = sum(1 for v in defend_verdicts if not v.publish)
    # Instrument the strictest judge (2026-09-01): defend cut 7 of 10 on the
    # first clean night and nothing recorded why, making "strict" and
    # "right" indistinguishable. One line per refusal, reason included.
    for v in defend_verdicts:
        if not v.publish:
            logger.info(
                "Defend refused %s: %s", v.id,
                (v.why or "no reason returned")[:160],
            )
    logger.info(
        "Ranked %d, considered %d, published %d",
        len(ranked),
        len(defend_verdicts),
        len(selected),
    )

    return SelectionResult(
        selected=selected,
        ranked_ids=[c.id for c in ranked],
        gate_kept=len(kept),
        gate_dropped=len(items) - len(kept),
        defend_rejected=rejected,
    )
