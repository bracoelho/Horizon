"""Main orchestrator coordinating the entire workflow."""

import asyncio
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Literal, Optional
from urllib.parse import unquote_plus, urlsplit
import httpx
from rich.console import Console

from .console_icons import get_icons
from .models import Config, ContentItem
from .storage.manager import StorageManager, safe_output_path
from .services.email import EmailManager
from .services.webhook import WebhookNotifier
from .scrapers.github import GitHubScraper
from .scrapers.hackernews import HackerNewsScraper
from .scrapers.rss import RSSScraper
from .scrapers.reddit import RedditScraper
from .scrapers.telegram import TelegramScraper
from .scrapers.twitter import TwitterScraper
from .scrapers.twitter_playwright import TwitterPlaywrightScraper
from .scrapers.openbb import OpenBBScraper
from .scrapers.ossinsight import OSSInsightScraper
from .scrapers.gdelt import GDELTScraper
from .scrapers.google_news import GoogleNewsScraper
from .ai.client import create_ai_client
from .ai.analyzer import ContentAnalyzer
from .ai.summarizer import DailySummarizer
from .ai.synthesis import synthesise
from .ai.enricher import ContentEnricher, EnrichmentBatchResult
from .ai.tokens import get_usage_snapshot
from .processing import ProfileRegistry
from .selection import SelectionSettings, to_candidates
from .selection import select as run_selection


_TRACKING_QUERY_PARAMETERS = {
    "_ga",
    "dclid",
    "fbclid",
    "gclid",
    "igshid",
    "li_fat_id",
    "mc_cid",
    "mc_eid",
    "msclkid",
    "ttclid",
    "twclid",
    "vero_id",
}


def _deduplication_url_key(url: str) -> tuple[str, str, str, str, Optional[int], str, str]:
    """Return a conservative URL identity key for cross-source deduplication."""
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    port = parsed.port
    if (scheme, port) in {("http", 80), ("https", 443)}:
        port = None

    path = parsed.path.rstrip("/") or "/"
    query_parts = []
    for part in parsed.query.split("&") if parsed.query else []:
        name = unquote_plus(part.partition("=")[0]).lower()
        if name.startswith("utm_") or name in _TRACKING_QUERY_PARAMETERS:
            continue
        query_parts.append(part)

    return (
        scheme,
        parsed.username or "",
        parsed.password or "",
        host,
        port,
        path,
        "&".join(query_parts),
    )


@dataclass
class BalancedDigestResult:
    """Items and selection statistics from balanced digest filtering."""

    items: List[ContentItem]
    enabled: bool = False
    group_counts: Dict[str, int] = field(default_factory=dict)
    group_limits: Dict[str, Optional[int]] = field(default_factory=dict)
    duplicate_categories: List[str] = field(default_factory=list)


@dataclass
class FilteringPipelineResult:
    """Items and statistics from score, topic, and digest filtering."""

    items: List[ContentItem]
    threshold_count: int
    topic_dedup_count: int
    topic_dedup_removed: int
    balanced_digest: BalancedDigestResult
    eligible_count: Optional[int] = None


@dataclass
class SourceFetchOutcome:
    """Result of fetching one configured source."""

    source_name: str
    status: Literal["success", "empty", "failure"]
    items: List[ContentItem] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        result: Dict[str, object] = {
            "source": self.source_name,
            "status": self.status,
            "item_count": len(self.items),
        }
        if self.error is not None:
            result["error"] = self.error
        return result


@dataclass
class FetchReport:
    """Aggregate diagnostics for one fetch across configured sources."""

    outcomes: List[SourceFetchOutcome] = field(default_factory=list)

    @property
    def status(self) -> Literal["not_attempted", "success", "partial_failure", "failure"]:
        if not self.outcomes:
            return "not_attempted"
        if self.failed_count == len(self.outcomes):
            return "failure"
        if self.failed_count:
            return "partial_failure"
        return "success"

    @property
    def failed_count(self) -> int:
        return sum(outcome.status == "failure" for outcome in self.outcomes)

    @property
    def all_failed(self) -> bool:
        return bool(self.outcomes) and self.failed_count == len(self.outcomes)

    def failure_message(self) -> str:
        failures = "; ".join(
            f"{outcome.source_name}: {outcome.error or 'unknown error'}"
            for outcome in self.outcomes
            if outcome.status == "failure"
        )
        return f"All {len(self.outcomes)} attempted sources failed ({failures})"

    def to_dict(self) -> Dict[str, object]:
        return {
            "status": self.status,
            "attempted": len(self.outcomes),
            "successful": len(self.outcomes) - self.failed_count,
            "empty": sum(outcome.status == "empty" for outcome in self.outcomes),
            "failed": self.failed_count,
            "item_count": sum(len(outcome.items) for outcome in self.outcomes),
            "sources": [outcome.to_dict() for outcome in self.outcomes],
        }


# What an edition is called. Held in one place because the same string has to
# match on the published page, in the feed and in the email subject, and three
# copies of a name drift.
EDITION_NAME = "AI Radar"


def _edition_date(when: datetime) -> str:
    """"22 August 2026", with no leading zero on the day."""
    return f"{when.day} {when:%B %Y}"


