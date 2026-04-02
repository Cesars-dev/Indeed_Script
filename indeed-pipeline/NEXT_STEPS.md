# Next Steps
> Updated: 2026-03-17 (session 11 — CDP root cause fully identified, fix in progress)
> Single source of truth for what to do next. Read top-to-bottom.

---

## ⚠️ Active Work Branch

> All session 11 code changes are on git branch **`fix/cdp-timeout-retry`** (local only, not pushed to `main`).
> To review or merge: `git diff main fix/cdp-timeout-retry -- src/playwright_indeed.py`
> To abandon: `git checkout main`

---

## Current State

**Apply engine is PRODUCTION READY. Infrastructure fully configured. Google Sheet wired.**

👉 **PROGRESS (Session 10):**
- **All 19 profiles on residential proxies** — synced AdsPower ↔ Supabase.
- **5 profiles activated** — slots 9, 10, 11, 12, 19 (active sessions + phone numbers).
- **Google Sheet → Pipeline wired** — Sheet headers renamed to match `apply_runner.py`, OAuth + SA auth working.
- **`gdrive_client.py`** — OAuth primary (user-context, no sharing needed), SA fallback.
- **Proposal Sheet ready**: 57 jobs at `https://docs.google.com/spreadsheets/d/1caEJGtEz9zzMniZuqjSfu6EzxHX7haUHcqk7Bht_RSE`
- **Mac AdsPower tunnel** — persistent via `autossh`.
- **Documentation** — `infrastructure.md`, `README.md`, `mcp-stack/` all current.

👉 **PROGRESS (Session 11 — 2026-03-17, branch `fix/cdp-timeout-retry`):**
- **Root cause of CDP timeout identified** — see BLOCKER section below (two-cause model: SWs + CF cookies).
- **`_kill_service_workers()` added** — raw CDP kills extension SWs before Playwright attaches. Fixes profile 1, not profile 2.
- **Next fix pending** — vanilla `playwright` for `connect_over_cdp` to bypass `rebrowser` addBinding deadlock with CF cookies.

---

## 🔴 BLOCKER — CDP Timeout on `connect_over_cdp`

**Symptom:** AdsPower starts the browser, `_cdp_alive()` passes (port responds to `/json/version`), but Playwright's `connect_over_cdp()` hangs for 15s then times out. WebSocket connects but handshake never completes.

**Root Cause (PROVEN — 2026-03-17):** Two causes identified via controlled A/B experiments (`docs/research/06_cdp_cookie_hang_deep_search.md`):

1. **Extension Service Workers** — AdsPower profiles with browsing history have Chrome extension SWs that deadlock `rebrowser_playwright`'s `addBinding` patch during `connect_over_cdp`. Fixed by `_kill_service_workers()` using raw CDP before attaching. ✅ Partially addresses first profile.

2. **Cloudflare + OAuth Cookies (PRIMARY)** — Profiles with session cookies (155 cookies: `cf_clearance`, `__cf_bm`, `__Secure-*` Indeed tokens, `_iidt` FingerprintJS) cause Chrome to stall during Playwright's CDP initialization sequence. Raw Python `websockets` library connects to the same port instantly — proving the issue is in `rebrowser_playwright`'s `addBinding` patch conflicting with CF cookie JS during browser attach.

**Controlled proof:**
| Test | Result |
|------|--------|
| Fresh profile, no cookies | ✅ 0.1s |
| Fresh profile + proxy (socks5) | ✅ 0.1s |
| Fresh profile + proxy + 155 cookies | ❌ 15s timeout |
| Active profile (noise off, FP overwritten) | ❌ 15s timeout |

**Next Fix: Use vanilla `playwright` for `connect_over_cdp` only**
Documented in `docs/research/05_cdp_timeout_action_plan.md` lines 252-264.
- rebrowser's `addBinding` patch racing with CF cookie JS = deadlock
- Vanilla playwright bypasses the patched connect without losing stealth (AdsPower fingerprinting is at C++ browser level)
- Workaround: import vanilla `playwright` just for connect, use rebrowser browser object afterward

```python
# Fastest proven fix:
import playwright.async_api as vanilla_pw
async with vanilla_pw.async_playwright() as pw:
    browser = await pw.chromium.connect_over_cdp(
        f"http://127.0.0.1:{debug_port}", timeout=15000
    )
```

**Prerequisite:** `pip install playwright==1.52.0` into venv_local (or use already-installed version).

---

**Next Action:**
1. **🔴 Validate vanilla playwright fix** — run Experiment 1 from `docs/research/05_cdp_timeout_action_plan.md`, swap to vanilla for connect only.
2. **Stress test** — Once CDP is stable, run pipeline against 10+ job listings from the proposal sheet.
3. **P5 (Manual Task)** — Continue activating remaining 14 profiles (Gmail + Indeed login). 1–2/day.
4. **P6 (Optimization)** — Search page warmup for `viewjob` branch.
5. **P7** — Per-profile resume download — blocked on Google Docs URLs.

