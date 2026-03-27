#!/usr/bin/env python3

import os
import re
import html
import time
from datetime import datetime
from urllib.parse import urlparse

import requests
import feedparser
from bs4 import BeautifulSoup

WORKDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SITE_DIR = os.path.join(WORKDIR, "site")
REPORTS_DIR = os.path.join(SITE_DIR, "reports")
INDEX_PATH = os.path.join(SITE_DIR, "index.html")
LATEST_PATH = os.path.join(SITE_DIR, "latest.html")

# --- Feeds ---
# Keep these curated + mostly RSS to avoid brittle scraping.
FEEDS = {
    "Startup / Venture + AI": [
        ("TechCrunch — AI", "https://techcrunch.com/tag/artificial-intelligence/feed/"),
        ("VentureBeat — AI", "https://venturebeat.com/category/ai/feed/"),
    ],
    "Big Tech + AI": [
        ("The Verge — AI", "https://www.theverge.com/artificial-intelligence/rss/index.xml"),
        ("Google Research", "https://research.google/blog/rss/"),
        ("Google Blog (all)", "https://blog.google/rss"),
        ("MIT Technology Review — AI", "https://www.technologyreview.com/topic/artificial-intelligence/feed/"),
    ],
    "Influencers / Pods / Newsletters": [
        ("Alex Finn (Substack)", "https://alexfinnofficial.substack.com/feed"),
        ("The Moonshot Podcast (X / Astro Teller)", "https://feeds.megaphone.fm/moonshot"),
        ("The Salim Ismail Podcast", "https://feeds.buzzsprout.com/2179612.rss"),
    ],
}

USER_AGENT = "OpenClaw Daily AI Report (+local script)"
TIMEOUT_S = 20
MAX_ITEMS_PER_FEED = 6


def _clean_html_to_text(s: str) -> str:
    if not s:
        return ""
    soup = BeautifulSoup(s, "html.parser")
    txt = soup.get_text(" ", strip=True)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def _fetch_feed(url: str):
    # feedparser can fetch itself, but we fetch with requests so we can set headers/timeouts.
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S)
    r.raise_for_status()
    return feedparser.parse(r.content)


def _fmt_date(entry) -> str:
    # Prefer published_parsed then updated_parsed
    t = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not t:
        return ""
    try:
        return time.strftime("%Y-%m-%d", t)
    except Exception:
        return ""


def build_html(report_date: str, sections):
    # Minimal CSS (good in Safari/Chrome). No external assets.
    css = """
    body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:32px;color:#111;line-height:1.45}
    h1{font-size:26px;margin:0 0 6px}
    .sub{color:#555;margin:0 0 22px}
    h2{margin:26px 0 10px;font-size:18px;border-top:1px solid #eee;padding-top:18px}
    .feed{margin:18px 0 8px;color:#333;font-weight:600}
    ul{margin:8px 0 18px;padding-left:18px}
    li{margin:10px 0}
    a{color:#0a66c2;text-decoration:none}
    a:hover{text-decoration:underline}
    .meta{color:#666;font-size:12px;margin-top:2px}
    .desc{color:#222;font-size:13px;margin-top:6px}
    .footer{color:#777;font-size:12px;margin-top:24px;border-top:1px solid #eee;padding-top:14px}
    code{background:#f6f6f6;padding:2px 4px;border-radius:4px}
    """

    parts = [
        "<!doctype html>",
        "<html><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>Daily AI Report — {html.escape(report_date)}</title>",
        f"<style>{css}</style>",
        "</head><body>",
        f"<h1>Daily AI Report</h1>",
        f"<p class='sub'>{html.escape(report_date)} • Curated from RSS feeds (news + podcasts/newsletters)</p>",
    ]

    for section_name, feeds in sections.items():
        parts.append(f"<h2>{html.escape(section_name)}</h2>")
        for feed_name, items in feeds:
            parts.append(f"<div class='feed'>{html.escape(feed_name)}</div>")
            if not items:
                parts.append("<p class='meta'>No items (feed error or empty).</p>")
                continue
            parts.append("<ul>")
            for it in items:
                title = html.escape(it.get("title", "(untitled)"))
                link = html.escape(it.get("link", ""))
                date = html.escape(it.get("date", ""))
                source = html.escape(it.get("source", ""))
                desc = html.escape(it.get("desc", ""))

                parts.append("<li>")
                if link:
                    parts.append(f"<a href='{link}' target='_blank' rel='noopener noreferrer'>{title}</a>")
                else:
                    parts.append(f"{title}")

                meta_bits = " • ".join([b for b in [date, source] if b])
                if meta_bits:
                    parts.append(f"<div class='meta'>{meta_bits}</div>")
                if desc:
                    parts.append(f"<div class='desc'>{desc}</div>")
                parts.append("</li>")
            parts.append("</ul>")

    parts.append(
        "<div class='footer'>Generated locally by OpenClaw at <code>daily-ai-report/scripts/generate_report.py</code>. "
        "If a feed breaks, update the RSS URL list at the top of the script.</div>"
    )
    parts.append("</body></html>")

    return "\n".join(parts)


def main():
    os.makedirs(SITE_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    now = datetime.now()
    report_date = now.strftime("%Y-%m-%d")

    sections = {}

    for section_name, feed_list in FEEDS.items():
        out_feeds = []
        for feed_name, feed_url in feed_list:
            items_out = []
            try:
                parsed = _fetch_feed(feed_url)
                entries = getattr(parsed, "entries", []) or []
                for e in entries[:MAX_ITEMS_PER_FEED]:
                    title = getattr(e, "title", "") or ""
                    link = getattr(e, "link", "") or ""
                    date = _fmt_date(e)

                    summary = getattr(e, "summary", "") or getattr(e, "description", "") or ""
                    summary_txt = _clean_html_to_text(summary)
                    if len(summary_txt) > 240:
                        summary_txt = summary_txt[:237] + "..."

                    items_out.append(
                        {
                            "title": title.strip(),
                            "link": link.strip(),
                            "date": date,
                            "source": _domain(link) or _domain(feed_url),
                            "desc": summary_txt,
                        }
                    )
            except Exception as ex:
                items_out = []

            out_feeds.append((feed_name, items_out))

        sections[section_name] = out_feeds

    html_out = build_html(report_date, sections)

    dated_path = os.path.join(REPORTS_DIR, f"{report_date}.html")
    with open(dated_path, "w", encoding="utf-8") as f:
        f.write(html_out)

    # Update stable links
    with open(LATEST_PATH, "w", encoding="utf-8") as f:
        f.write(html_out)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(html_out)

    print(dated_path)


if __name__ == "__main__":
    main()
