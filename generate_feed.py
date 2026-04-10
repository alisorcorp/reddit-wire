#!/usr/bin/env python3
"""Generate an RSS 2.0 podcast feed (output/feed.xml) from episodes in output/.

Scans for "Reddit Daily - <Month D, YYYY> - Final.mp3" (preferred) or the
unmixed fallback "Reddit Daily - <Month D, YYYY>.mp3", pairs each with its
matching `.txt` script for the episode description, and emits an
iTunes-compatible RSS feed suitable for Apple Podcasts.

Configuration via env vars (set in .env):
  PODCAST_TITLE            Show title            (default: "Reddit Wire")
  PODCAST_DESCRIPTION      Show description      (default: generic)
  PODCAST_AUTHOR           Show author           (default: "Reddit Wire")
  PODCAST_BASE_URL         Public base URL       (default: http://localhost:8080)
                           e.g. https://mac.your-tailnet.ts.net
  PODCAST_ARTWORK_URL      Full URL to cover art (default: {BASE_URL}/artwork.jpg)
  PODCAST_LANGUAGE         RFC 5646 tag          (default: en-us)
  PODCAST_CATEGORY         iTunes category       (default: Technology)

Usage:
  python3 generate_feed.py
"""
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape

from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = Path(__file__).parent / "output"
FEED_FILE = OUTPUT_DIR / "feed.xml"

SHOW_TITLE = os.getenv("PODCAST_TITLE", "Reddit Wire")
SHOW_DESCRIPTION = os.getenv(
    "PODCAST_DESCRIPTION",
    "Your daily Reddit briefing, summarized and read aloud.",
)
SHOW_AUTHOR = os.getenv("PODCAST_AUTHOR", "Reddit Wire")
BASE_URL = os.getenv("PODCAST_BASE_URL", "http://localhost:8080").rstrip("/")
ARTWORK_URL = os.getenv("PODCAST_ARTWORK_URL", f"{BASE_URL}/artwork.jpg")
LANGUAGE = os.getenv("PODCAST_LANGUAGE", "en-us")
CATEGORY = os.getenv("PODCAST_CATEGORY", "Technology")

EPISODE_RE = re.compile(
    r"^Reddit (?P<variant>\w+) - (?P<date>[A-Za-z]+ \d{1,2}, \d{4})(?P<final> - Final)?\.mp3$"
)


def parse_episode_date(date_str: str) -> datetime:
    """Parse 'April 10, 2026' into a timezone-aware datetime (noon UTC)."""
    return datetime.strptime(date_str, "%B %d, %Y").replace(
        hour=12, tzinfo=timezone.utc
    )


def probe_duration_seconds(mp3_path: Path) -> int:
    """Return MP3 duration in whole seconds via ffprobe. Zero on failure."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(mp3_path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        return int(float(result.stdout.strip()))
    except (subprocess.CalledProcessError, ValueError, subprocess.TimeoutExpired):
        return 0


def format_duration(seconds: int) -> str:
    """Format seconds as H:MM:SS for itunes:duration."""
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


def find_episodes() -> list[tuple[datetime, Path, Path | None]]:
    """Return [(pub_date, mp3_path, txt_path|None), ...] newest first.

    When both "- Final.mp3" and the plain fallback exist for a given
    (date, variant), the Final mix wins. Multiple variants per date
    (e.g. a Daily and an Afternoon) coexist as separate episodes.
    """
    by_key: dict[tuple[datetime, str], tuple[Path, bool]] = {}
    for p in OUTPUT_DIR.glob("Reddit *.mp3"):
        m = EPISODE_RE.match(p.name)
        if not m:
            continue
        try:
            date = parse_episode_date(m.group("date"))
        except ValueError:
            continue
        variant = m.group("variant")
        is_final = m.group("final") is not None
        key = (date, variant)
        existing = by_key.get(key)
        if existing is None or (is_final and not existing[1]):
            by_key[key] = (p, is_final)

    episodes: list[tuple[datetime, Path, Path | None]] = []
    # Sort: date desc, then variant (so Daily precedes Afternoon on same day)
    for (date, _variant), (mp3_path, _) in sorted(
        by_key.items(), key=lambda kv: (kv[0][0], kv[0][1]), reverse=True
    ):
        # Script file has no " - Final" suffix
        base = re.sub(r" - Final$", "", mp3_path.stem)
        txt_path = OUTPUT_DIR / f"{base}.txt"
        episodes.append((date, mp3_path, txt_path if txt_path.exists() else None))
    return episodes


def episode_description(txt_path: Path | None, fallback: str) -> str:
    """Return first ~600 chars of the script, or a fallback."""
    if txt_path is None:
        return fallback
    try:
        text = txt_path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return fallback
    if not text:
        return fallback
    if len(text) > 600:
        text = text[:600].rsplit(" ", 1)[0].rstrip(".,;:") + "..."
    return text


def build_feed() -> int:
    if not OUTPUT_DIR.exists():
        print(f"Error: {OUTPUT_DIR} does not exist", file=sys.stderr)
        return 1

    episodes = find_episodes()
    if not episodes:
        print("Warning: no episodes found in output/", file=sys.stderr)

    now = format_datetime(datetime.now(timezone.utc))
    items: list[str] = []
    for date, mp3_path, txt_path in episodes:
        filesize = mp3_path.stat().st_size
        duration = probe_duration_seconds(mp3_path)
        pub_date = format_datetime(date)
        title = re.sub(r" - Final$", "", mp3_path.stem)
        description = episode_description(
            txt_path, f"Reddit Wire briefing for {date.strftime('%B %d, %Y')}."
        )
        enclosure_url = f"{BASE_URL}/{quote(mp3_path.name)}"
        items.append(
            f"""    <item>
      <title>{escape(title)}</title>
      <description><![CDATA[{description}]]></description>
      <pubDate>{pub_date}</pubDate>
      <enclosure url="{escape(enclosure_url)}" length="{filesize}" type="audio/mpeg"/>
      <guid isPermaLink="false">{escape(enclosure_url)}</guid>
      <itunes:duration>{format_duration(duration)}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>"""
        )

    items_xml = "\n".join(items)
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>{escape(SHOW_TITLE)}</title>
    <link>{escape(BASE_URL)}</link>
    <description>{escape(SHOW_DESCRIPTION)}</description>
    <language>{escape(LANGUAGE)}</language>
    <lastBuildDate>{now}</lastBuildDate>
    <generator>Reddit Wire</generator>
    <itunes:author>{escape(SHOW_AUTHOR)}</itunes:author>
    <itunes:summary>{escape(SHOW_DESCRIPTION)}</itunes:summary>
    <itunes:category text="{escape(CATEGORY)}"/>
    <itunes:explicit>false</itunes:explicit>
    <itunes:image href="{escape(ARTWORK_URL)}"/>
    <itunes:owner>
      <itunes:name>{escape(SHOW_AUTHOR)}</itunes:name>
    </itunes:owner>
{items_xml}
  </channel>
</rss>
"""
    FEED_FILE.write_text(feed, encoding="utf-8")
    print(f"Feed written: {FEED_FILE} ({len(episodes)} episode{'s' if len(episodes) != 1 else ''})")
    return 0


if __name__ == "__main__":
    sys.exit(build_feed())
