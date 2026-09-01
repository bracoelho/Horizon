#!/usr/bin/env python3
"""Post-run health check for Horizon scheduled runs.

Parses the tee'd run log to distinguish "quiet run" from "broken run"
(BACKLOG #5/#6): a digest saying "no items met the threshold" reads
identically whether items scored low or every item silently failed.

Usage:
  python scripts/check_run_health.py horizon-run.log [--append-digest docs/_posts]

Effects:
  - Prints a health report; also writes it to $GITHUB_STEP_SUMMARY when set.
  - Emits GitHub workflow-command annotations (::error/::warning/::notice),
    which surface in the Annotations box at the top of the run page, the
    only surface visible without opening logs or the summary tab.
  - With --append-digest: appends a compact health footer to today's
    digest file(s) (docs/_posts/YYYY-MM-DD-summary-*.md).
  - Writes the error count to health_errors.txt so a later workflow step
    can fail the job AFTER the Pages deploy has published the digest.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
# Downloaded Actions job logs prefix every line with an ISO timestamp that raw
# stdout doesn't have. Strip it so the same script works on either, which
# matters because after-the-fact debugging uses the downloaded job log.
ISO_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T[\d:.]+Z\s?")
TIMESTAMP_RE = re.compile(r"^\[?\d{2}/\d{2}/\d{2}[^]]*\]?\s*")
QUOTED_RE = re.compile(r"'[^']*'|\"[^\"]*\"")
# Match ERROR/WARNING only in the log-level column (line start, or after the
# timestamp bracket, followed by the level's padding) so a story title
# containing the word "ERROR" can't fail the job. This gates the build, so a
# false positive would cry wolf and erode trust in the signal.
ERROR_RE = re.compile(r"(?:^|\])\s*ERROR\s{2,}")
WARNING_RE = re.compile(r"(?:^|\])\s*WARNING\s{2,}")
# GitHub renders ~10 annotations per level per step; group and cap below that.
MAX_ANNOTATIONS = 8
FOUND_RE = re.compile(r"Found (\d+) items? from (.+?)\s*$")
# Per-sub-source breakdown lines, e.g. "      • The Verge - AI: 1" or
# "      • OpenAI News: 0 (FAILED)". Only those printed during fetching are
# collected, the same format is reused later for selected items.
DETAIL_RE = re.compile(r"^\s*•\s*(?P<name>.+?):\s*(?P<count>\d+)(?P<failed>\s*\(FAILED\))?\s*$")
FETCHED_RE = re.compile(r"Fetched (\d+) items? from all sources")
ANALYZED_RE = re.compile(r"Analyzed (\d+) items? with AI")
SELECTED_RE = re.compile(r"Selected (\d+) items? with profile filters")
# The rest of the funnel. Reporting only fetched/analyzed/cleared made the
# footer contradict the page it sits on: a run that cleared 24 and published
# 17 looked like it had lost 7 items, when topic dedup had merged them.
MERGED_RE = re.compile(r"Merged (\d+) cross-source duplicates")
TOPIC_DEDUP_RE = re.compile(r"Removed (\d+) topic duplicates")
BALANCED_RE = re.compile(r"Balanced digest selected (\d+)/(\d+) items")
# Ranked selection replaces the threshold, topic-dedup and digest-cap stages,
# so none of the regexes above fire when it runs. Parsing its one line keeps
# the funnel honest under either selection path.
# The score floor is optional in the pattern so logs written before it existed
# still parse. A health check that stops reading old logs stops being usable on
# exactly the runs somebody is going back to understand.
SELECTION_RE = re.compile(
    r"Selection: (\d+) gated to (\d+), (\d+) ranked, (\d+) rejected by floor, "
    r"(?:(\d+) below the score floor, )?(\d+) published"
)
ENRICHED_RE = re.compile(r"Enriched (\d+)/(\d+) items")
# Emitted by analyze_items. The scores had taken four values in the radar's
# whole history and nothing recorded the shape, so every judging change was
# unmeasurable. See BACKLOG #39/#41.
SCORE_DIST_RE = re.compile(r"Score distribution: (\{.*\})")
# S1's tournament reports its own health each run.
SETWISE_RE = re.compile(r"Setwise: (\d+) picks, (\d+) retried, (\d+) fell back")
# A selection stage that produces nothing logs at WARNING and carries on with a
# fallback, so the 2026-08-20 run published one item and reported success. The
# fallbacks are right, because losing a stage should not lose the day's items,
# but a stage that never ran is a broken run and has to be said out loud.
# Matched only in their total forms: a ranker dropping one id of twenty-five is
# a model being sloppy, and failing the build on that would make the red X
# meaningless again.
COLLAPSE_PATTERNS = (
    (# No capture groups on purpose: the pipeline already applied the
    # half-or-more test before printing this line, so the two-group
    # equality guard below must not second-guess it.
    re.compile(r"Setwise collapse: \d+ of \d+ picks fell back"),
     "The setwise ranker collapsed: half or more of its picks fell back to "
     "arbitrary group order."),
    # Two groups on purpose: the guard below only treats this as a collapse
    # when the counts match. A gate that missed a handful of items still ran,
    # and failing the build on that is how a red X stops being read.
    (re.compile(r"Gate returned no verdict for (\d+) of (\d+) items?"),
     "The gate produced no verdict at all, so every item passed through "
     "unfiltered. The gate did not run."),
    (re.compile(r"Batch \S+ returned 0 of (\d+) results"),
     "A batch returned none of its results. Every entry in it failed."),
    (re.compile(r"Ranker omitted (\d+) of (\d+) ids"),
     "A whole ranking chunk came back empty, so those items were published "
     "or dropped without ever being ranked."),
    # These two print through console.print rather than the logger, so they
    # carry no WARNING column and were invisible here. They are on the live
    # threshold path, unlike the three above.
    (re.compile(r"dedup: could not parse AI response, skipping"),
     "Topic dedup could not parse its response and returned every item "
     "unchanged. Duplicates on the page were not merged, they were never "
     "looked for."),
    (re.compile(r"dedup: AI call failed"),
     "The topic dedup call failed and returned every item unchanged. "
     "Duplicates on the page were never looked for."),
)
TOKENS_RE = re.compile(
    r"Token usage this run: (\d+) tokens \(input: (\d+), output: (\d+)\)"
)
# Log records wrap when rich falls back to 80 columns, putting the item id and
# the actual cause on the lines below the one carrying the ERROR level. The
# workflow now sets COLUMNS so this should not happen, but downloaded logs from
# before that change still wrap, and a long enough message wraps at any width.
CONTINUATION_RE = re.compile(r"^\s{8,}(?![\u2022])\S")
# Item ids vary per failure and would defeat grouping once the continuation is
# joined back on. Collapse them so N failures of one kind stay one signature.
ITEM_ID_RE = re.compile(r"[\w.\-]+:[\w.\-]+:[0-9a-f]{8,}")
HASH_RE = re.compile(r"\b[0-9a-f]{12,}\b")


def parse_log(path: Path):
    per_source: dict[str, int] = {}
    per_feed: dict[str, tuple[int, bool]] = {}
    totals = {
        "fetched": None, "merged": None, "analyzed": None, "selected": None,
        "topic_dupes": None, "published": None, "pre_cap": None,
        "gated": None, "ranked": None, "floor_rejected": None, "below_score": 0,
        "enriched": None, "enrich_attempted": None,
        "tokens": None, "tokens_in": None, "tokens_out": None,
    }
    errors: list[str] = []
    collapsed: list[tuple[str, str]] = []
    warnings = 0
    fetching = True  # detail lines only count before fetching ends
    current_source = None
    open_error: int | None = None  # index in errors awaiting wrapped remainder

    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = ISO_PREFIX_RE.sub("", ANSI_RE.sub("", raw))
        if m := FOUND_RE.search(line):
            current_source = m.group(2)
            per_source[current_source] = int(m.group(1))
        # Only RSS reports what it attempted, so only its breakdown can show a
        # feed that returned nothing. Other scrapers' breakdowns are derived
        # from returned items (Google News lists ~50 publishers), which would
        # bury the signal this section exists for.
        elif fetching and current_source == "RSS Feeds" and (m := DETAIL_RE.match(line)):
            per_feed[m.group("name")] = (int(m.group("count")), bool(m.group("failed")))
        elif m := FETCHED_RE.search(line):
            totals["fetched"] = int(m.group(1))
            fetching = False
        elif m := ANALYZED_RE.search(line):
            totals["analyzed"] = int(m.group(1))
        elif m := SELECTED_RE.search(line):
            totals["selected"] = int(m.group(1))
        elif m := MERGED_RE.search(line):
            totals["merged"] = int(m.group(1))
        elif m := TOPIC_DEDUP_RE.search(line):
            totals["topic_dupes"] = int(m.group(1))
        elif m := BALANCED_RE.search(line):
            totals["published"] = int(m.group(1))
            totals["pre_cap"] = int(m.group(2))
        elif m := SELECTION_RE.search(line):
            totals["gated"] = int(m.group(2))
            totals["ranked"] = int(m.group(3))
            totals["floor_rejected"] = int(m.group(4))
            totals["below_score"] = int(m.group(5)) if m.group(5) else 0
            totals["published"] = int(m.group(6))
        elif m := ENRICHED_RE.search(line):
            totals["enriched"] = int(m.group(1))
            totals["enrich_attempted"] = int(m.group(2))
        elif m := SCORE_DIST_RE.search(line):
            try:
                totals["score_distribution"] = json.loads(m.group(1))
            except json.JSONDecodeError:
                pass  # a malformed line is not worth failing a health report
        elif m := SETWISE_RE.search(line):
            totals["setwise"] = {
                "picks": int(m.group(1)),
                "retried": int(m.group(2)),
                "fallbacks": int(m.group(3)),
            }
        elif m := TOKENS_RE.search(line):
            totals["tokens"] = int(m.group(1))
            totals["tokens_in"] = int(m.group(2))
            totals["tokens_out"] = int(m.group(3))
        if ERROR_RE.search(line):
            errors.append(line.strip()[:200])
            open_error = len(errors) - 1
        elif open_error is not None and CONTINUATION_RE.match(line):
            # A wrapped remainder of the record above: the part that names the
            # item and the cause. Join it back on, capped so a stack trace
            # cannot run away with the annotation.
            errors[open_error] = (errors[open_error] + " " + line.strip())[:400]
        elif line.strip():
            open_error = None
        if WARNING_RE.search(line):
            warnings += 1
        # Checked on every line, not just WARNING records: a stage can announce
        # its own failure through console.print, which carries no log level.
        for pattern, explanation in COLLAPSE_PATTERNS:
            if m := pattern.search(line):
                groups = m.groups()
                # The ranker warns on every omission. Only a chunk that came
                # back entirely empty means the call failed.
                if len(groups) == 2 and groups[0] != groups[1]:
                    continue
                collapsed.append((" ".join(line.split())[:200], explanation))
                break

    return per_source, per_feed, totals, errors, warnings, collapsed


def group_errors(errors: list[str]) -> list[tuple[str, int]]:
    """Collapse per-item errors into distinct signatures with counts.

    Analysis failures repeat once per item with only the item title varying,
    so 74 raw lines are really one problem. Grouping keeps the annotation
    list under GitHub's per-step cap and makes the real failure obvious.
    """
    groups: dict[str, int] = {}
    for line in errors:
        sig = TIMESTAMP_RE.sub("", line)
        sig = QUOTED_RE.sub("'…'", sig)
        sig = ITEM_ID_RE.sub("<item>", sig)
        sig = HASH_RE.sub("<hash>", sig)
        sig = " ".join(sig.split())
        groups[sig] = groups.get(sig, 0) + 1
    return sorted(groups.items(), key=lambda kv: -kv[1])


# Errors that cost an item its depth while still publishing it. These are a
# different kind of event from a broken run, and conflating the two is how a
# build ends up permanently red: every content-producing run between
# 2026-08-17 and 2026-08-18 failed on exactly two of these, out of seventeen
# items published successfully. A red X that appears every day stops being read,
# which is the failure this whole script exists to prevent.
DEGRADING_RE = re.compile(r"Error enriching item")
# Above this share of the items that reached enrichment, a degradation is no
# longer a couple of awkward abstracts; something systemic is wrong with the
# contract or the model, and the run should go red.
DEGRADED_FATAL_SHARE = 0.25


def split_by_severity(grouped, totals):
    """Separate errors that break a run from errors that only thin an item.

    Returns (fatal, degrading, escalated). `escalated` is True when the
    degrading errors are numerous enough to be a systemic problem rather than
    a few items, in which case they count as fatal after all.
    """
    fatal = [(s, c) for s, c in grouped if not DEGRADING_RE.search(s)]
    degrading = [(s, c) for s, c in grouped if DEGRADING_RE.search(s)]

    attempted = totals.get("enrich_attempted")
    degraded_count = sum(c for _, c in degrading)
    escalated = bool(degrading) and (
        not attempted
        or totals.get("enriched") == 0
        or degraded_count / attempted > DEGRADED_FATAL_SHARE
    )
    if escalated:
        fatal = fatal + degrading
        degrading = []
    return fatal, degrading, escalated


def annotate(level: str, message: str) -> None:
    """Emit a workflow command; shows in the run page's Annotations box."""
    clean = message.replace("\r", " ").replace("\n", " ").strip()
    print(f"::{level}::{clean}")


