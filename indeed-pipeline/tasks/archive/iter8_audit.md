# Surgeon Audit — Iteration 8

## Files Involved

| File | Lines | Role |
|------|-------|------|
| `scripts/batch_test.py` | 254 | Orchestrator — loads CSV, dedup, apply loop |
| `src/smartapply/gemini_fallback.py` | 137 | Gemini prompt + API call + JSON parse |
| `src/smartapply/router.py` | 438 | 12-shot form decision engine |

---

## Bug 1: Smart Dedup

### EXISTS
- `_load_attempted_urls()` at line 93 queries `test_run_logs` with `SELECT url LIMIT 500`
- Line 107: builds set from ALL rows: `{row["url"] for row in r.json()}`
- Line 116: filters out all attempted: `[u for u in _RAW_URLS if u[:100] not in _ATTEMPTED]`

### MISSING
- No status filter — success, failed, skipped ALL get deduped equally
- Transient failures (timeout, broken pipe, CDP crash) are permanently skipped
- No way to retry a failed URL on the next run

### FIX LOCATION
- Line 100-107: Add `status` to select, filter to only skip permanent outcomes
- Transient patterns to KEEP retryable: `Timeout`, `Broken pipe`, `JSONDecode`, `HTTPConnectionPool`, `TargetClosedError`

---

## Bug 2: JSONDecodeError from Gemini

### EXISTS
- `gemini_decide()` at line 119, JSON parse at line 136
- Lines 133-135: strips markdown fences (```json...```)
- Line 136: `return json.loads(raw)` — no error handling

### MISSING
- No regex fallback when json.loads fails
- No retry — exception propagates up, kills the whole attempt
- Gemini sometimes returns `{"action": "click"} extra text` or double JSON

### FIX LOCATION
- Line 136: wrap in try/except, add regex `re.search(r'\{.*\}', raw, re.DOTALL)` fallback
- If regex also fails → return safe default `{"action": "scroll", "reason": "bad JSON"}`

---

## Bug 3: 50-Step Runaway

### EXISTS
- `router.py` line 73: `for step in range(50)` — hard cap at 50 iterations
- Line 275: `same_url_actions += 1` after Gemini fill on same URL
- Line 295: `shot = 0` — resets to deterministic, creating infinite loop potential

### MISSING
- No bail-out on `same_url_actions >= 6`
- With scroll+reset, deterministic handlers may keep finding new elements
- Can loop 50 steps × 10s each = 500s wasted on one form

### FIX LOCATION
- After line 275 (`same_url_actions += 1`): add guard
  ```python
  if same_url_actions >= 6:
      return {"status": "failed", "reason": f"Stuck on same page ({same_url_actions} actions) — form too complex"}
  ```
- Same guard needed in Pro tier (around line 367)

---

## Bug 4: Transient Errors Burn MAX_FAILURES

### EXISTS  
- Line 230-245: status handling in main loop
- `success/skipped/disqualified` → done
- Everything else → `total_failures += 1` (lines 235, 240)
- Line 176: `if total_failures >= MAX_FAILURES: break`

### MISSING
- No distinction between real failures and transient infrastructure errors
- A run of 5 timeouts (bad luck) kills the pipeline at failure #10

### FIX LOCATION
- Lines 233-245: check reason for transient patterns before incrementing `total_failures`
- Transient = don't count, just rotate profile and retry
- Real = count toward MAX_FAILURES as before

---

## Bug 5: Generic Resume Instead of Per-Job Cover Letter

### EXISTS
- `_load_job_urls()` at line 73 reads CSV
- Line 80: only extracts `apply_url`: `[row["apply_url"].strip() for row in reader]`
- Line 66: `RESUME_PATH = .../resume_oswaldo.pdf` — hardcoded
- Line 165: `resume = RESUME_PATH if os.path.exists(RESUME_PATH) else None`
- Line 201: `result = await apply_to_job(url, resume, profile_id)` — same resume for all

### CSV STRUCTURE
```
apply_url, ..., google_doc_id
indeed.com/viewjob?jk=xxx, ..., https://docs.google.com/document/d/{DOC_ID}/edit?...
```

### MISSING
- `google_doc_id` column not extracted
- No download of Google Doc as PDF
- No per-job resume path

### FIX LOCATION
- Line 80: return list of `{"url": ..., "doc_url": ...}` dicts
- Lines 90, 115-116: adjust dedup to work with dicts
- Main loop (line 175): before `apply_to_job`, download doc as PDF
- Google export URL: `https://docs.google.com/document/d/{ID}/export?format=pdf`
- Extract ID from full URL: split on `/d/` and `/edit`

### DEPENDENCY
- `apply_to_job(url, docx_path, user_id)` at playwright_indeed.py:1154
- `docx_path` passed through to `handle_file_upload()` at handlers.py
- `set_input_files(docx_path)` — accepts any file path. No conversion needed.
