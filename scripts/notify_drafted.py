#!/usr/bin/env python3
"""Tell the owner a draft is waiting, and where to edit it.

Separate from notify_telegram.py because it reports a different event with a
different shape, and folding it in would give that script two jobs. Shares the
sending path only.

Runs with if: always(), so it also reports a drafting run that failed. Silence
after tapping a button reads as the button not working.
"""

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def send(token: str, chat_id: str, text: str) -> None:
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.load(resp)
    # Telegram answers 200 with ok:false for a rejected message, so a silent
    # success here would be a lie.
    if not body.get("ok"):
        raise RuntimeError(f"Telegram refused the message: {body}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--angle", default="?")
    args = ap.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not (token and chat_id):
        print("Telegram secrets not set. Skipping.")
        return 0

    repo = os.environ.get("GITHUB_REPOSITORY", "bracoelho/Horizon")
    path = Path("drafted_path.txt")
    title = Path("drafted_title.txt")

    if not path.exists():
        text = (
            f"🔴 <b>Drafting angle {esc(args.angle)} failed.</b>\n"
            "No draft was written. The run log says why."
        )
    else:
        edit = f"https://github.com/{repo}/edit/main/{path.read_text().strip()}"
        name = title.read_text().strip() if title.exists() else "the draft"
        text = (
            f"📄 <b>Draft ready</b>\n"
            f"<b>{esc(name)}</b>\n"
            f"From angle {esc(args.angle)}, held unpublished.\n\n"
            f'→ <a href="{esc(edit)}">Edit and publish</a>\n\n'
            "<i>Change published to true and commit. It is live in a minute.</i>"
        )

    try:
        send(token, chat_id, text)
        print("Notified.")
    except Exception as exc:  # noqa: BLE001
        # Never fail the job for a notification: the draft is already committed
        # and losing it to a messaging error would be the worse outcome.
        print(f"Could not notify: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
