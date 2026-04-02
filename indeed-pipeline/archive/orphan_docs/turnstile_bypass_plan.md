# Turnstile Bypass Plan — Human-Like Behavior

## How Turnstile Works

Cloudflare Turnstile has 3 modes:

| Mode | What User Sees | How It Validates | Our Strategy |
|---|---|---|---|
| **Invisible** | Nothing — "Just a moment" spinner | Browser signals only (fingerprint, JS engine, mouse/keyboard history) | Prevention — clean signals = auto-pass |
| **Managed** | Spinner → checkbox if suspicious | Starts invisible, escalates to checkbox | Prevention + Gemini click if escalated |
| **Interactive** | Checkbox immediately | User must click checkbox | Gemini click with human mouse movement |

## Current State

```
_is_cf()      → detects CF by page title + scripts in DOM     ✅ works
_bypass_cf()  → hunts for iframe via CSS selectors, clicks it  ❌ fragile, can't find new iframes
```

## Plan

### Phase 1: Prevention (reduce CF triggers)

> Goal: Pass invisible Turnstile automatically by having clean signals

- [ ] **Pre-warmup mouse movement** — before navigating to indeed.com, move mouse randomly around the page for 2-3s. Turnstile checks if mouse events exist in the browser session.
- [ ] **Keyboard activity** — press a few harmless keys (Tab, arrow keys) during warmup. CF checks for keyboard event listeners.
- [ ] **Longer initial session** — first warmup visit should be 15-30s (not 4-9s). Spend more time "reading" indeed.com before navigating.
- [ ] **Cookie persistence** — ensure AdsPower saves and reloads CF cookies between sessions. A returning visitor with valid `cf_clearance` cookie skips challenges entirely.
- [ ] **Profile rotation** — never use the same profile more than 2x per hour. Space applications 10+ minutes apart.

### Phase 2: Gemini-Based Visual Solving

> Goal: When visible Turnstile appears, let Gemini identify and click the checkbox

**Instead of separate `_bypass_cf()` code, route CF pages through the Gemini loop:**

```python
# In _gemini_loop, before normal form logic:
if await _is_cf(page):
    # Take screenshot, ask Gemini to find the checkbox
    screenshot = await _screenshot(page, debug_dir, f"cf_step_{step}")
    action = await _gemini_decide(screenshot, url, step, profile)
    # Gemini should return: {"action": "click", "target": "checkbox", ...}
    if action.get("action") == "click":
        await _execute(page, action, docx_path)
        await _delay(5.0, 8.0)  # wait for CF to validate
    continue  # re-check on next step
```

**Add to Gemini prompt:**
```
CLOUDFLARE / TURNSTILE:
  • If you see a "Verify you are human" page with a checkbox, click the checkbox
  • If you see a "Just a moment..." spinner with no checkbox, action = "scroll" (wait for auto-resolve)
  • Do NOT return "failed" for Cloudflare pages — they often auto-resolve
```

### Phase 3: Human Mouse Movement for CF Click

> Goal: When clicking the Turnstile checkbox, use realistic mouse movement

- [ ] Use `humancursor_playwright` for Bezier curve movement to the checkbox
- [ ] Add random pre-click hover (move near the checkbox, pause 200-500ms, then click)
- [ ] Vary click position within the checkbox area (not always center)
- [ ] Add post-click mouse drift (move away slightly after clicking)

### Phase 4: Fallback & Recovery

> Goal: Graceful handling when all bypass attempts fail

- [ ] If CF persists after 3 Gemini attempts → wait 30s (sometimes CF auto-resolves with delay)
- [ ] If CF persists after 60s total → mark profile as stonewalled, rotate to next profile
- [ ] **Don't reload excessively** — CF tracks reload patterns. Max 1 reload per CF encounter.
- [ ] Log CF encounter details (screenshot, page source) for debugging

## Implementation Priority

1. **Phase 2** (Gemini visual solving) — biggest impact, easiest to implement
2. **Phase 1** (prevention) — reduces CF triggers by ~70%
3. **Phase 3** (mouse movement) — polish for the click behavior
4. **Phase 4** (fallback) — already partially implemented

## Key Insight

The best CF strategy is **not needing to bypass it at all**. Clean AdsPower fingerprints + residential proxies + natural warmup behavior should auto-pass invisible Turnstile 90%+ of the time. The Gemini visual solver is for the 10% that escalate to a visible checkbox.
