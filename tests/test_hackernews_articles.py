"""A Hacker News link post carries its article ahead of its comments (NEWS-Radar N-283).

Before this, a link post's text was only its top comments, so the scorer judged
the commenters: on 12 Sep an item published at 7.0 on 1,297 characters of them.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.models import HackerNewsConfig
from src.scrapers.hackernews import HackerNewsScraper

COMMENTS = [{"by": "a", "text": "a comment"}]


def _story(story_id, url=None, text=None):
    story = {"id": story_id, "title": f"story {story_id}", "by": "x", "time": 1757600000, "score": 99, "type": "story"}
    if url:
        story["url"] = url
    if text:
        story["text"] = text
    return story


def _scraper(extractor, name="trafilatura"):
    registry = MagicMock()
    registry.get.side_effect = lambda n: extractor if n == "trafilatura" else None
    return HackerNewsScraper(HackerNewsConfig(content_extractor=name), AsyncMock(), registry)


def _items(scraper, stories):
    return [scraper._parse_story(s, COMMENTS) for s in stories]


def test_a_link_post_carries_its_article_ahead_of_the_comments():
    extractor = AsyncMock()
    extractor.extract.return_value = "The article itself."
    scraper = _scraper(extractor)
    (item,) = asyncio.run(scraper._attach_articles(_items(scraper, [_story(1, "https://example.com/a")])))
    assert item.content.startswith("The article itself.")
    assert "--- Top Comments ---" in item.content and "a comment" in item.content
    assert item.metadata["article_extracted"] is True
    extractor.extract.assert_awaited_once()


def test_a_post_on_hacker_news_itself_keeps_its_own_text():
    extractor = AsyncMock()
    scraper = _scraper(extractor)
    before = _items(scraper, [_story(2, text="Ask HN: a question")])
    (item,) = asyncio.run(scraper._attach_articles(before))
    assert item.content == before[0].content
    extractor.extract.assert_not_awaited()


def test_a_refused_page_keeps_the_comments():
    extractor = AsyncMock()
    extractor.extract.return_value = None
    scraper = _scraper(extractor)
    before = _items(scraper, [_story(3, "https://example.com/refused")])
    (item,) = asyncio.run(scraper._attach_articles(before))
    assert item.content == before[0].content
    assert item.metadata["article_extracted"] is False


def test_an_extractor_that_raises_keeps_the_comments():
    extractor = AsyncMock()
    extractor.extract.side_effect = RuntimeError("boom")
    scraper = _scraper(extractor)
    before = _items(scraper, [_story(4, "https://example.com/boom")])
    (item,) = asyncio.run(scraper._attach_articles(before))
    assert item.content == before[0].content


def test_no_extractor_configured_changes_nothing():
    extractor = AsyncMock()
    scraper = _scraper(extractor, name=None)
    before = _items(scraper, [_story(5, "https://example.com/b")])
    after = asyncio.run(scraper._attach_articles(before))
    assert [i.content for i in after] == [i.content for i in before]
    extractor.extract.assert_not_awaited()


def test_order_is_kept_across_mixed_posts():
    extractor = AsyncMock()
    extractor.extract.return_value = "article"
    scraper = _scraper(extractor)
    stories = [_story(6, "https://example.com/c"), _story(7, text="Show HN"), _story(8, "https://example.com/d")]
    after = asyncio.run(scraper._attach_articles(_items(scraper, stories)))
    assert [i.title for i in after] == ["story 6", "story 7", "story 8"]
