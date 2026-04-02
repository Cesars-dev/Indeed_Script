# External ATS — Cross-Reference (Audit ↔ Action Plan)

## Does the plan address every audit finding?

| Audit Finding | Addressed in Plan? | How |
|--------------|-------------------|-----|
| Skip point at line 1330-1340 | ✅ | Change 2 — replaces skip with click + external_ats_apply() |
| Missing external ATS handler | ✅ | Change 1 — new `external_ats.py` with 5 Flash + 3 Pro budget |
| Missing external Gemini prompt | ✅ | Change 3 — adds external ATS rules to gemini_fallback.py |
| New tab handling | ✅ | Change 2 — detects `len(pages) > 1` and switches to last page |
| Database missing columns | ✅ | Pre-requisite SQL migration — 7 ALTER TABLE statements |
| Success signals are Indeed-only | ✅ | Change 5 — adds 5 external success signals to dom_scanner.py |
| Bug: apply_step_log missing profile_id | ⚠️ PARTIAL | Fixed for external only. Existing SmartApply logs still missing it. |
| Bug: apply_runs missing profile_id | ⚠️ PARTIAL | Fixed for external only. Existing SmartApply logs still missing it. |

## Does the audit support every plan change?

| Plan Change | Supported by Audit? | Notes |
|------------|--------------------|----|
| Change 1: external_ats.py | ✅ | Audit confirms no handler exists. Uses existing _execute(), _screenshot(), gemini_decide() |
| Change 2: playwright_indeed.py | ✅ | Audit traces the exact skip point (line 1330-1340) |
| Change 3: gemini_fallback.py | ✅ | Audit confirms existing prompt lacks external guidance |
| Change 4: __init__.py | ✅ | Trivial export change |
| Change 5: dom_scanner.py | ✅ | Audit identifies Indeed-only success signals |
| SQL migration | ✅ | Audit verified actual column names from live DB |

## Gaps Found

### Gap 1: SmartApply logging not fixed
The audit found that `apply_step_log` and `apply_runs` are missing `profile_id` and `job_url` for ALL logs (not just external). The action plan only fixes this for external ATS.

**Decision:** Out of scope for this feature. The SmartApply router (router.py) is marked as "do not modify". We'll fix external logging now and address SmartApply logging in a separate PR.

### Gap 2: Popup window not handled
Audit Risk 1 mentions popup windows. Plan handles new tabs but not popup windows (window.open with specific dimensions).

**Decision:** Popup windows are rare for ATS. `page.context.pages` catches both new tabs AND popups opened via window.open(). No additional handling needed.

### Gap 3: Router conflict (Risk 3)
The plan intercepts at line 1330-1340 (before the router), which avoids the SmartApply router entirely. The external handler never calls `apply_smartapply()`.

**Decision:** ✅ Already resolved by design — the interception happens before the form engine routing at line 1375.

### Gap 4: _screenshot full_page parameter
The action plan calls `_screenshot(page, debug_dir, ss_name, full_page=use_pro)`. Need to verify `_screenshot()` accepts `full_page` parameter.

**Decision:** Check in preflight step.

### Gap 5: External prompt in gemini_fallback vs old _gemini_decide
There are TWO Gemini functions:
1. `_gemini_decide()` in `playwright_indeed.py` (used by old `_gemini_loop`)
2. `gemini_decide()` in `gemini_fallback.py` (used by `apply_smartapply` router)

The external handler uses `gemini_fallback.py` (the newer one). The action plan modifies the correct file.

**Decision:** ✅ Correct. Old `_gemini_loop` is only used when `SMARTAPPLY_V2=0`.

## Contradictions

None found. Plan and audit are aligned.

## Final Status

| Category | Status |
|----------|--------|
| All audit issues addressed | ✅ (2 deferred to separate PR) |
| All plan changes supported by audit | ✅ |
| Contradictions | None |
| Open gaps | 1 — verify _screenshot full_page param in preflight |
