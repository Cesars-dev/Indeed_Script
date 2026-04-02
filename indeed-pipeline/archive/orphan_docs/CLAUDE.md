# CLAUDE.md — Indeed Auto-Apply Pipeline

This file is auto-loaded by Claude CLI at session start. Follow the bootstrap sequence below before doing anything else.

---

## Bootstrap Sequence (do this every session, in order)

1. **Find and read the latest memory snapshot:**
   - Look for `memory_YYYY-MM-DD.md` files in this root directory
   - Read the one with the most recent date (e.g. `memory_2026-03-05.md`)
   - This tells you: what was done last session, what's blocking, and how to run the next test

2. **Read `README.md`** — architecture, 10 critical rules, coding standards, folder structure

3. **Read `NEXT_STEPS.md`** — current task list, prioritized P1–P7

4. **Only then respond or act.** Do not make assumptions about state — everything is in these files.

---

## What This Project Is

Automated Indeed job application pipeline. 19 rotating anti-detect browser profiles apply to jobs scraped by N8N + Apify. Gemini 2.5 Flash Vision reads each form screenshot and decides the next action — zero hardcoded selectors.

**Stack:** AdsPower (fingerprint spoofing) → Playwright CDP → Gemini Vision → Supabase log

---

## Folder Structure

```
indeed-pipeline/
├── CLAUDE.md                 ← this file (Claude CLI bootstrap)
├── README.md                 ← architecture, rules, coding standards
├── NEXT_STEPS.md             ← live task list (P1–P7)
├── PIPELINE_STATUS.md        ← status snapshot + runbook
├── USER_README.md            ← manual tasks requiring human hands
├── action_plan.md            ← completed fix plan (all 6 fixes done)
├── deep_search_eval.md       ← stealth architecture decisions
├── memory_YYYY-MM-DD.md      ← session state snapshot (START HERE)
│
├── src/                      ← active code (deployed to VPS)
│   ├── playwright_indeed.py  ← browser engine (Playwright + Gemini loop)
│   ├── apply_runner.py       ← job loop: CSV → dedup → rotate → apply
│   ├── orchestrator.py       ← cron entry point (9AM daily)
│   ├── webhook_server.py     ← VPS HTTP :8080 receiver
│   ├── supabase_client.py    ← DB helpers (log_execution, upsert, dedup)
│   └── gdrive_client.py      ← Google Drive download + PDF convert
│
├── scripts/                  ← local Mac-side scripts
│   ├── batch_test.py         ← primary test runner (run this for tests)
│   ├── test_playwright.py    ← CDP connection verifier
│   ├── audit_keys.sh         ← credential leak scanner
│   ├── tunnel.sh             ← SSH tunnel Mac <-> VPS
│   └── deprecated/           ← do NOT use
│
├── memory/                   ← distilled knowledge by topic
│   ├── 01_infrastructure.md  ← credentials, VPS, ports, scripts
│   ├── 02_browser_automation.md ← CDP rules, stealth, why Playwright
│   ├── 03_sessions_accounts.md  ← profiles, sessions, accounts
│   ├── 04_smartapply_form.md    ← Gemini loop, form behavior
│   └── 05_current_state_next.md ← blockers, architecture decisions
│
├── config/                   ← secrets + profile data
│   ├── accounts.json
│   └── google_service_account.json
│
├── archive/                  ← read-only history (do not use)
│   ├── nodriver/             ← old nodriver-era code
│   └── milestones_history/   ← m01–m25 raw milestone files
│
├── .env                      ← active credentials (NEVER commit)
├── requirements.txt
├── supabase_schema.sql
└── resume_oswaldo.pdf        ← shared resume fallback
```

---

## 10 Critical Rules — Never Violate

1. `playwright.connect_over_cdp(f"http://127.0.0.1:{debug_port}")` — NOT `connection_url`
2. AdsPower `browser/start` = GET, not POST
3. `tab[0]` = AdsPower internal page — NEVER touch. Work on `tab[1]` only
4. Port `50325` = Mac AdsPower (use this). Port `20725` = VPS-native (Forbidden = normal)
5. `window.scrollBy()` is banned — use `page.mouse.wheel()` (generates trusted WheelEvent)
6. `page.hover()` is banned for behavioral actions — use Bezier `human_move_mouse()`
7. `page.find(x, best_match=True)` is banned — use CSS selectors
8. Never hardcode credentials — always from `.env` via `python-dotenv`
9. `RUN_MODE=local` (Mac, direct AdsPower) vs `RUN_MODE=vps` (tunnel, CDP ports must be forwarded)
10. Sessions need 24h aging after fresh login before running any scripts

---

## How to Run a Test

```bash
# Prereqs: AdsPower open on Mac, stone_walled reset in Supabase, fresh Indeed URL ready
cd indeed-pipeline
PYTHONUNBUFFERED=1 PYTHONPATH=venv_local/lib/python3.13/site-packages python3.13 -u scripts/batch_test.py
# Paste fresh Indeed viewjob URL when prompted, then blank line
```

**Success criteria:** Steps go past 22, see submission screen or real failure reason.

---

## Key Architecture Facts

- `_PROFILES` dict loaded once at module import from Supabase — all 19 profiles cached
- Stone-walled reset is lazy — only triggers on `apply_to_job()` call, not scheduled
- `_gemini_loop()` has no timeout — natural exits: `done`, `failed`, `skip`, 10 consecutive failures, or 50 steps
- Profile data (name/phone/salary) comes from Supabase `adspower_profiles` — not `.env`
- CF detection PATCHes DB and updates in-memory `_PROFILES` cache immediately

---

## After Each Session

Update the memory snapshot:
- Create a new `memory_YYYY-MM-DD.md` at this root with what was done, DB state, blockers, next steps
- Update `NEXT_STEPS.md` to mark done items and add new ones
- Update relevant `memory/*.md` files if architectural knowledge changed
