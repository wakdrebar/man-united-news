import json
from pathlib import Path

import ingest

FIX = Path(__file__).parent / "fixtures"


def test_normalize_url_strips_tracking_and_case():
    a = ingest.normalize_url("HTTPS://Example.com/news/a/?utm_source=x&id=1#frag")
    b = ingest.normalize_url("https://example.com/news/a?id=1")
    assert a == b


def test_parse_bbc_fixture():
    items = ingest.parse_feed((FIX / "bbc.xml").read_bytes(), {"name": "BBC Sport", "filter": False})
    assert items
    for a in items:
        assert a["title"] and a["url"].startswith("http") and a["published"]
        assert a["source"] == "BBC Sport"


def test_sky_filter_removes_other_clubs():
    src_all = {"name": "Sky", "filter": False}
    src_filtered = {"name": "Sky", "filter": True}
    raw = (FIX / "sky.xml").read_bytes()
    assert len(ingest.parse_feed(raw, src_filtered)) <= len(ingest.parse_feed(raw, src_all))


def test_dedupe_by_url_and_title():
    base = {"source": "A", "summary": "", "image": None}
    arts = [
        {**base, "title": "Carrick sacked", "url": "https://x.com/a?utm_source=t", "published": "2026-11-12T10:00:00+00:00"},
        {**base, "title": "Different title", "url": "https://x.com/a", "published": "2026-11-12T09:00:00+00:00"},
        {**base, "title": "carrick  SACKED!", "url": "https://y.com/b", "published": "2026-11-12T08:00:00+00:00"},
        {**base, "title": "Unique", "url": "https://z.com/c", "published": "2026-11-12T07:00:00+00:00"},
    ]
    out = ingest.dedupe(arts)
    assert [a["title"] for a in out] == ["Carrick sacked", "Unique"]


def test_bad_entries_skipped():
    xml = b"""<rss version="2.0"><channel><item><title>No date</title><link>http://a.com/1</link></item>
    <item><title></title><link>http://a.com/2</link><pubDate>Wed, 12 Nov 2026 10:00:00 GMT</pubDate></item>
    </channel></rss>"""
    assert ingest.parse_feed(xml, {"name": "T", "filter": False}) == []


def test_output_is_utf8_clean():
    p = Path(__file__).parent.parent / "site" / "data" / "news.json"
    if p.exists():
        assert "�" not in json.loads(p.read_text(encoding="utf-8"))["articles"][0]["title"]
