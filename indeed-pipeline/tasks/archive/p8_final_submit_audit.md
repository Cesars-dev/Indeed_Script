# P8 Final Submit — AUDIT

> Phase: Final submit page blockers (reCAPTCHA, modals, button matching)
> Date: 2026-03-14 Session 7

---

## Evidence (from screenshots)

| Screenshot | Page State | Problem |
|------------|-----------|---------|
| `step_12.jpg` (k1a2vuov_1773487816) | "Save application progress before you exit" modal | Modal blocks page — bot burns shots trying to interact through it |
| `step_14.jpg` (k1a2vuov_1773487008) | "Here's an example of what the employer sees initially" modal | Second modal that pops up on review page — blocks submit |
| `step_15.jpg` (k1a2vuov_1773487008) | **Final submit page** — reCAPTCHA "I'm not a robot" unchecked, "Submit your application" button visible but greyed out | **BLOCKER**: reCAPTCHA not solved, submit button disabled until checked |
| `step_16.jpg` (k1a2vuov_1773487008) | Same as step_15 — no progress | Bot exhausted all 12 shots on this page |

---

## File-by-file Audit

### 1. `src/smartapply/router.py` (301 lines)

**Call flow:** `apply_smartapply()` → 50-step loop → deterministic handlers → Gemini Flash → Gemini Pro → exhaustion

**Relevant code paths:**

- **Lines 112-156 (Deterministic tier):** Calls handlers in order. `handle_continue_button` is LAST. If all handlers return `False`, `shot` increments. After 4 misses → escalates to Flash.
- **Lines 160-215 (Flash tier):** Takes screenshot, asks Gemini. Escape guardrail on line 165 presses `Escape` if `same_url_actions >= 2`. This SHOULD dismiss modals but only fires in Flash tier, not deterministic.
- **Lines 219-270 (Pro tier):** Same as Flash but with full-page screenshot and Pro model.
- **Lines 272-297 (Exhaustion):** All 12 shots exhausted → returns `failed`.

**MISSING:**
- ❌ No reCAPTCHA detection or handling anywhere
- ❌ No modal dismissal in deterministic tier (Escape only fires in Flash/Pro tiers)
- ❌ No "Save application progress" handler
- ❌ No "What the employer sees" handler

### 2. `src/smartapply/handlers.py` (281 lines)

**`handle_continue_button()` (lines 229-280):**
- Line 255: `if any(w in text_lower for w in ["continue", "next", "submit"]) or is_review`
- ✅ "submit" IS in the match list — so "Submit your application" SHOULD match via substring
- BUT: Line 240: `has_errors = len(dom["errors"]) > 0` — reCAPTCHA widget might inject error elements that block the click
- Line 245: `if not is_review_page and (has_unanswered_radio or has_empty_required_input or has_errors): return False`
- **Risk:** If reCAPTCHA is detected as an "error" by the DOM scanner, the handler won't even try to click Submit

**MISSING:**
- ❌ No handler for modal dismissal (close/X buttons, "Don't save" buttons)
- ❌ No handler for reCAPTCHA/reCAPTCHA checkbox

### 3. `src/smartapply/dom_scanner.py` (125 lines)

**Error detection (lines 117-121):**
```javascript
result.errors = [...document.querySelectorAll('[class*="error" i], [role="alert"], [class*="Error"]')]
    .filter(e => e.offsetParent !== null)
    .map(e => e.textContent.trim().substring(0, 120))
    .filter(t => t.length > 0);
```
- **Risk:** reCAPTCHA container or Indeed's "complete this step" alerts might match `[role="alert"]`, returning false errors that prevent `handle_continue_button` from firing

**Success detection (lines 109-112):**
```javascript
result.success = bodyText.includes('Application submitted')
    || bodyText.includes('application was submitted')
    || bodyText.includes('You applied');
```
- ✅ These are correct success signals

**MISSING:**
- ❌ No modal detection (overlay/dialog elements)
- ❌ No reCAPTCHA iframe detection

### 4. `src/playwright_indeed.py` (1364 lines)

**Existing CF/reCAPTCHA handling:**
- `_is_cf()` (lines 700-720): Detects **Cloudflare** scripts — NOT reCAPTCHA
- `_bypass_cf()` (lines 723-797): Clicks **CF Turnstile** iframes with Bezier movement
- `_solve_cf()` (lines 800-916): Gemini-powered CF solver — takes screenshot, asks Gemini for checkbox coords, clicks with Bezier

**Key insight:** `_solve_cf()` is designed for CF Turnstile but the same pattern works for reCAPTCHA:
1. Take screenshot
2. Ask Gemini where the checkbox is
3. Bezier mouse movement to coords
4. Click

**reCAPTCHA vs CF Turnstile differences:**
- CF iframe: `src*="challenges.cloudflare.com"` or `src*="turnstile"`
- reCAPTCHA iframe: `src*="google.com/recaptcha"` — different selector
- reCAPTCHA checkbox has `class="recaptcha-checkbox"` inside the iframe
- After clicking, reCAPTCHA may show an image challenge (not just a checkbox)

**MISSING:**
- ❌ `_is_cf()` does NOT detect reCAPTCHA — only Cloudflare
- ❌ No `_solve_recaptcha()` function
- ❌ No reCAPTCHA iframe detection

### 5. `src/smartapply/gemini_fallback.py` (112 lines)

- Builds targeted prompt from DOM data for Gemini
- **Does NOT mention reCAPTCHA** in the prompt — Gemini might try to click the checkbox but the executor can't interact with iframe content via normal selectors

### 6. `scripts/batch_test.py` (140 lines)

- ✅ Status check fixed (now checks "success" not "applied")
- ✅ load_dotenv fixed (explicit path + override=True)
- No other issues relevant to final submit

---

## Root Causes (Ordered by Impact)

### RC1 — reCAPTCHA on submit page (BLOCKER)
- Indeed has Google reCAPTCHA v2 ("I'm not a robot" checkbox) on the final submit page
- No code exists to detect or solve it
- The `_solve_cf()` pattern is close but targets CF-specific selectors
- Without solving reCAPTCHA, "Submit your application" button stays disabled

### RC2 — Modals blocking interaction
- "Save application progress before you exit" modal appears when the session takes too long
- "Here's an example of what the employer sees" modal appears on the review page
- The Escape guardrail only fires in Flash/Pro tiers (line 165, 224) — by then 4 shots are burned
- These modals are NOT detected by the DOM scanner

### RC3 — Error detection false positives
- `dom_scanner.py` picks up `[role="alert"]` elements that might be informational (not actual errors)
- This can prevent `handle_continue_button` from firing even when the form is actually complete

---

## Dependencies

| Component | Depends On |
|-----------|-----------|
| reCAPTCHA solver | `_screenshot()`, Gemini API, Bezier mouse movement (all exist) |
| Modal handler | `dom_scanner.py` (needs modal detection), `handlers.py` (new handler) |
| Submit button fix | `handlers.py` `handle_continue_button` (error guard logic) |

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| reCAPTCHA image challenge after checkbox | High | If checkbox alone doesn't work, we fail gracefully — most Indeed reCAPTCHA is invisible or checkbox-only |
| Modal detection false positives | Low | Use specific selectors, not generic |
| Breaking existing deterministic flow | Medium | Only ADD handlers, don't modify existing ones |
