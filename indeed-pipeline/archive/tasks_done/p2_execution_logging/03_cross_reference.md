# P2 Cross-Reference — Audit vs Action Plan
> Surgeon Framework Step 3

---

## Every Audit Issue → Plan Coverage

| # | Audit Issue | Plan Fix? | Verified |
|---|------------|----------|----------|
| 1 | `log_execution()` blocking in `batch_test.py` | ✅ Change 2b: swap to `sb_log()` | — |
| 2 | `_sb_log()` blocking in `batch_test.py` | ✅ Change 2c: swap to `sb_log()`, delete `_sb_log()` | — |
| 3 | `log_sync()` has undefined vars | ✅ Change 1: delete it | — |
| 4 | `is_job_applied()` + `upsert_applied_job()` dead | ✅ Change 3: delete | — |
| 5 | `executions` columns not fully populated | ✅ Change 2b: adds `job_url`, `url_type`, `reason`, `screenshot_dir` | — |
| 6 | `cf_detected` sent but not in schema | ✅ Change 2b: removed from payload | — |
| 7 | Viewjob warmup 22-71s | ✅ Change 4a: reduced to 7-15s | — |
| 8 | SmartApply warmup 10-24s | ✅ Change 4b: reduced to 3-6s | — |
| 9 | `apply_to_job()` doesn't return `steps` | ⚪ Deferred — `steps` column stays NULL for now. Not blocking. | — |
| 10 | NEXT_STEPS.md outdated | ✅ Change 5 | — |

## Every Plan Change → Audit Support

| Change | Audit evidence? | Notes |
|--------|----------------|-------|
| Delete `log_sync()` | ✅ Audit #3: undefined vars, 0 callers | Safe |
| Swap `batch_test.py` to `sb_log()` | ✅ Audit #1, #2: blocking calls identified | Core fix |
| Delete `is_job_applied()` + `upsert_applied_job()` | ✅ Audit #4: grep confirmed 0 callers in src/ | Safe |
| Speed up `_human_warmup()` | ✅ Audit #7: timed at 22-71s, user says 10-15s max | Needed |
| Speed up SmartApply warmup | ✅ Audit #8: timed at 10-24s | Needed |
| Update NEXT_STEPS.md | ✅ Audit #10: P1.5/P3/P4 already done | Housekeeping |

## Gaps

| # | Gap | Resolution |
|---|-----|------------|
| 1 | `steps` column stays NULL | Acceptable for now. Would require touching return dicts in `_gemini_loop_inner()` and `apply_smartapply()` — separate task, not blocking pipeline operation. |
| 2 | `batch_test.py` calls `sb_log()` which is async — but `batch_test.py` runs in `asyncio.run(main())` so the event loop IS running. | No issue — `log()` uses `get_running_loop().create_task()` which works fine inside an `async def main()`. ✅ |
| 3 | `_init_supabase()` call at line 111 — gets deleted when we remove `_sb_log()` setup code. | Need to also remove the `_init_supabase()` call from `main()`. ✅ Already covered in Change 2c. |

## Contradictions

None found.
