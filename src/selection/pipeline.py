"""Compose gate, rank and defend into one selection run."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
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
    # Sources whose items are a lead and never a candidate: they carry a
    # headline and one sentence, never an article, so nothing about them can
    # be defended. Matched as a case-insensitive substring of the item's
    # source name. Empty means the old behaviour. See NEWS-Radar BACKLOG #66a.
    lead_sources: List[str] = field(default_factory=list)


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
        # Printed to stdout, not logged: the CLI's default level is WARNING,
        # so an INFO line never reaches CI's log and the health check recorded
        # setwise: null on the mode's first live night (2026-09-02). The
        # funnel's own numbers survive for the same reason: they print.
        print(
            f"Setwise: {pick_stats.picks} picks, {pick_stats.retried} "
            f"retried, {pick_stats.fallbacks} fell back"
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

    # --- leads are not candidates -------------------------------------------
    # A source that publishes a headline and one sentence can tell us a story
    # exists and can never support a published claim: three weeks of evidence
    # (the Fable 5.1 release detected four times and published zero, and the
    # 2026-09-04 refusal of an acquisition whose whole body was one line) say
    # the defender is being asked to judge from a headline. Dropping them here
    # rather than at fetch keeps them in the gate's and the ranker's view, so
    # the day is still informed by them, and frees the shortlist slot they
    # cannot use. Printed, not logged, for the reason the setwise line gives.
    # The funnel must still account for every item, so the ranked count keeps
    # the full list: a lead held back sits below the shortlist cut, which is
    # true, and the printed line names how many and from where.
    ranked_all = list(ranked)
    if settings.lead_sources:
        needles = [s.lower() for s in settings.lead_sources]
        leads = [
            c for c in ranked
            if any(n in (c.source or "").lower() for n in needles)
        ]
        if leads:
            ranked = [c for c in ranked if c not in leads]
            print(
                f"Leads held back from the shortlist: {len(leads)} "
                f"({', '.join(sorted({c.source for c in leads}))})"
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
        ranked_ids=[c.id for c in ranked_all],
        gate_kept=len(kept),
        gate_dropped=len(items) - len(kept),
        defend_rejected=rejected,
    )
