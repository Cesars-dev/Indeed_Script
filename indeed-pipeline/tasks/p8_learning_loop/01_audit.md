# P8.1 AUDIT — Learning Loop Integration

> Surgeon Framework Step 1 — Read every file, trace every call, document what EXISTS vs MISSING.

---

## Files Read

| File | Lines | Purpose |
|------|-------|---------|
| `router.py` | 347 | Main loop — all log() calls live here |
| `patterns.py` | 196 | Static patterns + dynamic patterns loader |
| `handlers.py` | 354 | Deterministic handlers — call patterns matchers |
| `logger.py` | 61 | Fire-and-forget Supabase logger |
| `supabase_mcp_config.md` | 161 | Migration tool reference |

---

## What EXISTS

### Logging (router.py)

| Code Path | Table Logged | Line | What's Saved |
|-----------|-------------|------|-------------|
| Deterministic success | `apply_step_log` | L176 | step_num, url, tier="deterministic", success=True, page_pattern |
| Flash success/fail | `apply_step_log` | L220 | step_num, url, tier="flash", success, action JSON, dom_snapshot on fail |
| Pro success/fail | `apply_step_log` | L286 | step_num, url, tier="pro", success, action JSON, dom_snapshot, screenshot |
| 12-shot exhaustion | `apply_step_log` | L321 | step_num, url, tier="exhausted", dom_snapshot, error_msg |
| 12-shot exhaustion | `apply_runs` | L328 | status, reason, step counts, elapsed_s, debug_dir |
| Success signal | `apply_step_log` | L84 | step_num, url, tier="signal", success=True |

### Dynamic Patterns (patterns.py)

| Function | Line | Status |
|----------|------|--------|
| `load_dynamic_patterns()` | L161 | ✅ EXISTS — queries `apply_patterns` table, stores in `_dynamic_patterns` |
| `get_dynamic_answer()` | L187 | ⚠️ EXISTS but schema WRONG — expects `dom_signal.question_contains` nested field |

### Handler Calls to Dynamic Patterns (handlers.py)

| Handler | Line | Call |
|---------|------|------|
| `handle_radio_yesno` | L116 | `get_dynamic_answer(rg["question"])` — returns `(handler, answer)` |
| `handle_radio_range` | L164 | `get_dynamic_answer(rg["question"])` — returns `(handler, answer)` |

### Logger (logger.py)

- Fire-and-forget async POST to Supabase REST API
- Falls back to sync `requests` if aiohttp not installed
- Silent on all errors — never crashes pipeline
- Uses `loop.create_task()` — non-blocking

---

## What's MISSING

### MISSING 1: `apply_patterns` table in Supabase
- `load_dynamic_patterns()` queries it → gets 404 (table doesn't exist)
- `log("apply_patterns", {...})` would silently fail (logger swallows errors)
- **Need**: CREATE TABLE via Supabase `apply_migration` MCP tool

### MISSING 2: Q&A extraction after Gemini action
- Flash logs `action` JSON at L220 (contains `reason`, `target`, `value`)
- Pro logs `action` JSON at L286 (same fields)
- But neither extracts **question_text + answer_value** into `apply_patterns`
- The action JSON has:
  - `action.reason` → often contains the question context (e.g. "Selecting 'Yes' for the work authorization question")
  - `action.target` → the element clicked/typed
  - `action.value` → the value selected/typed
- **Need**: After Gemini action succeeds on `questions` URL, INSERT into `apply_patterns`

### MISSING 3: `get_dynamic_answer()` schema mismatch
- Current code (L190-194):
  ```python
  signal = pat.get("dom_signal", {})  # expects nested dict
  keyword = signal.get("question_contains", "")
  ```
- New table schema should have flat columns: `question_text`, `answer_value`, `answer_type`
- **Need**: Fix `get_dynamic_answer()` to match actual table schema

### MISSING 4: `load_dynamic_patterns()` never called
- Function exists but is never invoked from router.py or anywhere
- **Need**: Call at top of `apply_smartapply()` before the loop

### MISSING 5: reCAPTCHA solve not logged to Supabase
- L119-135: solve happens, prints to console, but no `log()` call
- **Need**: `log("apply_step_log", {...})` with tier="recaptcha"

### MISSING 6: Deterministic miss not logged
- L183: `shot += 1` on miss, only prints, no Supabase log
- **Need**: Log with tier="deterministic_miss" when escalating (shot reaches 4)

### MISSING 7: 50-step overflow not logged  
- L345-346: Returns failed but no `log()` call
- **Need**: `log("apply_step_log", {...})` + `log("apply_runs", {...})`

---

## Dependency Map

```
apply_patterns (Supabase)      ← MISSING: needs migration
       │
       ├── load_dynamic_patterns() (patterns.py L161) -- loads at startup
       │         │
       │         └── _dynamic_patterns (module var)
       │                  │
       │                  ├── get_dynamic_answer() (patterns.py L187) -- lookup
       │                  │       │                                      ← BROKEN: wrong schema
       │                  │       ├── handle_radio_yesno (handlers.py L116)
       │                  │       └── handle_radio_range (handlers.py L164)
       │                  │
       │                  └── (future: handle_text_input, handle_dropdown)
       │
       └── log("apply_patterns", data) (router.py) -- insert after Gemini
                                                     ← MISSING: not wired
```

---

## Risks

1. **Logger `log()` uses `loop.create_task()`** — INSERT to `apply_patterns` with UNIQUE constraint may silently fail on duplicate. This is fine for learning (duplicate = same answer) but we lose the `times_seen` increment.
   - **Mitigation**: Use Supabase upsert header `Prefer: resolution=merge-duplicates` in logger.py, OR accept duplicates are dropped silently (acceptable for Round 1).

2. **`action.reason` may not contain the actual question text** — Gemini's reason is a free-text explanation, not the exact question.
   - **Mitigation**: Also log `dom_snapshot` question text when available from the DOM scan.

3. **`apply_patterns` INSERT via fire-and-forget logger** — if Supabase is slow or down, patterns are lost.
   - **Mitigation**: Acceptable for Round 1. Patterns are also visible in `apply_step_log` action JSON.
