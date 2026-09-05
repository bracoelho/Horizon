"""Pass one: keep or drop, per item, cheaply.

Runs on the cheapest model through the Batch API. Emits no score, because a
number produced from a single item read in isolation carries no comparative
information and every later stage would treat it as if it did.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional, Protocol, Sequence

from .contract import Candidate, GateVerdict
from .prompts import GATE_SCHEMA, format_entries, gate_system, gate_user

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 40


class BatchRunner(Protocol):
    """What the gate needs from a client, and nothing more."""

    async def run(self, prompts: Sequence[tuple[str, str, str]]) -> Dict[str, str]:
        """Map (custom_id, system, user) triples to their text responses."""


def _parse(text: str) -> List[dict]:
    """Pull the verdict list out of a response, tolerating stray prose."""
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
    verdicts = payload.get("verdicts") if isinstance(payload, dict) else None
    return verdicts if isinstance(verdicts, list) else []


def chunk(items: Sequence[Candidate], size: int) -> List[List[Candidate]]:
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def build_requests(
    candidates: Sequence[Candidate],
    themes: Dict[str, str],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> List[tuple[str, str, str]]:
    """Build (custom_id, system, user) triples, one per batch of candidates."""
    system = gate_system(themes)
    requests = []
    for index, group in enumerate(chunk(candidates, batch_size)):
        entries = format_entries(
            [
                {
                    "id": c.id,
                    "title": c.title,
                    "source": c.source,
                    "summary": c.brief(),
                }
                for c in group
            ]
        )
        requests.append((f"gate-{index}", system, gate_user(entries)))
    return requests


def collect(
    responses: Dict[str, str],
    candidates: Sequence[Candidate],
    themes: Dict[str, str],
) -> List[GateVerdict]:
    """Turn raw responses into verdicts, one per candidate.

    An item the gate never ruled on is kept rather than dropped. A dropped item is
    invisible for the rest of the run, so an unparsed response must not silently
    delete work; the ranker will discard it cheaply if it does not belong.
    """
    known = {c.id for c in candidates}
    seen: Dict[str, GateVerdict] = {}
    # Why a verdict goes missing, counted rather than guessed (NEWS-Radar
    # BACKLOG #82). The no-verdict share ran 18, 22, 37 and 42 percent across
    # four runs and the log said only how many, never why. The counts below
    # separate the three causes that need different fixes: a response that
    # cannot be parsed at all loses its whole batch, a response that parses
    # while omitting ids loses items one by one, and an id that comes back
    # unrecognised means the model is rewriting identifiers, which is the
    # failure the setwise ranker already met once.
    unparseable = 0
    unknown_ids = 0

    for text in responses.values():
        rows = _parse(text)
        if not rows:
            unparseable += 1
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            item_id = str(raw.get("id", ""))
            if item_id not in known:
                unknown_ids += 1
                continue
            if item_id in seen:
                continue
            theme = raw.get("theme")
            if theme not in themes:
                theme = None
            seen[item_id] = GateVerdict(
                id=item_id,
                keep=bool(raw.get("keep")),
                theme=theme,
                reason=str(raw.get("reason", ""))[:400],
            )

    missing = known - set(seen)
    if missing:
        # "N of M", not "N": the health check fails the build on a stage that
        # collapsed, and cannot tell a two-item gap from a total failure unless
        # the line carries the total. Reporting the bare count made a healthy
        # run go red on 2026-08-22 with the explanation "the gate did not run",
        # when it had filtered 141 items down to 13.
        logger.warning(
            "Gate returned no verdict for %d of %d items; keeping them for the ranker",
            len(missing),
            len(known),
        )
        # Printed as well as logged, and separately, so the breakdown survives
        # the CLI's default level and reaches the run log the health check and
        # the morning review both read.
        print(
            f"Gate misses: {len(missing)} of {len(known)} unverdicted from "
            f"{len(responses)} responses; {unparseable} response(s) "
            f"unparseable, {unknown_ids} id(s) returned that no candidate has"
        )
    for item_id in missing:
        seen[item_id] = GateVerdict(id=item_id, keep=True, reason="no gate verdict")

    return [seen[c.id] for c in candidates]


def apply(
    candidates: Sequence[Candidate], verdicts: Sequence[GateVerdict]
) -> List[Candidate]:
    """Return kept candidates, tagged with the theme the gate chose."""
    by_id = {v.id: v for v in verdicts}
    kept = []
    for candidate in candidates:
        verdict = by_id.get(candidate.id)
        if verdict is None or not verdict.keep:
            continue
        kept.append(
            candidate.with_theme(verdict.theme) if verdict.theme else candidate
        )
    return kept
