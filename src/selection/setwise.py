"""Setwise ranking: many small closed questions instead of one fragile big one.

PLAN-S1's challenger to the chunked listwise ranker. Each call shows the
model `set_size` candidates and asks for the id of the most important,
through a schema whose single field is an enum of that set's exact ids (the
owner's mechanism: a wrong id is unsampleable, not merely detectable). A
tournament with replacement extracts the top `need` candidates: build the
bracket once, then after each extraction replay only the winner's path with
substitutes, so an extraction costs about log_k(n) calls.

Failure costs one comparison by construction: a pick that fails validation
retries once, then falls back to the group's first candidate in stable
order, logged. The total form (every pick fell back) is a collapse the
health check reddens, matching the listwise rule.
"""

from __future__ import annotations

import json
import logging
from typing import Awaitable, Callable, Dict, List, Optional, Sequence

from .contract import Candidate
from .prompts import setwise_schema, setwise_system, setwise_user

logger = logging.getLogger(__name__)

# complete(system, user, schema) -> raw model text
StructuredCompleter = Callable[[str, str, Dict[str, object]], Awaitable[str]]

DEFAULT_SET_SIZE = 7
EXTRACTION_MARGIN = 5  # defend reads `consider`; margin covers its rejections


class PickStats:
    """Counts the tournament's own health, for the funnel and metrics row."""

    def __init__(self) -> None:
        self.picks = 0
        self.retried = 0
        self.fallbacks = 0


def _entries(group: Sequence[Candidate]) -> str:
    return json.dumps(
        [
            {
                "id": c.id,
                "title": c.title,
                "source": f"{c.source}" + (f" · {c.theme}" if c.theme else ""),
                "summary": c.brief(300),
            }
            for c in group
        ]
    )


def _parse_best(text: str, valid: Dict[str, Candidate]) -> Optional[Candidate]:
    """The enum makes a wrong id unsampleable; this validation is the belt to
    those braces, catching refusals, truncation, or a provider that ignored
    the enum."""
    try:
        best = json.loads(text).get("best")
    except (json.JSONDecodeError, AttributeError):
        return None
    return valid.get(best)


async def _pick(
    complete: StructuredCompleter,
    group: Sequence[Candidate],
    stats: PickStats,
) -> Candidate:
    """Best of one small group, with one retry and a deterministic fallback."""
    if len(group) == 1:
        return group[0]
    valid = {c.id: c for c in group}
    schema = setwise_schema(list(valid))
    user = setwise_user(_entries(group))
    for attempt in (1, 2):
        stats.picks += 1
        try:
            text = await complete(setwise_system(), user, schema)
        except Exception as exc:
            logger.error("Setwise call failed for a set of %d: %s", len(group), exc)
            text = ""
        candidate = _parse_best(text, valid)
        if candidate is not None:
            return candidate
        if attempt == 1:
            stats.retried += 1
            logger.warning(
                "Setwise pick unreadable for a set of %d (attempt 1); retrying. "
                "First 120 chars: %r",
                len(group), text[:120],
            )
    stats.fallbacks += 1
    logger.warning(
        "Setwise pick failed twice for a set of %d; falling back to the "
        "group's first candidate", len(group),
    )
    return group[0]


class _Tournament:
    """Leaf groups, each with a current winner. The champion is the best of
    the winners; extracting it re-picks only its own group. With a consistent
    judge this yields exact selection order (each winner is its group's best,
    so the best of winners is the global best), and a failed pick's damage is
    confined to one group by construction."""

    def __init__(self, candidates: Sequence[Candidate], set_size: int) -> None:
        self.set_size = max(2, set_size)
        pool = list(candidates)
        self.groups: List[List[Candidate]] = [
            pool[i:i + self.set_size] for i in range(0, len(pool), self.set_size)
        ]
        self.winners: List[Optional[Candidate]] = [None] * len(self.groups)

    async def build(self, complete: StructuredCompleter, stats: PickStats) -> None:
        for j, group in enumerate(self.groups):
            self.winners[j] = await _pick(complete, group, stats)

    async def _best_of_winners(
        self, complete: StructuredCompleter, stats: PickStats
    ) -> Optional[Candidate]:
        alive = [w for w in self.winners if w is not None]
        if not alive:
            return None
        # Reduce in rounds of set_size until one remains.
        while len(alive) > 1:
            nxt = []
            for i in range(0, len(alive), self.set_size):
                nxt.append(await _pick(complete, alive[i:i + self.set_size], stats))
            alive = nxt
        return alive[0]

    async def extract(
        self, complete: StructuredCompleter, stats: PickStats
    ) -> Optional[Candidate]:
        champ = await self._best_of_winners(complete, stats)
        if champ is None:
            return None
        for j, group in enumerate(self.groups):
            if any(c.id == champ.id for c in group):
                remaining = [c for c in group if c.id != champ.id]
                self.groups[j] = remaining
                self.winners[j] = (
                    await _pick(complete, remaining, stats) if remaining else None
                )
                break
        return champ


async def setwise_rank(
    candidates: Sequence[Candidate],
    complete: StructuredCompleter,
    *,
    set_size: int = DEFAULT_SET_SIZE,
    need: Optional[int] = None,
    stats: Optional[PickStats] = None,
) -> List[Candidate]:
    """Return candidates with the top `need` exactly ordered, remainder in
    stable original order after them (so downstream counts still close)."""
    items = list(candidates)
    if len(items) <= 1:
        return items
    stats = stats if stats is not None else PickStats()
    want = min(len(items), need if need is not None else len(items))

    bracket = _Tournament(items, set_size)
    await bracket.build(complete, stats)

    ordered: List[Candidate] = []
    while len(ordered) < want:
        champ = await bracket.extract(complete, stats)
        if champ is None:
            break
        ordered.append(champ)

    chosen = {c.id for c in ordered}
    remainder = [c for c in items if c.id not in chosen]
    return ordered + remainder
