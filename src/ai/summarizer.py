"""Daily summary generation — pure programmatic rendering."""

import html
import re
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import quote, urlsplit

from .localization import normalize_language
from ..models import ContentItem


_CJK = r"[\u4e00-\u9fff\u3400-\u4dbf]"
_ASCII = r"[A-Za-z0-9]"
_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()<>#!|])")
_MARKDOWN_BLOCK_START = re.compile(r"(?m)^( {0,3})(>|[-+] |\d+[.)] )")
_URL_SAFE_CHARS = ":/?#[]@!$&'*,;=~%+"


def _escape_markdown(value: object) -> str:
    """Render untrusted text literally while retaining its readable content."""
    escaped = html.escape(str(value), quote=True)
    escaped = _MARKDOWN_SPECIAL.sub(r"\\\1", escaped)
    return _MARKDOWN_BLOCK_START.sub(r"\1\\\2", escaped)


def _safe_url(value: object) -> Optional[str]:
    """Return an HTML/Markdown-safe HTTP(S) URL, or None for unsafe URLs."""
    raw = str(value).strip()
    if not raw or any(ord(char) < 32 or ord(char) == 127 for char in raw):
        return None
    try:
        parsed = urlsplit(raw)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            return None
        parsed.port
    except (TypeError, ValueError):
        return None
    encoded = quote(raw, safe=_URL_SAFE_CHARS)
    return html.escape(encoded, quote=True)


def _pangu(text: str) -> str:
    """Insert a space between CJK and ASCII letters/digits (Pangu spacing)."""
    text = re.sub(rf"({_CJK})({_ASCII})", r"\1 \2", text)
    text = re.sub(rf"({_ASCII})({_CJK})", r"\1 \2", text)
    return text


LABELS = {
    "en": {
        "header": "Horizon Daily",
        "source": "Source",
        "background": "Background",
        "discussion": "Discussion",
        "references": "References",
        "tags": "Tags",
        "selected_items": "From {total} items, {selected} important content pieces were selected",
        # A quiet day is an editorial outcome and should read as one. The
        # inherited copy here addressed the operator of a tool, telling the
        # reader their information sources needed expansion and inviting them
        # to check whether the AI was working, on a page linked from a public
        # profile. Owner's words, with the order doing the work: the count
        # establishes that the run happened and the bar held, before anything
        # is asked of the reader.
        "empty_analyzed": "{total} items were analyzed and scored today, and none cleared the bar.",
        "empty_body": (
            "See the [method](/method/) for how the bar is set.\n\n"
            "If you saw something today that my radar missed, tell me on "
            "[LinkedIn](https://www.linkedin.com/in/bracoelho/).\n"
        ),
    },
    "zh": {
        "header": "Horizon 每日速递",
        "source": "来源",
        "background": "背景",
        "discussion": "社区讨论",
        "references": "参考链接",
        "tags": "标签",
        "selected_items": "从 {total} 条内容中筛选出 {selected} 条重要资讯。",
        # Same three beats as the English, and drops 阈值 the way the English
        # drops "threshold". Dormant: ai.languages is ["en"], so this has
        # never rendered. It wants a native read before Chinese is enabled.
        "empty_analyzed": "今天分析并评分了 {total} 条内容，没有一条达到标准。",
        "empty_body": (
            "评分标准见[方法](/method/)。\n\n"
            "如果今天有你认为重要、而本雷达未能捕捉的内容，"
            "欢迎在 [LinkedIn](https://www.linkedin.com/in/bracoelho/) 上告诉我。\n"
        ),
    },
}


@dataclass(frozen=True)
class SummaryItemView:
    item: ContentItem
    index: int
    global_index: int
    group_count: int
    title: str
    score: float | str
    anchor_id: str


@dataclass(frozen=True)
class SummaryGroupView:
    profile_id: str
    name: str
    items: List[SummaryItemView]


@dataclass(frozen=True)
class DailySummaryView:
    groups: List[SummaryGroupView]
    item_count: int


