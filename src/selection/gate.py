"""Pass one: keep or drop, per item, cheaply.

Runs on the cheapest model through the Batch API. Emits no score, because a
number produced from a single item read in isolation carries no comparative
information and every later stage would treat it as if it did.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional, Protocol, Sequence, Tuple

from .contract import Candidate, GateVerdict
from .prompts import GATE_SCHEMA, format_entries, gate_system, gate_user

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 40


class BatchRunner(Protocol):
    """What the gate needs from a client, and nothing more."""

    async def run(self, prompts: Sequence[tuple[str, str, str]]) -> Dict[str, str]:
        """Map (custom_id, system, user) triples to their text responses."""


def _parse(text: str) -> Tuple[List[dict], str]:
    """Pull the verdict list out of a response, and say HOW it failed.

    Returns (rows, kind) where kind is "" on success, "malformed" when the text
    is not readable JSON, and "wrong_shape" when it IS valid JSON that simply
    carries no `verdicts` list.

    The distinction is the whole point (NEWS-Radar N-016 / #102). Both used to
    return a bare [] and increment one counter called `unparseable`, which
    merged two failures needing opposite fixes: malformed text is a parse and
    retry problem, while valid JSON of the wrong shape is a PROMPT or SCHEMA
    problem and is not unparseable at all. A morning spent on the retry path
    would never have found the second.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return [], "malformed"
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return [], "malformed"
    verdicts = payload.get("verdicts") if isinstance(payload, dict) else None
    if isinstance(verdicts, list):
        return verdicts, ""
    return [], "wrong_shape"


def chunk(items: Sequence[Candidate], size: int) -> List[List[Candidate]]:
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def batch_keys(candidates: Sequence[Candidate], size: int) -> Dict[str, Dict[str, str]]:
    """The short key each item is shown under, per request: `gate-N` -> {key: id}.

    The model is shown `1` to `40` within its batch instead of the item's own id,
    and its answer is mapped back here. Measured on the 10-11 Sep night before it
    shipped (NEWS-Radar N-267, N-268): the model copies every id it is shown back,
    one feed's ids are 213 characters, and the batch holding them ran past the
    token ceiling in 5 of 5 replays and lost all forty verdicts; arXiv ids came
    back with their prefix stripped and matched nothing. Replayed with short keys
    the batch finished 5 of 5, no stripped ids came back, and verdicts landed on
    the right item as often as with the real ids.
    """
    return {
        f"gate-{index}": {str(k + 1): c.id for k, c in enumerate(group)}
        for index, group in enumerate(chunk(candidates, size))
    }


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
                    "id": str(k + 1),
                    "title": c.title,
                    "source": c.source,
                    "summary": c.brief(),
                }
                for k, c in enumerate(group)
            ]
        )
        requests.append((f"gate-{index}", system, gate_user(entries)))
    return requests


def collect(
    responses: Dict[str, str],
    candidates: Sequence[Candidate],
    themes: Dict[str, str],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    stops: Optional[Dict[str, str]] = None,
) -> List[GateVerdict]:
    """Turn raw responses into verdicts, one per candidate.

    An item the gate never ruled on is kept rather than dropped. A dropped item is
    invisible for the rest of the run, so an unparsed response must not silently
    delete work; the ranker will discard it cheaply if it does not belong.
    """
    known = {c.id for c in candidates}
    keys = batch_keys(candidates, batch_size)
    seen: Dict[str, GateVerdict] = {}
    # Why a verdict goes missing, counted rather than guessed (NEWS-Radar
    # BACKLOG #82). The no-verdict share ran 18, 22, 37 and 42 percent across
    # four runs and the log said only how many, never why. The counts below
    # separate the three causes that need different fixes: a response that
    # cannot be parsed at all loses its whole batch, a response that parses
    # while omitting ids loses items one by one, and an id that comes back
    # unrecognised means the model is rewriting identifiers, which is the
    # failure the setwise ranker already met once.
    malformed = 0
    wrong_shape = 0
    unknown_ids = 0

    for custom_id, text in responses.items():
        # A short key is read within its own batch; a full id is still accepted,
        # so a caller that shows real ids keeps working.
        table = keys.get(custom_id, {})
        rows, failure = _parse(text)
        if failure == "malformed":
            malformed += 1
        elif failure == "wrong_shape":
            wrong_shape += 1
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            said = str(raw.get("id", ""))
            item_id = table.get(said) or (said if said in known else None)
            if item_id is None:
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
    # Printed on EVERY run, zero included, so a clean night is a reading rather
    # than a silence (NEWS-Radar N-267). `stops` comes from the batch path; the
    # synchronous path has no stop reasons and says so instead of printing 0.
    truncated = (
        f"{sum(1 for s in stops.values() if s == 'max_tokens')} stopped at max_tokens"
        if stops is not None
        else "stop reasons not recorded"
    )
    print(
        f"Gate batches: {len(responses)} of {len(keys)} responses; {truncated}; "
        f"{malformed + wrong_shape} unparseable; {unknown_ids} unmatched id(s); "
        f"{len(missing)} of {len(known)} items unverdicted"
    )
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
        # `unparseable` stays the TOTAL so the decision table in NEWS-Radar's
        # CLAUDE.md keeps reading; the split is added beside it.
        unparseable = malformed + wrong_shape
        print(
            f"Gate misses: {len(missing)} of {len(known)} unverdicted from "
            f"{len(responses)} responses; {unparseable} response(s) "
            f"unparseable ({malformed} malformed, {wrong_shape} wrong-shape), "
            f"{unknown_ids} id(s) returned that no candidate has"
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
