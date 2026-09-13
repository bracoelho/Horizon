"""Pass 0 records the article behind a short or aggregator item and decides nothing (NEWS-Radar N-344)."""

import asyncio

import httpx
import pytest

from src.extractors import pull as P

ARTICLE = "<html><head><meta name='author' content='Jane Writer'><title>T</title></head><body><article>" + \
    "".join(f"<p>Paragraph {i} explains what the regulator decided about the grid and why operators must act.</p>" for i in range(30)) + \
    "</article></body></html>"


@pytest.fixture(autouse=True)
def no_dns(monkeypatch):
    async def plain(client, method, url, **kwargs):
        return await client.request(method, url, **kwargs)
    monkeypatch.setattr(P.url_security, "safe_request", plain)


def client_for(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_wants_short_items_and_google_links_only():
    assert P.wants_pull({"content": "x" * 600, "url": "https://a.example/1"})
    assert P.wants_pull({"content": "x" * 5000, "url": "https://news.google.com/rss/articles/ABC"})
    assert not P.wants_pull({"content": "x" * 601, "url": "https://a.example/1"})


def test_direct_item_gets_its_article_and_byline():
    def handler(request):
        return httpx.Response(200, text=ARTICLE)
    rec = asyncio.run(P.pull_one(client_for(handler), {"id": "i", "url": "https://pub.example/a", "content": "short", "author": "Pub"}))
    assert rec["route"] == "direct" and rec["status"] == 200 and rec["chars_after"] > 500
    assert rec["publisher"] == "Pub" and rec["blocked"] is None and len(rec["text"]) <= P.TEXT_CHARS


def test_google_link_resolved_through_batchexecute():
    page = '<div data-n-a-sg="SIG" data-n-a-ts="1757700000"></div>'
    reply = ')]}\'\n[["wrb.fr","Fbv4je","[\\"garturlres\\",\\"https://pub.example/story\\",1]"]]'

    def handler(request):
        if request.url.host == "news.google.com" and request.method == "GET":
            return httpx.Response(200, text=page)
        if request.url.path.endswith("batchexecute"):
            assert "SIG" in request.content.decode() and "TOKEN1" in request.content.decode()
            return httpx.Response(200, text=reply)
        return httpx.Response(200, text=ARTICLE)
    rec = asyncio.run(P.pull_one(client_for(handler), {"id": "g", "url": "https://news.google.com/rss/articles/TOKEN1?oc=5", "content": "snippet"}))
    assert rec["route"] == "batchexecute" and rec["final_url"] == "https://pub.example/story" and rec["text"]


def test_a_blocked_page_is_labelled_and_keeps_no_text():
    def handler(request):
        return httpx.Response(403, text="no")
    rec = asyncio.run(P.pull_one(client_for(handler), {"id": "b", "url": "https://pub.example/x", "content": ""}))
    assert rec["blocked"] == "http 403" and rec["text"] == "" and rec["chars_after"] == 0


def test_run_pull_counts_routes_and_skips_long_items():
    def handler(request):
        return httpx.Response(200, text=ARTICLE)
    entries = [{"id": "s", "url": "https://pub.example/s", "content": "short"},
               {"id": "l", "url": "https://pub.example/l", "content": "y" * 5000}]
    block = asyncio.run(P.run_pull(entries, spacing=0, client=client_for(handler)))
    assert block["wanted"] == 1 and block["with_article"] == 1 and block["routes"] == {"direct": 1}
    assert [r["id"] for r in block["items"]] == ["s"]


def test_batchexecute_url_loses_its_escape_and_keeps_escaped_slashes():
    assert P.parse_batchexecute('x"garturlres\\",\\"https://pub.example/a\\",1]') == "https://pub.example/a"
    assert P.parse_batchexecute('garturlres\\",\\"https:\\/\\/pub.example\\/b?x=1\\"') == "https://pub.example/b?x=1"
    assert P.parse_batchexecute("no marker here") is None
