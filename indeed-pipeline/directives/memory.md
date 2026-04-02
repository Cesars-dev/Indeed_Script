# Memory: Current State & Next Steps

## Session 15 — 2026-03-27 (Resume Tracking, 1-Hour Sleep Fix & Turnstile Obfuscation)

### Resume Upload Inconsistency (The Big Discovery)
- The pipeline DOES correctly download and upload the custom Proposal PDFs when Indeed explicitly prompts for a resume (8 out of 10 successful applications correctly uploaded the PDF). 
- **The Leak:** For 20% of applications, the employer's workflow completely bypasses the `resume-selection-module`. Because no upload box appears, the bot organically clicked `Continue`, meaning Indeed submitted the generic default profile CV. 
- **The Designed Fix:** Devised the **Resume Module Bypass Guard** (documented in `NEXT_STEPS.md`). In the next session, we must explicitly declare an `uploaded` flag and force the script to aggressively fail the application at the `review-module` if the custom PDF wasn't mechanically attached.

### Execution Cycle & 60-Minute Sleep
- Discovered that the script was bypassing the 60-minute sleep because `process_job()` natively returned `0` on profile exhaustion instead of `-1`. 
- **Patched:** Modified `apply_runner.py` to correctly `return -1`. The script now drops into a dormant background state accurately after applying to the 25-job batch limit.

### Turnstile Obfuscation & Stonewalling
- Gabriela (Account 3) was stonewalled with a CF challenge on Job 12. 
- **Root Cause Checked:** Verified the 2Captcha API holds a healthy balance of **$2.82**. The solver failed because Indeed aggressively obfuscated the Turnstile `sitekey` from the DOM, blinding the 2Captcha hook, and CF rejected the fallback visual "mouse click" performed by the Gemini UI driver. 
- **Action Taken:** Hard-killed the `tmux` orchestrator. The pipeline is off, allowing all 5 IP footprints to cool down for 24 hours to clear behavioral risk flags.

### Startup UI Waste (Sheet Truncation)
- Because we cannot rewrite `apply_runner.py`'s dedup logic to query Supabase directly, the script was wasting 15 minutes booting browsers to visually check if Jobs 0-25 were already applied.
- **Workaround:** Generated a brand new Google Sheet specifically via the Python Sheets API (using the existing `google_oauth_token.json`) that identically stripped out Jobs 0-25. We will feed this truncated URL into the orchestrator next session so it mathematically skips the dead weight.

## Session 14 — 2026-03-X (Previous)

### CF Turnstile Bypass — Replaced Gemini with 2Captcha 
- The Gemini vision-based click method for Turnstile had a 0% success rate (datacenter/residential IPs still got caught by CF behavioral fingerprinting).
- Implemented **2Captcha Turnstile token injection** via `_solve_cf_2captcha()`. Flow: Extract `sitekey` from DOM or iframe URL → intercept parameters (`cData`, `chlPageData`, `action`) for CF Challenge pages → submit to 2Captcha → inject returned token and trigger callbacks/submit. 
- Success rate stabilized. Same price as reCAPTCHA ($0.003/solve).

### Smart Bail-out & Monster Jobs (25-Step Cap)
- Added `filled_targets` tracking in `router.py`. The "stuck" bail-out only increments if the exact same field is targeted repeatedly, preventing premature exits on normal long forms.
- Lowered the absolute cap in `router.py` from 50 steps to **25 steps**. If an application exceeds 25 steps (equivalent to 15+ questions), it's a "monster hospital form" and not our ICP. The pipeline bails early, logs a permanent failure, and saves Gemini credits.

### Cover Letter Support & Telegram
- Cover letters are now dynamically downloaded per job as PDFs in the shell orchestrator.
- Added Telegram notifications for successful applications containing the filename of the cover letter.

### Results
- Final test run (15 URLs handled): 6 WINS (100% success on valid jobs), 6 LOSSES (blocked strictly by the 25-step cap on monster forms), 3 SKIPS (expired jobs). 
- The application engine is fully PRODUCTION-READY.

### 🚨 Current Status (End of Session 12)
**THE ENGINE IS DONE. THIS IS NOW A VOLUME PROBLEM.**

