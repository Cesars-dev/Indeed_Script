# Audit: Loop Detection — Deterministic→Gemini Escalation

## The Bug

**What happened:** SmartApply clicked "Continue" 12+ times on the same `contact-info-module` 
page without the URL ever changing. Each click "succeeded" (handler returned True), so `shot` 
reset to 0 every time, and Gemini never got a chance to look.

**Root cause (router.py L133-134):**
```python
if handled:
    shot = 0   # ← RESETS even if URL didn't change after the action
```

The handler chain runs: text_input (nothing to fill) → radio (none) → dropdown (none) → 
checkbox (none) → **continue_button → clicks Continue → returns True** → shot = 0 → repeat.

The `handle_continue_button` (handlers.py L229-270) checks for:
- Unanswered radios → probably none visible
- Empty **required** inputs → phone field might not be marked `required` in DOM
- Errors → might not appear until AFTER clicking Continue

So it happily clicks Continue, the form shows a validation error, the URL stays the same, 
and the loop repeats forever.

## Two Problems

### Problem 1: No stuck-page detection (router.py)
- L103-106: URL change resets `shot` to 0
- L133-134: Successful handler ALSO resets `shot` to 0
- **Missing:** Counter for "how many times have I acted on the SAME URL without it changing?"
- After N actions on same URL → force escalation to Gemini (it can SEE the validation errors)

### Problem 2: Continue button too eager (handlers.py)
- L236-238: Only checks `inp["required"]` — Indeed might not set `required` attribute
- L240: Only checks errors BEFORE clicking — errors appear AFTER
- **Missing:** After clicking Continue, check if URL actually changed

## Fix Strategy

### router.py — add `same_url_actions` counter
- Track consecutive successful actions on the same URL
- If `same_url_actions >= 3` → force `shot = 4` (skip to Gemini Flash)
- If `same_url_actions >= 5` → force `shot = 8` (skip to Gemini Pro)
- Reset counter when URL actually changes

### handlers.py — Continue button post-click URL check
- After clicking Continue, wait 2-4s, then check if URL changed
- If URL didn't change → return False (treat as failed)
- This prevents the "successful click that didn't do anything" loop

## Files to Change

| File | Lines | Change |
|------|-------|--------|
| router.py | L55-62 | Add `same_url_actions = 0` counter |
| router.py | L103-106 | Reset `same_url_actions` on URL change |
| router.py | L133-140 | Increment `same_url_actions`, force escalation if stuck |
| handlers.py | L264-267 | After Continue click, verify URL changed |
