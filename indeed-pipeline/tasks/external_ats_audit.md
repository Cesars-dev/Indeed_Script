# External ATS — Surgeon Audit

## Files Involved

| File | Lines | Role |
|------|-------|------|
| `src/playwright_indeed.py` | 1548 | Main entry point, _execute(), _gemini_decide(), apply_to_job() |
| `src/smartapply/router.py` | 422 | SmartApply 12-shot router (NOT to be modified) |
| `src/smartapply/gemini_fallback.py` | 112 | Gemini Flash/Pro decision engine with DOM-aware prompt |
| `src/smartapply/dom_scanner.py` | 153 | DOM scanner — generic HTML, works on ANY page |
| `src/smartapply/handlers.py` | — | Deterministic handlers (NOT to be modified) |
| `src/smartapply/logger.py` | 61 | Fire-and-forget Supabase logger |
| `src/smartapply/__init__.py` | 4 | Exports `apply_smartapply` |
| `scripts/batch_test.py` | 178 | Test runner, logs to `test_run_logs` table |

## Data Flow Trace

```
batch_test.py:131
  └─ apply_to_job(url, resume, profile_id)  [playwright_indeed.py:1131]
       ├─ _url_type(url)                     [line 1121] → "viewjob" | "smartapply" | "external"
       ├─ Build profile dict                 [line 1162-1172] → includes is_external, platform
       ├─ _start_profile(user_id)            [line ~1200] → AdsPower → debug_port
       ├─ connect_over_cdp()                 [line ~1220] → vanilla playwright
       ├─ _warmup_indeed(page)               [line ~1260] → indeed.com cookies
       │
       ├─ IF viewjob:                        [line 1290-1349]
       │   ├─ goto(viewjob URL)
       │   ├─ Find "Apply with Indeed" button [CSS selectors, line 1302-1328]
       │   ├─ IF found → click → goes to SmartApply
       │   ├─ IF NOT found:
       │   │   ├─ Check "Apply on company site" [line 1330-1335]
       │   │   └─ return SKIPPED ← ⚠️ THIS IS THE SKIP POINT
       │   └─ Click apply button → SmartApply loads
       │
       ├─ IF smartapply:                     [line 1351-1366]
       │   └─ Direct warmup + navigate
       │
       ├─ IF external:                       [line 1368-1373]
       │   └─ Direct navigate to external URL
       │
       └─ Route to form engine:              [line 1375-1381]
           ├─ IF SMARTAPPLY_V2=1 → apply_smartapply() from router.py
           └─ ELSE → _gemini_loop() (old loop)
```

## What EXISTS

### 1. URL Classification (line 1121-1127)
```python
def _url_type(url):
    if "indeed.com/viewjob" in url or "indeed.com/rc/clk" in url:
        return "viewjob"
    if "smartapply.indeed.com" in url or "indeedapply" in url.lower():
        return "smartapply"
    return "external"
```
✅ Already classifies external URLs correctly.

### 2. Profile dict with is_external (line 1162-1171)
```python
profile = {
    "is_external": is_external,
    "platform": platform,
    # ... name, email, phone, etc.
}
```
✅ Already passes external flag into profile dict.

### 3. External navigation (line 1368-1373)
```python
else:
    print(f"[playwright] External ATS → {apply_url[:80]}")
    await page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
    await _delay(3.0, 6.0)
    await _screenshot(page, debug_dir, "00_direct_land")
```
✅ Already handles navigating to external URLs (only for direct external URLs, not when clicking "Apply on company site" from viewjob).

### 4. Gemini prompt with is_external branch (line 391-396)
```python
if is_external:
    resume_instruction = '• Resume upload → use upload action when a file input appears'
```
✅ Already has external-aware prompt, but ONLY for resume instruction. Rest of prompt is Indeed-specific.

### 5. DOM scanner (dom_scanner.py)
✅ Generic HTML selectors — buttons, radios, inputs, selects, checkboxes, file inputs, modals, errors. Works on ANY website.

### 6. Action executor (_execute, line 451-730)
✅ Generic — uses get_by_role, get_by_label, get_by_text. Platform-agnostic. Works on any page.

### 7. Gemini fallback (gemini_fallback.py)
✅ DOM-aware prompt builder. Uses generic element descriptions. NOT Indeed-specific.

### 8. Logger (logger.py)
✅ Generic fire-and-forget POST to any Supabase table. Accepts any dict.

### 9. The Skip Point (line 1330-1340)
```python
if not apply_btn:
    try:
        await page.get_by_text("Apply on company site", exact=False).first.wait_for(
            state="visible", timeout=2000
        )
        return {"status": "skipped", "reason": "External apply — company ATS"}  # ← SKIP
    except Exception:
        pass
    title = await page.title()
    return {"status": "skipped", "reason": f"No apply button found (page: {title[:60]})"}
```
⚠️ THIS is where we intercept. Instead of returning skipped, we click the button and route to external handler.

## What's MISSING

### 1. External ATS handler function
No function exists to handle external ATS forms. Need `external_ats_apply()`.

### 2. External-specific Gemini prompt
The `gemini_fallback.py` prompt is generic but missing external ATS-specific guidance (login wall detection, account creation detection, ATS-specific button text patterns).

### 3. New tab handling
When clicking "Apply on company site", Indeed often opens a NEW TAB. The current code doesn't handle tab switching after click. Need to detect new tab and switch `page` reference.

### 4. Database columns
Verified schema — missing columns:
- `apply_step_log`: missing `profile_id`, `job_url`, `ats_domain`
- `apply_patterns`: missing `ats_domain`
- `apply_runs`: missing `profile_id`, `job_url`, `ats_domain`

### 5. Success signals for external ATS
`dom_scanner.py` success detection (line 137-140) checks for "Application submitted", "You applied" — these are Indeed-specific. External ATS pages say things like "Thank you for your application", "Your application has been received", "Application Complete".

## Risks / Conflicts

### Risk 1: New tab vs redirect
"Apply on company site" might:
- Open a new tab (most common)
- Redirect in the same tab
- Open a popup window
Need to handle all three.

### Risk 2: Warmup on external domain
The current flow does `_warmup_indeed()` before navigating. For external URLs this is fine (bakes Indeed cookies), but after clicking "Apply on company site" we land on an external domain where Indeed cookies have no bearing.

### Risk 3: Router conflict
After clicking "Apply on company site" and landing on external page, the code flows to line 1375-1381 which routes to `apply_smartapply()`. The SmartApply router has Indeed-specific guards (line 98-110: `profile.indeed.com` check, `/settings` check). Need to intercept BEFORE hitting the router.

### Risk 4: Gemini cost
5 Flash + 3 Pro = 8 calls per external job. With 60% external rate and 20 jobs per batch, that's ~12 external jobs × 8 calls = ~96 Gemini calls per batch. Need to verify this is within budget.

### Risk 5: DOM scanner success signals
External ATS success text won't match "Application submitted" or "You applied". Need to add external success signals to dom_scanner.py OR handle success detection in the external handler.

## Bugs Found in Existing Code

### Bug 1: apply_step_log missing profile_id
The SmartApply router's `log()` calls (router.py lines 88, 188, 237, etc.) don't include `profile_id` or `job_url`. These are missing from ALL existing logs, not just external. This should be fixed across the board.

### Bug 2: apply_runs missing profile_id
Same issue — router.py line 393-401 doesn't log `profile_id`.

### Bug 3: Success detection is Indeed-only
dom_scanner.py line 137-140 only detects Indeed success text. This is a gap even for SmartApply edge cases.