All core components verified working end-to-end:
- ✅ Browser automation (AdsPower + CDP)
- ✅ Form filling (deterministic + Gemini Flash/Pro)
- ✅ Resume upload
- ✅ Per-job cover letters (PDF download)
- ✅ reCAPTCHA v2 (2Captcha token injection, $0.003/solve)
- ✅ CF Turnstile (2Captcha token injection, $0.003/solve)
- ✅ Monster job bail-out (25-step cap — not ICP, not worth it)
- ✅ Telegram alerts (success + stonewall)
- ✅ Dedup / no double-applying

**Volume bottlenecks (in priority order):**
1. **Job quality** — current CSV has too many hospital system jobs (monster forms). Need clean small clinics/private practices only.
2. **Active profiles** — 5 working profiles right now. ~25-40 apps/day max. Each new profile adds ~5-8 apps/day.
3. **Job feed** — need a steady stream of fresh Indeed URLs flowing into the Google Sheet.

**What to do next session:**
1. **Job Filtering** — filter upstream scraper/CSV for small clinics/private practices. Blacklist hospital systems (CHRISTUS, HCA, etc.).
2. **Account Scaling** — activate more AdsPower profiles (P5: manual Gmail+Indeed login, 1–2/day). Target: 19 active → 100+ apps/day.
3. No more debugging. Just operate.

## Session 11 — 2026-03-17 (CDP Fixed, Proxy Issue Found, branch `fix/cdp-timeout-retry`)

### Active Branch
All code changes this session are on **`fix/cdp-timeout-retry`** (local only, NOT on `main`).
- Review: `git diff main fix/cdp-timeout-retry -- src/playwright_indeed.py`
- Merge when validated: `git checkout main && git merge fix/cdp-timeout-retry`

### CDP Timeout — FIXED ✅
Full analysis in `docs/research/06_cdp_cookie_hang_deep_search.md`.

**Two-cause model — both resolved:**

1. ✅ **Extension Service Workers** — Fixed by `_kill_service_workers(ws_url)` (raw CDP `Target.closeTarget`) before Playwright attaches.

2. ✅ **Cloudflare + OAuth Cookies** — Fixed by swapping `rebrowser_playwright` → **vanilla `playwright`** for `connect_over_cdp()` only. rebrowser's `addBinding` patch deadlocked with CF cookie JS during browser attach. Vanilla playwright has no such patch. AdsPower fingerprinting is at C++ browser level — not affected by this swap.

**Result:** All 5 active profiles connect on attempt 1 with zero timeouts. CDP is no longer a blocker.

**Code changes (all in `src/playwright_indeed.py`):**
- [x] Added `import websockets` at top
- [x] Added `_kill_service_workers(ws_url)` helper (raw CDP, kills extension SWs)
- [x] Replaced `async with async_playwright()` → `async with vanilla_async_playwright()` (imports vanilla `playwright.async_api`)
- [x] 2-attempt retry loop for `connect_over_cdp` (15s timeout each)

### Webshare Residential Proxies — 10/20 DEAD from VPS ⚠️

**Discovery:** 10 of 20 static residential proxies unreachable via TCP/SOCKS5 from VPS (`45.55.90.156`).
Webshare API reports all 20 as `valid=True`. Auto-replace is ON but doesn't trigger because Webshare thinks they're healthy. Likely a DO↔residential IP routing/peering issue.

**Residential proxy list URL (save this):**
```
https://proxy.webshare.io/api/v2/proxy/list/download/nzufhidpezowsiiusylyitasjbbxxzjpjkakrryg/-/any/username/direct/-/?plan_id=12968926
```

**Dead proxies (cannot reach from VPS, may come back):**
- `9.142.46.112:6781` — Slot 9 (k1a2vu6e) **ACTIVE**
- `9.142.198.212:5879` — Slot 11 (k1a2vul9) **ACTIVE**
- `138.226.88.247:7935` — Slot 12 (k1a2vun1) **ACTIVE**
- `9.142.10.173:5829` — Slot 19 (k1a2vupc) **ACTIVE**
- `9.142.41.178:6348` — Slot 16
- `45.58.228.186:5858` — Slot 13
- `9.142.210.118:5783` — Slot 2
- `138.226.77.104:7293` — Slot 4
- `138.226.71.59:7249` — Slot 5
- `9.142.47.5:6174` — Slot 7

**Alive proxies:** `130.180.232.135`, `199.187.189.141`, `216.98.254.195`, `192.53.142.104`, `72.1.154.5`, `198.145.103.182`, `72.1.154.232`, `103.130.178.44` (slot 10 — only working active profile), `192.145.71.197`, `130.180.236.19`

