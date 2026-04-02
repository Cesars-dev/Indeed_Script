# P8.1 Action Plan — Learning Loop + Logging Gaps

> Based on: `tasks/p8_logging_audit.md` (audit)

---

## Change 1: Create `apply_patterns` Table (Supabase Migration)

```sql
CREATE TABLE IF NOT EXISTS apply_patterns (
  id SERIAL PRIMARY KEY,
  question_text TEXT NOT NULL,
  answer_value TEXT NOT NULL,
  answer_type TEXT DEFAULT 'unknown',
  source TEXT DEFAULT 'gemini',
  times_seen INT DEFAULT 1,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(question_text, answer_value)
);
NOTIFY pgrst, 'reload schema';
```

- Uses UNIQUE constraint so duplicate Q&A pairs increment `times_seen` instead of inserting duplicates
- Table name matches what `patterns.py:load_dynamic_patterns()` already queries (L171)

---

## Change 2: Log Gemini Q&A Pairs (router.py)

**Where**: After Flash action succeeds (L225), and after Pro action succeeds (L292)
**What**: If URL contains "questions", extract question context from action and log to `apply_patterns`

```python
# After ok = True and action logged, add:
if "questions" in url and action.get("target"):
    log("apply_patterns", {
        "question_text": action.get("reason", "")[:500],
        "answer_value": str(action.get("value") or action.get("target", ""))[:200],
        "answer_type": action.get("action", "unknown"),
        "source": "flash" or "pro",
    })
```

**Lines affected**: ~L225 (Flash) and ~L292 (Pro) — 4 lines each, after existing `log()` calls

---

## Change 3: Log reCAPTCHA Results (router.py)

**Where**: L118-137 (reCAPTCHA block)
**What**: Log solve result to `apply_step_log`

```python
log("apply_step_log", {
    "step_num": step, "url": url, "tier": "recaptcha",
    "success": True,  # or False
})
```

**Lines affected**: L121 (after solve success) and L136 (after solve failure) — 4 lines each

---

## Change 4: Log Deterministic Misses (router.py)

**Where**: L183 (after all handlers miss)
**What**: Log the miss with DOM snapshot for pattern analysis

```python
# After shot += 1 at L183:
if shot == 4:  # only log when escalating (not every miss)
    log("apply_step_log", {
        "step_num": step, "url": url, "tier": "deterministic_miss",
        "success": False, "dom_snapshot": dom,
    })
```

**Lines affected**: L184 — 5 lines insert

---

## Change 5: Log Max Steps Exceeded (router.py)

**Where**: L346 (end of function)
**What**: Log to both `apply_step_log` and `apply_runs`

```python
# Replace bare return at L346:
elapsed = round(time.time() - t0, 1)
log("apply_step_log", {
    "step_num": step, "url": url, "tier": "exhausted",
    "success": False, "error_msg": f"Exceeded 50 steps ({elapsed}s)",
})
return {"status": "failed", "reason": f"Exceeded 50 steps ({elapsed}s)"}
```

**Lines affected**: L345-346 — replace 2 lines with 6

---

## Change 6: Wire `load_dynamic_patterns()` at Startup (router.py)

**Where**: Top of `apply_smartapply()` function, before the loop
**What**: Call `load_dynamic_patterns()` once per run

```python
from .patterns import load_dynamic_patterns
load_dynamic_patterns()
```

**Lines affected**: ~L68 — 2 lines insert

---

## Change 7: Fix `get_dynamic_answer()` Schema Match (patterns.py)

**Where**: `get_dynamic_answer()` at L187-195
**What**: Current code expects `dom_signal.question_contains` nested field. New table uses flat `question_text`. Fix the lookup.

```python
def get_dynamic_answer(question: str) -> tuple[str, str] | None:
    q = question.lower()
    for pat in _dynamic_patterns:
        keyword = pat.get("question_text", "").lower()
        if keyword and keyword in q:
            return (pat.get("answer_type", ""), pat.get("answer_value", ""))
    return None
```

**Lines affected**: L187-195 — replace 9 lines

---

## Files Modified (Total)

| File | Changes | Lines Added |
|------|---------|------------|
| `router.py` | Gaps 2-6 | ~25 lines |
| `patterns.py` | Gap 7: fix schema | ~5 lines |
| Supabase | Gap 1: migration | 1 query |

**Zero behavioral changes to working code. All additions are logging + lookup.**