### Pipeline stages
| Stage | Status |
|-------|--------|
| VPS AdsPower headless (port 30025) | ✅ systemd service |
| Playwright CDP on VPS | ✅ confirmed |
| Screenshots in headless | ✅ Skia renderer |
| CF Turnstile bypass | ✅ residential IPs + minimal init script |
| Job page → Apply click | ✅ |
| Resume upload | ✅ `resume_oswaldo.pdf` |
| Phone fill | ✅ from Supabase |
| Profile/location step | ✅ |
| Country dropdown | ⚠️ JS fallback added — untested on fresh run |
| Questions module | ✅ deterministic + Gemini fallback |
| Review page reached | ✅ |
| reCAPTCHA v2 solve | ✅ 2Captcha token injection |
| Submission | ✅ clicks Submit after reCAPTCHA |
| Gemini model | ✅ `gemini-3.1-pro-preview` |
| Learning loop (`apply_patterns`) | ✅ table created, wired, end-to-end verified |

### Rotation strategy — Dead Simple

```
apply(account_1)  → log result → next
apply(account_2)  → log result → next
...
apply(account_19) → log result → sleep(1h)
apply(account_1)  → log result → next   ← round 2
...
```

**Execution handler (same path for every outcome):**
```python
result = await apply_to_job(url, account)
# result = success | failed | skipped | cf_block
upsert_supabase(result)  # log it
# → trigger next account
```

- No math, no conditionals on flow — every result goes to Supabase, pipeline moves on
- 1h sleep after each full cycle of all 19 accounts
- Volume/cadence emerges naturally from apply duration — no hardcoded waits
- CF hit = same flow, just logged as `cf_block`, profile marked in Supabase, continues


---

## ~~🔴 PRIORITY 0 — Solve CF Datacenter IP Block~~ ✅ DONE

Resolved — pipeline now bypasses CF Turnstile via residential proxies on AdsPower profiles.

---

## ~~🔴 PRIORITY 1 — Fix timeout + stone_walled check~~ ✅ DONE

### 1a — Execution limits
**File:** `src/playwright_indeed.py`

- Delete the `asyncio.wait_for` wrapper around `_gemini_loop_inner` — let it run to completion
- Set step limit to **50** in `_gemini_loop_inner` (`range(50)`)
- Update Gemini prompt step display from `/35` to `/50`
- At 10 consecutive action failures: exit loop, return `{"status": "failed", "reason": "10 consecutive failures"}`

**Every exit path follows the same pattern:**
- `success` → log to `executions` → move to next account
- `failed` → log to `executions` → move to next account
- `cf_block` → log to `executions` → move to next account
- `skipped` → log to `executions` → move to next account

### 1b — Stone-walled check
**File:** `src/playwright_indeed.py`

**Before each apply attempt:**
- Read `stone_walled` and `stone_walled_at` from the profile
- If `stone_walled = true` and under 24h since `stone_walled_at`: return `{"status": "skipped", "reason": "stone_walled"}`
- If `stone_walled = true` and over 24h since `stone_walled_at`: PATCH `adspower_profiles` to set `stone_walled=false`, `stone_walled_at=null`, then proceed

**When CF block is detected (Turnstile iframe, `/cdn-cgi/challenge` in URL, or 403 response):**
- PATCH `adspower_profiles` for that profile: `stone_walled=true`, `stone_walled_at=now`, `cf_hits+1`, `last_cf_hit=now`, `risk_level='hot'`
- Return `{"status": "cf_block"}`

---

## ~~🔴 PRIORITY 1.5 — Turnstile Bypass via Gemini~~ ✅ DONE

Phase A complete: `_solve_cf()` (lines 740-851) uses Gemini visual solver with Bezier mouse movement, 6 retries, `_bypass_cf()` iframe fallback. Called in all 3 URL branches. Stonewalling on failure.

---

## ~~🔴 PRIORITY 2 — Wire execution logging~~ ✅ DONE

Fire-and-forget via `smartapply/logger.py` (`log(table, data)` uses `asyncio.create_task()`). `batch_test.py` logs to both `test_run_logs` and `executions` tables without blocking. Dead code (`is_job_applied`, `upsert_applied_job`) deleted from `supabase_client.py`.

---

## ~~🔴 PRIORITY 3 — Per-profile applicant data~~ ✅ DONE

`_load_profiles()` fetches all rows from `adspower_profiles` at startup, cached as `_PROFILES[user_id]`. `PROFILE_DATA` dict and `APPLICANT_*` env vars deleted. All fields (`full_name`, `email`, `phone_number`, `salary_hr`, `salary_yr`, etc.) sourced from Supabase. Resume falls back to `resume_oswaldo.pdf` if `resume_path` is NULL.

