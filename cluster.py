"""Group articles that cover the same event, so they can be compared across sources.

No AI here: articles are linked when their title+summary wording is similar (TF-IDF cosine) and they were
published close together in time. Output: site/data/clusters.json, one entry per "top story", i.e. a group
covered by at least MIN_SOURCES different sources. The scheduled Claude task reads this file and writes the
actual comparison to site/data/stories.json (see routines/whole-story.md).
"""
import hashlib
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
NEWS_FILE = ROOT / "site" / "data" / "news.json"
OUTPUT_FILE = ROOT / "site" / "data" / "clusters.json"

KINDS = {"news", "live"}     # skip videos, galleries and polls
WINDOW_DAYS = 7              # only look at recent articles
MAX_GAP_HOURS = 72           # linked articles must be published within this of each other
THRESHOLD = 0.30             # cosine similarity needed to link two articles
MIN_SOURCES = 3              # a "top story" is covered by at least this many different sources

STOP = set("""a about after again all also am an and any are as at be because been before being but by can could did do
does for from had has have he her his how i if in into is it its just like more most new not now of off on one only or our
out over said say says she so some than that the their them then there these they this to up us was we were what when which
who why will with would you your man manchester united utd utds club news latest live report reports reaction""".split())


def tokens(text: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if len(w) < 3 or w in STOP:
            continue
        out.append(w[:-1] if w.endswith("s") and len(w) > 4 else w)  # crude plural stripping
    return out


def vectors(articles: list[dict]) -> list[dict]:
    """TF-IDF vectors (unit length). Title counts double because it carries the event."""
    docs = [Counter(tokens(a["title"]) * 2 + tokens(a.get("summary", ""))) for a in articles]
    df = Counter(t for d in docs for t in d)
    n = len(docs)
    vecs = []
    for d in docs:
        v = {t: (1 + math.log(c)) * math.log((n + 1) / (df[t] + 0.5)) for t, c in d.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({t: x / norm for t, x in v.items()})
    return vecs


def cosine(a: dict, b: dict) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(t, 0.0) for t, x in a.items())


def hours_apart(a: dict, b: dict) -> float:
    return abs(datetime.fromisoformat(a["published"]).timestamp()
               - datetime.fromisoformat(b["published"]).timestamp()) / 3600


def build_clusters(articles: list[dict], now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    cutoff = now.timestamp() - WINDOW_DAYS * 86400
    pool = [a for a in articles
            if a.get("kind", "news") in KINDS and datetime.fromisoformat(a["published"]).timestamp() >= cutoff]
    vecs = vectors(pool)

    parent = list(range(len(pool)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(pool)):
        for j in range(i + 1, len(pool)):
            if hours_apart(pool[i], pool[j]) <= MAX_GAP_HOURS and cosine(vecs[i], vecs[j]) >= THRESHOLD:
                parent[find(i)] = find(j)

    groups: dict[int, list[dict]] = {}
    for i, a in enumerate(pool):
        groups.setdefault(find(i), []).append(a)

    clusters = []
    for members in groups.values():
        sources = sorted({m["source"] for m in members})
        if len(sources) < MIN_SOURCES:
            continue
        members.sort(key=lambda m: m["published"])
        clusters.append({
            "id": hashlib.sha1(members[0]["url"].encode()).hexdigest()[:10],
            "sources": sources,
            "size": len(members),
            "first": members[0]["published"],
            "last": members[-1]["published"],
            "articles": [{k: m.get(k) for k in ("title", "url", "source", "published", "summary", "kind")}
                         for m in members],
        })
    clusters.sort(key=lambda c: c["last"], reverse=True)
    return clusters


def main() -> int:
    try:
        articles = json.loads(NEWS_FILE.read_text(encoding="utf-8"))["articles"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        print("no news.json; nothing to cluster")
        return 0
    clusters = build_clusters(articles)
    OUTPUT_FILE.write_text(json.dumps({"generated": datetime.now(timezone.utc).isoformat(),
                                       "min_sources": MIN_SOURCES, "clusters": clusters},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(clusters)} top stories from {len(articles)} articles")
    return 0


if __name__ == "__main__":
    sys.exit(main())
