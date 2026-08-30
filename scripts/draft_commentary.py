#!/usr/bin/env python3
"""Draft the day's commentary from a chosen angle.

Run by workflow_dispatch, so the owner can choose an angle from his phone and
have a draft waiting a few minutes later. The daily run proposes; this drafts;
he edits and flips `published`.

Never publishes. The file is written with `published: false`, and that switch
stays his.

Usage:
  python scripts/draft_commentary.py --angle 2
"""

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ai.client import create_ai_client  # noqa: E402
from src.ai.prompting.commentary import (  # noqa: E402
    DRAFT_SCHEMA,
    draft_system,
    draft_user,
)
from src.storage.manager import StorageManager  # noqa: E402

PROPOSAL = Path("data/commentary_proposal.json")
OUT_DIR = Path("docs/_commentary")


def slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return "-".join(s.split("-")[:8])[:60].strip("-") or "commentary"


async def run(angle_index: int) -> int:
    if not PROPOSAL.exists():
        print(f"No proposal at {PROPOSAL}. The last run published nothing.")
        return 1
    proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))
    angles = proposal.get("angles") or []
    if not 1 <= angle_index <= len(angles):
        print(f"Angle {angle_index} does not exist; the proposal has {len(angles)}.")
        return 1
    angle = angles[angle_index - 1]

    config = StorageManager().load_config()
    client = create_ai_client(config.ai)
    raw = await client.complete(
        draft_system(),
        draft_user(
            title=proposal.get("title", ""),
            theme=proposal.get("theme", ""),
            body=proposal.get("plain", ""),
            angle=angle,
        ),
        schema=DRAFT_SCHEMA,
    )
    drafted = json.loads(raw)
    beats = drafted.get("beats") or []
    # The schema cannot pin the count, so the caller checks it. Four is the
    # standard; a piece with three has lost a beat and one with five has
    # reinvented the one we merged.
    if len(beats) != 4:
        print(f"Expected four beats, got {len(beats)}. Not writing a draft.")
        return 1

    title = str(drafted.get("title") or proposal.get("title", "Untitled")).strip()
    body = "\n\n".join(
        f"**{str(b.get('label','')).strip()}.** {str(b.get('text','')).strip()}"
        for b in beats
        if str(b.get("text", "")).strip()
    )
    now = datetime.now(timezone.utc)
    front = "\n".join([
        "---",
        # His switch. A drafting job does not get to publish.
        "published: false",
        f"title: {json.dumps(title)}",
        f"date: {now.strftime('%Y-%m-%d %H:%M:%S +0000')}",
        f"theme: {proposal.get('theme','')}",
        f"item_title: {json.dumps(proposal.get('title',''))}",
        f"item_url: {json.dumps(proposal.get('url',''))}",
        f"item_score: {json.dumps(str(proposal.get('score','')))}",
        f"edition_url: {proposal.get('edition_url','')}",
        "---",
        "",
    ])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{slug(title)}.md"
    path.write_text(front + body + "\n", encoding="utf-8")

    print(f"Drafted {path}")
    print(f"::notice::Drafted '{title}' from angle {angle_index}. Held unpublished.")
    Path("drafted_path.txt").write_text(str(path), encoding="utf-8")
    Path("drafted_title.txt").write_text(title, encoding="utf-8")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--angle", type=int, required=True, help="1, 2 or 3")
    return asyncio.run(run(ap.parse_args().angle))


if __name__ == "__main__":
    sys.exit(main())