---

## ~~🟡 PRIORITY 4 — Job URL sourcing~~ ✅ DONE (test mode)

`batch_test.py` reads URLs from stdin (`_read_urls_from_stdin()`). Production mode: n8n feeds URLs via webhook (n8n config, not pipeline code).

---

## 🟡 PRIORITY 5 — Activate sessions (your manual task)

AdsPower profiles hold persistent sessions — log in once inside AdsPower and the session stays.

Do 1–2 profiles per day. Start from slot 1 — `k19td50a` (slot 10) already has a session.

**Per profile:**
1. Open AdsPower → launch that profile's browser
2. Go to `gmail.com` → log in with that profile's email (from `adspower_profiles`)
3. Go to `indeed.com` → Sign In with that Gmail → confirm homepage shows logged in
4. Find any receptionist job → click Easy Apply → complete the one-time profile wizard (name, phone, resume) → close
5. Set `cookie_status = 'active'` for that `user_id` in Supabase

---

## 🟡 PRIORITY 6 — Search page warmup (viewjob only)

**File:** `src/playwright_indeed.py` — `viewjob` branch only

In the `viewjob` URL handling block, before navigating to the job URL:
1. Navigate to `indeed.com/jobs?q=<search_term>&l=<state>` using values from the job record (default: `"receptionist"` / `"US"` if missing)
2. Let the humanization layer handle the pause
3. Navigate to the job URL

Apply this change to the `viewjob` branch only. The `smartapply` branch already has its own warmup.

---

## 🔵 P7 — Per-profile resume download + upload

**Current state:** Pipeline uploads `resume_oswaldo.pdf` (shared, hardcoded). Need per-profile PDFs sourced from Google Docs.

**Format:** PDF — pipeline already uploads PDF. Google Docs exports to PDF natively — no LibreOffice, no conversion.

**Input:** CSV with one Google Docs URL per profile.

**File:** `scripts/download_resumes.py` (new script, run once before pipeline)

1. Read CSV — each row: `user_id`, `google_doc_url`
2. Download via export URL: `https://docs.google.com/document/d/DOCID/export?format=pdf`
3. Verify file is `> 100kb` — Indeed rejects smaller files
4. Save to `resumes/<user_id>.pdf`
5. Update `adspower_profiles.resume_path` in Supabase with the local path

**Constraint:** Google Doc must be set to "Anyone with link can view" for unauthenticated export to work.

**Pipeline at runtime:** reads `resume_path` from profile dict — falls back to `resume_oswaldo.pdf` if NULL (P3 already handles this).

---

## 🔵 P-NEXT — Long-term

`resume_path` column exists in `adspower_profiles` — all 19 set to NULL, pipeline falls back to `resume_oswaldo.pdf`. P7 will populate these once Google Docs URLs are provided.


## ⚪ DONE — Do not revisit

| Item | Status |
|------|--------|
| `RUN_MODE=local` in `.env` + code guard | ✅ |
| Humanization layer (mouse.wheel, Bezier warmup, init script, honeypot guard) | ✅ |
| Gemini API key + model (`gemini-3.1-pro-preview`) | ✅ upgraded from 2.5-flash |
| AdsPower CDP connect + tunnel | ✅ + fixed debug port (52018) |
| Resume upload | ✅ `resume_oswaldo.pdf` |
| Supabase MCP — both projects connected | ✅ |
| API keys centralized + audit clean | ✅ |
| 10 new AdsPower profiles created (slots 9, 11–19) | ✅ |
| `accounts.json` updated with all 19 profiles | ✅ |
| Supabase `adspower_profiles` updated — 19 rows, slots 1–19 | ✅ |
| Perplexity CF research completed | ✅ `docs/Indeed pipeline strategy deep search.md` |
| Rotation strategy confirmed: 1 apply/session, 20-min cycle, all 19 profiles | ✅ |
| Excessive scrolling fix (removed micro-scrolls, failure scrolls) | ✅ 2026-03-13 |
| Speed up form delays (0.5-1.2s per step, was 0.8-3.0s) | ✅ 2026-03-13 |
| Duplicate select_option fix (iterates all matches) | ✅ 2026-03-13 |
| Phone from Supabase (not hardcoded) | ✅ 2026-03-13 |
| Gemini prompt v3 (page scanning, duplicate radios, multi-slot) | ✅ 2026-03-13 |
| `ADSPOWER_FIXED_PORT` env var for tunneled testing | ✅ 2026-03-13 |
| `tunnel.sh` updated with CDP port 52018 | ✅ 2026-03-13 |
| Fingerprint JSONB column added to `adspower_profiles` | ✅ 2026-03-13 |
| 19/19 profile fingerprints read from AdsPower → Supabase | ✅ 2026-03-13 |
| Dynamic fingerprint injection in `playwright_indeed.py` (replaced hardcoded) | ✅ 2026-03-13 |
| 3 mobile profiles (slots 6, 17, 18) converted to desktop | ✅ 2026-03-13 |
| `deviceMemory` null handling bug fixed (`or 8`) | ✅ 2026-03-13 |
| AdsPower API reference saved to `mcp-stack/adspower/API_REFERENCE.md` | ✅ 2026-03-13 |
| Deploy to VPS (synced via GitHub) | ✅ 2026-03-13 |
| P1.5 Turnstile bypass — `_solve_cf()` Gemini visual solver + `_bypass_cf()` iframe fallback | ✅ 2026-03-13 |
| P2 execution logging — fire-and-forget via `smartapply/logger.py`, dead code cleaned | ✅ 2026-03-13 |
| P3 per-profile applicant data from Supabase (`_load_profiles()` + `_PROFILES` cache) | ✅ 2026-03-13 |
| P4 job URL sourcing — stdin test mode in `batch_test.py` | ✅ 2026-03-13 |
| Warmup speed: viewjob 7-15s (was 22-71s), SmartApply 3-6s (was 10-24s) | ✅ 2026-03-13 |