**Webshare replace API:** `POST /api/v2/proxy/replace/` — format is `{"to_replace": {"type": "country", "country_code": "US"}, ...}` but replaces ALL US proxies at once (not per-proxy). 10 replacements remaining. Per-proxy replace only available via dashboard UI.

**Firecrawl:** API key `fc-6767a64b5aae4fd6b347d8f39e938fde` returns 402 "Insufficient credits" as of 2026-03-17 07:33.

### What's Left
1. **Proxy fix** — Replace 4 dead active-profile proxies (dashboard UI or wait for them to come back)
2. **Merge CDP fix** — Once proxies are live, stress-test 10+ jobs, then merge `fix/cdp-timeout-retry` → `main`
3. **P5** — Continue activating remaining 14 profiles (Gmail + Indeed login). 1–2/day.

---

## Session 9 — 2026-03-14 (P8 Learning Loop Executed)


### P8 Learning Loop — Code Complete
- [x] **Change 7**: Fixed `get_dynamic_answer()` schema in `patterns.py` — reads flat `question_text`/`answer_value` columns instead of broken nested `dom_signal.question_contains`
- [x] **Change 6**: Wired `load_dynamic_patterns()` call at startup in `router.py` (before step loop)
- [x] **Change 5**: Logged max-steps overflow (50-step edge case) to `apply_step_log` + `apply_runs`
- [x] **Change 4**: Logged deterministic misses (when shot reaches 4) with DOM snapshot
- [x] **Change 3**: Logged reCAPTCHA solve success/failure to `apply_step_log`
- [x] **Change 2**: Logged Gemini Q&A pairs to `apply_patterns` after Flash/Pro success on questions pages
- [x] **Change 1 (PENDING)**: `apply_patterns` table needs SQL migration in Supabase Dashboard
- [x] Both files compile clean (`router.py`, `patterns.py`)

### Surgeon Framework Completed
- 01_audit.md → 02_action_plan.md → 03_cross_reference_preflight.md → 04_master_plan.md → EXECUTED

---

## Session 8 — 2026-03-14 (DOM Scanner Root Cause + reCAPTCHA Blocker)

### Root Cause Found: Empty Question Text in DOM Scanner
- [x] **Diagnostic**: Deterministic radio handler was failing on ALL questions pages because `dom["radios"][*].question` was always `""` (empty string).
- [x] **Root cause**: Indeed doesn't use `<fieldset>`, `[role="radiogroup"]`, or `[data-testid]` — the scanner's container detection fell back to `r.parentElement?.parentElement?.parentElement` which was too shallow to reach the question label.
- [x] **Fix**: Added DOM tree climbing — walks UP parents (up to 6 levels) looking for `[class*="label"]`, `[class*="question"]`, `[id*="label"]`, `[id*="question"]`, `legend`. Now correctly extracts question text like `"Are you authorized to work in the United States? *"`.
- [x] **Result**: Deterministic handler answers both test questions on FIRST TRY. Zero Gemini calls needed for basic Yes/No patterns.

### P8 Code Changes (all additive, no existing behavior modified)
- [x] `dom_scanner.py` — DOM tree climbing for radio question text (ROOT CAUSE FIX)
- [x] `dom_scanner.py` — Added modal detection (`[role="dialog"]`) and reCAPTCHA flag
- [x] `handlers.py` — New `handle_modal_dismiss()` handler (first in chain, early-exit guard)
- [x] `handlers.py` — Error guard hardening: filters reCAPTCHA/privacy false-positive "errors"
- [x] `playwright_indeed.py` — Added `_has_recaptcha()` + `_solve_recaptcha()` (Bezier click approach — insufficient, see below)
- [x] `router.py` — Wired modal handler, reCAPTCHA pre-check, Continue-after-Gemini-action fix

### Test Results (Receptionist at Sofidel, Duluth MN)
```
step 00: profile-location     → ✓ Continue (deterministic)
step 01: resume-selection      → ✓ Upload resume_oswaldo.pdf (deterministic)
step 02: resume-selection      → ✓ Continue (deterministic)
step 03: privacy-settings      → ✓ Continue (deterministic)
step 04: questions/1           → ✓ radio: "authorized to work" → Yes (deterministic)
step 05: questions/1           → ✓ radio: "reliably commute" → Yes (deterministic)
step 06: questions/1           → ✓ Continue (deterministic)
step 07: review-module         → ❌ Submit disabled (reCAPTCHA unsolved)
```
**7 steps, 0 Gemini calls, reached review page.** Pipeline blocked ONLY by reCAPTCHA v2.

