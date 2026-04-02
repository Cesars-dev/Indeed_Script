# Surgeon Master Plan — Iteration 8 (PREFLIGHT VERIFIED)

## Verification Against Actual Code

### C1: Smart Dedup — VERIFIED
- Line 100-107 in batch_test.py: confirmed `params={"select": "url", "limit": 500}` — needs `status,reason` added
- Line 107: `{row["url"] for row in r.json()}` — needs filter logic
- `TRANSIENT_PATTERNS` defined once at module level near line 67

### C2: JSON Fallback — VERIFIED  
- Line 132-136 in gemini_fallback.py: confirmed `json.loads(raw)` with no try/except
- Need to add `import re` at top (already has `import json` at line 6)

### C3: Bail-out — VERIFIED
- Line 275 in router.py: `same_url_actions += 1` — add guard AFTER this line
- Line 367 (Pro tier): same pattern — add guard
- Checked: both follow identical structure

### C4: Transient Skip — VERIFIED
- Lines 226-245 in batch_test.py: confirmed flow
- `continue` inside `while not success` loop (line 183) — verified works correctly
- `url_attempts` incremented at line 190 BEFORE status check — transient retries DO count toward url_attempts max (2). Correct.

### C5: Cover Letter — VERIFIED
- Line 80: `[row["apply_url"].strip() for row in reader]` — change to dict extraction
- Line 90: `_RAW_URLS = _load_job_urls()` → rename to `_RAW_JOBS`
- Line 116: `[u for u in _RAW_URLS if u[:100] not in _ATTEMPTED]` → adjust for dicts
- Line 175: `for url in DEBUG_URLS` → `for job in DEBUG_JOBS`
- Line 201: `apply_to_job(url, resume, profile_id)` — pass cover letter path
- `apply_to_job` signature at playwright_indeed.py:1154: `(apply_url, docx_path, user_id)` — docx_path accepts any file path ✅

## All Open Items from Cross-Reference: RESOLVED

| # | Resolution |
|---|-----------|
| 1 | url_attempts increments correctly for transient retries |
| 2 | Dedup updated to work with dicts |
| 3 | TRANSIENT_PATTERNS at module level, shared |
| 4 | "form too complex" is NOT transient — counts as real failure |
| 5 | Export URL try/except + fallback to generic resume |
| 6 | Regex handles flat JSON action dicts |

## Execution Order

1. `src/smartapply/gemini_fallback.py` — Bug 2 (JSON fallback)
2. `src/smartapply/router.py` — Bug 3 (same-URL bail-out, 2 locations)
3. `scripts/batch_test.py` — Bugs 1, 4, 5 (smart dedup, transient skip, cover letter)
4. Compile-check all 3 files
5. Commit
6. Run pipeline

## Status: AIRTIGHT — Ready to execute
