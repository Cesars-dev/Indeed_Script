# Task: SmartApply Iteration 8

## What we're fixing

5 small bugs, all in `scripts/batch_test.py` and `src/smartapply/gemini_fallback.py`.

### Bug 1: Smart Dedup
**File:** `scripts/batch_test.py` → `_load_attempted_urls()`  
**Problem:** Dedup skips ALL previously attempted URLs — even transient failures (timeout, broken pipe). Those jobs never get retried.  
**Fix:** Only skip `success` + `skipped` + real `failed`. Let transient failures (timeout, broken pipe, JSONDecode, CDP crash) stay in the retry pool.

### Bug 2: JSONDecodeError from Gemini
**File:** `src/smartapply/gemini_fallback.py` → `gemini_decide()`  
**Problem:** Gemini sometimes returns `}}` or extra text around JSON. `json.loads()` crashes, whole attempt fails.  
**Fix:** Add regex fallback — extract first `{...}` block from response. If that also fails, return `{"action": "scroll", "reason": "bad JSON retry"}`.

### Bug 3: 50-Step Runaway
**File:** `src/smartapply/router.py`  
**Problem:** Scroll+reset fix keeps forms alive too long. One job hit 50 steps / 580s on the same URL.  
**Fix:** If `same_url_actions >= 6`, bail out — the form is too complex.

### Bug 4: Transient Errors Burn MAX_FAILURES Budget
**File:** `scripts/batch_test.py`  
**Problem:** Timeout/broken pipe counts toward the 10-failure limit. Pipeline stops early on bad luck.  
**Fix:** Only count real failures toward MAX_FAILURES. Transient errors → retry, don't increment counter.

### Bug 5: Using Generic Resume Instead of Per-Job Cover Letter
**File:** `scripts/batch_test.py` → `_load_job_urls()` + apply loop  
**Problem:** CSV has a `google_doc_id` column with a tailored cover letter for EACH job. Pipeline ignores it and uploads `resume_oswaldo.pdf` for every application.  
**Fix:**
1. `_load_job_urls()` returns `[{url, doc_url}]` instead of `[url]`
2. Before each apply, download the Google Doc as PDF: `https://docs.google.com/document/d/{ID}/export?format=pdf`
3. Cache in `/tmp/cover_letters/{job_id}.pdf`
4. Pass that file to `apply_to_job()` instead of generic resume
