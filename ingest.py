"""Man United news ingestion: fetch RSS feeds, normalize, dedupe, write data/news.json."""
import calendar
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser
import requests

ROOT = Path(__file__).parent
SOURCES_FILE = ROOT / "sources.json"
OUTPUT_FILE = ROOT / "site" / "data" / "news.json"
STATUS_FILE = ROOT / "site" / "data" / "status.json"
MAX_ARTICLES = 500
MAX_AGE_DAYS = 30
TIMEOUT = 15
RETRIES = 3
UA = "Mozilla/5.0 (compatible; ManUnitedNewsTracker/0.1)"

# Used for sources that mix several clubs (filter: true).
RELEVANCE = re.compile(
    r"man(?:chester)?\.? ?utd|man(?:chester)? united|old trafford|carrington|"
    r"red devils|amorim|ten hag|ineos|ratcliffe", re.I)

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
                   "utm_content", "at_medium", "at_campaign", "ocid", "cmpid"}

log = logging.getLogger("ingest")


def normalize_url(url: str) -> str:
    """Canonical form used for dedupe: lowercase host, no tracking params/fragment."""
    p = urlsplit(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(p.query) if k not in TRACKING_PARAMS])
    path = p.path.rstrip("/") or "/"
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, query, ""))


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def clean_text(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"&nbsp;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def entry_time(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            return datetime.fromtimestamp(calendar.timegm(st), tz=timezone.utc)
    return None


def entry_image(entry) -> str | None:
    for key in ("media_thumbnail", "media_content"):
        items = entry.get(key) or []
        if items and items[0].get("url"):
            return items[0]["url"]
    for enc in entry.get("enclosures") or []:
        if str(enc.get("type", "")).startswith("image") and enc.get("href"):
            return enc["href"]
    return None


def parse_feed(content: bytes, source: dict) -> list[dict]:
    """Turn raw feed bytes into article dicts. Pure function: easy to test."""
    feed = feedparser.parse(content)
    articles = []
    for e in feed.entries:
        title = clean_text(e.get("title", ""))
        link = e.get("link", "")
        when = entry_time(e)
        if not title or not link or not when:
            continue  # unusable entry
        summary = clean_text(e.get("summary", ""))[:400]
        if source.get("filter") and not RELEVANCE.search(f"{title} {summary} {link}"):
            continue
        articles.append({
            "title": title,
            "url": link,
            "source": source["name"],
            "published": when.isoformat(),
            "summary": summary,
            "image": entry_image(e),
        })
    return articles


def dedupe(articles: list[dict]) -> list[dict]:
    """Drop repeats by normalized URL or normalized title; keep the earliest-seen."""
    seen_urls, seen_titles, out = set(), set(), []
    for a in sorted(articles, key=lambda a: a["published"], reverse=True):
        u, t = normalize_url(a["url"]), normalize_title(a["title"])
        if u in seen_urls or t in seen_titles:
            continue
        seen_urls.add(u)
        seen_titles.add(t)
        out.append(a)
    return out


def fetch(url: str) -> bytes:
    last = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
            r.raise_for_status()
            return r.content
        except requests.RequestException as exc:
            last = exc
            log.warning("fetch %s attempt %d failed: %s", url, attempt, exc)
            time.sleep(2 * attempt)
    raise last


def load_existing() -> list[dict]:
    try:
        return json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))["articles"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return []


def run() -> int:
    sources = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    existing = load_existing()
    fetched, status = [], []
    for src in sources:
        try:
            items = parse_feed(fetch(src["url"]), src)
            fetched.extend(items)
            status.append({"source": src["name"], "ok": True, "items": len(items)})
            log.info("%s: %d items", src["name"], len(items))
        except Exception as exc:  # one bad source must not stop the others
            status.append({"source": src["name"], "ok": False, "error": str(exc)})
            log.error("%s FAILED: %s", src["name"], exc)

    # Merge with previous run so articles that rolled out of a feed are kept.
    merged = dedupe(fetched + existing)
    cutoff = datetime.now(timezone.utc).timestamp() - MAX_AGE_DAYS * 86400
    merged = [a for a in merged if datetime.fromisoformat(a["published"]).timestamp() >= cutoff]
    merged = merged[:MAX_ARTICLES]
    new_count = len(merged) - len({normalize_url(a["url"]) for a in existing} & {normalize_url(a["url"]) for a in merged})

    now = datetime.now(timezone.utc).isoformat()
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    if not any(s["ok"] for s in status):
        log.error("All sources failed; leaving news.json untouched")
    else:
        OUTPUT_FILE.write_text(json.dumps({"updated": now, "articles": merged},
                                          ensure_ascii=False, indent=1), encoding="utf-8")
    STATUS_FILE.write_text(json.dumps({"run": now, "new": new_count, "sources": status},
                                      indent=1), encoding="utf-8")
    log.info("Done: %d articles total, %d new", len(merged), new_count)
    return 0 if any(s["ok"] for s in status) else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(run())
