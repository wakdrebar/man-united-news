# United News: project handover note

Read this first. It lets a new Claude session on any computer pick up where earlier ones stopped.

## What this is
A Manchester United news tracker. A web app (PWA) the owner uses on desktop and iPhone. It collects
headlines from RSS feeds, removes duplicates, and shows them in a simple mobile-friendly page.
It links out to the original articles; it does not copy full article text.

- Live app: https://wakdrebar.github.io/man-united-news/
- Repo (public): https://github.com/wakdrebar/man-united-news (owner: wakdrebar)
- Health page: `/health.html` on the live site (7-day review of the pipeline)

## How it works
```
cron-job.org (every 15 min) ──► GitHub Actions workflow "Update news and deploy" (.github/workflows/update.yml)
   (GitHub's own cron is a backup, but runs only ~hourly)
        1. run tests (pytest)
        2. python ingest.py   -> fetch feeds, dedupe, classify, write site/data/news.json + status.json + health.json
        3. python review.py   -> write site/data/review.json (7-day health review)
        4. commit changed site/data/* back to the repo
        5. deploy the site/ folder to GitHub Pages
        6. python review.py --strict -> fails the run on severe problems, so GitHub emails the owner
```
No server and no database. The data is JSON files in `site/data/`.

## Files
| Path | Purpose |
|---|---|
| `ingest.py` | Fetch, parse, filter, dedupe, classify, merge with old articles, record run health |
| `review.py` | Builds the 7-day health review (`build_review` is a pure function, tested) |
| `sources.json` | Feed list. Each has `name`, `url`, `filter` |
| `tests/` | pytest tests; `tests/fixtures/` holds saved real feed responses |
| `site/index.html`, `app.js`, `style.css` | The app (plain HTML/JS/CSS, no build step) |
| `site/health.html` | Health page |
| `site/sw.js`, `manifest.webmanifest`, `icons/` | Offline support and phone/desktop install |
| `site/data/` | Generated data. **Owned by the automation** |

## Behaviour worth knowing
- **Sources:** BBC Sport, The Guardian, Manchester Evening News, Sky Sports.
- **Filter modes** (`filter` in sources.json): `false` keeps everything; `"keywords"` needs a United keyword
  (Sky is a general-sport feed); `"tags"` keeps an item if a keyword matches or its first tag is "Manchester United"
  (used for the Guardian, whose feed tags league-wide roundups as United too).
  Keyword list is `RELEVANCE` in `ingest.py`. **Update it when the manager changes** (currently Pochettino, after Carrick).
- **Dedupe:** by normalized URL (tracking params removed) or normalized title.
- **Kinds:** each article is `news`, `live`, `poll`, `video` or `gallery`, from its URL slug and title (`classify`).
  The app shows tabs: News, Live & Polls, Media.
- **Retention:** 30 days, max 500 articles. Old stored articles are re-classified on every run.
- **App:** time-range buttons (Today / This week / Last 2 weeks / Whole story, each with a count), source chips,
  refresh button, "NEW" marker, stale-data warning after 3 hours. Tab and range choices are remembered per browser.
- **Service worker:** bump `CACHE` in `site/sw.js` when the list of cached files changes.

## Rules for working on this repo
1. **`git pull` before you start.** The automation commits new data constantly, so the local copy gets behind fast.
2. **Do not commit `site/data/*`.** If a local `python ingest.py` changed them, run `git checkout -- site/data` first.
3. Run `python -m pytest -q` before pushing. The workflow also runs the tests and will not deploy if they fail.
4. Preview locally: `python -m http.server 8765 --directory site`, then open http://localhost:8765
5. Pushing to `main` redeploys the live site within a minute or so.
6. Git warnings about "LF will be replaced by CRLF" on Windows are harmless.
7. Commit author: the owner's GitHub noreply address, not a personal email (the repo is public).
8. Never put tokens or passwords in the repo or in chat.

## Decisions and history
- Chosen approach: iterative. Fix the data pipeline first, then the UI, then features.
- Chose a free static setup (GitHub Pages + Actions) so there is no server to run.
- GitHub's own schedule only delivers about one run per hour, even when set to every 5 minutes. So an external timer
  (cron-job.org) calls the workflow's `workflow_dispatch` every 15 minutes using a fine-grained GitHub token
  limited to this repo (Actions: read and write). **The token expires on 2027-02-17**; after that the timer gets
  HTTP 401 and the app falls back to hourly updates. The owner should make a new token before then.
- About 1% of runs fail at the GitHub Pages deploy step with "No artifacts named github-pages were found". This is a
  temporary GitHub-side glitch, the next run recovers, and the owner chose **not** to add a retry.
- Skipped on purpose: copying full article text (copyright), unfiltered BBC/MEN feeds (they are already United-specific).

## Still to do
1. Check on a real phone that "Add to Home Screen" works (the iPhone view of the app has been confirmed).
2. After a week of data, read the health page and tune filters (missed or off-topic stories).
3. Maybe add a README for the repo.
4. Phase 5 features, one at a time: transfer-rumour tags, fixtures and results, push notifications, search and bookmarks.

## About the owner
Not highly technical. Prefers step-by-step explanations in plain language, and iterative development: get each
step right before adding features. Ask before outward-facing actions (creating repos, pushing, creating accounts).
Uses a Windows laptop (this project was built there), a MacBook and an iPhone.
