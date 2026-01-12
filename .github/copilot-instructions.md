**Purpose**
- **Short:** Help AI coding agents become productive quickly in this repo by describing the app shape, run/development commands, constraints, and code pointers.

**High-Level Architecture**
- **Single-file GUI + scraper:** The app is a desktop Tkinter GUI that computes an "overall" rank by scraping MCTiers leaderboards. See [main.py](main.py#L1-L220).
- **Major components:**
  - **Constants & config:** `TIER_POINTS`, `GAMEMODES`, `URL` (see [main.py](main.py#L1-L40)).
  - **Browser builder:** `build_driver()` configures a Firefox profile with UA and anti-automation prefs (see [main.py](main.py#L35-L52)).
  - **Scraper:** `scrape_top_scores()` scrolls the leaderboard and extracts numeric scores with deduplication and stability logic (see [main.py](main.py#L53-L115)).
  - **Business logic & UI:** score/rank calculation and Tkinter widgets, with `calculate()` gluing scrape + UI (see [main.py](main.py#L116-L160) and [main.py](main.py#L160-L199)).

**Run & Developer Workflow**
- **Run locally:** the app is launched with `python main.py` in a Python environment that has `selenium` installed.
- **Required external deps:** `selenium` plus a system Firefox and matching `geckodriver` on `PATH`. The scraper intentionally runs a headful Firefox (not headless) to avoid Cloudflare.
- **Install example:**
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install selenium`
  - Ensure `firefox` and `geckodriver` are available in PATH.

**Key Patterns & Project Constraints (do not change lightly)**
- **Headful Firefox required:** `build_driver()` explicitly sets `options.headless = False` to avoid Cloudflare blocking — do not switch to headless without replacing anti-bot measures (see [main.py](main.py#L35-L42)).
- **User-Agent spoofing & prefs:** code sets `general.useragent.override` and toggles `dom.webdriver.enabled` to reduce automation signals — preserve this approach or provide equivalent alternatives when changing browsing behavior (see [main.py](main.py#L44-L52)).
- **Stability/deduplication logic in scraping:** `scrape_top_scores()` uses a loop with `stable_loops` and de-duplication to detect when no more rows are loading; retain or reimplement this when altering scraping (see [main.py](main.py#L53-L115)).
- **No network/time assumptions:** expect Cloudflare/rate-limiting; add retries and careful waits rather than fast aggressive scraping.

**When Editing / Extending**
- **If changing scraping logic:** write unit-tests that mock Selenium `webdriver` and `find_elements`. Do not run real Cloudflare-protected pages in CI.
- **If adding headless or CI-friendly scraping:** implement an explicit switch and document how to provide authenticated/whitelisted access or use API alternatives — do not silently flip `headless`.
- **If packaging:** note that bundling with PyInstaller requires bundling `geckodriver` and testing on target platforms.

**Safety & Testing Notes**
- **Local dev only:** scraping a live site can be flaky; prefer mocking in tests.
- **Respect site policies:** this project already uses measures to look like a browser — retain conservative request rates and avoid mass automated runs.

**References (quick links)**
- `TIER_POINTS` and constants: [main.py](main.py#L14-L21)
- `REAL_USER_AGENT` and UA usage: [main.py](main.py#L27-L33)
- `build_driver()` (Firefox prefs): [main.py](main.py#L35-L52)
- `scrape_top_scores()` (scroll/load/dedupe): [main.py](main.py#L53-L115)
- UI entry / mainloop: [main.py](main.py#L160-L199)

If any section is unclear or you'd like the file to include more examples (mocking snippets, packaging notes, or CI guidance), tell me which part to expand.