class DailySummarizer:
    """Generates daily Markdown summaries from pre-analyzed content items."""

    def __init__(
        self,
        profile_names: Optional[Dict[str, Dict[str, str]]] = None,
        profile_order: Optional[List[str]] = None,
    ):
        self.profile_names = profile_names or {}
        self.profile_order = profile_order or []

    @staticmethod
    def _profile_id(item: ContentItem) -> str:
        if item.processing:
            return item.processing.classification.profile
        return item.profile if isinstance(item.profile, str) else "unclassified"

    def profile_name(self, profile_id: str, language: str) -> str:
        names = self.profile_names.get(profile_id, {})
        return names.get(
            language,
            names.get(
                "default",
                profile_id.replace("-", " ").replace("_", " ").title(),
            ),
        )

    def build_view(
        self,
        items: List[ContentItem],
        language: str,
    ) -> DailySummaryView:
        grouped_items: Dict[str, List[ContentItem]] = {}
        for item in items:
            grouped_items.setdefault(self._profile_id(item), []).append(item)

        ordered_groups = list(grouped_items.items())
        if self.profile_order:
            order = {
                profile_id: index
                for index, profile_id in enumerate(self.profile_order)
            }
            ordered_groups = sorted(
                ordered_groups,
                key=lambda group: order.get(group[0], len(order)),
            )

        groups = []
        global_index = 1
        for profile_id, profile_items in ordered_groups:
            view_items = []
            for index, item in enumerate(profile_items, start=1):
                artifact = (
                    item.processing.artifacts.get(language)
                    if item.processing
                    else None
                )
                analysis = item.processing.analysis if item.processing else None
                view_items.append(
                    SummaryItemView(
                        item=item,
                        index=index,
                        global_index=global_index,
                        group_count=len(profile_items),
                        title=normalize_language(
                            artifact.title if artifact else item.title, language
                        ),
                        score=(
                            analysis.score
                            if analysis and analysis.score is not None
                            else "?"
                        ),
                        anchor_id=self._item_anchor(profile_id, index),
                    )
                )
                global_index += 1
            groups.append(
                SummaryGroupView(
                    profile_id=profile_id,
                    name=normalize_language(
                        self.profile_name(profile_id, language), language
                    ),
                    items=view_items,
                )
            )
        return DailySummaryView(groups=groups, item_count=len(items))

    @staticmethod
    def _item_anchor(profile_id: str, index: int) -> str:
        safe_profile_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", profile_id).strip("-")
        return f"item-{safe_profile_id or 'unclassified'}-{index}"

    async def generate_summary(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        language: str = "en",
        preamble: Optional[str] = None,
    ) -> str:
        """Generate daily summary in Markdown format.

        Items are rendered in score-descending order (already sorted by orchestrator).

        Args:
            items: High-scoring content items (already enriched)
            date: Date string (YYYY-MM-DD)
            total_fetched: Total number of items fetched before filtering
            language: Output language, either "en" or "zh"

        Returns:
            str: Markdown formatted summary
        """
        labels = LABELS.get(language, LABELS["en"])

        if not items:
            return self._generate_empty_summary(date, total_fetched, labels)

        header = (
            f"# {labels['header']} - {date}\n\n"
            f"> {labels['selected_items'].format(total=total_fetched, selected=len(items))}\n\n"
        )
        # The synthesis pass reads the whole edition at once. It sits above the
        # contents so it is the first thing a reader meets, and it is optional:
        # a failed synthesis costs the preamble, never the edition.
        if preamble and preamble.strip():
            header += f"{preamble.strip()}\n\n"
        header += "---\n\n"

        toc_sections = []
        body_sections = []
        view = self.build_view(items, language)
        for group in view.groups:
            profile_name = _escape_markdown(group.name)
            if language == "zh":
                profile_name = _pangu(profile_name)
            toc_entries = [f"**{profile_name}**"]
            for view_item in group.items:
                title = _escape_markdown(view_item.title)
                if language == "zh":
                    title = _pangu(title)
                toc_entries.append(
                    f"{view_item.index}. [{title}](#{view_item.anchor_id}) "
                    f"\u2b50\ufe0f {view_item.score}/10"
                )
            toc_sections.append("\n".join(toc_entries))
            body_sections.append(f"## {profile_name}\n\n")
            body_sections.extend(
                self._format_item(
                    view_item.item,
                    labels,
                    language,
                    view_item.index,
                    heading_level=3,
                    anchor_id=view_item.anchor_id,
                    title_override=view_item.title,
                    score_override=view_item.score,
                )
                for view_item in group.items
            )

        toc = "\n\n".join(toc_sections) + "\n\n---\n\n"
        return normalize_language(header + toc + "".join(body_sections), language)

    def generate_webhook_overview(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        language: str = "en",
    ) -> str:
        """Generate a compact overview for multi-message webhook delivery."""
        labels = LABELS.get(language, LABELS["en"])
        if not items:
            return self._generate_empty_summary(date, total_fetched, labels)

        if language == "zh":
            header = (
                f"# {labels['header']} - {date}\n\n"
                f"> 从 {total_fetched} 条内容中筛选出 {len(items)} 条重要资讯。\n\n"
                "下面会按内容逐条发送详情，你可以只看感兴趣的标题。\n\n"
            )
        else:
            header = (
                f"# {labels['header']} - {date}\n\n"
                f"> Selected {len(items)} important items from {total_fetched} fetched items.\n\n"
                "Details will be sent item by item so you can read only the topics you care about.\n\n"
            )

        sections = []
        view = self.build_view(items, language)
        for group in view.groups:
            profile_name = _escape_markdown(group.name)
            if language == "zh":
                profile_name = _pangu(profile_name)
            entries = [f"**{profile_name}**"]
            for view_item in group.items:
                title = _escape_markdown(view_item.title)
                if language == "zh":
                    title = _pangu(title)
                url = _safe_url(view_item.item.url)
                title_link = f"[{title}]({url})" if url else title
                entries.append(
                    f"{view_item.index}. {title_link} "
                    f"\u2b50\ufe0f {view_item.score}/10"
                )
            sections.append("\n".join(entries))

        return normalize_language(header + "\n\n".join(sections), language)

    def generate_webhook_item(
        self,
        item: ContentItem,
        language: str,
        index: int,
        total: int,
        *,
        title: Optional[str] = None,
        score: float | str | None = None,
    ) -> str:
        """Generate one item message for multi-message webhook delivery."""
        labels = LABELS.get(language, LABELS["en"])
        prefix = f"第 {index}/{total} 条\n\n" if language == "zh" else f"Item {index}/{total}\n\n"
        return normalize_language(
            prefix
            + self._format_item(
                item,
                labels,
                language,
                index,
                title_override=title,
                score_override=score,
            ).rstrip("-\n "),
            language,
        )

    def _format_item(
        self,
        item: ContentItem,
        labels: dict,
        language: str,
        index: int,
        *,
        heading_level: int = 2,
        anchor_id: Optional[str] = None,
        title_override: Optional[str] = None,
        score_override: float | str | None = None,
        include_heading: bool = True,
        include_rule: bool = True,
    ) -> str:
        """Format a single ContentItem into Markdown."""
        artifact = item.processing.artifacts.get(language) if item.processing else None
        analysis = item.processing.analysis if item.processing else None
        _title = title_override or (artifact.title if artifact else item.title)
        title = _escape_markdown(_title)
        raw_url = str(item.url)
        url = _safe_url(raw_url)
        score = (
            score_override
            if score_override is not None
            else analysis.score
            if analysis and analysis.score is not None
            else "?"
        )
        meta = item.metadata

        summary = analysis.summary if not artifact and analysis else ""
        primary_block = (
            next((block for block in artifact.blocks if block.primary), None)
            if artifact
            else None
        )

        summary = _escape_markdown(summary)
        primary_content = (
            _escape_markdown(primary_block.content) if primary_block else ""
        )

        if language == "zh":
            title = _pangu(title)
            summary = _pangu(summary)
            primary_content = _pangu(primary_content)

        # Source line with parts joined by " · ", link appended at end
        source_type = item.source_type.value
        source_parts = [_escape_markdown(source_type)]
        if meta.get("subreddit"):
            source_parts.append(_escape_markdown(f"r/{meta['subreddit']}"))
        if meta.get("feed_name"):
            source_parts.append(_escape_markdown(meta["feed_name"]))
        else:
            source_parts.append(_escape_markdown(item.author or "unknown"))
        if item.published_at:
            if language == "zh":
                source_parts.append(
                    f"{item.published_at.month}月{item.published_at.day}日 "
                    f"{item.published_at:%H:%M}"
                )
            else:
                day = item.published_at.strftime("%d").lstrip("0")
                source_parts.append(item.published_at.strftime(f"%b {day}, %H:%M"))
        source_line = " \u00b7 ".join(source_parts)  # ·

        discussion_url = meta.get("discussion_url")
        if discussion_url:
            safe_discussion_url = _safe_url(discussion_url)
            if safe_discussion_url and str(discussion_url) != raw_url:
                source_line += f' · [{labels["discussion"]}]({safe_discussion_url})'

        title_link = f"[{title}]({url})" if url else title

        lines = (
            [
                f'<a id="{anchor_id or f"item-{index}"}"></a>',
                f"{'#' * heading_level} {title_link} \u2b50\ufe0f {score}/10",  # ⭐️
            ]
            if include_heading
            # An item's own page puts the title, the score and the link in the
            # layout, where they can carry markup a digest heading cannot.
            else []
        )
        if summary.strip():
            lines.extend(["", summary])
        if primary_content.strip():
            lines.extend(["", primary_content])
        lines.extend(["", source_line])

        if artifact:
            for block in artifact.blocks:
                if block.primary:
                    continue
                block_title = _escape_markdown(block.title)
                block_content = _escape_markdown(block.content)
                if language == "zh":
                    block_title = _pangu(block_title)
                    block_content = _pangu(block_content)
                lines.extend(["", f"**「{block_title}」** {block_content}"])

        sources = artifact.sources if artifact else []
        if sources:
            reference_items = []
            for source in sources:
                reference_title = html.escape(source.title, quote=True)
                reference_url = _safe_url(source.url)
                if reference_url:
                    reference_items.append(f'<li><a href="{reference_url}">{reference_title}</a></li>\n')
                else:
                    reference_items.append(f"<li>{reference_title}</li>\n")
            items_html = "".join(reference_items)
            lines += [
                "",
                f'<details><summary>{labels["references"]}</summary>\n<ul>\n{items_html}\n</ul>\n</details>',
            ]

        if analysis and analysis.tags:
            tags_str = ", ".join([f"`#{_escape_markdown(t)}`" for t in analysis.tags])
            lines.append("")
            lines.append(f"**{labels['tags']}**: {tags_str}")

        if include_rule:
            lines.append("")
            lines.append("---")

        return "\n".join(lines).lstrip("\n") + "\n\n"


    def render_item_body(self, item: ContentItem, language: str) -> str:
        """The body of an item's own page: everything below the title.

        The same renderer the digest uses, with the heading and the closing
        rule left off, so an item reads identically in both places and there is
        one place to change how an item looks.
        """
        labels = LABELS.get(language, LABELS["en"])
        return self._format_item(
            item,
            labels,
            language,
            index=1,
            include_heading=False,
            include_rule=False,
        ).strip() + "\n"

    def _generate_empty_summary(self, date: str, total_fetched: int, labels: dict) -> str:
        """Generate summary when no high-scoring items were found."""
        return (
            f"# {labels['header']} - {date}\n\n"
            f"> {labels['empty_analyzed'].format(total=total_fetched)}\n\n"
            + labels["empty_body"]
        )
