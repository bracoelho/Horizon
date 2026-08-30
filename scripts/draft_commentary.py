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


def _voice_findings(drafted: dict) -> list:
    """Run the same audit the build gate runs, before writing anything.

    Importing the gate rather than restating its patterns: two copies of a
    rule drift, and this one exists to predict exactly what that one will say.
    """
    import importlib.util
    import tempfile

    spec = importlib.util.spec_from_file_location(
        "check_voice", Path(__file__).with_name("check_voice.py")
    )
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)

    text = "\n\n".join(
        f"**{b.get('label','')}.** {b.get('text','')}"
        for b in (drafted.get("beats") or [])
    )
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(f"{drafted.get('title','')}\n\n{text}")
        tmp = Path(fh.name)
    try:
        return [f"{name}: {found!r}" for _, name, found, _ in gate.check(tmp)]
    finally:
        tmp.unlink(missing_ok=True)


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
    system = draft_system()
    user = draft_user(
        title=proposal.get("title", ""),
        theme=proposal.get("theme", ""),
        body=proposal.get("plain", ""),
        angle=angle,
    )

    # One repair attempt. The model reaches for "rather than" and "X, not Y"
    # even when told twice, and the gate then throws the whole draft away. The
    # first attempt went from three violations to one after the prompt was
    # tightened, so handing the finding back is likely to clear the last one,
    # and a rejected draft costs a person a second tap on their phone.
    drafted = {}
    for attempt in (1, 2):
        raw = await client.complete(system, user, schema=DRAFT_SCHEMA)
        drafted = json.loads(raw)
        findings = _voice_findings(drafted)
        if not findings:
            break
        print(f"Attempt {attempt} broke the standard: {'; '.join(findings)}")
        if attempt == 2:
            print("Second attempt still flags. Carrying the findings as a note.")
            break
        user += (
            "\n\n# Your previous attempt was rejected\n\n"
            + "\n".join(f"- {f}" for f in findings)
            + "\n\nRewrite it without those. State the positive claim and stop."
        )
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
    # Whatever the audit still flags rides with the draft as an editor's note.
    # It stopped being a build gate because it cannot tell a flourish from a
    # comparison: STYLE.md bans "the rhetorical uses of" rather than and
    # instead of, and the grep matches every use. STYLE.md fails its own audit
    # thirteen times, three of them while explaining the rule. A person reading
    # the draft settles that in a second; a pattern never will.
    remaining = _voice_findings(drafted)
    note = ""
    if remaining:
        note = (
            "\n\n<!-- Voice check, for your eye rather than a gate.\n"
            "Delete this block when you edit.\n\n"
            + "\n".join(f"  {f}" for f in remaining)
            + "\n\n\"rather than\" and \"instead of\" are only banned in their\n"
            "rhetorical use, so a plain comparison here is fine and this note\n"
            "is wrong. \", not\" and \"not just\" are the flourish itself.\n-->"
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{slug(title)}.md"
    path.write_text(front + body + note + "\n", encoding="utf-8")
    Path("voice_notes.txt").write_text(str(len(remaining)), encoding="utf-8")

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