def emit_annotations(per_source, per_feed, totals, grouped, warnings,
                     cadence=None, cadence_gap=False, collapsed=None) -> None:
    headline = (
        f"Radar run: {funnel(totals).replace('**', '')}. "
        f"{sum(c for _, c in grouped)} errors, {warnings} warnings"
    )
    if totals["tokens"]:
        headline += f", {totals['tokens']:,} tokens"
    annotate("notice", headline)

    if note := enrichment_note(totals):
        annotate("warning", note.lstrip("- ").replace("**", ""))

    for line, explanation in collapsed or []:
        annotate("error", f"{explanation} Log line: {line}")

    for line in cadence or []:
        if line.startswith("- 🔴"):
            annotate("error", line.lstrip("- 🔴").replace("**", "").strip())
        elif line.startswith("- 🟡"):
            annotate("warning", line.lstrip("- 🟡").replace("**", "").strip())

    if zero := sorted(n for n, c in per_source.items() if c == 0):
        annotate(
            "warning",
            f"Sources returning zero items: {', '.join(zero)}. "
            "Zero across several consecutive runs means dead.",
        )

    if failed := sorted(n for n, (_, f) in (per_feed or {}).items() if f):
        # Warning, not error: Horizon logs feed failures as warnings and the job
        # stays green, so a red annotation here would contradict the job status.
        # Still louder than a zero-item feed, which may simply be quiet.
        annotate("warning", f"Feeds that FAILED to fetch: {', '.join(failed)}")

    fatal, degrading, escalated = split_by_severity(grouped, totals)
    if escalated:
        annotate(
            "error",
            "Enrichment failed on more than a quarter of the items that reached "
            "it. Treating this as a broken run, not a few thin items.",
        )
    for sig, count in fatal[:MAX_ANNOTATIONS]:
        annotate("error", f"{count}x {sig[:300]}")
    if len(fatal) > MAX_ANNOTATIONS:
        annotate(
            "error",
            f"{len(fatal) - MAX_ANNOTATIONS} further distinct error type(s) "
            "not shown. See the run log.",
        )
    # Degradation is reported at warning level so the job stays green. The
    # item published; only its depth was lost.
    for sig, count in degrading[:MAX_ANNOTATIONS]:
        annotate("warning", f"{count}x {sig[:300]}")


