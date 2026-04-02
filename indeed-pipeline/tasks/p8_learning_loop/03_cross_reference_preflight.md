# P8.1 Cross-Reference + Preflight (Combined)

## Audit ↔ Action Plan Alignment

| Audit Gap | Plan Change | Aligned? |
|-----------|-------------|----------|
| GAP 1: Gemini Q&A not extracted | Change 1 (table) + Change 2 (router log) | ✅ |
| GAP 2: reCAPTCHA not logged | Change 3 (router log) | ✅ |
| GAP 3: Deterministic miss not logged | Change 4 (router log) | ✅ |
| GAP 4: Max steps not logged | Change 5 (router log) | ✅ |
| GAP 5: Success not in executions | Covered by batch_test.py already | ✅ N/A |
| — | Change 6 (load_dynamic_patterns) | ✅ Enables lookup |
| — | Change 7 (fix schema in patterns.py) | ✅ Fixes existing dead code |

## Preflight: Line Numbers Verified Against Actual Code

| Change | Target Line | Verified? |
|--------|------------|-----------|
| 2: Flash Q&A log | After L225 (Flash success) | ✅ L225 is `if ok:` block |
| 2: Pro Q&A log | After L292 (Pro success) | ✅ L292 is `if ok:` block |
| 3: reCAPTCHA log | L121 (after solve) | ✅ `recaptcha_solved = True` |
| 4: Det miss log | L183 (shot += 1) | ✅ `shot += 1` line |
| 5: Max steps log | L345-346 (final return) | ✅ bare return |
| 6: load_dynamic | ~L68 (before loop) | ✅ before `for step in range(50)` |
| 7: patterns.py | L187-195 | ✅ `get_dynamic_answer` function |

## Risk Assessment
- **Zero risk to existing flow** — all changes are INSERT logging or pre-loop lookup
- **UNIQUE constraint** on apply_patterns prevents duplicates
- **Fire-and-forget logger** means failed inserts don't crash pipeline

## Verdict: EXECUTE
All 7 changes verified. No conflicts. No open issues.
