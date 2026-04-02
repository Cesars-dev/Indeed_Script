# Audit: Human-Like Delays on Deterministic Actions

## Files Involved

| File | Lines | What |
|------|-------|------|
| `src/smartapply/handlers.py` | L12-14 | `_human_delay()` → 3-5s (used before field actions) |
| `src/smartapply/handlers.py` | L30 | `sleep(1)` after file upload |
| `src/smartapply/handlers.py` | L149 | `sleep(0.3)` after text fill |
| `src/smartapply/handlers.py` | L265 | `sleep(0.5)` after button click |
| `src/smartapply/router.py` | L116 | `sleep(0.3)` after scroll (shot 2) |
| `src/smartapply/router.py` | L140 | `sleep(0.5)` after deterministic success |
| `src/smartapply/router.py` | L173 | `sleep(0.5)` after Flash success |
| `src/smartapply/router.py` | L208 | `sleep(0.5)` after Pro success |

## Current Timing Profile

### handlers.py — per-field actions
- `_human_delay()`: `random.uniform(3.0, 5.0)` → ✅ GOOD before each action
- Post-file-upload: `sleep(1)` → ⚠️ could be longer (upload processing)
- Post-text-fill: `sleep(0.3)` → ❌ TOO FAST — human pauses after typing
- Post-button-click: `sleep(0.5)` → ❌ TOO FAST — page transition needs dwell

### router.py — between steps
- Post-scroll: `sleep(0.3)` → ❌ TOO FAST for "reading" scroll
- Post-deterministic-success: `sleep(0.5)` → ❌ TOO FAST between field actions
- Post-Flash-success: `sleep(0.5)` → OK (Gemini API adds 10-15s natural delay)
- Post-Pro-success: `sleep(0.5)` → OK (same — Gemini API delay covers it)

## What a HUMAN looks like
- Read a question: 1.5-3s
- Type a short answer: 1-2s (after reading)
- Click a radio/dropdown: 0.5-1s (after reading)
- Move between fields: 0.8-1.5s
- After clicking Continue: 1.5-3s (watching page load)
- After uploading file: 2-4s (watching progress bar)

## What's MISSING
1. **Post-action dwell** — after filling a field, human looks at it briefly (0.8-2s)
2. **Between-step thinking** — router moves to next step too fast (0.5s vs 1.5-3s)
3. **Post-upload wait** — 1s is too quick, should be 2-4s
4. **Post-button wait** — 0.5s is too quick for page transition, should be 2-4s

## What's ALREADY GOOD
- `_human_delay()` (3-5s) before each field action — ✅ simulates reading
- Gemini calls add natural 10-15s delay — ✅ no change needed there
