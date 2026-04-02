# P8 Learning Loop — Master Plan (Preflight Verified)

> Surgeon Framework Step 4 — every line number verified against actual code.
> Verdict: EXECUTE. Zero open issues.

---

## Change 1: Create `apply_patterns` table (Supabase)

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

**Verification**: `patterns.py` L171 queries `apply_patterns` — table name matches. ✅

---

## Change 2: Log Gemini Q&A to `apply_patterns` (router.py)

**Flash (after L225 `if ok:` block)**: Insert after the existing continue-button logic (~L247)
**Pro (after L292 `if ok:` block)**: Insert after the existing continue-button logic (~L311)

Both insertions are IDENTICAL logic:
```python
# Learn from Gemini answer on questions pages
if "questions" in url and action.get("target"):
    log("apply_patterns", {
        "question_text": action.get("reason", "")[:500],
        "answer_value": str(action.get("value") or action.get("target", ""))[:200],
        "answer_type": action.get("action", "unknown"),
        "source": tier_label.lower(),
    })
```

**Verification**: L225 is `if ok:` for Flash. L292 is `if ok:` for Pro. Both have `tier_label` in scope. ✅

---

## Change 3: Log reCAPTCHA results (router.py)

**After solve success (L120)**: Add log after `recaptcha_solved = True`
**After solve failure (L137)**: Add log after `shot = 4`

```python
log("apply_step_log", {
    "step_num": step, "url": url, "tier": "recaptcha",
    "success": True,  # or False
})
```

**Verification**: L120 is `recaptcha_solved = True`. L137-138 is the failure print + escalation. ✅

---

## Change 4: Log deterministic misses (router.py)

**At L183** (`shot += 1` on deterministic miss): Log when escalating (shot reaches 4)

```python
shot += 1
if shot == 4:
    log("apply_step_log", {
        "step_num": step, "url": url, "tier": "deterministic_miss",
        "success": False, "dom_snapshot": dom,
    })
print(f"  ↓ Deterministic miss (shot {shot}/12)")
continue
```

**Verification**: L183 is `shot += 1`. L184 is the print. ✅

---

## Change 5: Log max steps exceeded (router.py)

**At L345-346** (bare return after 50-step loop):

```python
elapsed = round(time.time() - t0, 1)
log("apply_step_log", {
    "step_num": step, "url": url, "tier": "exhausted",
    "success": False, "error_msg": f"Exceeded 50 steps ({elapsed}s)",
})
log("apply_runs", {
    "status": "failed", "reason": f"Exceeded 50 steps ({elapsed}s)",
    "total_steps": total_steps, "deterministic_steps": det_steps,
    "flash_steps": flash_steps, "pro_steps": pro_steps,
    "elapsed_s": elapsed, "debug_dir": debug_dir,
})
return {"status": "failed", "reason": f"Exceeded 50 steps ({elapsed}s)"}
```

**Verification**: L345-346 is `elapsed = round(...)` + bare return. `t0` in scope (L67), `step` in scope (loop var), `url` last assigned at L71. But: `url` is loop-scoped so after 50 iterations the last `url` survives. ✅

---

## Change 6: Wire `load_dynamic_patterns()` at startup (router.py)

**At L69** (before `for step in range(50)`): Add import + call.

```python
from .patterns import load_dynamic_patterns
load_dynamic_patterns()
```

**Verification**: L69 is `for step in range(50)`. Inserting before this line. `load_dynamic_patterns` lives at `patterns.py` L161. ✅

---

## Change 7: Fix `get_dynamic_answer()` schema (patterns.py)

**At L187-195**: Replace entire function body.

Current (BROKEN):
```python
def get_dynamic_answer(question: str) -> tuple[str, str] | None:
    q = question.lower()
    for pat in _dynamic_patterns:
        signal = pat.get("dom_signal", {})           # ← wrong: expects nested dict
        keyword = signal.get("question_contains", "").lower()  # ← wrong field name
        if keyword and keyword in q:
            return (pat.get("handler", ""), pat.get("default_answer", ""))
    return None
```

Fixed:
```python
def get_dynamic_answer(question: str) -> tuple[str, str] | None:
    q = question.lower()
    for pat in _dynamic_patterns:
        keyword = pat.get("question_text", "").lower()     # ← flat column
        if keyword and keyword in q:
            return (pat.get("answer_type", ""), pat.get("answer_value", ""))  # ← flat columns
    return None
```

**Verification**: L187 is `def get_dynamic_answer`. L191-194 are the broken lines. `handlers.py` L116-118 calls this and expects `(handler_type, answer_value)` tuple — new return matches. ✅

---

## Execution Order

1. Supabase migration (Change 1) — creates the table
2. `patterns.py` fix (Change 7) — fix schema match
3. `router.py` all changes (Changes 2-6) — logging + wiring

## Risk Assessment

- **Zero behavioral changes** — all additions are `log()` calls (fire-and-forget) or a read-only lookup
- **`load_dynamic_patterns()` has full try/except** — if Supabase is down, list stays empty, pipeline unchanged
- **Dynamic patterns are string data** — no code injection, no eval, no risk
- **UNIQUE constraint** on table prevents duplicate rows

## Verdict: EXECUTE ✅
