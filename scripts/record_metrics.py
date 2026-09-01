#!/usr/bin/env python3
"""Append one row per run to the metrics series the ops page reads.

Every run computes a rich picture of itself: the funnel, per-feed counts,
token usage, the score distribution. Until this script existed all of it was
printed to four ephemeral surfaces and thrown away with the runner, so the
question "show me the last three weeks" had no answer, and a change to the
judging system (BACKLOG #40) had no baseline to be measured against.

One row per run, appended to docs/assets/data/runs.json. The file lives under
assets rather than _data because Jekyll does not publish _data, and the ops
page reads it with a same-origin fetch. The workflow commits it back to main
after the deploy, which is how the series survives to the next checkout.

Inputs are the artifacts the run already produces:
  health_summary.json   written by check_run_health.py
  docs/_items/*.md      this run's published items only, since the directory
                        is gitignored on main and starts empty each checkout
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

FRONT_RE = re.compile(r"^(\w+):\s*(.*)$")
MAX_ROWS = 400  # a year-plus of daily runs; the page stays a fast fetch


def read_front_matter(path: Path) -> dict:
    """The few scalar fields an item page carries, no YAML dependency."""
    fields = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return fields
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if m := FRONT_RE.match(line):
            fields[m.group(1)] = m.group(2).strip().strip('"')
    return fields


def published_items(items_dir: Path) -> list[dict]:
    out = []
    for path in sorted(items_dir.glob("*.md")):
        fm = read_front_matter(path)
        row = {"theme": fm.get("theme", ""),
               "source": fm.get("source", "")}
        try:
            row["score"] = float(fm.get("score", ""))
        except ValueError:
            row["score"] = None
        out.append(row)
    return out


def build_row(health: dict, items: list[dict]) -> dict:
    totals = health.get("totals", {})
    themes: dict[str, int] = {}
    for item in items:
        if item["theme"]:
            themes[item["theme"]] = themes.get(item["theme"], 0) + 1
    return {
        # The run's identity, so a row can be traced to its logs.
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "event": os.environ.get("GITHUB_EVENT_NAME", ""),
        "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        # The funnel, verbatim from the health summary so the two surfaces
        # cannot disagree about a run.
        "funnel": {
            k: totals.get(k)
            for k in (
                "fetched", "merged", "gated", "analyzed", "selected",
                "ranked", "floor_rejected", "below_score", "topic_dupes",
                "published", "enriched", "tokens",
            )
            if totals.get(k) is not None
        },
        "score_distribution": totals.get("score_distribution") or {},
        "setwise": totals.get("setwise"),
        "published_by_theme": themes,
        "published_scores": [
            i["score"] for i in items if i["score"] is not None
        ],
        # Schema v2 (SPEC-CONTROL-ROOM §3): per-item detail feeds the
        # judgment map and the reader-side lens; per_feed feeds the source
        # ledger. Old rows lack these and every view must degrade to that.
        "items": items,
        "per_feed": health.get("per_feed"),
        "errors": health.get("errors", 0),
        "degraded": health.get("degraded", 0),
        "warnings": health.get("warnings", 0),
        "zero_sources": health.get("zero_sources", []),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--health", type=Path, default=Path("health_summary.json"))
    ap.add_argument("--items", type=Path, default=Path("docs/_items"))
    ap.add_argument(
        "--series", type=Path, default=Path("docs/assets/data/runs.json")
    )
    args = ap.parse_args()

    try:
        health = json.loads(args.health.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        # A run that died before the health check still notified; it can also
        # still deploy. Metrics are an observer and never a reason to fail.
        print(f"No usable health summary ({exc}); recording nothing.")
        return 0

    items = published_items(args.items) if args.items.is_dir() else []
    row = build_row(health, items)

    series: list = []
    if args.series.exists():
        try:
            series = json.loads(args.series.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # Refuse to silently destroy history: a corrupt series is a
            # finding, and overwriting it would erase the evidence.
            print(f"{args.series} exists but is not JSON; not touching it.")
            return 1
    if any(r.get("run_id") == row["run_id"] and row["run_id"] for r in series):
        print(f"Run {row['run_id']} already recorded; leaving the series as is.")
        return 0

    series.append(row)
    series = series[-MAX_ROWS:]
    args.series.parent.mkdir(parents=True, exist_ok=True)
    args.series.write_text(
        json.dumps(series, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Recorded run {row['run_id'] or '(local)'}: "
          f"{len(series)} run(s) in the series.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