def funnel(totals) -> str:
    """The whole chain from raw pull to published, as one line.

    Reporting fetched, analyzed and cleared alone left the biggest drop
    invisible: a reader comparing "cleared 24" against a page of 17 items had
    no way to tell merged duplicates from lost coverage.
    """
    steps = []
    if totals["fetched"] is not None:
        steps.append(f"{totals['fetched']} fetched")
    if totals["merged"]:
        steps.append(f"{totals['merged']} cross-source duplicates merged")
    # Order follows the pipeline, and the pipeline's order depends on the path.
    # Ranking gates first and scores only the survivors; the threshold path has
    # to score everything before it can filter on a score. Printing a fixed
    # order would misreport whichever path it was not written for.
    gated_first = totals.get("gated") is not None
    if gated_first:
        steps.append(f"{totals['gated']} kept by the gate")
    if totals["analyzed"] is not None:
        steps.append(
            f"{totals['analyzed']} analyzed"
            + (" (the survivors)" if gated_first else "")
        )
    if totals["selected"] is not None:
        steps.append(f"{totals['selected']} cleared threshold")
    # The ranker and the shortlist cut were both missing, so the selection
    # funnel could not close: the 2026-08-22 run read "13 kept by the gate ->
    # 10 rejected by the floor -> 0 published", which implies three items went
    # missing. They were ranked below the shortlist the floor reads.
    if totals.get("ranked") is not None:
        steps.append(f"{totals['ranked']} ranked")
        considered = (
            (totals.get("floor_rejected") or 0)
            + (totals.get("below_score") or 0)
            + (totals.get("published") or 0)
        )
        below = totals["ranked"] - considered
        if below > 0:
            steps.append(f"{below} below the shortlist cut")
    if totals.get("floor_rejected"):
        steps.append(f"{totals['floor_rejected']} rejected by the floor")
    if totals.get("below_score"):
        steps.append(f"{totals['below_score']} under the score floor")
    if totals["topic_dupes"]:
        steps.append(f"{totals['topic_dupes']} topic duplicates merged")
    # The digest cap is a stage like any other and hides the biggest drop of
    # all when it bites: on 2026-08-18 it cut 45 qualifying items to 24, and
    # the footer showed only the 24.
    if totals.get("pre_cap") and totals["published"] is not None:
        held = totals["pre_cap"] - totals["published"]
        if held > 0:
            steps.append(f"{held} held back by the digest cap")
    if totals["published"] is not None:
        steps.append(f"**{totals['published']} published**")
    return " → ".join(steps)


