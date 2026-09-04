"""Pass three: the absolute floor.

Ranking says which items lead; this says whether any of them clear the bar at all.
Keeping those two jobs apart is what lets a quiet day publish two items and a busy
day publish five, without either being a threshold everything ties on.

This is also the first stage that can afford to read an item in full, because it
only ever runs on the handful that ranked highest.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Awaitable, Callable, Dict, List, Sequence

from .contract import Candidate, DefendVerdict
from .prompts import DEFEND_SCHEMA, defend_system, defend_user

logger = logging.getLogger(__name__)

DEFAULT_CONSIDER = 10
DEFAULT_MAX_PUBLISH = 6
DEFAULT_CONTENT_CHARS = 6000

Completer = Callable[[str, str], Awaitable[str]]


def _parse(text: str) -> Dict[str, object]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return {}
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return payload if isinstance(payload, dict) else {}


async def defend(
    ranked: Sequence[Candidate],
    complete: Completer,
    theme_questions: Dict[str, str],
    *,
    consider: int = DEFAULT_CONSIDER,
    max_publish: int = DEFAULT_MAX_PUBLISH,
    content_chars: int = DEFAULT_CONTENT_CHARS,
    concurrency: int = 4,
) -> tuple[List[Candidate], List[DefendVerdict]]:
    """Read the top `consider` in full and return those that clear the bar.

    Order is preserved: this filters the ranking, it does not reorder it.
    """
    shortlist = list(ranked)[:consider]
    if not shortlist:
        return [], []

    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def judge(candidate: Candidate) -> DefendVerdict:
        async with semaphore:
            body = (candidate.content or candidate.summary)[:content_chars]
            try:
                text = await complete(
                    defend_system(theme_questions.get(candidate.theme or "", "")),
                    defend_user(candidate.title, candidate.source, candidate.url, body),
                )
            except Exception as exc:
                # A failed judgement must not silently publish. Reject and say so.
                logger.error("Defend failed for %s: %s", candidate.id, exc)
                return DefendVerdict(candidate.id, False, f"defend failed: {exc}")

        payload = _parse(text)
        if "publish" not in payload:
            logger.warning("Defend returned no verdict for %s", candidate.id)
            return DefendVerdict(candidate.id, False, "no verdict returned")
        nexus = str(payload.get("ai_nexus", "")).strip().lower()
        why = str(payload.get("why", ""))[:600]
        if nexus == "neither":
            # The charter check (NEWS-Radar BACKLOG #78). Logged at warning, not
            # info, because the CLI defaults to warning and a decision nobody
            # can see is the defect this project keeps re-learning.
            logger.warning(
                "Defend refused %s: no AI nexus (%s)", candidate.id, candidate.title
            )
            return DefendVerdict(candidate.id, False, f"no AI nexus: {why}", nexus)
        if not nexus:
            # Unknown, never refused: an unanswered field must not empty an
            # edition, the same rule the score floor follows for unscored items.
            logger.warning("Defend returned no AI nexus for %s", candidate.id)
        return DefendVerdict(
            id=candidate.id,
            publish=bool(payload.get("publish")),
            why=why,
            ai_nexus=nexus,
        )

    verdicts = await asyncio.gather(*(judge(c) for c in shortlist))
    passed = {v.id for v in verdicts if v.publish}
    selected = [c for c in shortlist if c.id in passed][:max_publish]
    return selected, list(verdicts)
