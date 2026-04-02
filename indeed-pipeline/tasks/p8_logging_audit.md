# Logging Audit — Are We Capturing Everything?

> Surgeon Framework Step 1: Audit every log path in the router

---

## Summary: 4 GAPS FOUND

We log most things, but **we're NOT logging Gemini's question-answer pairs** (the most valuable data for learning), and **several failure paths are silent**.

---

## What IS Being Logged ✅

### `apply_step_log` (Supabase) — per-step logging
| Path | Logged? | Fields |
|------|---------|--------|
| Deterministic success | ✅ L176 | step_num, url, tier="deterministic", success=True, page_pattern |
| Flash action | ✅ L220 | step_num, url, tier="flash", success, action JSON, dom_snapshot on fail |
| Pro action | ✅ L286 | step_num, url, tier="pro", success, action JSON, dom_snapshot, screenshot |
| 12-shot exhaustion | ✅ L321 | step_num, url, tier="exhausted", dom_snapshot, error_msg |
| Success signal | ✅ L84 | step_num, url, tier="signal", success=True |

### `apply_runs` (Supabase) — per-run summary
| Path | Logged? |
|------|---------|
| 12-shot exhaustion | ✅ L328 | status, reason, step counts, elapsed_s |

### `executions` (Supabase) — via batch_test.py → supabase_client.py
| Path | Logged? |
|------|---------|
| Per job attempt | ✅ via `log_execution()` |

---

## What's NOT Being Logged ❌

### GAP 1: Gemini Q&A pairs not extracted
**Impact: CRITICAL for learning loop**
- Flash/Pro log the full `action` JSON (contains "reason", "target", "value")
- But we never extract: **question text + answer chosen**
- Without this, `apply_patterns` table can't be populated automatically
- **Fix**: After Gemini answers on questions page, extract question text from DOM + answer from action → INSERT into `apply_patterns`

### GAP 2: reCAPTCHA solve result not logged
**Impact: Medium — tracking costs and timing**
- reCAPTCHA detection + solve happens at L113-137
- Success/failure prints to console but NOT to Supabase
- **Fix**: Add `log("apply_step_log", {...})` after solve attempt

### GAP 3: Deterministic miss not logged  
**Impact: Low — but useful for pattern analysis**
- When ALL deterministic handlers miss (L183), we just print and increment `shot`
- No log to Supabase = we can't analyze what patterns are missing
- **Fix**: Add log with tier="deterministic_miss", dom_snapshot

### GAP 4: Max steps exceeded (line 346) not logged
**Impact: Low — edge case**
- If loop hits 50 steps, returns failed but doesn't log to Supabase
- **Fix**: Add `log("apply_step_log", {...})` + `log("apply_runs", {...})`

### GAP 5: Success (post-apply) not logging to `executions`
**Impact: Medium — we don't know which jobs succeeded at the execution level**
- `apply_step_log` records success but `executions` table is populated by batch_test.py
- Need to verify batch_test.py calls `log_execution()` on both success AND failure

---

## Action Plan for Training Run

### Before Round 1 (19 profiles × 2 jobs = 38 attempts):

1. **Create `apply_patterns` table** in Supabase:
```sql
CREATE TABLE apply_patterns (
  id SERIAL PRIMARY KEY,
  question_text TEXT NOT NULL,
  answer_value TEXT NOT NULL,
  answer_type TEXT DEFAULT 'unknown',  -- radio_yesno, text, dropdown, checkbox
  source TEXT DEFAULT 'gemini',
  times_seen INT DEFAULT 1,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

2. **Fix GAP 1**: After Gemini acts on a questions page, extract Q&A:
```python
# In router.py, after Flash/Pro action succeeds on questions URL:
if "questions" in url and ok and action.get("value"):
    log("apply_patterns", {
        "question_text": action.get("reason", "")[:200],
        "answer_value": action.get("value", ""),
        "answer_type": action.get("action", "unknown"),
        "source": tier_label.lower(),
    })
```

3. **Fix GAP 2**: Log reCAPTCHA results:
```python
log("apply_step_log", {
    "step_num": step, "url": url, "tier": "recaptcha",
    "success": solved, "action": {"solve_time_s": elapsed},
})
```

4. **Fix GAP 3**: Log deterministic misses (optional but useful)

### After Round 1:
- Query `apply_step_log WHERE tier='exhausted'` → these are the failure patterns
- Query `apply_step_log WHERE tier='flash' OR tier='pro'` → these are Gemini's answers
- Query `apply_patterns` → these are the learned Q&A pairs
- Feed new patterns back into `patterns.py` YESNO_ANSWERS / RANGE_ANSWERS

---

## Expected Data from 38-attempt Training Run

| Metric | Expected |
|--------|----------|
| Total step logs | ~200-300 rows |
| Successful apps | ~25-30 (70-80% success rate) |
| Failed apps | ~8-13 (unknown questions, expired jobs) |
| Unique questions seen | ~15-30 new patterns |
| Gemini calls | ~40-80 (for unknown questions) |
| reCAPTCHA solves | ~25-30 ($0.09 total cost) |
