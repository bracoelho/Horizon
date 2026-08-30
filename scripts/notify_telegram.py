#!/usr/bin/env python3
"""Send a Telegram notification summarising a Horizon run.

Reads the health summary written by check_run_health.py and the digest post
that run produced, then sends a short message with the top items and a link
to the published page.

Sent from the workflow rather than through Horizon's own webhook because
Horizon's templates expose only message_title and summary, there is no
placeholder for a link, which is the main thing this message is for. Doing
it here also lets us respect Telegram's 4096-character limit and stay silent
on quiet runs.

Usage:
  python scripts/notify_telegram.py [--health health_summary.json] [--always]

Environment:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID , required; without them this exits
                                          quietly so the pipeline works
                                          unchanged until they are set.
  GITHUB_EVENT_NAME                    , "schedule" or "workflow_dispatch",
                                          reported as the run type.
  GITHUB_SERVER_URL, GITHUB_REPOSITORY, GITHUB_RUN_ID, used to link the run
                                          when a message reports errors.
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

TELEGRAM_LIMIT = 4096
ITEM_RE = re.compile(r"^### \[(?P<title>.+?)\]\((?P<url>[^)]+)\)\s*⭐️?\s*(?P<score>[\d.]+)/10")
MAX_ITEMS_SHOWN = 5

RUN_TYPES = {
    "schedule": "scheduled",
    "workflow_dispatch": "manual",
    "repository_dispatch": "triggered",
    "push": "on push",
}


def esc(text: str) -> str:
    """Escape for Telegram's HTML parse mode."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def site_base(config_path: Path) -> str:
    """Build the site's base URL from Jekyll's _config.yml."""
    url, baseurl = "", ""
    if config_path.is_file():
        for line in config_path.read_text(encoding="utf-8").splitlines():
            if m := re.match(r'^url:\s*"?([^"#]*)"?', line):
                url = m.group(1).strip()
            elif m := re.match(r'^baseurl:\s*"?([^"#]*)"?', line):
                baseurl = m.group(1).strip()
    return f"{url.rstrip('/')}{baseurl.rstrip('/')}"


def post_url(post_path: str, base: str) -> str:
    """Map docs/_posts/YYYY-MM-DD-slug.md to its Jekyll URL."""
    stem = Path(post_path).stem
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})-(.+)$", stem)
    if not m:
        return base or ""
    year, month, day, slug = m.groups()
    return f"{base}/{year}/{month}/{day}/{slug}.html"


def parse_items(post_path: Path) -> list[dict]:
    items = []
    if not post_path.is_file():
        return items
    for line in post_path.read_text(encoding="utf-8").splitlines():
        if m := ITEM_RE.match(line.strip()):
            items.append(m.groupdict())
    return items


def commentary_lines(base: str, path: Path = Path("commentary_proposal.json")) -> list:
    """The day's candidate to write about, assembled by the run.

    The owner wants a queue of subjects rather than a blank page each
    morning, and choosing one was happening at a keyboard. The angles are the
    item's own enrichment blocks, which already answer the commentary's
    beats, so this costs no extra model call and cannot claim more than the
    radar found.

    Absent file means the run published nothing, or predates this. Silence is
    the right answer either way.
    """
    try:
        p = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not p.get("title"):
        return []

    out = ["", "✍️ <b>Worth writing about</b>"]
    head = esc(str(p.get("theme") or ""))
    if p.get("score") is not None:
        head += f" · {esc(str(p['score']))}"
    out.append(head)
    out.append(f'<b>{esc(p["title"])}</b>')
    if p.get("plain"):
        out.append(f"<i>{esc(p['plain'])}</i>")

    for n, angle in enumerate(p.get("angles") or [], start=1):
        heading = esc(str(angle.get("heading") or "").strip())
        if heading:
            out.append(f"{n}. <b>{heading}</b>")

    if p.get("url"):
        out.append(f'\n→ <a href="{esc(p["url"])}">Read the source</a>')
    return out


