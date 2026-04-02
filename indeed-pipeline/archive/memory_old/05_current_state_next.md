# Memory: Current State & Next Steps

## Session 4 — 2026-03-13 (audit & cleanup pass)

- [x] Deploy to VPS (synced via GitHub)
- [x] Audit P1.5–P4 against codebase — confirmed P1.5, P3, P4 already done
- [x] P2 execution logging — swapped blocking `log_execution()` to fire-and-forget `sb_log()` via existing `smartapply/logger.py`
- [x] Deleted dead code: `log_sync()` (broken), `is_job_applied()`, `upsert_applied_job()`
- [x] Speed up warmups — viewjob 7-15s (was 22-71s), SmartApply 3-6s (was 10-24s)
- [x] Updated NEXT_STEPS.md — marked P1.5/P2/P3/P4 done

## Where We Are (March 13, 2026 — Session 4)

**Pipeline is fully built, deployed, and audited.** All core modules working. P0–P4 complete.

**Status:** VPS AdsPower ✅ | Playwright CDP ✅ | Gemini ✅ | CF bypass ✅ | Fingerprints ✅ | Logging ✅ | Per-profile data ✅

### What's working
- AdsPower headless on VPS — systemd service, port 30025, `--api-key` auth
- Playwright `connect_over_cdp()` via `rebrowser-playwright` (fixes `Runtime.enable` leak)
- Gemini 2.5 Flash + 3.1 Pro escalation — vision-based form navigation
- SmartApply v2 router — 6-shot engine (deterministic → Flash → Pro)
- 19 profiles — unique desktop fingerprints in Supabase, dynamically injected via `add_init_script`
- CF Turnstile bypass — `_solve_cf()` Gemini visual solver + `_bypass_cf()` iframe fallback + stonewalling
- Fire-and-forget execution logging — `smartapply/logger.py` → async `create_task()` to Supabase
- Per-profile applicant data — `_load_profiles()` from Supabase, no hardcoded constants
- Warmups — viewjob 7-15s, SmartApply 3-6s (optimized session 4)

### What's left

| # | Priority | Task | Notes |
|---|----------|------|-------|
| 1 | **P5** | Activate sessions (manual) | Log into Gmail+Indeed per profile in AdsPower. 1-2/day. |
| 2 | **P6** | Search page warmup for viewjob URLs | Navigate to `indeed.com/jobs?q=...&l=...` before job URL |
| 3 | **P7** | Per-profile resume download | `download_resumes.py` — Google Docs → PDF. Blocked on Docs URLs. |

---

## Architecture Decision Log

### VPS AdsPower Port Discovery (March 2026)
- Port 20725: ghost-locked by `main.min.js` / `bundles.min.js` inside AdsPower — reports "Port: 20725 is occupied" even when `ss -tlnp` shows nothing. NEVER use.
- Port 30025: works with `--api-key` flag on binary. No GUI login needed.
- Binary needs `DISPLAY=:99` (Xvfb) even for headless — GTK dependency.
- Symlink at `/usr/local/bin/adspower_global` → `/opt/AdsPower Global/adspower_global` (space in path workaround for systemd).

### CF Turnstile Shadow DOM Discovery
- `document.querySelectorAll('iframe')` returns 0 for Turnstile widgets
- Turnstile iframe is injected via shadow DOM — invisible to standard DOM queries
- `page.frames` (Playwright API) DOES find it: `challenges.cloudflare.com/cdn-cgi/challenge-platform/.../turnstile/...`
- For interacting with Turnstile, must use `page.frames` not CSS selectors

### Why Playwright over nodriver (for SmartApply)?
- nodriver `best_match=True` selected wrong DOM elements
- WebSocket 500 crashes mid-session
- Playwright has `get_by_role()`, `get_by_label()`, auto-waits
- nodriver in attach mode adds zero fingerprint protection — AdsPower handles all of that

### Why Gemini Vision instead of hardcoded selectors?
- SmartApply DOM changes randomly — selectors break silently
- Gemini reads the actual rendered form and decides the right action
- Handles any new question type, any new layout automatically

### Logging Architecture (Session 4)
- `smartapply/logger.py` is the single fire-and-forget logger
- `log(table, data)` → `asyncio.create_task()` → never blocks pipeline
- `batch_test.py` logs to both `test_run_logs` and `executions` tables
- `log_sync()` was deleted (referenced undefined variables, 0 callers)
- `is_job_applied()` + `upsert_applied_job()` deleted (dead code, old `applied_jobs` table)

### VPS Safety Rules
- **Never `pkill -u julio`** — kills Antigravity IDE. Only kill specific processes by name.
- **Never run `find /`** — hammers disk I/O, stalls other sessions.
- VPS has ~3.8GB RAM total. AdsPower + browser uses ~800MB. Watch for OOM killer.