def enrichment_note(totals):
    """A failed enrichment leaves the item published and thin.

    A failed second pass still publishes the headline and the summary, with no
    background and no references, and the page gives no sign. Name it, or the
    only visible effect is a red X on a run that looks otherwise complete.
    """
    done, tried = totals["enriched"], totals["enrich_attempted"]
    if done is None or tried is None or done >= tried:
        return None
    return (
        f"- ⚠️ **{tried - done} of {tried} published items lost their background"
        " section** because enrichment failed. They carry a headline and a"
        " summary only."
    )


def build_report(per_source, per_feed, totals, grouped, warnings,
                 cadence=None, collapsed=None) -> str:
    zero_sources = sorted(n for n, c in per_source.items() if c == 0)
    fatal_head, degrading_head, _ = split_by_severity(grouped, totals)
    lines = ["## Run health", ""]
    lines.append(f"- **Funnel:** {funnel(totals)}")
    # Count the two kinds separately in the headline. One number covering both
    # is what made "2 errors" sit above a page where nothing had gone missing.
    tail = f"- **Errors:** {sum(c for _, c in fatal_head)}"
    if degrading_head:
        tail += f" | **Items published thin:** {sum(c for _, c in degrading_head)}"
    tail += f" | **Warnings:** {warnings}"
    if totals["tokens"]:
        tail += (
            f" | **Tokens:** {totals['tokens']:,}"
            f" ({totals['tokens_in']:,} in / {totals['tokens_out']:,} out)"
        )
    lines.append(tail)
    for line, explanation in collapsed or []:
        lines.append(f"- 🔴 **A pipeline stage produced nothing.** {explanation}")
        lines.append(f"  - `{line}`")
    lines += cadence or []
    if note := enrichment_note(totals):
        lines.append(note)
    if per_source:
        counts = ", ".join(f"{n}: {c}" for n, c in sorted(per_source.items()))
        lines.append(f"- **Per-source items:** {counts}")
    if zero_sources:
        lines.append(
            f"- ⚠️ **Sources returning zero items:** {', '.join(zero_sources)}"
            ". Zero across several consecutive runs means dead."
        )
    if per_feed:
        failed = sorted(n for n, (_, f) in per_feed.items() if f)
        empty = sorted(n for n, (c, f) in per_feed.items() if c == 0 and not f)
        live = sorted(((n, c) for n, (c, f) in per_feed.items() if c > 0),
                      key=lambda kv: -kv[1])
        if failed:
            lines.append(f"- 🔴 **Feeds that FAILED to fetch:** {', '.join(failed)}")
        if live:
            lines.append("- **Feeds with items:** "
                         + ", ".join(f"{n}: {c}" for n, c in live))
        if empty:
            lines.append(f"- **Feeds with nothing in window ({len(empty)}):** "
                         + ", ".join(empty))
    fatal, degrading, escalated = split_by_severity(grouped, totals)
    if escalated:
        lines.append(
            "- 🔴 **Enrichment failed on more than a quarter of the items that"
            " reached it.** That is a broken run, not a few thin items."
        )
    if fatal:
        fatal_count = sum(c for _, c in fatal)
        lines.append(
            f"- 🔴 **{fatal_count} ERROR line(s), {len(fatal)} distinct type(s)**"
            ". The digest may be incomplete:"
        )
        lines += [f"  - **{count}x** `{sig[:300]}`" for sig, count in fatal]
    if degrading:
        degraded_count = sum(c for _, c in degrading)
        lines.append(
            f"- 🟡 **{degraded_count} item(s) published without background.**"
            " Everything that cleared the bar is on the page; those items carry"
            " a headline and a summary only:"
        )
        lines += [f"  - **{count}x** `{sig[:300]}`" for sig, count in degrading]
    if not fatal and not degrading:
        lines.append(
            "- ✅ **No errors**. If the digest is empty, items scored"
            " below threshold."
        )
    return "\n".join(lines) + "\n"


