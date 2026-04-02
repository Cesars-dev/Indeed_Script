# 🏗️ Architecture — Visual Map

> How the whole system connects. Updated: 2026-03-13

---

## The Big Picture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         JOB SOURCING                                    │
│                                                                          │
│  ┌─────────────────┐     ┌──────────────┐     ┌──────────────────────┐  │
│  │  Agentic        │     │     N8N      │     │  Apply Engine        │  │
│  │  Proposal Gen   │────→│  (connector) │────→│  (webhook / stdin)   │  │
│  │  (scrape+rank   │     │  bridges the │     │  receives job URLs   │  │
│  │   +write cover) │     │  two systems │     │                      │  │
│  └─────────────────┘     └──────────────┘     └──────────┬───────────┘  │
│                                                          │               │
│                                                          │               │
└──────────────────────────────────────────────────────────┼───────────────┘
                                                           │
                              ┌─────────────────┐         │
                              │  apply_runner   │◄────────┘
                              │  (or batch_test)│
                              └────────┬────────┘
                                       │
                         ┌─────────────┼──────────────┐
                         ▼             ▼              ▼
                    ┌────────┐   ┌────────┐   ┌────────────┐
                    │ Dedup  │   │ Resume │   │   Profile   │
                    │  check │   │  fetch │   │   rotate    │
                    │   (SB) │   │  (PDF) │   │  (19 accts) │
                    └────────┘   └────────┘   └──────┬─────┘
                                                     │
                                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        APPLY ENGINE (per job)                            │
│                                                                          │
│  ┌──────────────┐     ┌──────────────┐     ┌─────────────────────────┐  │
│  │   AdsPower   │────→│  Browser     │────→│   playwright_indeed.py  │  │
│  │   API :30025 │     │  CDP Port    │     │   apply_to_job()        │  │
│  │              │     │              │     │                         │  │
│  │  19 profiles │     │  rebrowser-  │     │  1. Warmup (10-15s)     │  │
│  │  unique FP   │     │  playwright  │     │  2. CF check → solve    │  │
│  │  SOCKS5 proxy│     │              │     │  3. Navigate to job     │  │
│  └──────────────┘     └──────────────┘     │  4. Click Apply         │  │
│                                            │  5. SmartApply v2 →     │  │
│                                            └───────────┬─────────────┘  │
│                                                        │                 │
│                                                        ▼                 │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │                  SmartApply v2 Router (6-shot)                    │   │
│  │                                                                   │   │
│  │   ┌────────┐  miss   ┌────────┐  miss   ┌────────┐               │   │
│  │   │  DOM   │────────→│ Gemini │────────→│ Gemini │               │   │
│  │   │  Scan  │         │ Flash  │         │  Pro   │               │   │
│  │   │        │         │        │         │        │               │   │
│  │   │ Shot   │         │ Shot   │         │ Shot   │               │   │
│  │   │ 1-2    │         │ 3-4    │         │ 5-6    │               │   │
│  │   └───┬────┘         └───┬────┘         └───┬────┘               │   │
│  │       │hit               │hit               │hit                  │   │
│  │       ▼                  ▼                  ▼                     │   │
│  │   ┌─────────────────────────────────────────────┐                │   │
│  │   │              Execute Action                  │                │   │
│  │   │  click / fill / select / upload / continue   │                │   │
│  │   └──────────────────────┬──────────────────────┘                │   │
│  │                          │                                        │   │
│  │                   next step (up to 50)                            │   │
│  │                          │                                        │   │
│  │              ┌───────────┼───────────┐                            │   │
│  │              ▼           ▼           ▼                            │   │
│  │         ✅ success   ❌ failed   ⚠️ disqualified                  │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└────────────────────────────────────────────────┬─────────────────────────┘
                                                 │
                                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          LOGGING (fire-and-forget)                       │
│                                                                          │
│  smartapply/logger.py                                                    │
│  log(table, data) → asyncio.create_task() → never blocks pipeline       │
│                                                                          │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐                 │
│  │  executions  │   │ test_run_logs│   │apply_step_log│                 │
│  │              │   │              │   │              │                 │
│  │  1 row per   │   │  batch test  │   │  1 row per   │                 │
│  │  apply call  │   │  results     │   │  form step   │                 │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘                 │
│         └──────────────────┼──────────────────┘                          │
│                            ▼                                             │
│                    ┌───────────────┐                                     │
│                    │   Supabase    │                                     │
│                    │   REST API   │                                     │
│                    └───────────────┘                                     │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## CF Bypass Flow

```
Page loads
    │
    ▼
_is_cf(page) ── no ──→ continue normally
    │
   yes
    │
    ▼
_solve_cf(page)                          _bypass_cf(page)
├─ Screenshot → Gemini                   ├─ Find Turnstile iframe
├─ "Where is the checkbox?"              │  via page.frames
├─ Bezier mouse → click                  ├─ Click checkbox
├─ Wait 5-8s for validation              ├─ Wait for clearance
├─ Retry up to 6 times                   └─ Fallback method
│
├─ ✅ Cleared → continue to job
└─ ❌ Failed → _cf_stonewalled(profile)
                ├─ Mark profile stone_walled=true in Supabase
                ├─ Slack webhook notification → human reviews
                └─ Return {status: skipped}
```

---

## Profile Rotation

```
19 AdsPower Profiles
┌────┬────┬────┬────┬────┬────┬────┬────┬────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐
│ S1 │ S2 │ S3 │ S4 │ S5 │ S6 │ S7 │ S8 │ S9 │ S10 │ S11 │ S12 │ S13 │ S14 │ S15 │ S16 │ S17 │ S18 │ S19 │
└────┴────┴────┴────┴────┴────┴────┴────┴────┴──┬──┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘
                                                 │
                                        Only S10 active ✅
                                        18 need Gmail+Indeed login (P5)

Each profile has:
├─ Unique browser fingerprint (from Supabase)
├─ Dedicated SOCKS5 residential proxy
├─ Gmail account
├─ Indeed account (email+password)
└─ Applicant data (name, phone, salary, education)
```

---

## Data Flow

```
Supabase Tables
┌──────────────────┐     ┌──────────────┐     ┌───────────────────┐
│adspower_profiles │     │  executions  │     │search_combinations│
│                  │     │              │     │                   │
│ 19 rows          │     │ 1 row/apply  │     │ 10 keyword combos │
│ fingerprint JSONB│     │ status       │     │ drives N8N scrape │
│ applicant data   │     │ elapsed_s    │     │                   │
│ proxy assignment │     │ reason       │     │                   │
└──────────────────┘     └──────────────┘     └───────────────────┘

┌──────────────────┐     ┌──────────────┐     ┌───────────────────┐
│  applied_jobs    │     │test_run_logs │     │     proxies       │
│                  │     │              │     │                   │
│ dedup log        │     │ dev/test     │     │ 100 Webshare US   │
│ job_id (PK)      │     │ batch runs   │     │ SOCKS5 residential│
└──────────────────┘     └──────────────┘     └───────────────────┘
```

---

## File System (VPS)

```
/root/indeed-pipeline/          ← deployed production code (git pull)
/home/julio/projects/Indeed_Script/  ← dev workspace (this repo)

/root/.config/adspower_global/  ← AdsPower data + browser profiles
/opt/AdsPower Global/           ← AdsPower binary (space in path!)
/tmp/playwright_debug/          ← screenshots per apply session
```
