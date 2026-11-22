from datetime import datetime, timedelta, timezone

import cluster

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)


def art(title, source, hours_ago=2.0, summary="", kind="news"):
    return {"title": title, "url": f"https://{source.replace(' ', '').lower()}.com/{abs(hash(title))}",
            "source": source, "summary": summary, "kind": kind,
            "published": (NOW - timedelta(hours=hours_ago)).isoformat()}


DRONE = [
    art("Drone operator filmed Pochettino first training session", "BBC Sport", 5, "Footage leaked online"),
    art("Drone footage of Pochettino first training session leaked online", "Sky Sports", 4),
    art("Drone pilot apologises for secretly filming Pochettino training session", "The Guardian", 3),
]
ROONEY = [
    art("Rooney says he considered taking own life at Old Trafford", "BBC Sport", 30),
    art("Rooney contemplated taking own life at lowest point of career", "Sky Sports", 29),
    art("Wayne Rooney reveals he contemplated taking own life", "The Guardian", 28),
]


# Unrelated stories, like the real pool of hundreds of articles. Word weights (IDF) depend on this background.
TOPICS = ["Garnacho wing contract", "Amad Diallo injury", "Dalot suspension", "Onana penalty save", "Mount hamstring",
          "Maguire captaincy", "Casemiro future", "Mainoo England", "Hojlund goals", "Martinez defence", "Shaw fitness",
          "Lindelof return", "Eriksen midfield", "Rashford loan", "Antony transfer", "Wan-Bissaka offer", "Evans coaching",
          "Malacia recovery", "Heaton backup", "Yoro debut", "Zirkzee form", "Ugarte partnership", "Collyer academy",
          "Wheatley prospect", "Gore scouting", "Ratcliffe stadium", "Glazer sale", "Carrington pitches", "Trafford ticketing",
          "Lisandro tackle", "Mazraoui crosses", "Leny aerial", "Bayindir saves", "Dorgu pace", "Fletcher interview"]
FILLER = [art(f"{t} update number {i}", src, 10 + i)
          for i, t in enumerate(TOPICS) for src in ["BBC Sport"][:1]]


def test_same_event_across_three_sources_is_one_story():
    out = cluster.build_clusters(DRONE + FILLER, NOW)
    assert len(out) == 1 and out[0]["size"] == 3 and len(out[0]["sources"]) == 3


def test_different_events_stay_separate():
    out = cluster.build_clusters(DRONE + ROONEY + FILLER, NOW)
    assert len(out) == 2
    for c in out:
        titles = " ".join(a["title"].lower() for a in c["articles"])
        assert ("drone" in titles) != ("rooney" in titles)  # never mixed


def test_needs_at_least_three_sources():
    assert cluster.build_clusters(DRONE[:2] + FILLER, NOW) == []
    two_sources = DRONE[:2] + [art("Drone footage of Pochettino first training session appears", "BBC Sport", 3)]
    assert cluster.build_clusters(two_sources + FILLER, NOW) == []


def test_articles_far_apart_in_time_are_not_linked():
    old = [dict(a, published=(NOW - timedelta(hours=120)).isoformat()) for a in DRONE[:2]]
    mixed = old + [DRONE[2]]
    assert cluster.build_clusters(mixed + FILLER, NOW) == []


def test_videos_polls_and_old_articles_are_ignored():
    videos = [dict(a, kind="video") for a in DRONE]
    assert cluster.build_clusters(videos, NOW) == []
    ancient = [dict(a, published=(NOW - timedelta(days=30)).isoformat()) for a in DRONE]
    assert cluster.build_clusters(ancient, NOW) == []


def test_cluster_id_is_stable_and_sorted_oldest_first():
    first = cluster.build_clusters(DRONE + FILLER, NOW)[0]
    again = cluster.build_clusters(list(reversed(DRONE + FILLER)), NOW)[0]
    assert first["id"] == again["id"]
    assert [a["published"] for a in first["articles"]] == sorted(a["published"] for a in first["articles"])
