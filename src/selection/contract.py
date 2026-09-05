"""The data contract selection owns.

This module deliberately imports nothing from the surrounding pipeline. Selection
is the part of this project worth owning outright, so it speaks its own types and
can be developed, tested and eventually moved without the engine coming with it.
The one adapter that knows about the engine lives in `adapter.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Candidate:
    """One item under consideration, holding only what selection needs."""

    id: str
    title: str
    summary: str
    source: str
    url: str
    published_at: Optional[datetime] = None
    theme: Optional[str] = None
    content: str = ""

    def with_theme(self, theme: str) -> "Candidate":
        return replace(self, theme=theme)

    def with_content(self, content: str) -> "Candidate":
        return replace(self, content=content)

    def brief(self, max_chars: int = 400) -> str:
        """The short form shown to the gate and the ranker."""
        summary = " ".join(self.summary.split())
        if len(summary) > max_chars:
            summary = summary[:max_chars].rstrip() + "..."
        return summary


@dataclass(frozen=True)
class GateVerdict:
    """Keep or drop, and which theme it belongs to. Deliberately carries no score."""

    id: str
    keep: bool
    theme: Optional[str] = None
    reason: str = ""


@dataclass(frozen=True)
class DefendVerdict:
    """Whether a ranked item clears the bar on its own merits."""

    id: str
    publish: bool
    why: str = ""
    # "about-ai", "constraint-on-ai", "neither", or "" when the model did not
    # answer (older responses, or a parse that lost the field). Empty means
    # unknown and never means refused: a stage that cannot judge must not
    # silently drop the day's items.
    ai_nexus: str = ""


@dataclass(frozen=True)
class SelectionResult:
    """What a full selection run produced, including what it discarded and why.

    The discarded counts exist so a run can explain itself in the health footer:
    an edition of four items is only trustworthy if you can see what the other
    six hundred were and where they fell out.
    """

    selected: list[Candidate] = field(default_factory=list)
    ranked_ids: list[str] = field(default_factory=list)
    gate_kept: int = 0
    gate_dropped: int = 0
    defend_rejected: int = 0
    # The verdicts themselves, not only how many were rejected: a recorded
    # night that holds the field and the outcome but not the decisions cannot
    # answer whether a strong item lost a comparison or never reached the
    # shortlist, which is the wall the 2026-09-03 picks trial hit and the
    # reason the outer loop's ledger is sequenced where it is.
    defend_verdicts: list[DefendVerdict] = field(default_factory=list)

    @property
    def published_count(self) -> int:
        return len(self.selected)


@dataclass(frozen=True)
class BatchUnit:
    """One batched completion, in selection's own vocabulary.

    Structurally matches what the AI client's batch path consumes. Defining it
    here rather than importing the engine's version is what keeps this package
    free of engine imports, which is the point of owning the contract at all.
    """

    custom_id: str
    system: str
    user: str
    schema: Optional[dict] = None
    effort: Optional[str] = None
    model: Optional[str] = None
    max_tokens: Optional[int] = None