class HorizonOrchestrator:
    """Orchestrates the complete workflow for content aggregation and analysis."""

    icons = get_icons()

    def __init__(
        self,
        config: Config,
        storage: StorageManager,
        console: Optional[Console] = None,
        profiles: Optional[ProfileRegistry] = None,
    ):
        """Initialize orchestrator.

        Args:
            config: Application configuration
            storage: Storage manager
            console: Shared Rich Console instance
        """
        self.config = config
        self.storage = storage
        self.console = console or Console(stderr=True)
        self.icons = get_icons(config.display.icon_style)
        self.profiles = profiles or ProfileRegistry.load(
            Path(config.processing.profiles_dir), config.processing.default_profile
        )
        self.profiles.validate_source_references(
            config.sources.model_dump(mode="json")
        )
        for profile_id in config.processing.profile_settings:
            self.profiles.get(profile_id)
        if config.digest.profile_order:
            configured_profiles = set(config.digest.profile_order)
            unknown_profiles = configured_profiles - self.profiles.ids
            if unknown_profiles:
                raise ValueError(
                    "digest.profile_order contains unknown profiles "
                    f"({', '.join(sorted(unknown_profiles))})"
                )
            config.digest.profile_order.extend(
                profile.id
                for profile in self.profiles.profiles
                if profile.id not in configured_profiles
            )
        self.email_manager = EmailManager(config.email, console=self.console) if config.email else None
        self.webhook_notifier = (
            WebhookNotifier(config.webhook, console=self.console, icons=self.icons)
            if config.webhook and config.webhook.enabled
            else None
        )
        self.last_fetch_report: Optional[FetchReport] = None

    async def run(self, force_hours: int = None) -> None:
        """Execute the complete workflow.

        Args:
            force_hours: Optional override for time window in hours
        """
        self.console.print(
            f"[bold cyan]{self.icons['start']} Horizon - Starting aggregation...[/bold cyan]\n"
        )

        # Check email subscriptions if configured
        if (
            self.email_manager
            and self.config.email
            and self.config.email.enabled
            and self.config.email.imap_enabled
        ):
            self.console.print(f"{self.icons['email']} Checking for new email subscriptions...")
            self.email_manager.check_subscriptions(self.storage)

        try:
            # 1. Determine time window
            since = self._determine_time_window(force_hours)
            self.console.print(
                f"{self.icons['date']} Fetching content since: "
                f"{since.strftime('%Y-%m-%d %H:%M:%S')}\n"
            )

            # 2. Fetch content from all sources
            all_items = await self.fetch_all_sources(since)
            self.console.print(
                f"{self.icons['fetched']} Fetched {len(all_items)} items from all sources\n"
            )

            if self.last_fetch_report and self.last_fetch_report.all_failed:
                raise RuntimeError(self.last_fetch_report.failure_message())

            if not all_items:
                self.console.print("[yellow]No new content found. Exiting.[/yellow]")
                return

            # 3. Merge cross-source duplicates (same URL from different sources)
            merged_items = self.merge_cross_source_duplicates(all_items)
            if len(merged_items) < len(all_items):
                self.console.print(
                    f"{self.icons['merge']} Merged "
                    f"{len(all_items) - len(merged_items)} cross-source duplicates "
                    f"→ {len(merged_items)} unique items\n"
                )

            # 4 and 5, and the order between them depends on the path.
            #
            # Ranking gates first and analyses only the survivors. Scoring
            # every fetched item and then letting a cheap gate discard three
            # quarters of them was the pipeline's largest avoidable cost: on
            # 2026-08-27 Sonnet scored 212 items so that Haiku could keep 64.
            # The threshold path has no gate, so it still has to score
            # everything before it can filter on the score.
            if self.config.selection.enabled:
                important_items, _selection = await self.select_by_ranking(
                    merged_items
                )
            else:
                analyzed_items = await self.analyze_items(merged_items)
                self.console.print(
                    f"{self.icons['ai']} Analyzed {len(analyzed_items)} items with AI\n"
                )
                filtering_result = await self.select_digest_items(
                    analyzed_items,
                )
                important_items = filtering_result.items

            # Show per-sub-source selection breakdown
            selected_counts: Dict[str, int] = defaultdict(int)
            for item in important_items:
                key = f"{item.source_type.value}/{self._sub_source_label(item)}"
                selected_counts[key] += 1
            for source_key, count in sorted(selected_counts.items()):
                self.console.print(f"      {self.icons['detail']} {source_key}: {count}")
            self.console.print("")

            # 6. Search related stories + enrich with background knowledge (2nd AI pass)
            await self.enrich_items(important_items)

            # 6b. Synthesise the edition. One call over the whole selected set,
            # which is the only stage that reads the items as a group.
            preamble = None
            if self.config.digest.synthesis_enabled and important_items:
                self.console.print(
                    f"{self.icons['summary']} Synthesising the edition..."
                )
                preamble = await synthesise(
                    important_items,
                    create_ai_client(self.config.ai),
                    model=self.config.digest.synthesis_model,
                )
                if preamble:
                    self.console.print(
                        f"   Wrote a {len(preamble.split())}-word opening\n"
                    )
                else:
                    self.console.print("   [yellow]No opening written[/yellow]\n")

            # 7. Generate and save daily summaries for each configured language
            now_utc = datetime.now(timezone.utc)
            today = now_utc.strftime("%Y-%m-%d")
            # Runs happen more than once a day, and the published post was named
            # by date alone in "w" mode, so the day's second run overwrote the
            # first — a quiet second run deleted items already published. Adding
            # the run time gives each run its own post.
            run_time = now_utc.strftime("%H%M")
            for lang in self.config.ai.languages:
                summarizer = DailySummarizer(
                    profile_names=self.profiles.names,
                    profile_order=self.config.digest.profile_order,
                    block_titles=self.profiles.block_titles,
                )
                summary = await summarizer.generate_summary(
                    important_items,
                    today,
                    len(all_items),
                    language=lang,
                    preamble=preamble,
                )

                # Save to data/summaries/
                summary_path = self.storage.save_daily_summary(today, summary, language=lang)
                self.console.print(
                    f"{self.icons['save']} Saved {lang.upper()} summary to: {summary_path}\n"
                )

                # Copy to docs/ for GitHub Pages
                try:
                    from pathlib import Path

                    post_filename = f"{today}-{run_time}-summary-{lang}.md"
                    posts_dir = Path("docs/_posts")
                    posts_dir.mkdir(parents=True, exist_ok=True)

                    dest_path = safe_output_path(posts_dir, post_filename)

                    # Add Jekyll front matter
                    front_matter = (
                        "---\n"
                        "layout: default\n"
                        # The edition's own name, not the upstream project's.
                        # This string is what a subscriber sees in a feed
                        # reader every day, so it was the most repeated words
                        # the audience read and none of them were the owner's.
                        # Language is marked only when it is not the primary
                        # one, since a suffix on every title is noise.
                        f"title: \"{EDITION_NAME}, {_edition_date(now_utc)}"
                        f"{'' if lang == 'en' else f' ({lang.upper()})'}\"\n"
                        # Full timestamp, not just the date: Jekyll orders posts
                        # by this field, and with several runs a day a date-only
                        # value leaves same-day posts in an arbitrary order.
                        f"date: {now_utc.strftime('%Y-%m-%d %H:%M:%S %z')}\n"
                        f"lang: {lang}\n"
                        # Counts in front matter so the index can show what a
                        # run produced without opening it.
                        f"items: {len(important_items)}\n"
                        f"analyzed: {len(all_items)}\n"
                        "---\n\n"
                    )

                    # Strip leading H1 header to avoid duplication with Jekyll title
                    summary_content = summary
                    first_line = summary_content.strip().split("\n")[0]
                    if first_line.startswith("# "):
                        parts = summary_content.split("\n", 1)
                        if len(parts) > 1:
                            summary_content = parts[1].strip()

                    with open(dest_path, "w", encoding="utf-8") as f:
                        f.write(front_matter + summary_content)

                    self.console.print(
                        f"{self.icons['document']} Copied {lang.upper()} summary "
                        f"to GitHub Pages: {dest_path}\n"
                    )

                    written = self._write_item_pages(
                        summarizer,
                        important_items,
                        today=today,
                        run_time=run_time,
                        lang=lang,
                        edition_url=(
                            f"/{today[:4]}/{today[5:7]}/{today[8:10]}/"
                            f"{run_time}-summary-{lang}.html"
                        ),
                        edition_title=f"{today} {now_utc.strftime('%H:%M')} UTC",
                        published_at=now_utc,
                    )
                    self.console.print(
                        f"{self.icons['document']} Wrote {written} {lang.upper()} "
                        f"item page(s)\n"
                    )

                    if lang == self.config.ai.languages[0]:
                        await self._write_commentary_proposal(
                            summarizer, important_items, lang, edition_url=(
                                f"/{today[:4]}/{today[5:7]}/{today[8:10]}/"
                                f"{run_time}-summary-{lang}.html"
                            )
                        )
                except Exception as e:
                    self.console.print(
                        f"[yellow]{self.icons['warning']} Failed to copy "
                        f"{lang.upper()} summary to docs/: {e}[/yellow]\n"
                    )

                # Send email if configured
                if self.email_manager and self.config.email and self.config.email.enabled:
                    self.console.print(
                        f"{self.icons['email']} Sending {lang.upper()} email summary..."
                    )
                    subscribers = self.storage.load_subscribers()
                    subject = (
                        f"{EDITION_NAME}, {_edition_date(now_utc)}"
                        f"{'' if lang == 'en' else f' ({lang.upper()})'}"
                    )
                    self.email_manager.send_daily_summary(summary, subject, subscribers)

                # Send webhook notification if configured
                if self.webhook_notifier:
                    await self.webhook_notifier.send_daily_summary(
                        summary=summary,
                        important_items=important_items,
                        all_items_count=len(all_items),
                        date=today,
                        lang=lang,
                        summarizer=summarizer,
                    )

            self.console.print(
                f"[bold green]{self.icons['success']} "
                "Horizon completed successfully![/bold green]"
            )
            usage = get_usage_snapshot()
            if usage.total_tokens > 0:
                self.console.print(
                    f"\n{self.icons['tokens']} Token usage this run: "
                    f"{usage.total_tokens} tokens "
                    f"(input: {usage.total_input_tokens}, output: {usage.total_output_tokens})"
                )
                for provider, u in sorted(usage.per_provider.items()):
                    if u.total <= 0:
                        continue
                    self.console.print(
                        f"   {self.icons['detail']} {provider}: {u.total} tokens "
                        f"(in: {u.input_tokens}, out: {u.output_tokens})"
                    )

        except Exception as e:
            self.console.print(
                f"[bold red]{self.icons['error']} Error: {e}[/bold red]"
            )

            # Send webhook failure notification if configured
            if self.webhook_notifier:
                await self.webhook_notifier.send_failure(
                    date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    error_message=str(e),
                )

            raise

    def _determine_time_window(self, force_hours: int = None) -> datetime:
        if force_hours:
            since = datetime.now(timezone.utc) - timedelta(hours=force_hours)
        else:
            hours = self.config.collection.time_window_hours
            since = datetime.now(timezone.utc) - timedelta(hours=hours)
        return since

    async def fetch_all_sources(self, since: datetime) -> List[ContentItem]:
        """Fetch content from all configured sources.

        This is a stable stage entry point for integrations such as MCP.

        Args:
            since: Fetch items published after this time

        Returns:
            List[ContentItem]: All fetched items
        """
        self.last_fetch_report = None
        async with httpx.AsyncClient(timeout=30.0) as client:
            tasks = []

            # GitHub sources
            if self.config.sources.github:
                github_scraper = GitHubScraper(self.config.sources.github, client)
                tasks.append(self._fetch_with_progress("GitHub", github_scraper, since))

            # Hacker News
            if self.config.sources.hackernews.enabled:
                hn_scraper = HackerNewsScraper(self.config.sources.hackernews, client)
                tasks.append(self._fetch_with_progress("Hacker News", hn_scraper, since))

            # RSS feeds
            if self.config.sources.rss:
                from .extractors import ExtractorRegistry
                rss_scraper = RSSScraper(
                    self.config.sources.rss,
                    client,
                    ExtractorRegistry(self.config.extractors),
                )
                tasks.append(self._fetch_with_progress("RSS Feeds", rss_scraper, since))

            # Reddit
            if self.config.sources.reddit.enabled:
                reddit_scraper = RedditScraper(self.config.sources.reddit, client)
                tasks.append(self._fetch_with_progress("Reddit", reddit_scraper, since))

            # Telegram
            if self.config.sources.telegram.enabled:
                telegram_scraper = TelegramScraper(self.config.sources.telegram, client)
                tasks.append(self._fetch_with_progress("Telegram", telegram_scraper, since))

            # Twitter (Apify or Playwright mode)
            if self.config.sources.twitter and self.config.sources.twitter.enabled:
                tw_cfg = self.config.sources.twitter
                if tw_cfg.mode == "playwright":
                    twitter_scraper = TwitterPlaywrightScraper(tw_cfg)
                else:
                    twitter_scraper = TwitterScraper(tw_cfg, client)
                tasks.append(self._fetch_with_progress("Twitter", twitter_scraper, since))

            # OpenBB (financial news / filings via the OpenBB Platform SDK)
            if self.config.sources.openbb and self.config.sources.openbb.enabled:
                openbb_scraper = OpenBBScraper(self.config.sources.openbb, client)
                tasks.append(self._fetch_with_progress("OpenBB", openbb_scraper, since))

            # OSS Insight trending repos
            if self.config.sources.ossinsight and self.config.sources.ossinsight.enabled:
                oss_scraper = OSSInsightScraper(self.config.sources.ossinsight, client)
                tasks.append(self._fetch_with_progress("OSS Insight", oss_scraper, since))

            # GDELT 2.0 DOC API (key-less global news)
            if self.config.sources.gdelt and self.config.sources.gdelt.enabled:
                gdelt_scraper = GDELTScraper(self.config.sources.gdelt, client)
                tasks.append(self._fetch_with_progress("GDELT", gdelt_scraper, since))

            # Google News RSS (key-less news search)
            if self.config.sources.google_news and self.config.sources.google_news.enabled:
                gn_scraper = GoogleNewsScraper(self.config.sources.google_news, client)
                tasks.append(self._fetch_with_progress("Google News", gn_scraper, since))

            # Fetch all concurrently
            outcomes = await asyncio.gather(*tasks)
            self.last_fetch_report = FetchReport(outcomes=list(outcomes))

            # Flatten successful and empty outcomes; failures remain in the report.
            all_items: List[ContentItem] = []
            for outcome in outcomes:
                all_items.extend(outcome.items)

            return all_items

    async def _fetch_with_progress(
        self, name: str, scraper, since: datetime
    ) -> SourceFetchOutcome:
        """Fetch from a scraper with progress indication.

        Args:
            name: Source name for display
            scraper: Scraper instance
            since: Fetch items after this time

        Returns:
            SourceFetchOutcome: Named fetch result and diagnostics
        """
        self.console.print(f"{self.icons['fetch']} Fetching from {name}...")
        try:
            items = await scraper.fetch(since)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.console.print(f"[red]   Failed to fetch {name}: {error}[/red]")
            return SourceFetchOutcome(
                source_name=name,
                status="failure",
                error=error,
            )

        self.console.print(f"   Found {len(items)} items from {name}")

        # Prefer a scraper's own tally of what it attempted: a breakdown derived
        # from returned items cannot show a sub-source that returned nothing,
        # which is exactly the case worth seeing (dead feed vs quiet feed).
        attempted: Dict[str, int] = getattr(scraper, "attempted_counts", None) or {}
        failed = getattr(scraper, "failed_feeds", None) or set()
        if attempted:
            for sub, count in sorted(attempted.items()):
                suffix = " (FAILED)" if sub in failed else ""
                self.console.print(
                    f"      {self.icons['detail']} {sub}: {count}{suffix}"
                )
        else:
            sub_counts: Dict[str, int] = defaultdict(int)
            for item in items:
                sub_counts[self._sub_source_label(item)] += 1
            if len(sub_counts) > 1:
                for sub, count in sorted(sub_counts.items()):
                    self.console.print(f"      {self.icons['detail']} {sub}: {count}")

        return SourceFetchOutcome(
            source_name=name,
            status="success" if items else "empty",
            items=items,
        )

    @staticmethod
    def _sub_source_label(item: ContentItem) -> str:
        """Return a human-readable sub-source label for an item."""
        meta = item.metadata
        if meta.get("subreddit"):
            return f"r/{meta['subreddit']}"
        if meta.get("feed_name"):
            return meta["feed_name"]
        if meta.get("channel"):
            return f"@{meta['channel']}"
        if meta.get("period") and meta.get("repo"):
            return f"ossinsight:{meta.get('primary_language', 'all')}"
        if meta.get("repo"):
            return meta["repo"]
        if meta.get("watchlist"):
            return meta["watchlist"]
        if meta.get("source_name"):
            return meta["source_name"]
        if meta.get("gn_query"):
            return f"google_news:{meta['gn_query']}"
        if meta.get("domain"):
            return meta["domain"]
        return item.author or "unknown"

    def merge_cross_source_duplicates(self, items: List[ContentItem]) -> List[ContentItem]:
        """Merge items that point to the same URL from different sources.

        This is a stable stage helper for integrations such as MCP.

        Keeps the item with the richest content and combines metadata.

        Args:
            items: Items to deduplicate

        Returns:
            List[ContentItem]: Deduplicated items
        """
        # Group by normalized URL
        url_groups: Dict[tuple[object, ...], List[ContentItem]] = {}
        for item in items:
            if isinstance(item.profile, list):
                requested_profile: object = tuple(
                    profile_id.strip() for profile_id in item.profile
                )
            else:
                requested_profile = (item.profile or "auto").strip() or "auto"
            key = (*_deduplication_url_key(str(item.url)), requested_profile)
            url_groups.setdefault(key, []).append(item)

        merged = []
        for group in url_groups.values():
            group_copies = [item.model_copy(deep=True) for item in group]
            if len(group) == 1:
                merged.append(group_copies[0])
                continue

            # Pick the item with the richest content as primary
            primary = max(group_copies, key=lambda x: len(x.content or ""))

            # Merge metadata and source info from other items
            all_sources = []
            for item in group_copies:
                if item.source_type.value not in all_sources:
                    all_sources.append(item.source_type.value)
                # Merge metadata (engagement, discussion, etc.)
                for mk, mv in item.metadata.items():
                    if mk not in primary.metadata or not primary.metadata[mk]:
                        primary.metadata[mk] = mv

                # Append content (e.g., comments from another source)
                if item is not primary and item.content:
                    if primary.content and item.content not in primary.content:
                        primary.content = (primary.content or "") + f"\n\n--- From {item.source_type.value} ---\n" + item.content

            primary.metadata["merged_sources"] = all_sources
            merged.append(primary)

        return merged

    async def merge_topic_duplicates(
        self,
        items: List[ContentItem],
        *,
        log: bool = True,
    ) -> List[ContentItem]:
        """Merge items covering the same topic using AI semantic deduplication.

        This is a stable stage helper for integrations such as MCP.

        Sends all item titles, tags, and summaries to AI in a single call.
        Items must already be sorted by analysis score descending so that the first
        item in each duplicate group is always the highest-scored one.
        Content (comments) from duplicate items is merged into the primary.

        Falls back to returning items unchanged if the AI call fails.
        """
        if len(items) <= 1:
            return items

        from .ai.prompting.deduplication import TOPIC_DEDUP_SYSTEM, TOPIC_DEDUP_USER
        from .ai.utils import parse_json_response

        # Build the item list for the prompt
        lines = []
        for i, item in enumerate(items):
            analysis = item.processing.analysis if item.processing else None
            tags = ", ".join(analysis.tags) if analysis and analysis.tags else "—"
            summary = analysis.summary if analysis else "—"
            lines.append(f"[{i}] {item.title}\n    Tags: {tags}\n    Summary: {summary}")
        items_text = "\n\n".join(lines)

        try:
            ai_client = create_ai_client(self.config.ai)
            response = await ai_client.complete(
                system=TOPIC_DEDUP_SYSTEM,
                user=TOPIC_DEDUP_USER.format(items=items_text),
            )
            result = parse_json_response(response)
            if result is None:
                if log:
                    self.console.print("[yellow]  dedup: could not parse AI response, skipping[/yellow]")
                return items

            duplicate_groups = result.get("duplicates", [])
        except Exception as e:
            if log:
                self.console.print(f"[yellow]  dedup: AI call failed ({e}), skipping[/yellow]")
            return items

        if not duplicate_groups:
            return items

        # Build a set of indices to drop (all non-primary duplicates)
        drop_indices: set[int] = set()
        for group in duplicate_groups:
            if not isinstance(group, list) or len(group) < 2:
                continue
            primary_idx = group[0]
            if primary_idx < 0 or primary_idx >= len(items):
                continue
            primary = items[primary_idx]
            for dup_idx in group[1:]:
                if not isinstance(dup_idx, int) or dup_idx < 0 or dup_idx >= len(items):
                    continue
                if dup_idx == primary_idx:
                    continue
                dup = items[dup_idx]
                # Merge comments/content from the duplicate into the primary
                if dup.content:
                    if not primary.content or dup.content not in primary.content:
                        label = dup.source_type.value
                        primary.content = (primary.content or "") + f"\n\n--- From {label} ---\n{dup.content}"
                if log:
                    self.console.print(
                        f"   [dim]dedup: keep [{primary_idx}] {primary.title}[/dim]\n"
                        f"   [dim]       drop [{dup_idx}] {dup.title}[/dim]"
                    )
                drop_indices.add(dup_idx)

        return [item for i, item in enumerate(items) if i not in drop_indices]

    async def filter_items(
        self,
        items: List[ContentItem],
        *,
        threshold: Optional[float] = None,
        topic_dedup: bool = True,
        apply_balance: bool = True,
        log: bool = True,
    ) -> FilteringPipelineResult:
        """Apply score thresholding, optional topic dedup, and digest balancing."""
        threshold_items = []
        for item in items:
            if self.passes_profile_filter(item, threshold):
                threshold_items.append(item)
        threshold_items.sort(
            key=lambda item: (
                item.processing.analysis.score
                if item.processing and item.processing.analysis and item.processing.analysis.score is not None
                else -1
            ),
            reverse=True,
        )

        if log:
            self.console.print(
                f"{self.icons['filter']} Selected {len(threshold_items)} items "
                "with profile filters\n"
            )

        deduped_items = threshold_items
        if topic_dedup and deduped_items:
            profile_groups: Dict[str, List[ContentItem]] = defaultdict(list)
            for item in deduped_items:
                profile_id = (
                    item.processing.classification.profile
                    if item.processing
                    else self.profiles.default_profile
                )
                profile_groups[profile_id].append(item)
            deduped_items = []
            for profile_id, profile_items in profile_groups.items():
                settings = self.config.processing.profile_settings.get(profile_id)
                if settings is None or settings.topic_dedup:
                    deduped_items.extend(
                        await self.merge_topic_duplicates(profile_items, log=log)
                    )
                else:
                    deduped_items.extend(profile_items)
            deduped_items.sort(
                key=lambda item: (
                    item.processing.analysis.score
                    if item.processing
                    and item.processing.analysis
                    and item.processing.analysis.score is not None
                    else -1
                ),
                reverse=True,
            )
        topic_dedup_removed = len(threshold_items) - len(deduped_items)

        if log and topic_dedup_removed:
            self.console.print(
                f"{self.icons['cleanup']} Removed {topic_dedup_removed} topic duplicates "
                f"→ {len(deduped_items)} unique items\n"
            )

        balanced_digest = (
            self.apply_balanced_digest(deduped_items, log=log)
            if apply_balance
            else BalancedDigestResult(items=deduped_items)
        )
        return FilteringPipelineResult(
            items=balanced_digest.items,
            threshold_count=len(threshold_items),
            topic_dedup_count=len(deduped_items),
            topic_dedup_removed=topic_dedup_removed,
            balanced_digest=balanced_digest,
        )

    def _selection_settings(self) -> SelectionSettings:
        config = self.config.selection
        return SelectionSettings(
            gate_model=config.gate_model,
            rank_model=config.rank_model,
            defend_model=config.defend_model,
            gate_effort=config.gate_effort,
            rank_effort=config.rank_effort,
            defend_effort=config.defend_effort,
            gate_batch_size=config.gate_batch_size,
            rank_chunk_size=config.rank_chunk_size,
            rank_carry=config.rank_carry,
            consider=config.consider,
            max_publish=config.max_publish,
            defend_concurrency=config.defend_concurrency,
            use_batch=config.use_batch,
        )

    def _theme_questions(self) -> Dict[str, str]:
        """Each theme's own question, taken from its profile, for the prompts."""
        questions = {}
        for profile_id in self.config.processing.profile_settings:
            try:
                profile = self.profiles.get(profile_id)
            except Exception:
                continue
            questions[profile_id] = (profile.analysis_prompt or "").strip()[:600]
        return questions

    async def select_by_ranking(
        self, items: List[ContentItem]
    ) -> tuple[List[ContentItem], object]:
        """Choose the edition by comparative ranking rather than by threshold.

        Returns the selected items in rank order, plus the selection result for
        reporting. Items keep their pipeline identity: selection works on its own
        Candidate type and the ids map back here, which is what keeps the module
        free of engine imports.
        """
        candidates = to_candidates(items)
        by_id = {item.id: item for item in items}

        async def analyse_survivors(kept):
            """Score only what the gate kept, then hand the results back.

            The gate reads titles and raw content, which `to_candidates`
            already falls back to, so it never needed the analysis pass. Rank
            and defend read better with a model-written summary, so the
            scoring happens here rather than being dropped: after the cheap
            filter, before the expensive comparison.
            """
            survivors = [by_id[c.id] for c in kept if c.id in by_id]
            if not survivors:
                return kept
            await self.analyze_items(survivors)
            self.console.print(
                f"{self.icons['ai']} Analyzed {len(survivors)} items with AI "
                f"(the gate's survivors, not all {len(items)})\n"
            )
            refreshed = {c.id: c for c in to_candidates(survivors)}
            # Preserve the gate's order and its theme decision, which the
            # rebuilt candidates do not carry.
            return [
                refreshed[c.id].with_theme(c.theme) if c.theme else refreshed[c.id]
                for c in kept
                if c.id in refreshed
            ]

        result = await run_selection(
            candidates,
            create_ai_client(self.config.ai),
            self._theme_questions(),
            self._selection_settings(),
            after_gate=analyse_survivors,
        )

        by_id = {item.id: item for item in items}
        selected: List[ContentItem] = []
        for candidate in result.selected:
            item = by_id.get(candidate.id)
            if item is None:
                continue
            # Record the theme the gate chose so the digest can group by it.
            if candidate.theme and item.processing:
                item.processing.classification.profile = candidate.theme
            selected.append(item)

        # Format kept stable: scripts/check_run_health.py parses this line to
        # build the funnel. Selection replaces the threshold and digest-cap
        # stages, so without it the footer would report no published count at
        # all and stop explaining the page it sits on.
        self.console.print(
            f"{self.icons['filter']} Selection: {len(items)} gated to "
            f"{result.gate_kept}, {len(result.ranked_ids)} ranked, "
            f"{result.defend_rejected} rejected by floor, "
            f"{len(selected)} published\n"
        )
        return selected, result

    async def select_digest_items(
        self,
        items: List[ContentItem],
        *,
        threshold: Optional[float] = None,
        topic_dedup: bool = True,
        log: bool = True,
    ) -> FilteringPipelineResult:
        """Select final digest items using the same stages for every entry point."""
        initial = await self.filter_items(
            items,
            threshold=threshold,
            topic_dedup=topic_dedup,
            apply_balance=False,
            log=log,
        )
        candidates = initial.items
        await self._expand_twitter_discussion(candidates)

        # Targeted re-analysis can lower a score, so reapply profile filters.
        eligible = [
            item
            for item in candidates
            if self.passes_profile_filter(item, threshold)
        ]
        eligible.sort(
            key=lambda item: (
                item.processing.analysis.score
                if item.processing
                and item.processing.analysis
                and item.processing.analysis.score is not None
                else -1
            ),
            reverse=True,
        )
        balanced = self.apply_balanced_digest(eligible, log=log)
        return FilteringPipelineResult(
            items=balanced.items,
            threshold_count=initial.threshold_count,
            topic_dedup_count=initial.topic_dedup_count,
            topic_dedup_removed=initial.topic_dedup_removed,
            balanced_digest=balanced,
            eligible_count=len(eligible),
        )

    def passes_profile_filter(
        self,
        item: ContentItem,
        threshold: Optional[float] = None,
    ) -> bool:
        if not item.processing or not item.processing.analysis:
            return False
        profile_id = item.processing.classification.profile
        settings = self.config.processing.profile_settings.get(profile_id)
        effective_threshold = threshold
        if effective_threshold is None and settings is not None:
            effective_threshold = settings.threshold
        if effective_threshold is None:
            return True
        score = item.processing.analysis.score
        return score is not None and score >= effective_threshold

    def _reserve_profile_slots(
        self,
        selected: List[tuple[ContentItem, str]],
        profile_limits: Dict[str, int],
        max_items: Optional[int],
    ) -> List[tuple[ContentItem, str]]:
        """Fill each profile's reserved slots first, then backfill by score.

        `selected` arrives sorted by score, so taking the first N of a profile
        takes its best N. Profiles with no configured limit take part only in
        the backfill. Unused slots are given back, so a day when a theme finds
        nothing produces a full edition rather than a short one.
        """
        taken: Dict[str, int] = defaultdict(int)
        reserved: List[tuple[ContentItem, str]] = []
        spare: List[tuple[ContentItem, str]] = []

        for entry in selected:
            profile_id = (
                entry[0].processing.classification.profile
                if entry[0].processing and entry[0].processing.classification
                else self.profiles.default_profile
            )
            limit = profile_limits.get(profile_id)
            if limit is not None and taken[profile_id] < limit:
                taken[profile_id] += 1
                reserved.append(entry)
            else:
                spare.append(entry)

        if max_items is None:
            kept = reserved + spare
        else:
            # Reserved items keep their places even past the cap: a guarantee
            # that a global cut can overturn is not a guarantee.
            room = max_items - len(reserved)
            kept = reserved + (spare[:room] if room > 0 else [])

        # Hand back a score-ordered list, which is what every stage downstream
        # assumes, including the order items appear in within a theme.
        return sorted(
            kept,
            key=lambda entry: (
                entry[0].processing.analysis.score
                if entry[0].processing
                and entry[0].processing.analysis
                and entry[0].processing.analysis.score is not None
                else -1
            ),
            reverse=True,
        )

    def apply_balanced_digest(
        self,
        items: List[ContentItem],
        *,
        log: bool = True,
    ) -> BalancedDigestResult:
        """Apply configured category quotas and the final item cap.

        Categories are read from ``item.metadata["category"]``. If a category
        appears in more than one configured group, the first group in config
        order wins.
        """
        digest = self.config.digest
        groups = digest.category_groups
        max_items = digest.max_items
        profile_limits = digest.profile_limits

        if not groups and max_items is None and not profile_limits:
            return BalancedDigestResult(items=items)

        sorted_items = sorted(
            items,
            key=lambda item: (
                item.processing.analysis.score
                if item.processing and item.processing.analysis and item.processing.analysis.score is not None
                else -1
            ),
            reverse=True,
        )

        category_to_group: Dict[str, str] = {}
        duplicate_categories: List[str] = []
        for group_key, group in groups.items():
            for category in group.categories:
                if category in category_to_group:
                    if category_to_group[category] != group_key:
                        duplicate_categories.append(category)
                    continue
                category_to_group[category] = group_key

        if log:
            for category in sorted(set(duplicate_categories)):
                first_group = category_to_group[category]
                self.console.print(
                    f"[yellow]Warning: category '{category}' is configured in multiple "
                    f"groups; using '{first_group}'.[/yellow]"
                )

        selected: List[tuple[ContentItem, str]] = []
        group_counts: Dict[str, int] = defaultdict(int)
        default_group = digest.default_group

        for item in sorted_items:
            category = item.metadata.get("category")
            group_key = (
                category_to_group.get(category, default_group)
                if isinstance(category, str)
                else default_group
            )

            if group_key in groups:
                limit = groups[group_key].limit
            else:
                limit = digest.default_group_limit

            if limit is not None and group_counts[group_key] >= limit:
                continue

            selected.append((item, group_key))
            group_counts[group_key] += 1

        # Reserve each profile its slots before the global cut. The cut is by
        # score across every profile, so without this a theme publishing at 7.0
        # takes the whole edition and a theme whose bar is 6.5 never appears,
        # however many of its items cleared. Seen on 2026-08-18: 24 of 24
        # published items came from one theme while two themes showed nothing.
        if profile_limits:
            selected = self._reserve_profile_slots(
                selected, profile_limits, max_items
            )
        elif max_items is not None:
            selected = selected[:max_items]

        final_counts: Dict[str, int] = defaultdict(int)
        for _, group_key in selected:
            final_counts[group_key] += 1

        group_limits: Dict[str, Optional[int]] = {
            group_key: group.limit for group_key, group in groups.items()
        }
        group_limits.setdefault(default_group, digest.default_group_limit)

        if log:
            self.console.print(
                f"{self.icons['balance']} Balanced digest selected "
                f"{len(selected)}/{len(items)} items"
            )
            for group_key, group in groups.items():
                label = group.name or group_key
                self.console.print(
                    f"      {self.icons['detail']} {label}: "
                    f"{final_counts.get(group_key, 0)}/{group.limit}"
                )
            if (
                final_counts.get(default_group, 0)
                or digest.default_group_limit is not None
            ):
                limit_label = (
                    str(digest.default_group_limit)
                    if digest.default_group_limit is not None
                    else "unlimited"
                )
                self.console.print(
                    f"      {self.icons['detail']} {default_group}: "
                    f"{final_counts.get(default_group, 0)}/{limit_label}"
                )
            self.console.print("")

        return BalancedDigestResult(
            items=[item for item, _ in selected],
            enabled=True,
            group_counts=dict(final_counts),
            group_limits=group_limits,
            duplicate_categories=sorted(set(duplicate_categories)),
        )

    async def _expand_twitter_discussion(self, items: List[ContentItem]) -> None:
        """Second-stage: fetch reply text for important Twitter items and re-analyze.

        Only runs when sources.twitter.fetch_reply_text is True.
        Bounded by max_tweets_to_expand to control cost.
        """
        tw_cfg = self.config.sources.twitter
        if not tw_cfg or not tw_cfg.enabled or not tw_cfg.fetch_reply_text:
            return

        from .models import SourceType

        twitter_items = [
            item for item in items
            if item.source_type == SourceType.TWITTER
        ][:tw_cfg.max_tweets_to_expand]

        if not twitter_items:
            return

        self.console.print(
            f"{self.icons['discussion']} Fetching reply text for "
            f"{len(twitter_items)} Twitter items..."
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            if tw_cfg.mode == "playwright":
                self.console.print(
                    "   [yellow]Reply expansion not yet supported in Playwright mode.[/yellow]"
                )
                return
            scraper = TwitterScraper(tw_cfg, client)
            expanded = []
            for item in twitter_items:
                try:
                    reply_lines = await scraper.fetch_replies_for_item(item)
                    if TwitterScraper.append_discussion_content(item, reply_lines):
                        expanded.append(item)
                        self.console.print(
                            f"   {self.icons['discussion']} {len(reply_lines)} replies "
                            f"added to: {item.title[:60]}"
                        )
                except Exception as exc:
                    self.console.print(
                        f"   [yellow]{self.icons['warning']} Reply fetch failed for "
                        f"{item.id}: {exc}[/yellow]"
                    )

        if not expanded:
            return

        self.console.print(
            f"   Re-analyzing {len(expanded)} Twitter items with reply context...\n"
        )
        ai_client = create_ai_client(self.config.ai)
        analyzer = ContentAnalyzer(ai_client, self.profiles, console=self.console)
        await analyzer.analyze_batch(expanded)

    async def _commentary_angles(
        self, *, title: str, theme: str, profile_id: str, body: str
    ) -> List[dict]:
        """Three ranked angles for the day's candidate, from one model call.

        Worth the call. The first version reused the item's block headings and
        stopped working the day those headings were fixed per theme, because
        two of the three then read the same every day. A heading says what a
        passage is about; an angle is a claim someone would defend. One cannot
        stand in for the other.

        The published commentary is the ledger. Reading its titles keeps the
        proposal from offering back something already written, and needs no
        store beyond the files themselves.

        Returns an empty list on any failure. A missing proposal is a quiet
        notification; a broken one would cost the digest.
        """
        from pathlib import Path

        from .ai.prompting.commentary import (
            ANGLE_SCHEMA,
            angles_system,
            angles_user,
        )

        already: List[str] = []
        for path in sorted(Path("docs/_commentary").glob("*.md")):
            if path.name in {"README.md", "template.md"}:
                continue
            for line in path.read_text(encoding="utf-8").splitlines()[:12]:
                if line.startswith("title:"):
                    already.append(line.split(":", 1)[1].strip().strip('"'))
                    break

        try:
            client = create_ai_client(self.config.ai)
            raw = await client.complete(
                angles_system(),
                angles_user(
                    title=title,
                    theme=theme,
                    theme_question=self._theme_questions().get(profile_id, ""),
                    body=body[:4000],
                    already_written=already,
                ),
                schema=ANGLE_SCHEMA,
            )
            angles = json.loads(raw).get("angles") or []
            return [
                {
                    "claim": str(a.get("claim", "")).strip(),
                    "audience": str(a.get("audience", "")).strip(),
                    "rank_reason": str(a.get("rank_reason", "")).strip(),
                }
                for a in angles
                if str(a.get("claim", "")).strip()
            ][:3]
        except Exception as exc:  # noqa: BLE001
            self.console.print(
                f"[yellow]{self.icons['warning']} Could not draft commentary "
                f"angles: {exc}[/yellow]"
            )
            return []

    async def _write_commentary_proposal(
        self,
        summarizer: DailySummarizer,
        items: List[ContentItem],
        lang: str,
        *,
        edition_url: str,
    ) -> None:
        """Pick the day's commentary candidate and write it for the notifier.

        The owner wants a pipeline of things to write about rather than a
        blank page each morning, and the choice was happening at a keyboard.

        No model call. The angles come from the item's own enrichment blocks,
        which already answer the commentary's beats: the first block names the
        belief being challenged, the rest name who is exposed and what to do.
        Assembling what the run already produced costs nothing and keeps the
        proposal honest about what the radar actually found.

        Selection follows `digest.profile_order`, which is the owner's stated
        preference. Score is not the tiebreak because it does not separate:
        published items are almost always 7.0.
        """
        from pathlib import Path

        if not items:
            return
        order = self.config.digest.profile_order or []

        def rank_key(item: ContentItem) -> tuple:
            profile_id = (
                item.processing.classification.profile
                if item.processing and item.processing.classification
                else ""
            )
            place = order.index(profile_id) if profile_id in order else len(order)
            score = (
                item.processing.analysis.score
                if item.processing and item.processing.analysis
                and item.processing.analysis.score is not None
                else 0.0
            )
            return (place, -score)

        pick = sorted(items, key=rank_key)[0]
        artifact = pick.processing.artifacts.get(lang) if pick.processing else None
        analysis = pick.processing.analysis if pick.processing else None
        profile_id = (
            pick.processing.classification.profile
            if pick.processing and pick.processing.classification
            else ""
        )

        angles = await self._commentary_angles(
            title=artifact.title if artifact else pick.title,
            theme=summarizer.profile_name(profile_id, lang),
            profile_id=profile_id,
            body="\n\n".join(
                f"{b.title}: {' '.join(str(b.content).split())}"
                for b in (artifact.blocks if artifact else [])
            ) or (analysis.summary if analysis else ""),
        )

        payload = {
            "title": artifact.title if artifact else pick.title,
            "theme": summarizer.profile_name(profile_id, lang),
            "score": analysis.score if analysis else None,
            "url": str(pick.url),
            "item_url": f"/item/{self._item_slug(pick.title, '')}/",
            "edition_url": edition_url,
            "plain": " ".join(
                str(
                    next(
                        (b.content for b in artifact.blocks if b.primary),
                        analysis.summary if analysis else "",
                    )
                    if artifact
                    else (analysis.summary if analysis else "")
                ).split()
            )[:320],
            "angles": angles[:3],
        }
        try:
            Path("commentary_proposal.json").write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            self.console.print(
                f"{self.icons['document']} Commentary candidate: "
                f"{payload['theme']}, {payload['title'][:60]}\n"
            )
        except Exception as exc:  # noqa: BLE001
            self.console.print(
                f"[yellow]{self.icons['warning']} Could not write the "
                f"commentary proposal: {exc}[/yellow]\n"
            )

    @staticmethod
    def _item_slug(title: str, fallback: str) -> str:
        """A stable, readable filename fragment for an item's own page."""
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        slug = "-".join(slug.split("-")[:9])[:70].strip("-")
        return slug or fallback

    def _write_item_pages(
        self,
        summarizer: DailySummarizer,
        items: List[ContentItem],
        *,
        today: str,
        run_time: str,
        lang: str,
        edition_url: str,
        edition_title: str,
        published_at: datetime,
    ) -> int:
        """Write each published item as its own Jekyll document.

        The digest is one markdown blob per run, which is why the site could
        only ever lead with a log of runs. Giving every item a document lets
        the homepage group by theme, gives each theme an archive, and gives an
        item a permalink that can be linked to on its own.

        A failure here costs the item pages and leaves the digest intact, so it
        never takes the run down with it.
        """
        from pathlib import Path

        items_dir = Path("docs/_items")
        items_dir.mkdir(parents=True, exist_ok=True)
        view = summarizer.build_view(items, lang)
        written = 0

        for group in view.groups:
            for view_item in group.items:
                item = view_item.item
                try:
                    body = summarizer.render_item_body(item, lang)
                    slug = self._item_slug(view_item.title, view_item.anchor_id)
                    name = f"{today}-{run_time}-{view_item.global_index:02d}-{slug}-{lang}.md"
                    artifact = (
                        item.processing.artifacts.get(lang)
                        if item.processing
                        else None
                    )
                    front = [
                        "---",
                        "layout: item",
                        f"title: {json.dumps(view_item.title)}",
                        f"date: {published_at.strftime('%Y-%m-%d %H:%M:%S %z')}",
                        f"lang: {lang}",
                        f"theme: {group.profile_id}",
                        f"theme_name: {json.dumps(group.name)}",
                        # Quoted: an item with no analysis scores "?", and a bare
                        # "?" is not a valid YAML scalar.
                        f"score: {json.dumps(view_item.score)}",
                        f"link: {json.dumps(str(item.url))}",
                        f"source: {json.dumps(self._sub_source_label(item))}",
                        f"edition_url: {json.dumps(edition_url)}",
                        f"edition_title: {json.dumps(edition_title)}",
                        # An item whose second pass failed publishes with a
                        # headline and no background. Say so in the data, so
                        # the site can tell the two apart.
                        f"enriched: {'true' if artifact else 'false'}",
                        "---",
                        "",
                    ]
                    dest = safe_output_path(items_dir, name)
                    with open(dest, "w", encoding="utf-8") as f:
                        f.write("\n".join(front) + body)
                    written += 1
                except Exception as exc:  # noqa: BLE001
                    self.console.print(
                        f"[yellow]{self.icons['warning']} Could not write item "
                        f"page for {item.id}: {exc}[/yellow]"
                    )
        return written

    async def enrich_items(self, items: List[ContentItem]) -> EnrichmentBatchResult:
        """Enrich items with background knowledge (2nd AI pass).

        For each item that passed the score threshold, call AI to generate
        background knowledge based on the item's actual content.

        Args:
            items: Important items to enrich (modified in-place)
        """
        if not items:
            return EnrichmentBatchResult()

        self.console.print(
            f"{self.icons['enrich']} Enriching with background knowledge..."
        )
        ai_client = create_ai_client(self.config.ai)
        enricher = ContentEnricher(
            ai_client,
            self.profiles,
            self.config.ai.languages,
            console=self.console,
        )
        result = await enricher.enrich_batch(items)
        self.console.print(
            f"   Enriched {result.succeeded_count}/{len(items)} items"
        )
        if result.failed_count:
            self.console.print(
                f"   [yellow]Skipped {result.failed_count} items after enrichment "
                f"failed: {', '.join(result.failed_ids)}[/yellow]"
            )
        self.console.print("")
        return result

    async def analyze_items(self, items: List[ContentItem]) -> List[ContentItem]:
        """Analyze content items with AI.

        Args:
            items: Items to analyze

        Returns:
            List[ContentItem]: Analyzed items
        """
        self.console.print(f"{self.icons['ai']} Analyzing content with AI...")

        ai_client = create_ai_client(self.config.ai)
        analyzer = ContentAnalyzer(ai_client, self.profiles, console=self.console)

        return await analyzer.analyze_batch(items)

    async def _generate_summary(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        language: str = "en",
    ) -> str:
        """Generate daily summary.

        Args:
            items: Important items to include (already enriched with background/related)
            date: Date string
            total_fetched: Total items fetched
            language: Output language ("en" or "zh")

        Returns:
            str: Markdown summary
        """
        self.console.print(f"{self.icons['summary']} Generating daily summary...")

        summarizer = DailySummarizer(
            profile_names=self.profiles.names,
            profile_order=self.config.digest.profile_order,
            block_titles=self.profiles.block_titles,
        )

        return await summarizer.generate_summary(items, date, total_fetched, language=language)