# GitHub's scheduler is best effort and has been between 29 and 104 minutes
# late on this repo. The window is anchored to when a run starts, not to the
# cron time, so what threatens coverage is the gap between consecutive starts
# growing past the window. Warn while there is still headroom.
CADENCE_WARN_HEADROOM_HOURS = 1.0


def _api(url: str, token: Optional[str]):
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "horizon-run-health",
    })
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def cadence_lines(starts: list[datetime], window_hours: float) -> tuple[list[str], bool]:
    """Compare the gap between the last two scheduled starts against the window.

    `starts` is newest first. Returns the report lines and whether the gap has
    actually exceeded the window, which means items fell between two runs and
    nothing will ever pick them up.
    """
    if len(starts) < 2:
        return (["- **Cadence:** first scheduled run on this schedule, no gap to"
                 " compare yet."], False)

    gap = starts[0] - starts[1]
    gap_hours = gap.total_seconds() / 3600
    headroom = window_hours - gap_hours
    shape = f"{gap_hours:.1f}h since the previous scheduled run, window is {window_hours:g}h"

    if headroom < 0:
        return ([
            f"- 🔴 **Cadence: {shape}.** The gap is wider than the window, so"
            f" items published in the missing {abs(headroom):.1f}h were never"
            " fetched by either run."
        ], True)
    if headroom < CADENCE_WARN_HEADROOM_HOURS:
        return ([
            f"- 🟡 **Cadence: {shape}**, leaving {headroom:.1f}h of overlap."
            " Scheduler drift is eating the margin; a longer delay next run"
            " would open a gap."
        ], False)
    return ([f"- **Cadence:** {shape}, {headroom:.1f}h of overlap."], False)


