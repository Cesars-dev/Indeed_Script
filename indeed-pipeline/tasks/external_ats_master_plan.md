# External ATS — Master Plan (Preflight Complete)

## Preflight Verification

| Claim | Verified Against Code? | Result |
|-------|----------------------|--------|
| Skip point at lines 1330-1340 | ✅ Viewed lines 1325-1345 | Exact match — `"External apply — company ATS"` at line 1335 |
| `_screenshot(full_page=True)` works | ✅ Line 243 signature | `async def _screenshot(page, debug_dir, label, full_page=False)` — confirmed |
| `_execute()` is platform-agnostic | ✅ Lines 451-730 | Uses `get_by_role`, `get_by_label`, `get_by_text` — no Indeed-specific selectors |
| `dom_scanner.py` works on any page | ✅ Lines 1-153 | All generic HTML selectors |
| `gemini_decide()` in gemini_fallback.py | ✅ Line 94 | `async def gemini_decide(screenshot, dom, profile, use_pro=False)` |
| `log()` in logger.py | ✅ Line 50 | `def log(table, data)` — accepts any dict |
| `page.context.pages` for new tabs | ✅ Playwright API | Standard — returns all pages opened in context |
| DB columns verified live | ✅ Queried Supabase REST API | Missing: profile_id, job_url, ats_domain on 3 tables |

## All Open Items: RESOLVED

| Item | Resolution |
|------|-----------|
| Gap 4: _screenshot full_page | ✅ Confirmed it accepts `full_page` kwarg (line 243) |
| SmartApply logging gap | Deferred — out of scope, router.py not modified |

## Execution Checklist (step-by-step)

### Step 0: SQL Migration
```sql
ALTER TABLE apply_step_log ADD COLUMN IF NOT EXISTS profile_id text;
ALTER TABLE apply_step_log ADD COLUMN IF NOT EXISTS job_url text;
ALTER TABLE apply_step_log ADD COLUMN IF NOT EXISTS ats_domain text;
ALTER TABLE apply_patterns ADD COLUMN IF NOT EXISTS ats_domain text;
ALTER TABLE apply_runs ADD COLUMN IF NOT EXISTS profile_id text;
ALTER TABLE apply_runs ADD COLUMN IF NOT EXISTS job_url text;
ALTER TABLE apply_runs ADD COLUMN IF NOT EXISTS ats_domain text;
```

### Step 1: Create `src/smartapply/external_ats.py`
- New file, ~140 lines
- Function: `external_ats_apply(page, docx_path, profile, debug_dir, job_url, profile_id)`
- Uses: `gemini_decide()`, `_screenshot()`, `_execute()`, `scan_dom()`, `log()`
- Budget: 5 Flash + 3 Pro = 8 max
- Success detection: body text scan for external success signals
- Fail-fast: login wall / account creation detection
- Logging: every step → apply_step_log, every run → apply_runs, every learned field → apply_patterns

### Step 2: Modify `src/smartapply/__init__.py`
- Add: `from .external_ats import external_ats_apply`
- Add to `__all__`

### Step 3: Modify `src/smartapply/gemini_fallback.py`
- In `build_targeted_prompt()`, after line 70 (profile summary), add external ATS rules block
- Only appended when `profile.get("is_external")` is True

### Step 4: Modify `src/smartapply/dom_scanner.py`
- Line 138-140: add 5 external success signals to the `result.success` check

### Step 5: Modify `src/playwright_indeed.py`
- Lines 1330-1340: replace skip with click + tab handling + external_ats_apply() call
- Pass `job_url=apply_url` and `profile_id=user_id` to external handler

### Step 6: Verify
- Python syntax check on all modified files
- Run pipeline with a known external ATS job URL

## Zero Open Issues — Ready to Execute
