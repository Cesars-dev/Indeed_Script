# P2 Audit — Execution Logging
> Surgeon Framework Step 1
> Date: 2026-03-13

---

## Existing Logging Infrastructure

### 1. `src/smartapply/logger.py` — Fire-and-forget async logger (ALREADY EXISTS)

**Location:** `src/smartapply/logger.py` (75 lines)

**Functions:**
| Function | Type | What it does | Used by |
|----------|------|-------------|---------|
| `log(table, data)` | async fire-and-forget | Gets running event loop → `create_task(_post(...))` → returns immediately | `router.py` (6 calls) |
| `_post(table, data)` | async | `aiohttp.post()` to Supabase REST API, falls back to `requests` if no aiohttp | Called by `log()` |
| `log_sync(table, data)` | sync blocking | Same but synchronous | **NOT CALLED ANYWHERE** |

**Tables being logged to (from `router.py`):**
- `apply_step_log` — one row per step (5 calls in router.py)
- `apply_runs` — one row per exhausted-shots failure (1 call in router.py)

**⚠️ BUG:** `log_sync()` references `_SB_URL`, `_SB_KEY`, `_SB_HDRS` — these variables DO NOT EXIST in logger.py. The function would crash with `NameError` if ever called. Dead code.

### 2. `src/supabase_client.py` — Blocking sync client

**Functions:**
| Function | Type | Used by | Status |
|----------|------|---------|--------|
| `get_fresh_combinations()` | sync | Unknown (search combos) | Alive |
| `mark_combination_used()` | sync | Unknown (search combos) | Alive |
| `is_job_applied()` | sync | **NOTHING** | ❌ Dead code — references old `applied_jobs` table |
| `upsert_applied_job()` | sync | **NOTHING** | ❌ Dead code — references old `applied_jobs` table |
| `log_execution()` | sync blocking | `batch_test.py` line 153 | Alive but **BLOCKING** — exactly the problem |

### 3. `scripts/batch_test.py` — Test harness (how logging is wired today)

**Line 24:** `from src.supabase_client import log_execution`
**Lines 153-160:** Calls `log_execution()` with a dict after every apply — **this is a BLOCKING HTTP POST**.

Also has its own `_sb_log()` (lines 71-91) which POSTs to `test_run_logs` — also blocking.

---

## Data Flow Map

```
batch_test.py
  ├── calls apply_to_job() ──────────────────────────────► playwright_indeed.py
  │                                                              │
  │   (no logging inside apply_to_job itself)                    │
  │                                                              ▼
  │                                                        smartapply/router.py
  │                                                              │
  │                                                    log("apply_step_log")  ← async fire-and-forget ✅
  │                                                    log("apply_runs")      ← async fire-and-forget ✅
  │                                                              │
  ├── receives result dict ◄─────────────────────────────────────┘
  │
  ├── log(entry) ──► local JSONL file ✅ (non-blocking)
  ├── _sb_log(RUN_ID, entry) ──► test_run_logs ❌ (BLOCKING HTTP)
  └── log_execution({...}) ──► executions ❌ (BLOCKING HTTP)
```

**Problem:** `batch_test.py` makes 2 blocking HTTP calls after every apply.

---

## Supabase `executions` Table Schema (from supabase_schema.sql)

```sql
CREATE TABLE IF NOT EXISTS executions (
  id             SERIAL PRIMARY KEY,
  run_id         TEXT,
  profile_id     TEXT,
  job_id         TEXT,
  job_url        TEXT,
  url_type       TEXT,        -- viewjob | smartapply | external
  status         TEXT,        -- success | failed | skipped | error
  reason         TEXT,
  steps          INTEGER,
  elapsed_s      FLOAT,
  screenshot_dir TEXT,
  ts             TIMESTAMPTZ DEFAULT NOW()
);
```

**What `batch_test.py` currently populates:** `run_id`, `profile_id`, `job_id`, `status`, `elapsed_s`, `cf_detected`
**What's missing:** `job_url`, `url_type`, `reason`, `steps`, `screenshot_dir`
**What's wrong:** `cf_detected` is NOT a column in the schema — it would be silently ignored by Supabase REST API.

---

## Warmup Timing Audit

### `_human_warmup()` (viewjob URLs) — lines 869-886

| Phase | Sleep range | Scroll loops | Est. total |
|-------|------------|-------------|------------|
| Homepage | 4.0-9.0s | 3-6 scrolls × (0.8-2.5s) | 6.4-24s |
| Job page | 10.0-22.0s | 3-5 scrolls × (2.0-5.0s) | 16-47s |
| **Total** | | | **22-71s** ⚠️ |

User requirement: **10-15s total.**

### SmartApply warmup — lines 1119-1126

| Phase | Sleep range | Scroll loops | Est. total |
|-------|------------|-------------|------------|
| Homepage | 5.0-10.0s | 2-4 scrolls × (0.8-2.0s) | 6.6-18s |
| Navigate + land | 3.0-6.0s | — | 3-6s |
| **Total** | | | **10-24s** ⚠️ |

---

## Summary of Issues

| # | Issue | Severity | Location |
|---|-------|----------|----------|
| 1 | `log_execution()` in `batch_test.py` is BLOCKING | 🔴 | `scripts/batch_test.py:153` |
| 2 | `_sb_log()` in `batch_test.py` is BLOCKING | 🔴 | `scripts/batch_test.py:71` |
| 3 | `log_sync()` has undefined vars (`_SB_URL`, `_SB_KEY`, `_SB_HDRS`) | 🟡 | `src/smartapply/logger.py:63` |
| 4 | `is_job_applied()` + `upsert_applied_job()` dead code | 🟡 | `src/supabase_client.py:56-73` |
| 5 | `executions` columns not fully populated | 🟡 | `scripts/batch_test.py:153-160` |
| 6 | `cf_detected` sent but not in schema | 🟡 | `scripts/batch_test.py:159` |
| 7 | Viewjob warmup 22-71s (should be 10-15s) | 🔴 | `src/playwright_indeed.py:878-886` |
| 8 | SmartApply warmup 10-24s (should be ~5-8s) | 🟡 | `src/playwright_indeed.py:1119-1123` |
| 9 | `apply_to_job()` doesn't return `steps` or `screenshot_dir` | 🟡 | `src/playwright_indeed.py:900` |
| 10 | NEXT_STEPS.md marks P1.5, P3, P4 as "not started" — they're done | 🟡 | `NEXT_STEPS.md` |
