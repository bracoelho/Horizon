"""Does GitHub's runner get to follow a Google News link, or is it challenged?

The question this answers, and nothing else: Reddit works from the owner's Mac
and is refused from CI (NEWS-Radar SOURCES.md). Google may do the same. If the
runner is challenged, resolution has to move to a paid search route or to the
owner's machine, and that is a design decision we should take on evidence.

No model calls, no secrets, no writes. Prints and exits 0 either way: this is a
measurement, not a gate.
"""
import re
import sys
import urllib.request

FEED = ("https://news.google.com/rss/search?q=AI%20AND%20%28utility%20OR%20%22power%20grid%22"
        "%20OR%20%22energy%20transition%22%20OR%20%22data%20center%20power%22%20OR%20electricity"
        "%29&hl=en-US&gl=US&ceid=US:en")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36")
N = 5


def feed_links():
    req = urllib.request.Request(FEED, headers={"User-Agent": UA})
    xml = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    links = re.findall(r"<link>(https://news\.google\.com/rss/articles/[^<]+)</link>", xml)
    print(f"feed: {len(xml)} bytes, {len(links)} article links found")
    return links[:N]


def main():
    try:
        links = feed_links()
    except Exception as e:
        print(f"FEED UNREACHABLE FROM THE RUNNER: {type(e).__name__}: {e}")
        return 0
    if not links:
        print("FEED REACHED BUT NO ARTICLE LINKS PARSED: the runner may be served a different feed")
        return 0

    from playwright.sync_api import sync_playwright
    resolved = challenged = failed = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=UA)
        for url in links:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                try:
                    page.wait_for_url(lambda u: "news.google.com" not in u, timeout=15000)
                except Exception:
                    pass
                final = page.url
                if "news.google.com" not in final:
                    resolved += 1
                    print(f"RESOLVED     {final.split('/')[2]}")
                else:
                    challenged += 1
                    # the title is the cheapest signal of a consent or captcha wall
                    print(f"STILL GOOGLE title={page.title()[:70]!r}")
            except Exception as e:
                failed += 1
                print(f"ERROR        {type(e).__name__}: {str(e)[:90]}")
        browser.close()

    print(f"\nVERDICT resolved={resolved} still-google={challenged} error={failed} of {len(links)}")
    print("resolved==len(links) means the runner is allowed and resolution can live in the pipeline.")
    print("Any other result means it cannot, and the fallback decision is the owner's.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