def check_cadence(window_hours: float) -> tuple[list[str], bool]:
    """Read the last two scheduled starts from the API.

    Never fails the run on its own account: a rate limit or an outage here is
    not a reason to lose a digest, so any error degrades to a note.
    """
    repo = os.environ.get("GITHUB_REPOSITORY")
    workflow = os.environ.get("GITHUB_WORKFLOW_REF", "")
    token = os.environ.get("GITHUB_TOKEN")
    if not repo:
        return [], False
    # GITHUB_WORKFLOW_REF is "owner/repo/.github/workflows/f.yml@refs/heads/main".
    # The ref after the @ contains slashes, so strip it before taking the
    # basename or this lands on "main" and the check silently does nothing.
    workflow_file = workflow.split("@")[0].split("/")[-1] if workflow else ""
    if not workflow_file:
        return [], False
    url = (f"https://api.github.com/repos/{repo}/actions/workflows/"
           f"{workflow_file}/runs?event=schedule&per_page=5")
    try:
        payload = _api(url, token)
        starts = [
            datetime.fromisoformat(r["run_started_at"].replace("Z", "+00:00"))
            for r in payload.get("workflow_runs", [])
        ]
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as exc:
        return [f"- **Cadence:** could not be checked ({type(exc).__name__})."], False
    starts.sort(reverse=True)
    return cadence_lines(starts, window_hours)