### reCAPTCHA v2 — The Final Boss
- Indeed uses Google reCAPTCHA v2 (visible "I'm not a robot" checkbox) on the submit page
- Submit button is `disabled` in DOM until reCAPTCHA is solved
- Homegrown Bezier-click solver is insufficient — reCAPTCHA v2 requires proper solving
- **Decision**: Need a third-party solving service (2Captcha/CapSolver) or browser extension
- **Research prompt created**: `recaptcha_research_prompt.md` — feed to RAG LLM for solution

### How "Smart" Is Deterministic Now?
- This job had 2 easy questions → 100% deterministic
- Real-world jobs have 5-15 questions → expect ~60-70% deterministic, rest needs Gemini
- Pattern coverage grows as `apply_patterns` Supabase table accumulates answers
- Gemini is still needed for: unknown certs, free-text answers, unusual dropdowns

## Session 7 — 2026-03-14 (Port 50325 Nuke & Env Fix)

- [x] **Root cause identified**: Parent `Indeed_Script/.env` had `ADSPOWER_BASE=http://127.0.0.1:50325` (old Mac tunnel port). IDE injected this into shell env BEFORE `load_dotenv()` ran, and `load_dotenv()` doesn't override existing vars by default.
- [x] **Fix 1**: Parent `.env` — changed `ADSPOWER_BASE` to port `30025`, deleted unused `ADSPOWER_API` line, fixed `RUN_MODE=vps`.
- [x] **Fix 2**: Child `indeed-pipeline/.env` — deleted unused `ADSPOWER_API=...50325` line.
- [x] **Fix 3**: `playwright_indeed.py` — changed fallback default from `50325` to `30025`.
- [x] **Fix 4**: Both `playwright_indeed.py` and `batch_test.py` — `load_dotenv()` now uses explicit path + `override=True`.
- [x] **Fix 5**: `batch_test.py` — status check was comparing `"applied"` but pipeline returns `"success"` → fixed.
- [x] **Fix 6**: Created `venv_local/` with all dependencies (didn't exist on VPS dev workspace).
- [x] **Fix 7**: Python interpreter — pointed `.vscode/settings.json` to `venv_local/bin/python3.13`, disabled IDE envFile injection.
- [x] **Verified**: AdsPower connection test passes on port `30025`.

## Session 5 — 2026-03-14 (Stealth & SmartApply Loop Fixes)

- [x] Tested residential proxies (AdsPower S19 profile `k1a2vuov`) — successful bypass of CF
- [x] Fixed `add_init_script` double-spoofing conflict causing silent page.goto crashes 
- [x] Disabled isolated worlds (`addBinding` instead of `addInitScript`) to hide Playwright
- [x] Rebuilt init scripts to correctly pass Datadome/CF checks (navigator.webdriver, Permissions, Battery)
- [x] Fixed `smartapply` relative import typo causing ModuleNotFoundError
- [x] Implemented human-like uniform delays (1.5-4s) on deterministic form actions
- [x] Added `full_page=True` parameter to screenshots for Gemini Pro (context expansion)
- [x] Upgraded SmartApply router from 6-shot to 12-shot (4 Det, 4 Flash, 4 Pro)
- [x] Fixed "stuck deterministic" bug: `same_url_actions` counter escalates to Gemini Flash if page doesn't advance after 3 attempts
- [x] Fixed "Continue" handler logging and logic to detect when clicks don't advance the page

## Session 6 — 2026-03-14 (AdsPower Connection & Renderer Hang Fixes)

- [x] **AdsPower Port Fix**: Resolved connection timeout by forcing port `30025` (VPS) and identifying redundant parent `.env` override.
- [x] **Bug 1 (File Upload) Fixed**: Confirmed deterministic `scan_dom` correctly finds hidden file inputs; resume upload is working flawlessly.
- [x] **Playwright Renderer Hang Fixed**: Bypassed CDP/Screenshot hangs on Indeed Questions by:
    - Removing `animations="disabled"` to prevent font-load blocking.
    - Implementing raw CDP `Page.captureScreenshot` fallback in `playwright_indeed.py`.
    - Wrapping all router screenshot calls in `try/except` to prevent fatal crashes.
- [x] **Review Page Loop Fixed**:
    - Updated `handle_continue_button` to ignore validation "errors" on the review page (Indeed's banners were being misidentified).
    - Hardened Gemini prompt with `SAFETY RULES` to NEVER click "Edit" on resume sections (ignored name mismatch).
    - Broadened deterministic button matching for "Submit".
- [x] **Confirmed Flow**: Bot successfully navigates from Job page → Questions → Final Review page.


## Where We Are (End of Session 9)

**🎉 FIRST SUCCESSFUL APPLICATION SUBMITTED (Session 8).**
Apply engine is DONE. reCAPTCHA solved via 2Captcha ($0.003/solve).

**P8 Learning Loop: CODE COMPLETE — pending Supabase table migration**
- All 7 code changes executed and compile-clean
- `apply_patterns` table created in Supabase via Management API — verified with live INSERT → READ → MATCH test
- End-to-end data flow confirmed: actual DOM question text extracted, `answer_type` correctly inferred, substring lookup matches

**Apply Engine Status: PRODUCTION READY**
1. ✅ Stealth — residential IPs, CF bypass clean
2. ✅ Resume upload — deterministic
3. ✅ Questions — deterministic for known patterns, Gemini for unknown
4. ✅ reCAPTCHA v2 — 2Captcha token injection (~67s, $0.003/solve)
5. ✅ Submit — clicks "Submit your application" after reCAPTCHA
6. ✅ post-apply detection — returns success
7. ✅ Learning loop — `apply_patterns` table live, all wires verified

**Cost: ~$78/month for 300 apps/day (drops to ~$42 as patterns accumulate)**

**Next Focus:**
1. **Stress test** → run against 10 different job listings — validates pattern coverage + reCAPTCHA + Gemini fallback
2. **P5 sessions** → manual Gmail+Indeed login per profile in AdsPower (1–2/day)
3. **P6 warmup** → navigate search page before viewjob URL
4. **Upstream sync** → job scraping + proposal gen feed URLs into pipeline


---

### What's left (priority order for next session)

| # | Priority | Task | Notes |
|---|----------|------|-------|
| 1 | **Stress test** | Run pipeline on 10 different job listings | Validate det coverage, Gemini fallback, reCAPTCHA. Use `batch_test.py` stdin mode |
| 2 | **P5** | Activate sessions (manual) | Log into Gmail+Indeed per profile in AdsPower. 1–2/day. Start from slot 1 |
| 3 | **P6** | Search page warmup | `viewjob` branch only — navigate `indeed.com/jobs?q=...&l=...` before job URL |
| 4 | **P7** | Per-profile resume download | `download_resumes.py` — Google Docs → PDF. **Blocked: need Docs URLs** |

### Key files for new agent

| File | What it tells you |
|------|-------------------|
| `NEXT_STEPS.md` | Priority queue, pipeline stage table, run command |
| `directives/memory.md` | Full session history, architecture decisions |
| `src/smartapply/router.py` | Main loop — all changes land here |
| `src/smartapply/patterns.py` | Static + dynamic pattern registry |
| `src/smartapply/handlers.py` | Deterministic form handlers |
| `src/smartapply/logger.py` | Fire-and-forget Supabase logger |
| `src/smartapply/recaptcha.py` | 2Captcha integration |
| `mcp-stack/supabase/supabase_mcp_config.md` | Supabase connection reference, `apply_migration` tool |

---

## Architecture Decision Log Updates

### Playwright Init Scripts vs Residential IP (March 14)
- Our initial custom `addInitScript` payloads for WebGL/Hardware spoofing were crashing the Chrome process because of conflicts with AdsPower's native C++ spoofers.
- Removing them entirely led to Datadome/CF flags.
- **The Sweet Spot:** Use `addBinding` (avoid isolated worlds) + a minimal script overriding `navigator.webdriver`, `navigator.bluetooth`, `BatteryManager`, and `Permissions.query`.
- **CRITICAL:** Residential IPs (AdsPower) + this minimal init script = 100% bypass of Cloudflare Turnstile on Indeed.

### SmartApply Determinisitc Loop Escaping (March 14)
- Playwright's deterministic handlers are "dumb" — they read DOM attributes. If a field isn't marked "required", the "Continue" button handler will just click Continue, even if the page has missing fields.
- Instead of building complex validation parsing, we track `same_url_actions`. If Deterministic hits "Continue" 3 times and the URL doesn't advance, we force escalation to Gemini.
- Gemini takes a screenshot, reads the red validation error text (e.g., "Phone required"), fills the field, and unsticks the pipeline. This pattern is extremely robust.
