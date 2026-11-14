"""7-day health review of the news pipeline.

Reads site/data/health.json (one entry per run) and news.json, writes site/data/review.json.
`python review.py --strict` exits 1 when there is a severe problem (the workflow then fails
and GitHub emails the repo owner).
"""
import json
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "site" / "data"
WINDOW_DAYS = 7


def ts(s: str) -> float:
    return datetime.fromisoformat(s).timestamp()


def build_review(runs: list[dict], articles: list[dict], now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    issues: list[dict] = []

    def issue(level, msg):
        issues.append({"level": level, "msg": msg})

    runs = sorted(runs, key=lambda r: r["t"])
    review = {"generated": now.isoformat(), "window_days": WINDOW_DAYS, "runs": len(runs)}

    # --- coverage and run cadence -------------------------------------------------
    if runs:
        span_days = (now.timestamp() - ts(runs[0]["t"])) / 86400
        gaps = [(ts(b["t"]) - ts(a["t"])) / 60 for a, b in zip(runs, runs[1:])]
        review["since"] = runs[0]["t"]
        review["last_run"] = runs[-1]["t"]
        review["span_days"] = round(span_days, 1)
        review["complete"] = span_days >= WINDOW_DAYS - 0.1
        review["cadence_min"] = {
            "median": round(statistics.median(gaps), 1) if gaps else None,
            "max": round(max(gaps), 1) if gaps else None,
            "runs_per_day": round(len(runs) / max(span_days, 1 / 24), 1),
        }
        if not review["complete"]:
            issue("info", f"Collecting data: {span_days:.1f} of {WINDOW_DAYS} days so far.")
        if gaps and statistics.median(gaps) > 30:
            issue("warn", f"Runs are infrequent: median gap {statistics.median(gaps):.0f} min (GitHub throttling?).")
        age_h = (now.timestamp() - ts(runs[-1]["t"])) / 3600
        if age_h > 3:
            issue("severe", f"No pipeline run for {age_h:.1f} hours.")
    else:
        review.update({"since": None, "last_run": None, "span_days": 0, "complete": False,
                       "cadence_min": None})
        issue("severe", "No runs recorded yet.")

    # --- per-source health --------------------------------------------------------
    names = sorted({n for r in runs for n in r["s"]})
    newest_by_source = {}
    for a in articles:
        t = ts(a["published"])
        if t > newest_by_source.get(a["source"], 0):
            newest_by_source[a["source"]] = t
    sources = []
    for n in names:
        seen = [r["s"][n] for r in runs if n in r["s"]]
        ok_runs = [s for s in seen if s[0]]
        consec_fail = 0
        for s in reversed(seen):
            if s[0]:
                break
            consec_fail += 1
        zero_tail = 0
        for s in reversed(seen):
            if s[0] and s[1] == 0:
                zero_tail += 1
            else:
                break
        newest = newest_by_source.get(n)
        info = {
            "name": n,
            "runs": len(seen),
            "ok_pct": round(100 * len(ok_runs) / len(seen), 1) if seen else None,
            "avg_items": round(statistics.mean(s[1] for s in ok_runs), 1) if ok_runs else 0,
            "consecutive_failures": consec_fail,
            "newest_article_hours": round((now.timestamp() - newest) / 3600, 1) if newest else None,
        }
        status = "ok"
        if consec_fail >= 3:
            status = "warn"; issue("warn", f"{n}: failing for the last {consec_fail} runs.")
        if len(seen) >= 10 and info["ok_pct"] < 90:
            status = "warn"; issue("warn", f"{n}: only {info['ok_pct']}% of runs succeeded.")
        if zero_tail >= 5:
            status = "warn"; issue("warn", f"{n}: fetched OK but returned 0 items in the last {zero_tail} runs (feed format change or filter too strict?).")
        if newest is None or info["newest_article_hours"] > 48:
            status = "warn"; issue("warn", f"{n}: no new article in the last 48h.")
        info["status"] = status
        sources.append(info)
    review["sources"] = sources
    if runs and all(not v[0] for v in runs[-1]["s"].values()):
        issue("severe", "Every source failed in the latest run.")

    # --- content ------------------------------------------------------------------
    per_day = Counter()
    for r in runs:
        per_day[r["t"][:10]] += r.get("new", 0)
    review["new_per_day"] = dict(sorted(per_day.items()))
    review["articles"] = {
        "total": len(articles),
        "by_kind": dict(Counter(a.get("kind", "news") for a in articles)),
        "by_source": dict(Counter(a["source"] for a in articles)),
    }

    review["issues"] = issues
    review["verdict"] = ("severe" if any(i["level"] == "severe" for i in issues)
                         else "attention" if any(i["level"] == "warn" for i in issues)
                         else "healthy")
    return review


def main(argv: list[str]) -> int:
    try:
        runs = json.loads((DATA / "health.json").read_text(encoding="utf-8"))["runs"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        runs = []
    try:
        articles = json.loads((DATA / "news.json").read_text(encoding="utf-8"))["articles"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        articles = []
    review = build_review(runs, articles)
    (DATA / "review.json").write_text(json.dumps(review, indent=1), encoding="utf-8")
    print(f"verdict: {review['verdict']} | runs: {review['runs']} | span: {review['span_days']}d")
    for i in review["issues"]:
        print(f"  [{i['level']}] {i['msg']}")
    return 1 if "--strict" in argv and review["verdict"] == "severe" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
