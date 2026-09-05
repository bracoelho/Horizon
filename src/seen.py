"""What the radar has already fetched, so a wider window costs nothing.

A source's cadence and the run's window were one number until 2026-09-05. That
worked while every source published daily and hid every source that did not:
NIST returned zero items in five measured runs because its newest post was
twelve days old, and the health check called it a dead source.

Widening a slow feed's window alone would re-fetch and re-analyse the same
items every night for a month, and could publish one twice, because the
pipeline deliberately keeps no cross-run memory. This store is that memory, and
only that: an id, and the date it was first seen. It answers one question, has
this been through the pipeline before, and it prunes itself.

Kept deliberately small and separate from the metrics series: this is
operational state, not evidence, and it must be safe to delete. Deleting it
costs one night of re-analysis and nothing else.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

DEFAULT_KEEP_DAYS = 120


class SeenStore:
    """Ids already fetched, with the date each was first seen."""

    def __init__(self, path: Path, keep_days: int = DEFAULT_KEEP_DAYS):
        self.path = Path(path)
        self.keep_days = keep_days
        self._seen: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._seen = {str(k): str(v) for k, v in data.items()}
        except (OSError, json.JSONDecodeError) as exc:
            # A corrupt store must not stop a run: an empty one costs one
            # night of re-analysis, which is the same cost as not having it.
            logger.warning("Seen store unreadable (%s); starting empty", exc)
            self._seen = {}

    def __len__(self) -> int:
        return len(self._seen)

    def is_new(self, item_id: str) -> bool:
        return item_id not in self._seen

    def filter_new(self, items: Iterable) -> list:
        """Items whose id this store has not recorded, order preserved."""
        return [i for i in items if self.is_new(getattr(i, "id", ""))]

    def record(self, items: Iterable) -> int:
        today = date.today().isoformat()
        added = 0
        for item in items:
            item_id = getattr(item, "id", "")
            if item_id and item_id not in self._seen:
                self._seen[item_id] = today
                added += 1
        return added

    def prune(self) -> int:
        cutoff = (datetime.now() - timedelta(days=self.keep_days)).date().isoformat()
        stale = [k for k, v in self._seen.items() if v < cutoff]
        for k in stale:
            del self._seen[k]
        return len(stale)

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self._seen, ensure_ascii=False, indent=0),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Seen store not saved (%s)", exc)
