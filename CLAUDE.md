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
        2b. python cluster.py -> group same-event articles (3+ sources) into site/data/clusters.json
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
| `cluster.py` | Groups articles about the same event (TF-IDF similarity, no AI). Threshold 0.30 was tuned on real data: lower values wrongly merge separate events |
| `routines/whole-story.md` | Instructions for the scheduled Claude cloud task that writes the Whole story analyses |
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
- **Whole story tab (new, 22 Nov 2026):** the owner wants each big story compared across sources to expose bias and give
  one fuller account. `cluster.py` finds events covered by 3+ sources (`clusters.json`). A **scheduled Claude cloud task**
  (runs on the owner's Claude plan, no extra API bill; the owner chose this) follows `routines/whole-story.md`: it reads the
  full article text, then writes `site/data/stories.json` (agree / differ / how each source framed it / balanced summary,
  with links to originals). The app tab shows it, labelled as AI-written. Rules: own words only, never store or commit article
  text (the repo is public), evidence-based bias notes, never judge a source by reputation. Until the task exists and has
  run, the tab honestly says there are no comparisons yet.
  The old time-range button "Whole story" was renamed **All time**.
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
  The timer is verified working (see Status).
- About 1% of runs fail at the GitHub Pages deploy step with "No artifacts named github-pages were found". This is a
  temporary GitHub-side glitch, the next run recovers, and the owner chose **not** to add a retry.
- Skipped on purpose: copying full article text (copyright), unfiltered BBC/MEN feeds (they are already United-specific).

## Status (as of 22 Nov 2026)
Phases 1 to 3 are done and deployed: ingestion, automation, and the installable web app. Verified:
- The owner has the app running on an iPhone and it looks right.
- **First full 7-day review (15 to 22 Nov): healthy.** 495 runs recorded, all four sources at 99.8 to 100% success, no issues flagged.
- **Run frequency fixed:** since the cron-job.org timer started (19 Nov), 407 consecutive runs were a median 14.7 min apart, never more than 15. Before it, GitHub's schedule alone left gaps of up to 164 min.
- 341 articles stored: 280 news, 43 video, 15 live, 2 polls, 1 gallery. New articles per day: roughly 9 to 34.
- Manchester Evening News supplies most items (189 of 341); the Guardian the fewest (40). Sky returns only about 1 or 2 United items per run, since its feed is general sport.
- 12 tests pass.

## Still to do
0. **Finish the Whole story automation.** Code, tab and instructions are built and deployed; the cloud task is not created yet.
   Needs the owner to connect GitHub to their Claude account (https://claude.ai/connect-github), because cloud tasks must clone
   the repo. Then, with the `schedule` skill / RemoteTrigger tool: (a) run ONE small test task to verify it can fetch full article
   pages and `git push` to `main` (unverified; cloud network access and branch rules may block this), (b) check how much plan
   allowance a run uses, (c) create the recurring task (minimum interval 1 hour; every few hours is plenty; cron is in UTC, owner is
   in Asia/Singapore, UTC+8), prompt = "follow routines/whole-story.md". If pushes to `main` are not allowed, find another way for
   the result to reach the repo and update the instructions.
1. Check "Add to Home Screen" on the iPhone (the web page itself is confirmed working there).
2. Tune filters from real output: look for missed or off-topic stories now that a full week of data exists.
3. Consider a README for the repo, and a deploy retry (the owner declined the retry once; ask again only if failures become more frequent).
4. Phase 5 features, one at a time: transfer-rumour tags, fixtures and results, push notifications, search and bookmarks.
5. Before 17 Feb 2027: replace the expiring GitHub token in cron-job.org.

## Setting up on the owner's MacBook (macOS)
**If the owner says they are on macOS (or a MacBook), walk them through this step by step in plain language.**
Give one step at a time, say what they should see, and wait for them to confirm before the next step. They are not technical.
1. Open the Terminal app (press Cmd+Space, type "Terminal", press Enter).
2. Install Homebrew if missing: `brew --version` shows whether it is installed. If not, send them to https://brew.sh for the install command.
3. `brew install git gh python`
4. `gh auth login`, choose GitHub.com, HTTPS, then "Login with a web browser". They copy the one-time code shown in Terminal, sign in as **wakdrebar** in the browser, and paste the code. (The code is a code to type into a GitHub page after signing in, not a password.)
5. `gh repo clone wakdrebar/man-united-news`, then `cd man-united-news`
6. `git config user.name wakdrebar` and set the GitHub noreply email (see rule 7 above) so the repo stays free of personal email.
7. `pip3 install -r requirements.txt pytest`, then `python3 -m pytest -q` (expect all tests to pass).
8. Preview: `python3 -m http.server 8765 --directory site`, then open http://localhost:8765 in Safari. Ctrl+C stops it.
9. Open the folder in Claude Code (desktop app, Code tab) so a session starts here with this file loaded.
Daily routine on either computer: `git pull` before starting, then `git add -A`, `git commit -m "..."`, `git push` when done.
Note the chat history does not move between computers; this file is how a new session catches up. Update it after big changes.

## About the owner
Not highly technical. Prefers step-by-step explanations in plain language, and iterative development: get each
step right before adding features. Ask before outward-facing actions (creating repos, pushing, creating accounts).
Uses a Windows laptop (this project was built there), a MacBook and an iPhone.
