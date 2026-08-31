"""Pass two: order the survivors.

The only stage that sees more than one item at a time, which is what makes it the
only stage able to answer "which of these matters most". Large sets are ranked in
chunks and the winners run off against each other, so the comparison stays inside
a context the model can actually hold.
"""

from __future__ import annotations

import json
import logging
from typing import Awaitable, Callable, Dict, List, Sequence

from .contract import Candidate
from .prompts import RANK_SCHEMA, format_entries, rank_system, rank_user

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 25
DEFAULT_CARRY = 10

Completer = Callable[[str, str], Awaitable[str]]


def _parse_order(text: str) -> List[str]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return []
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return []
    order = payload.get("order") if isinstance(payload, dict) else None
    if not isinstance(order, list):
        return []
    return [str(value) for value in order]


def reconcile(order: Sequence[str], group: Sequence[Candidate]) -> List[Candidate]:
    """Apply a returned order to a group, defensively.

    A model can drop an id, invent one, or repeat one. Unknown ids are discarded
    and anything it failed to mention is appended in its original position, so the
    stage degrades to "unranked" rather than to "silently lost items".
    """
    by_id = {c.id: c for c in group}
    # The model strips namespace prefixes from long ids: replay 33343845452
    # caught it returning `f686992522aa0a24` for
    # `google_news:article:f686992522aa0a24`, deterministically, every pass,
    # which is what collapsed the Google News-heavy chunk on two consecutive
    # live nights while parsing as perfectly valid JSON. A trailing segment
    # that names exactly one candidate is that candidate; an ambiguous one
    # stays unmatched rather than guessed.
    by_suffix: Dict[str, Candidate] = {}
    for c in group:
        tail = c.id.rsplit(":", 1)[-1]
        by_suffix[tail] = None if tail in by_suffix else c
    rescued = 0
    ranked: List[Candidate] = []
    seen = set()
    for item_id in order:
        candidate = by_id.get(item_id)
        if candidate is None:
            candidate = by_suffix.get(item_id)
            if candidate is not None:
                rescued += 1
        if candidate is None or candidate.id in seen:
            continue
        seen.add(candidate.id)
        ranked.append(candidate)
    if rescued:
        logger.info(
            "Rescued %d prefix-stripped id(s) by unambiguous suffix", rescued
        )

    missing = [c for c in group if c.id not in seen]  # seen holds full ids
    if missing:
        logger.warning(
            "Ranker omitted %d of %d ids; appending them unranked",
            len(missing),
            len(group),
        )
        # Two consecutive live runs failed with every id unmatched on the
        # remainder chunk, and the response parsed as valid JSON, so the
        # raw-on-parse-failure log never fired and nobody has ever seen what
        # the model actually returns in this state. Show the evidence: what
        # it sent against what was asked.
        if not ranked:
            logger.warning(
                "Ranker returned %d id(s), none matching. Returned sample: %r; expected sample: %r",
                len(order),
                list(order)[:5],
                [c.id for c in group[:3]],
            )
    return ranked + missing


def _entries(group: Sequence[Candidate]) -> str:
    return format_entries(
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


async def _rank_call(complete: Completer, group: Sequence[Candidate]) -> str:
    """Run one ranking call, logging a failure rather than swallowing it.

    An exception here used to surface only as "omitted N of N ids", which reads
    like a model that ignored instructions rather than a call that never
    returned. On 2026-08-20 two whole chunks failed this way and the log gave no
    reason for either.
    """
    try:
        return await complete(rank_system(), rank_user(_entries(group)))
    except Exception as exc:
        logger.error(
            "Rank call failed for a chunk of %d, leaving it unranked: %s",
            len(group),
            exc,
        )
        return ""


# Enough of the response to tell malformed JSON from a truncation from prose,
# without pasting a whole rejected answer into the run log.
RAW_LOG_CHARS = 400


async def _order_for(
    complete: Completer, group: Sequence[Candidate]
) -> List[str]:
    """Rank one group, retrying once when the response cannot be read.

    A call that fails and a response that cannot be parsed are different
    problems and used to look identical. `_parse_order` discards the text it
    could not read, so a parse failure surfaced only as "omitted N of N ids",
    which gave no way to tell malformed JSON from a truncated response from a
    model that answered in prose. On 2026-08-27 and 2026-08-29 whole chunks
    failed this way and neither log said why.

    The retry is here because a chunk that cannot be read otherwise promotes
    its first `carry` items on arbitrary order, and those go on to displace
    genuinely ranked items in the runoff.
    """
    for attempt in (1, 2):
        text = await _rank_call(complete, group)
        if not text:
            continue  # _rank_call already logged the exception
        order = _parse_order(text)
        if order:
            if attempt > 1:
                logger.info(
                    "Ranker read the response on retry for a chunk of %d",
                    len(group),
                )
            return order
        logger.warning(
            "Ranker could not read the response for a chunk of %d "
            "(attempt %d of 2). First %d chars: %r",
            len(group),
            attempt,
            RAW_LOG_CHARS,
            text[:RAW_LOG_CHARS],
        )
    return []


async def rank(
    candidates: Sequence[Candidate],
    complete: Completer,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    carry: int = DEFAULT_CARRY,
    _depth: int = 0,
) -> List[Candidate]:
    """Return candidates ordered most important first."""
    items = list(candidates)
    if len(items) <= 1:
        return items

    if len(items) <= chunk_size:
        return reconcile(await _order_for(complete, items), items)

    # Too many to compare at once: rank in chunks, then run the winners off.
    groups = [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]
    winners: List[Candidate] = []
    for group in groups:
        order = await _order_for(complete, group)
        winners.extend(reconcile(order, group)[:carry])

    # Guard against a runoff that cannot shrink, which would recurse forever.
    if len(winners) >= len(items) or _depth >= 3:
        return winners or items

    return await rank(
        winners, complete, chunk_size=chunk_size, carry=carry, _depth=_depth + 1
    )