def build_message(health: dict, run_type: str) -> str:
    posts = health.get("posts") or []
    base = site_base(Path("docs/_config.yml"))
    stats = health.get("totals", {})
    errors = health.get("errors", 0)

    when = health.get("finished_utc", "")
    header = "🛰 <b>Radar</b>"
    if when:
        header += f" · {esc(when)} UTC"
    header += f" · {esc(run_type)}"
    lines = [header]

    nothing_cleared = stats.get("selected") == 0 and not health.get("incomplete")
    if health.get("incomplete"):
        lines.append("🔴 <b>The run failed before the health check ran.</b> "
                     "No digest was produced.")
        errors = 0  # don't also print the generic error block below
    elif nothing_cleared:
        lines.append(f'Nothing met the threshold · {stats.get("analyzed")} analyzed')
    else:
        # Lead with what the message is about to list. "24 cleared threshold"
        # above a list of 17 items reads as seven items gone missing, when
        # topic dedup merged them.
        published = stats.get("published")
        head = f'{published} published · ' if published is not None else ""
        lines.append(
            f'{head}{stats.get("selected")} cleared threshold · '
            f'{stats.get("analyzed")} analyzed'
        )
    lines.append("")

    if errors:
        run_link = ""
        server, repo, run_id = (
            os.environ.get("GITHUB_SERVER_URL", ""),
            os.environ.get("GITHUB_REPOSITORY", ""),
            os.environ.get("GITHUB_RUN_ID", ""),
        )
        if server and repo and run_id:
            run_link = f'\n<a href="{server}/{repo}/actions/runs/{run_id}">View the failing run</a>'
        lines.insert(2, f"🔴 <b>{errors} error(s) during this run.</b> "
                        f"The digest may be incomplete.{run_link}\n")

    # Reported, but not as an alarm: these items are on the page, without their
    # background section. Saying "the digest may be incomplete" for this made
    # every ordinary run read like a failure.
    if degraded := health.get("degraded", 0):
        lines.append(
            f"🟡 {degraded} item(s) published without background research.\n"
        )

    if zero := health.get("zero_sources"):
        lines.append(f"⚠️ No items from: {esc(', '.join(zero))}\n")

    # Trust the run's own count over the digest file: if nothing cleared, don't
    # list whatever the page happens to contain. The two only disagree when the
    # page is stale, but a message contradicting itself is worse than a terse one.
    for post in posts:
        items = [] if nothing_cleared else parse_items(Path(post))
        link = post_url(post, base)
        for item in items[:MAX_ITEMS_SHOWN]:
            host = urllib.parse.urlparse(item["url"]).netloc.removeprefix("www.")
            lines.append(
                f'⭐ <b>{esc(item["score"])}</b> '
                f'<a href="{esc(item["url"])}">{esc(item["title"])}</a>'
                f"\n<i>{esc(host)}</i>"
            )
        if len(items) > MAX_ITEMS_SHOWN:
            lines.append(f"…and {len(items) - MAX_ITEMS_SHOWN} more")
        if link:
            lines.append(f'\n→ <a href="{link}">Read the full digest</a>')

    lines += commentary_lines(base)

    message = "\n".join(lines)
    if len(message) > TELEGRAM_LIMIT:
        message = message[: TELEGRAM_LIMIT - 20].rsplit("\n", 1)[0] + "\n…(truncated)"
    return message


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
        json.load(resp)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--health", type=Path, default=Path("health_summary.json"))
    ap.add_argument("--always", action="store_true",
                    help="notify even when nothing cleared threshold")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the message instead of sending it")
    ap.add_argument("--self-test", action="store_true",
                    help="send a sample message to verify credentials and "
                         "delivery without running the pipeline")
    args = ap.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not args.dry_run and not (token and chat_id):
        if args.self_test:
            # Silence is the correct behavior for a normal run without
            # secrets, but for a self-test it is the failure being tested.
            print("Telegram secrets are not set. Nothing to test.")
            return 1
        print("Telegram secrets not set. Skipping notification.")
        return 0

    run_type = RUN_TYPES.get(
        os.environ.get("GITHUB_EVENT_NAME", ""),
        os.environ.get("GITHUB_EVENT_NAME") or "local",
    )

    if args.self_test:
        # Verifies the whole delivery path, secrets, network, formatting , 
        # without a pipeline run, which otherwise costs a couple of minutes
        # of model calls per attempt. Use after rotating credentials too.
        message = (
            "🧪 <b>Radar test message</b>\n"
            f"Triggered {esc(run_type)}.\n\n"
            "If you can read this, <code>TELEGRAM_BOT_TOKEN</code> and "
            "<code>TELEGRAM_CHAT_ID</code> are set correctly and run "
            "notifications will arrive here.\n\n"
            '→ <a href="https://radar.bcoelho.com/">The radar</a>'
        )
        if args.dry_run:
            print(message)
            return 0
        try:
            send(token, chat_id, message)
            print("Test message sent.")
        except Exception as e:  # noqa: BLE001
            print(f"Test message FAILED: {e}")
            return 1  # a failed self-test should be visibly red
        return 0

    if args.health.is_file():
        health = json.loads(args.health.read_text(encoding="utf-8"))
    else:
        # No health summary means the run died before the health check ran.
        # That is exactly when a notification is most useful, so send one.
        health = {"totals": {}, "errors": 1, "incomplete": True,
                  "posts": [], "finished_utc": "", "zero_sources": []}

    quiet = not health.get("errors") and not health.get("totals", {}).get("selected")
    if quiet and not args.always:
        print("Nothing cleared threshold and no errors. Staying silent.")
        return 0

    message = build_message(health, run_type)
    if args.dry_run:
        print(message)
        return 0

    try:
        send(token, chat_id, message)
        print("Telegram notification sent.")
    except Exception as e:  # noqa: BLE001 - never fail the build over a notification
        print(f"Telegram notification failed: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
