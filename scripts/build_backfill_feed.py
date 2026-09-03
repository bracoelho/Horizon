#!/usr/bin/env python3
"""Build a static RSS feed from a site's sitemap, for the born-blind backfill.

The radar's first working run was 2026-08-16. Everything published before
that date on a source was never seen, and the feeds that mirror those
sources reach back only a few weeks (the Claude blog mirror to 19 August,
the Anthropic mirror to 26 July). A sitemap reaches the whole archive with
a lastmod per page, so this script turns the slice of a sitemap between
two dates into an RSS 2.0 file the normal RSS scraper can read. The item's
body is left to the scraper's `content_extractor` (trafilatura), so the
feed only needs link, title and date; each page is fetched once here to
read its title and its published date from the JSON-LD block.

Usage:
  build_backfill_feed.py --sitemap URL --include /blog/ [--include /news/]
      --since 2026-06-01 --until 2026-08-16 --title "Claude Blog archive"
      --out data/backfill/claude-blog.xml

The output is committed and served raw from GitHub, because the RSS
source model requires an http URL. Re-run to refresh; the file is
deterministic for a given sitemap state.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import html
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from email.utils import format_datetime

UA = "Mozilla/5.0 (compatible; NEWS-Radar backfill; +https://radar.bcoelho.com/method/)"


def fetch(url: str, limit: int = 400_000) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read(limit).decode("utf-8", "ignore")


def sitemap_entries(url: str) -> list[tuple[str, str]]:
    x = fetch(url, limit=5_000_000)
    return re.findall(r"<url>\s*<loc>([^<]*)</loc>\s*(?:<lastmod>([^<]*)</lastmod>)?", x)


def page_meta(url: str) -> dict:
    """Title and published date from the page; falls back gracefully."""
    out = {"url": url, "title": None, "published": None, "description": None}
    try:
        h = fetch(url)
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)[:120]
        return out
    m = re.search(r"<title>([^<]*)</title>", h, re.I)
    if m:
        t = html.unescape(m.group(1)).strip()
        out["title"] = re.split(r"\s*(?:\||\\)\s*", t)[0].strip() or t
    for ld in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', h, re.S):
        try:
            data = json.loads(ld)
        except json.JSONDecodeError:
            continue
        nodes = data if isinstance(data, list) else [data]
        for n in nodes:
            if not isinstance(n, dict):
                continue
            for k in ("datePublished", "dateCreated"):
                v = n.get(k)
                if v and not out["published"]:
                    out["published"] = v
            if n.get("headline") and not out["title"]:
                out["title"] = n["headline"]
            if n.get("description") and not out["description"]:
                out["description"] = n["description"]
    m = re.search(r'<meta[^>]+(?:name|property)="(?:description|og:description)"[^>]+content="([^"]*)"', h, re.I)
    if m and not out["description"]:
        out["description"] = html.unescape(m.group(1))
    if not out["published"]:
        # Static sites without JSON-LD (the Alignment Science blog) print the
        # date in prose; the first full date on the page is the publish date.
        m = re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2}), (20\d{2})\b", h)
        if m:
            out["published"] = f"{m.group(1)} {int(m.group(2)):02d}, {m.group(3)}"
    return out


def index_entries(url: str, includes: list[str]) -> list[tuple[str, str]]:
    """Links from an index page, for sites with neither feed nor sitemap."""
    from urllib.parse import urljoin

    h = fetch(url, limit=2_000_000)
    seen: dict[str, str] = {}
    # Walk the page in order; a month heading ("August 2026") dates every
    # link that follows it until the next heading. The first of the month
    # is recorded as a lastmod proxy, used when the page itself has no date.
    months = {m: i for i, m in enumerate(
        ["January", "February", "March", "April", "May", "June", "July",
         "August", "September", "October", "November", "December"], 1)}
    current = ""
    for tok in re.finditer(r'\b(January|February|March|April|May|June|July|August|September|October|November|December) (20\d{2})\b|href="([^"#]+)"', h):
        if tok.group(1):
            current = f"{tok.group(2)}-{months[tok.group(1)]:02d}-01"
            continue
        href = tok.group(3)
        if any(s in href for s in includes):
            seen.setdefault(urljoin(url, href), current)
    return list(seen.items())


def parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%b %d, %Y", "%B %d, %Y"):
        try:
            d = datetime.strptime(s.replace("Z", "+0000"), fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    m = re.match(r"(\w{3}) (\d{1,2})$", s)  # "Jul 06": year unknown, caller decides
    return None if not m else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sitemap", help="sitemap URL (lastmod pre-filters the slice)")
    ap.add_argument("--index", help="index page URL, for sites with neither feed nor sitemap; dates come from each page")
    ap.add_argument("--include", action="append", required=True, help="path substring to keep; repeatable")
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()

    if not (a.sitemap or a.index):
        ap.error("one of --sitemap or --index is required")
    if a.sitemap:
        entries = [(u, d) for u, d in sitemap_entries(a.sitemap) if any(s in u for s in a.include)]
        entries = [(u, d) for u, d in entries if d and a.since <= d[:10] <= a.until]
        print(f"{len(entries)} sitemap entries in {a.since}..{a.until} under {a.include}", file=sys.stderr)
    else:
        entries = index_entries(a.index, a.include)
        entries = [(u, d) for u, d in entries if not d or a.since[:7] <= d[:7] <= a.until[:7]]
        print(f"{len(entries)} index links under {a.include} (month headings as date proxy); page dates preferred", file=sys.stderr)
    source_link = a.sitemap or a.index

    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        metas = list(ex.map(page_meta, [u for u, _ in entries]))
    lastmod = dict(entries)

    items = []
    dropped = 0
    for m in metas:
        pub = parse_date(m.get("published"))
        proxy = parse_date(lastmod.get(m["url"]))
        if a.index and proxy and (not pub or pub.strftime("%Y-%m") != proxy.strftime("%Y-%m")):
            # Index mode: the month heading outranks a stray date in the page
            # text (a citation, a footnote), which is what the text fallback finds.
            pub = proxy
        pub = pub or proxy
        if not m.get("title") or not pub:
            dropped += 1
            continue
        if not (a.since <= pub.strftime("%Y-%m-%d") <= a.until):
            dropped += 1
            continue
        items.append((pub, m))
    items.sort(key=lambda t: t[0], reverse=True)
    print(f"{len(items)} items kept, {dropped} dropped (no title/date or published outside the range)", file=sys.stderr)

    def esc(s: str) -> str:
        return html.escape(s or "", quote=False)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0"><channel>',
        f"<title>{esc(a.title)}</title>",
        f"<link>{esc(source_link)}</link>",
        f"<description>Born-blind backfill feed built from the sitemap, {a.since} to {a.until}. Bodies come from the page at fetch time.</description>",
    ]
    for pub, m in items:
        lines += [
            "<item>",
            f"<title>{esc(m['title'])}</title>",
            f"<link>{esc(m['url'])}</link>",
            f"<guid isPermaLink=\"true\">{esc(m['url'])}</guid>",
            f"<pubDate>{format_datetime(pub)}</pubDate>",
            f"<description>{esc(m.get('description') or m['title'])}</description>",
            "</item>",
        ]
    lines.append("</channel></rss>")
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {a.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
