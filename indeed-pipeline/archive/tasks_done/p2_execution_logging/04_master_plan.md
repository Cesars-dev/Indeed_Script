# P2 Master Plan — AIRTIGHT
> Surgeon Framework Step 4
> All claims verified against real line numbers. Zero open issues.

---

## Change 1: Fix `logger.py` — delete broken `log_sync()`

**File:** `src/smartapply/logger.py`
**Delete:** Lines 61-75 (the entire `log_sync()` function)
**Reason:** References `_SB_URL`, `_SB_KEY`, `_SB_HDRS` which don't exist. 0 callers.

---

## Change 2: Rewrite `batch_test.py` — remove all blocking HTTP logging

**File:** `scripts/batch_test.py`

### 2a. Swap import (line 24)
```python
# DELETE:
from src.supabase_client import log_execution  # noqa: E402

# ADD:
from src.smartapply.logger import log as sb_log  # noqa: E402
```

### 2b. Delete `_sb_log` infrastructure (lines 44-91)
Delete everything from `# ── Supabase logging ──` through `_sb_log()` function:
- Lines 44-51: `SUPABASE_URL`, `SUPABASE_KEY`, `_SB_HEADERS`, `_SB_ENABLED`
- Lines 55-68: `_init_supabase()`
- Lines 71-91: `_sb_log()`

### 2c. Delete `_init_supabase()` call (line 111)
```python
# DELETE:
    _init_supabase()
```

### 2d. Replace logging calls (lines 151-160)
```python
# BEFORE (lines 151-160):
        log(entry)
        _sb_log(RUN_ID, entry)
        log_execution({
            "run_id":     RUN_ID,
            "profile_id": PROFILE_ID,
            "job_id":     url[:100],
            "status":     result["status"],
            "elapsed_s":  round(elapsed, 1),
            "cf_detected": result.get("reason", "").startswith("CF"),
        })

# AFTER:
        log(entry)
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

Note: `log(entry)` on line 151 is the LOCAL file logger (defined at line 101) — keep it. Renamed imports avoid collision: `sb_log` = Supabase fire-and-forget, `log` = local JSONL.

---

## Change 3: Delete dead code from `supabase_client.py`

**File:** `src/supabase_client.py`
**Delete:** Lines 56-73 (`is_job_applied()` + `upsert_applied_job()`)
**Keep:** `get_fresh_combinations()`, `mark_combination_used()`, `log_execution()` (uploader may use it later)

---

## Change 4a: Speed up `_human_warmup()` 

**File:** `src/playwright_indeed.py` lines 869-886

```python
# REPLACE lines 877-886 with:
    await page.goto("https://www.indeed.com", wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(random.uniform(2.0, 4.0))
    for _ in range(random.randint(1, 2)):
        await human_scroll(page, random.randint(100, 200))
        await asyncio.sleep(random.uniform(0.3, 0.8))
    await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(random.uniform(3.0, 6.0))
    for _ in range(random.randint(1, 2)):
        await human_scroll(page, random.randint(100, 200))
        await asyncio.sleep(random.uniform(0.5, 1.5))
```

Total: ~7-15s ✅

Also update docstring (lines 870-875) to say `10-15s total` instead of `10-30s`.

---

## Change 4b: Speed up SmartApply warmup

**File:** `src/playwright_indeed.py` lines 1120-1123

```python
# REPLACE lines 1120-1123 with:
                await asyncio.sleep(random.uniform(2.0, 4.0))
                for _ in range(random.randint(1, 2)):
                    await human_scroll(page, random.randint(80, 150))
                    await asyncio.sleep(random.uniform(0.3, 0.8))
```

Total: ~3-6s ✅

---

## Change 5: Update `NEXT_STEPS.md`

Add to DONE table:
- Deploy to VPS ✅ 2026-03-13
- P1.5 Turnstile Gemini bypass (Phase A) ✅ 2026-03-13
- P2 execution logging (fire-and-forget) ✅ 2026-03-13
- P3 per-profile applicant data ✅ 2026-03-13
- P4 job URL sourcing (stdin test mode) ✅ 2026-03-13

---

## Execution Order

1. `logger.py` — delete `log_sync()`
2. `batch_test.py` — swap imports, delete blocking infra, rewire logging
3. `supabase_client.py` — delete dead functions
4. `playwright_indeed.py` — speed up `_human_warmup()`
5. `playwright_indeed.py` — speed up SmartApply warmup
6. `NEXT_STEPS.md` — mark done

## Open Issues: ZERO
