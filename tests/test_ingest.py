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


def _rss(title, tags, desc="x"):
    cats = "".join(f"<category>{t}</category>" for t in tags)
    return f"""<rss version="2.0"><channel><item><title>{title}</title><link>http://a.com/{abs(hash(title))}</link>
    <description>{desc}</description><pubDate>Wed, 12 Nov 2026 10:00:00 GMT</pubDate>{cats}</item></channel></rss>""".encode()


def test_tags_mode_keeps_primary_united_tag():
    src = {"name": "G", "filter": "tags"}
    assert len(ingest.parse_feed(_rss("Midfield rebuild talk", ["Manchester United", "Football"]), src)) == 1


def test_tags_mode_drops_league_roundup():
    src = {"name": "G", "filter": "tags"}
    raw = _rss("10 talking points from the weekend", ["Premier League", "Manchester United", "Arsenal"])
    assert ingest.parse_feed(raw, src) == []


def test_tags_mode_keyword_rescues_untagged_primary():
    src = {"name": "G", "filter": "tags"}
    raw = _rss("Why Carrick was sacked", ["Premier League", "Manchester United"])
    assert len(ingest.parse_feed(raw, src)) == 1


def test_keywords_mode_and_legacy_true():
    other = _rss("Arsenal beat Barca", [])
    for mode in ("keywords", True):
        assert ingest.parse_feed(other, {"name": "S", "filter": mode}) == []
    assert len(ingest.parse_feed(other, {"name": "S", "filter": False})) == 1


# ---- classification -------------------------------------------------------------
def _art(url, title="Some title"):
    return {"url": url, "title": title}


def test_classify_live_poll_video_gallery_news():
    c = ingest.classify
    assert c(_art("https://www.manchestereveningnews.co.uk/sport/football/football-news/man-united-news-live-mauricio-34905073")) == "live"
    assert c(_art("https://www.manchestereveningnews.co.uk/sport/football/mauricio-pochettino-press-conference-live-34906479")) == "live"
    assert c(_art("https://www.theguardian.com/football/live/2026/nov/08/man-utd-v-aston-villa-premier-league-live")) == "live"
    assert c(_art("https://www.theguardian.com/football/2026/nov/12/carrick-sacked-relegation-zone-live")) == "live"
    assert c(_art("https://www.skysports.com/football/news/transfer-news-live-updates-and-latest-on-deals")) == "live"
    assert c(_art("https://x.com/football-news/poll-mauricio-pochettino-success-34907311", "Poll: Will he succeed?")) == "poll"
    assert c(_art("https://www.bbc.co.uk/sport/football/videos/cm3vgx55kp3ro")) == "video"
    assert c(_art("https://x.com/football-news/gallery/michael-carricks-crazy-final-week-34901278")) == "gallery"
    assert c(_art("https://x.com/news/a", "Carrick's last week in pictures")) == "gallery"
    assert c(_art("https://x.com/news/why-carrick-was-sacked", "Why Carrick was sacked")) == "news"


def test_classify_avoids_false_positives():
    c = ingest.classify
    assert c(_art("https://x.com/news/fans-live-in-fear-34000", "Man United fans live in fear of another loss")) == "news"
    assert c(_art("https://x.com/news/delivered-the-goods", "Alive and kicking: United deliver")) == "news"
    assert c(_art("https://x.com/news/pollock-signs", "Pollock signs new deal")) == "news"
