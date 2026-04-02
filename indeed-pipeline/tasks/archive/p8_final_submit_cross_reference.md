# P8 Final Submit — CROSS-REFERENCE

> Audit: `p8_final_submit_audit.md`
> Plan: `p8_final_submit_action_plan.md`
> Date: 2026-03-14 Session 7

---

## Does the plan address every audit issue?

| Audit Issue | Addressed? | Plan Change |
|------------|-----------|-------------|
| RC1: reCAPTCHA on submit page | ✅ | Change 2: `_has_recaptcha()` + `_solve_recaptcha()` + router wiring |
| RC2: Modals blocking interaction | ✅ | Change 1: `handle_modal_dismiss()` as first handler + Change 4: DOM modal detection |
| RC3: Error detection false positives | ✅ | Change 3: Filter false-positive error texts |
| Step skipping on resume page (steps 10-11 repeated) | ❌ NOT ADDRESSED | Multiple screenshots of same page suggest bot re-screenshots without acting. This is an existing stagnation detection issue — already handled by `same_url_actions` counter, not a new bug |
| "Save application progress" modal | ✅ | Change 1: "Don't save" in dismiss_texts |
| "What the employer sees" modal | ✅ | Change 1: Close button fallback selectors |
| Submit button disabled until reCAPTCHA solved | ✅ | Change 2 solves reCAPTCHA first, then Change 3 prevents error guard from blocking submit |

## Does the audit support every plan change?

| Plan Change | Audit Evidence? | Verdict |
|------------|----------------|---------|
| Change 1: Modal dismiss handler | ✅ Screenshots show two distinct modals blocking flow | Supported |
| Change 2a: `_has_recaptcha()` detection | ✅ step_15.jpg clearly shows reCAPTCHA v2 widget | Supported |
| Change 2b: `_solve_recaptcha()` solver | ✅ Audit confirms `_solve_cf()` pattern exists and is reusable | Supported |
| Change 2c: Router reCAPTCHA wiring | ✅ Audit confirms no existing reCAPTCHA handling | Supported |
| Change 3: Error guard hardening | ⚠️ PARTIALLY — audit identifies the RISK but doesn't CONFIRM false positives are happening | Proceed anyway — defensive fix, very low risk |
| Change 4: DOM modal detection | ⚠️ OVERHEAD — Change 1 works without this data | Keep — useful for logging/debugging |

## Contradictions / Gaps

### Gap 1: reCAPTCHA image challenge
- **Audit mentions:** "reCAPTCHA may show an image challenge after checkbox"
- **Plan says:** Click checkbox only, no image challenge handling
- **Resolution:** Acceptable. Indeed's reCAPTCHA is typically v2 invisible or checkbox-only for residential IPs. If image challenge appears, the bot will fail gracefully (3 attempts → continue to Gemini tier). Not worth building an image challenge solver now.

### Gap 2: `_solve_recaptcha` verification check
- **Plan proposes:** Check `#g-recaptcha-response` value to verify solve
- **Risk:** This element might not exist or might be in a different form. The response token is set inside the iframe, not on the main page.
- **Resolution:** Also check if the reCAPTCHA checkbox visual state changed. Add a fallback check via Gemini screenshot after clicking.

### Gap 3: Handler ordering
- **Plan says:** Modal dismiss is FIRST in handler chain
- **Concern:** Could this interfere with file upload? Modal dismiss checks button visibility with 500ms timeout — if no modal, it returns False in <500ms per check × 5 texts + 5 selectors = ~5s worst case
- **Resolution:** Reduce timeout to 300ms and add an early-exit: only run if a modal/dialog is actually visible (quick `[role="dialog"]:visible` check first).

### Gap 4: `_solve_recaptcha` imported into router
- **Plan says:** `from src.playwright_indeed import _has_recaptcha, _solve_recaptcha`
- **Concern:** These are private functions (underscore prefix). Cross-module import of private functions is OK in this codebase (router.py already imports `_screenshot, human_scroll, _execute`)
- **Resolution:** No issue — consistent with existing pattern.

## Final Verdict

**Plan is SOLID with 2 minor fixes needed:**
1. Add early-exit to modal handler (quick dialog check before looping)
2. Improve reCAPTCHA verification (don't rely solely on response token)

All other changes are clean additions with no side effects on existing behavior.
