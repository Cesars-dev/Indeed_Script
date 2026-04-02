# P2 Action Plan — Execution Logging + Warmup Fix
> Surgeon Framework Step 2
> Derived from 01_audit.md

---

## Architecture

The fire-and-forget logger already exists: `src/smartapply/logger.py`.
`log(table, data)` uses `asyncio.create_task()` — never blocks the pipeline.

**Strategy:** Make `batch_test.py` use the existing `log()` instead of blocking HTTP calls. Fix the logger bug. Clean dead code. Fix warmups.

---

## Change 1: Fix `logger.py` bug + delete dead `log_sync()`

**File:** `src/smartapply/logger.py`
**Issue:** `log_sync()` references `_SB_URL`, `_SB_KEY`, `_SB_HDRS` — undefined. Will crash.
**Fix:** Delete `log_sync()` entirely (lines 61-74). It's never called anywhere.

---

## Change 2: Swap `batch_test.py` from blocking → fire-and-forget

**File:** `scripts/batch_test.py`

### 2a. Replace `log_execution()` import with `log()` from smartapply

```python
# BEFORE (line 24):
from src.supabase_client import log_execution

# AFTER:
from src.smartapply.logger import log as sb_log
```

### 2b. Replace blocking `log_execution()` call with async `sb_log()`

```python
# BEFORE (lines 153-160):
log_execution({
    "run_id":     RUN_ID,
    "profile_id": PROFILE_ID,
    "job_id":     url[:100],
    "status":     result["status"],
    "elapsed_s":  round(elapsed, 1),
    "cf_detected": result.get("reason", "").startswith("CF"),
})

# AFTER:
sb_log("executions", {
    "run_id":         RUN_ID,
    "profile_id":     PROFILE_ID,
    "job_id":         url[:100],
    "job_url":        url[:500],
    "url_type":       kind,
    "status":         result["status"],
    "reason":         result.get("reason", "")[:500],
    "elapsed_s":      round(elapsed, 1),
    "screenshot_dir": f"/tmp/playwright_debug/{PROFILE_ID}_{int(t0)}",
})
```

### 2c. Replace blocking `_sb_log()` with `sb_log()`

```python
# BEFORE (line 152):
_sb_log(RUN_ID, entry)

# AFTER:
sb_log("test_run_logs", {
    "run_id":     RUN_ID,
    "job_num":    i + 1,
    "url":        url[:500],
    "url_type":   kind,
    "status":     result["status"],
    "reason":     result.get("reason", "")[:500],
    "elapsed_s":  round(elapsed, 1),
    "profile_id": PROFILE_ID,
})
```

Delete the `_sb_log()` function (lines 71-91) and its setup code (lines 44-68: `_SB_HEADERS`, `_SB_ENABLED`, `_init_supabase()`).

---

## Change 3: Delete dead code from `supabase_client.py`

**File:** `src/supabase_client.py`
**Delete:** `is_job_applied()` (lines 56-63) + `upsert_applied_job()` (lines 66-73)
**Reason:** No callers in codebase. Reference old `applied_jobs` table.

---

## Change 4: Speed up warmups

### 4a. `_human_warmup()` — lines 869-886

**Target:** 10-15s total (was 22-71s)

```python
async def _human_warmup(page: Page, job_url: str):
    from humancursor_playwright import PlaywrightCursor
    # Homepage — 2-4s
    await page.goto("https://www.indeed.com", wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(random.uniform(2.0, 4.0))
    for _ in range(random.randint(1, 2)):
        await human_scroll(page, random.randint(100, 200))
        await asyncio.sleep(random.uniform(0.3, 0.8))
    # Job page — 3-6s
    await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(random.uniform(3.0, 6.0))
    for _ in range(random.randint(1, 2)):
        await human_scroll(page, random.randint(100, 200))
        await asyncio.sleep(random.uniform(0.5, 1.5))
```

Timing: homepage 2-4s + scrolls ~0.6-1.6s + job page 3-6s + scrolls ~1-3s = **~7-15s total** ✅

### 4b. SmartApply warmup — lines 1119-1123

```python
# BEFORE:
await asyncio.sleep(random.uniform(5.0, 10.0))
for _ in range(random.randint(2, 4)):
    await human_scroll(page, random.randint(100, 250))
    await asyncio.sleep(random.uniform(0.8, 2.0))

# AFTER:
await asyncio.sleep(random.uniform(2.0, 4.0))
for _ in range(random.randint(1, 2)):
    await human_scroll(page, random.randint(80, 150))
    await asyncio.sleep(random.uniform(0.3, 0.8))
```

Timing: 2-4s + scrolls ~0.6-1.6s = **~3-6s** ✅

---

## Change 5: Update `NEXT_STEPS.md`

Move to DONE table:
- Deploy ✅
- P1.5 ✅ (Phase A complete)
- P3 ✅
- P4 ✅ (test mode)
- P2 logging ✅ (fire-and-forget via existing logger)

---

## NOT changing

- `apply_to_job()` return signature — stays `{status, reason}`
- `_gemini_loop_inner()` — no changes
- `_solve_cf()` / `_bypass_cf()` — done, don't touch
- `executions` table schema — no migration needed
- `_PROFILES` / `_load_profiles()` — done
- `log()` function in `logger.py` — works, just need to fix the dead `log_sync`
- `get_fresh_combinations()` / `mark_combination_used()` in `supabase_client.py` — alive, keep

---

## Execution Order

1. Fix `logger.py` — delete broken `log_sync()`
2. Update `batch_test.py` — swap to fire-and-forget `sb_log()`
3. Delete dead code from `supabase_client.py`
4. Speed up `_human_warmup()` 
5. Speed up SmartApply warmup
6. Update `NEXT_STEPS.md`
