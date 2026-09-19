"""The edition contract writer, v1 (NEWS-Radar specs/EDITION-CONTRACT.json).

Builds one dict per run from what the night published and what the ladder
recorded, and nothing here is read by any stage: the page, Telegram and the
commentary proposal each move to it on a declared night of their own. The
radar's `tools/edition_contract.py` is the validator and the master of the
shape; this writer is checked against it at landing and its own tests hold
the invariants the contract states.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

CONTRACT_VERSION = 1
SHELF_MAX = 4  # N-228: four per shelf on every shelf


def normalise_url(url: str) -> str:
    """One string per address: lowercase scheme and host, no fragment, no
    tracking parameters, no trailing slash. Two carriers of one page then
    share an event id even when a newsletter added its `utm_source`."""
    parts = urlsplit(str(url or "").strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid", "ref"}]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def event_id(url: str) -> str:
    """Stable across editions: the first 16 hex characters of sha256 over the
    normalised url. v1 keys on the article's own url; the same-event guard,
    whose purpose is now counting carriers, will key a group on its anchor."""
    return hashlib.sha256(normalise_url(url).encode("utf-8")).hexdigest()[:16]


def _rank_key(article: dict) -> tuple:
    score = article.get("score")
    urgency = ((article.get("judgement") or {}).get("urgency"))
    return (-(score if isinstance(score, (int, float)) else -1),
            -(urgency if isinstance(urgency, (int, float)) else -1),
            article.get("title") or "")


def build_edition(*, run_id: str, night: str, generated_at: str, fork_commit: str,
                  taxonomy: str, seat: str, themes: Dict[str, str], theme_order: Sequence[str],
                  published: Sequence[dict], ladder: Optional[dict], cost: Optional[dict]) -> dict:
    """`published`: one dict per published item with id, title, url, item_url,
    source, publisher, published_at, theme, score. `ladder`: the fixture's
    ladder block or None. `cost`: the per-stage summary or None."""
    rows = {r["id"]: r for r in (ladder or {}).get("items", [])}
    articles: Dict[str, dict] = {}
    for p in published:
        row = rows.get(p["id"], {})
        vote = None
        if row.get("theme") is not None or row.get("agree") is not None:
            vote = {"theme": row.get("theme"), "runs": (ladder or {}).get("runs"), "agree": row.get("agree")}
        judgement = row.get("judgement") if isinstance(row.get("judgement"), dict) else None
        labels = row.get("labels") if isinstance(row.get("labels"), dict) else None
        art = {
            "id": p["id"], "title": p["title"], "url": p["url"], "item_url": p.get("item_url") or "",
            "source": p.get("source") or "", "publisher": p.get("publisher") or None,
            "published_at": p.get("published_at") or None, "theme": p["theme"], "score": p.get("score"),
            "vote": vote, "judgement": judgement, "labels": labels,
            "talk": (judgement or {}).get("line") or None,
            "event_id": event_id(p["url"]),
            "carriers": [{"source": p.get("source") or "", "url": p["url"],
                          "publisher": p.get("publisher") or None, "id": p["id"]}],
            "carrier_count": 1,
        }
        articles[p["id"]] = art
    rank = [a["id"] for a in sorted(articles.values(), key=_rank_key)]
    shelves: List[dict] = []
    for theme in list(theme_order) + [t for t in themes if t not in theme_order]:
        ids = [i for i in rank if articles[i]["theme"] == theme]
        if ids:
            shelves.append({"theme": theme, "question": themes.get(theme, ""), "articles": ids[:SHELF_MAX]})
    return {
        "contract_version": CONTRACT_VERSION,
        "run_id": str(run_id), "night": night, "generated_at": generated_at, "fork_commit": fork_commit,
        "taxonomy": taxonomy, "seat": seat,
        "shelves": shelves,
        "rank": rank,
        "rank_basis": "ladder judgement" if ladder and any(a["judgement"] for a in articles.values()) else "analysis score",
        "articles": articles,
        "lead": None,
        "commentary": {"candidates": list(rank), "proposal": None},
        "thread": {"refers_to": []},
        "quiet": len(rank) == 0,
        "cost": cost or {},
    }
