"""Pass 0, the pull: the article behind a short or aggregator item, RECORDING ONLY.

For every fetched item that arrived with 600 characters or fewer, or through a Google News
link, resolve the publisher's URL and extract the article, and record the route, the status,
the length before and after, the publisher, the page's own byline and the text (capped at
6,000 characters) in the fixture's `pull` block (NEWS-Radar N-344; the ladder lab's E14,
OS research/ladder-lab/E14-RESULTS.md: 78 percent of aggregator links came back with the
article). Nothing reads the block: the scorer, the sift and the vote still read the item as
it arrived. The byline is recorded for the story anchor and is never sent to a model (E17).

Routes, in the order tried for a Google News link: the HTTP redirect, Google's
batchexecute decoder (signature and timestamp read from the article page), then the
page's first outbound link. Every request goes through `safe_request`, which refuses a
non-public address at each hop; one request a second; a 20-second timeout.

The batchexecute route calls an endpoint Google does not document. It is the route that
resolved the links in E14; if Google changes it, the route records "batchexecute: no url in
reply" and the item stays a snippet, labelled so.
"""

from __future__ import annotations

import asyncio
import collections
import json
import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx

from ..url_security import UnsafeURLError
from .. import url_security
from .trafilatura import ARTICLE_HEADERS

logger = logging.getLogger(__name__)

SHORT_CHARS = 600
TEXT_CHARS = 6000
BATCHEXECUTE = "https://news.google.com/_/DotsSplashUi/data/batchexecute"


def wants_pull(entry: dict) -> bool:
    """E14's selection: short on arrival, or behind a Google News link."""
    return len(entry.get("content") or "") <= SHORT_CHARS or "news.google." in (entry.get("url") or "")


def google_signature(html: str, url: str) -> Optional[Tuple[str, str, str]]:
    """(token, timestamp, signature) from a Google News article page, or None."""
    token = url.split("/articles/")[1].split("?")[0] if "/articles/" in url else None
    m = re.search(r'data-n-a-sg="([^"]+)"[^>]*data-n-a-ts="(\d+)"', html)
    if m:
        return (token, m.group(2), m.group(1)) if token else None
    m = re.search(r'data-n-a-ts="(\d+)"[^>]*data-n-a-sg="([^"]+)"', html)
    if m:
        return (token, m.group(1), m.group(2)) if token else None
    return None


def batchexecute_payload(token: str, timestamp: str, signature: str) -> str:
    inner = json.dumps(["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
                                       "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0], token, int(timestamp), signature])
    return json.dumps([[["Fbv4je", inner, None, "generic"]]])


def parse_batchexecute(text: str) -> Optional[str]:
    if "garturlres" not in text:
        return None
    # The URL sits inside a JSON string that is itself inside JSON, so its quotes
    # arrive escaped. Stopping at a backslash as well as a quote is what keeps
    # the escape off the end of the URL (the lab's E14 first run left a trailing
    # backslash on 54 URLs); an escaped slash inside the URL is kept and undone.
    m = re.search(r'(https?:(?:\\/|/){2}(?:[^"\\]|\\/)+)', text.split("garturlres", 1)[1])
    if not m:
        return None
    return m.group(1).replace("\\/", "/")


async def resolve(client: httpx.AsyncClient, url: str) -> Tuple[Optional[str], str]:
    """(publisher URL, route) for a Google News link, or (None, why not)."""
    response = await url_security.safe_request(client, "GET", url, headers=ARTICLE_HEADERS)
    if "news.google." not in str(response.url):
        return str(response.url), "redirect"
    html = response.text
    sig = google_signature(html, url)
    if sig:
        token, ts, sg = sig
        reply = await url_security.safe_request(
            client, "POST", BATCHEXECUTE, data={"f.req": batchexecute_payload(token, ts, sg)},
            headers={**ARTICLE_HEADERS, "content-type": "application/x-www-form-urlencoded;charset=UTF-8"},
        )
        found = parse_batchexecute(reply.text)
        return (found, "batchexecute") if found else (None, "batchexecute: no url in reply")
    link = re.search(r'<a[^>]+href="(https?://(?!news\.google)[^"]+)"', html)
    if link:
        return link.group(1), "page-link"
    return None, "unresolved: no signature, no link"


def _extract(html: str) -> Tuple[Optional[str], str]:
    try:
        import trafilatura
    except ImportError:
        return None, ""
    text = None
    byline = ""
    try:
        text = trafilatura.extract(html, include_comments=False, include_tables=False) or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Pull extraction failed: %s", exc)
    try:
        meta = trafilatura.extract_metadata(html)
        byline = (getattr(meta, "author", None) or "") if meta is not None else ""
    except Exception:  # noqa: BLE001
        byline = ""
    return text, byline


async def pull_one(client: httpx.AsyncClient, entry: dict) -> dict:
    url = entry.get("url") or ""
    rec: Dict[str, Any] = {"id": entry.get("id"), "url": url, "publisher": entry.get("author") or "",
                           "chars_before": len(entry.get("content") or ""), "chars_after": 0,
                           "route": None, "final_url": None, "final_host": None, "status": None,
                           "byline": "", "blocked": None, "text": ""}
    try:
        if "news.google." in url:
            final, route = await resolve(client, url)
        else:
            final, route = url, "direct"
        rec["route"], rec["final_url"] = route, final
        if not final:
            rec["blocked"] = route
            return rec
        response = await url_security.safe_request(client, "GET", final, headers=ARTICLE_HEADERS)
        rec["status"] = response.status_code
        rec["final_host"] = response.url.host
        if response.status_code != 200:
            rec["blocked"] = f"http {response.status_code}"
            return rec
        text, byline = _extract(response.text)
        rec["byline"] = byline
        if not text:
            rec["blocked"] = "no extractable text (consent page, paywall or script-rendered)"
            return rec
        rec["chars_after"] = len(text)
        rec["text"] = text[:TEXT_CHARS]
    except (httpx.HTTPError, UnsafeURLError) as exc:
        rec["blocked"] = f"exception: {str(exc)[:120]}"
    except Exception as exc:  # noqa: BLE001 - one page must not cost the others
        rec["blocked"] = f"exception: {str(exc)[:120]}"
    return rec


async def run_pull(entries: Iterable[dict], *, spacing: float = 1.0, timeout: float = 20.0,
                   client: Optional[httpx.AsyncClient] = None) -> dict:
    """Pull every wanted entry, one at a time, `spacing` seconds apart; return the fixture block."""
    wanted = [e for e in entries if wants_pull(e)]
    own = client is None
    client = client or httpx.AsyncClient(timeout=timeout, follow_redirects=False)
    items: List[dict] = []
    try:
        for n, entry in enumerate(wanted):
            if n and spacing:
                await asyncio.sleep(spacing)
            items.append(await pull_one(client, entry))
    finally:
        if own:
            await client.aclose()
    routes = collections.Counter(r["route"] or "none" for r in items)
    return {"wanted": len(wanted), "with_article": sum(1 for r in items if r["text"]),
            "routes": dict(routes), "items": items}