---

## CF Risk Reference (from Perplexity)

| Signal | Risk | Notes |
|--------|------|-------|
| ~~Datacenter ASN~~ | ~~🔴 #1~~ | ✅ RESOLVED — all 19 profiles now on residential IPs (March 15) |
| Browser fingerprint | 🟠 #2 | AdsPower covers most, but canvas/audio/JA3 still leak |
| WheelEvent isTrusted | 🟡 #3 | Verify we use `page.mouse.wheel()` not `dispatchEvent` |
| Same ASN across 19 accounts | 🟡 #4 | Mitigated — 19 unique residential IPs across different subnets |
| Uniform timing patterns | 🟢 #5 | Already humanized — could vary more |

**What "burned" looks like:**
- CF hit on 1st apply of a fresh session (was 3rd before)
- CF on basic Indeed homepage load after 24h rest
- Same account challenged from a clean/residential IP

## Run Command
```bash
cd indeed-pipeline
PYTHONUNBUFFERED=1 PYTHONPATH=venv_local/lib/python3.13/site-packages python3.13 -u scripts/batch_test.py
```

## Session 15 Updates (Current State)

### ✅ Accomplished
1. **Dynamic Proposal Downloads:** Successfully updated `gdrive_client.py` to use the user-context OAuth token (`google_oauth_token.json`) and force-refresh it. Verified that it correctly downloads and formats the specific proposal PDFs for each job.
2. **Stress Tested 5 Profiles:** Safely executed the core SmartApply loop through all 5 active profiles. Successfully uploaded proposals, solved reCaptcha safely via 2Captcha, and successfully bailed safely on un-automatable jobs (external sites, missing hometown data). 
3. **Execution Lifecycle Memory:** Implemented an in-memory `attempted_job_ids` tracking set inside `apply_runner.py` to bypass false-failures recursively during the same run and skip redundant evaluations perfectly.

### ⚠️ Pending Fixes & Backlog
1. **[UNVERIFIED] 1-Hour Sleep Rotation Fix:** Updated `process_job()` to correctly return `-1` when all accounts hit their application limit. The intent is to ensure the pipeline drops into the structural 60-minute background sleep instead of unintentionally shutting itself down. *Status: Code patched, but pending verification from the next live run.*
2. **Fix `applied=1` Success Detector:** When a job requires no extra questions, Indeed redirects directly to `viewjob?jk=...&applied=1`. The bot currently doesn't recognize this as a "Success" screen, exhaustively searches for "submit" buttons for 25 steps, times out, and falsely logs the job as `failed` in Supabase.
3. **Fix "Hidden Continue Button" Loop:** The bot successfully answers custom UI questions (like "Health information management") using the Flash fallback, but if the "Continue" button is hidden below the fold, Flash doesn't see it. The bot then gets stuck in a loop repeatedly answering the same question until the 25-step safety timeout kills the application. *Fix strategy: TBD by user.*
4. **Proxy Swapping:** 14 of the 19 profiles currently have dead Webshare proxies attached to them. Requires bulk swapping via the AdsPower API so all 19 profiles can be put in rotation.
5. **Resume Module Bypass Guard:** If an employer's application flow skips the `resume-selection-module` entirely, Indeed defaults to the generic profile CV. *Fix strategy:* Add an `uploaded_custom_resume = False` tracking variable inside the core application loop. Set it to `True` only when `set_input_files()` fires successfully. Once the bot reaches the final `review-module`, check the flag. If it's `False`, abort the application and log it as `failed — no resume upload option provided`.