def todays_posts(posts_dir: Path) -> list[Path]:
    """This run's digest file(s), the newest per language for today.

    Posts are named "<date>-<HHMM>-summary-<lang>.md" (the run time was added
    so a day's second run stops overwriting the first). Several files can
    therefore share a date, and only the one this run just wrote should get
    this run's health footer. The pre-timestamp "<date>-summary-<lang>.md"
    form is still matched so older digests aren't missed.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    newest_per_lang: dict[str, tuple[str, Path]] = {}
    for post in posts_dir.glob(f"{today}-*summary-*.md"):
        lang = post.stem.rsplit("summary-", 1)[-1]
        # Rank by the HHMM in the name, not mtime: this run wrote the latest
        # time for today, and filesystem timestamps can be reordered by
        # anything that touches the files (checkout, copy, deploy tooling).
        middle = post.stem[len(today) + 1:].rsplit("-summary-", 1)[0]
        stamp = middle if middle.isdigit() else ""  # legacy name sorts first
        if lang not in newest_per_lang or stamp > newest_per_lang[lang][0]:
            newest_per_lang[lang] = (stamp, post)
    return sorted(p for _, p in newest_per_lang.values())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("logfile", type=Path)
    ap.add_argument("--append-digest", type=Path, default=None,
                    help="posts dir; appends footer to today's summary files")
    ap.add_argument("--window-hours", type=float, default=None,
                    help="the run's --hours window; enables the cadence check")
    args = ap.parse_args()

    per_source, per_feed, totals, errors, warnings, collapsed = parse_log(args.logfile)
    grouped = group_errors(errors)

    cadence, cadence_gap = ([], False)
    if args.window_hours:
        cadence, cadence_gap = check_cadence(args.window_hours)

    report = build_report(
        per_source, per_feed, totals, grouped, warnings,
        cadence=cadence, collapsed=collapsed,
    )
    print(report)
    emit_annotations(
        per_source, per_feed, totals, grouped, warnings,
        cadence=cadence, cadence_gap=cadence_gap, collapsed=collapsed,
    )

    import os
    if summary_path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(report)

    posts: list[Path] = []
    if args.append_digest and args.append_digest.is_dir():
        posts = todays_posts(args.append_digest)
        for post in posts:
            # Digests already end with a horizontal rule; don't stack a second.
            existing = post.read_text(encoding="utf-8").rstrip()
            separator = "\n\n" if existing.endswith("---") else "\n\n---\n\n"
            with open(post, "a", encoding="utf-8") as f:
                f.write(separator + report)
            print(f"Appended health footer to {post}")

    fatal, degrading, escalated = split_by_severity(grouped, totals)
    # Only errors that actually damage the run fail the job. Items that
    # published thin are reported and stay green, so a red X keeps meaning
    # "go and look" rather than "another Tuesday".
    fatal_count = sum(c for _, c in fatal)
    # A gap wider than the window means items existed and no run ever saw them.
    # That is lost coverage rather than lost depth, so it goes red.
    if cadence_gap:
        fatal_count += 1
    # A stage that never ran is the failure this whole script exists to catch:
    # the run looks complete, publishes something, and reports success.
    fatal_count += len(collapsed)
    Path("health_errors.txt").write_text(str(fatal_count), encoding="utf-8")
    # Machine-readable form for notify_telegram.py, so the notifier doesn't
    # have to re-parse the log and the two can't disagree about a run.
    Path("health_summary.json").write_text(json.dumps({
        "totals": totals,
        "per_source": per_source,
        "zero_sources": sorted(n for n, c in per_source.items() if c == 0),
        "errors": fatal_count,
        "degraded": sum(c for _, c in degrading),
        "degraded_escalated": escalated,
        "warnings": warnings,
        "posts": [str(p) for p in posts],
        "finished_utc": datetime.now(timezone.utc).strftime("%d %b %H:%M"),
    }, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
